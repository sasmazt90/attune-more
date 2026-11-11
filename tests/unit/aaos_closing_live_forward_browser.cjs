/** Live AAOS forwarding (scripts/qa/aaos/closing_live_forward.cjs) in a real Chromium with CDP interception, as the
 * AAOS harness uses it: the page's own request (method, Host, Origin, body) reaches the upstream server unchanged, the
 * answer reaches the page, and a request the page abandons is aborted upstream (its connection closes) within a bounded
 * time. Loopback servers only; skipped when no Playwright/Chromium is installed. */
const assert = require('node:assert/strict');
const http = require('node:http');
const {cancellationRegistry, forwardVerbatim, fulfillHeaders} = require('../../scripts/qa/aaos/closing_live_forward.cjs');

let chromium;
try { ({chromium} = require(process.env.ATTUNE_QA_PLAYWRIGHT || 'playwright')); } catch { console.log('SKIP: playwright not installed'); process.exit(0); }

const listen = handler => new Promise(ok => { const server = http.createServer(handler); server.listen(0, '127.0.0.1', () => ok(server)); });

(async () => {
  const seen = [];
  const upstream = await listen((req, res) => {
    const row = {at: Date.now(), headers: req.headers, url: req.url, body: '', closedAt: null, answered: false};
    seen.push(row);
    req.on('data', chunk => { row.body += chunk; });
    res.on('close', () => { if (!row.answered) row.closedAt = Date.now(); });
    const delay = req.url.includes('slow') ? 4000 : 50;
    setTimeout(() => { if (row.closedAt) return; row.answered = true; res.writeHead(200, {'Content-Type': 'audio/wav', 'X-TTS-Source': 'fixture', 'Server-Timing': 'tts-total;dur=1'}); res.end(Buffer.alloc(64, 1)); }, delay);
  });
  const origin = await listen((req, res) => { res.writeHead(200, {'Content-Type': 'text/html'}); res.end('<!doctype html><title>t</title>'); });
  const pageOrigin = `http://127.0.0.1:${origin.address().port}`, target = `http://127.0.0.1:${upstream.address().port}`;
  let browser;
  try {
    browser = await chromium.launch();
  } catch (error) { console.log('SKIP: no Chromium (' + String(error).slice(0, 80) + ')'); upstream.close(); origin.close(); return; }
  const page = await browser.newPage();
  const registry = cancellationRegistry(page), outcomes = [];
  await page.route(url => url.pathname.startsWith('/api/mental-neural-speech'), async route => {
    const request = route.request(), entry = registry.signalFor(request);
    try {
      const answer = await forwardVerbatim(request, target, entry.controller.signal);
      outcomes.push({kind: 'answered', status: answer.status});
      await route.fulfill({status: answer.status, headers: fulfillHeaders(answer.headers), body: answer.body});
    } catch (error) {
      outcomes.push({kind: 'aborted', abortedAt: entry.abortedAt, reason: entry.reason, error: error.name});
      await route.abort().catch(() => {});
    } finally { registry.release(request); }
  });
  await page.goto(pageOrigin + '/');
  const body = JSON.stringify({text: 'Fixture line.', language: 'en', speechConsent: true, speakerProfile: 'female-calm-v1'});
  // 1) Answered: the page gets the upstream answer; upstream got the page's own Host, Origin and body.
  const answered = await page.evaluate(async body => {
    const r = await fetch('/api/mental-neural-speech', {method: 'POST', headers: {'Content-Type': 'application/json'}, body});
    return {status: r.status, source: r.headers.get('x-tts-source'), bytes: (await r.arrayBuffer()).byteLength};
  }, body);
  assert.deepEqual(answered, {status: 200, source: 'fixture', bytes: 64});
  assert.equal(seen[0].headers.host, new URL(pageOrigin).host);
  assert.equal(seen[0].headers.origin, pageOrigin);
  assert.equal(seen[0].body, body, 'body forwarded byte for byte (speechConsent is the page\'s own)');
  // 2) Abandoned: the page aborts after 300 ms; upstream must see its connection closed soon after.
  const abortedAt = await page.evaluate(async body => {
    const controller = new AbortController();
    const pending = fetch('/api/mental-neural-speech?slow=1', {method: 'POST', headers: {'Content-Type': 'application/json'}, body, signal: controller.signal}).catch(e => e.name);
    await new Promise(ok => setTimeout(ok, 300));
    const at = Date.now();
    controller.abort();
    await pending;
    return at;
  }, body);
  await new Promise(ok => setTimeout(ok, 1500));
  const slow = seen.find(row => row.url.includes('slow'));
  assert(slow && slow.closedAt, 'upstream connection of the abandoned request was closed');
  assert(!slow.answered, 'abandoned request was not answered');
  const lagMs = slow.closedAt - abortedAt;
  assert(lagMs >= 0 && lagMs < 1000, 'abort reached upstream within 1 s, took ' + lagMs + ' ms');
  assert.equal(outcomes.at(-1).kind, 'aborted');
  assert.match(outcomes.at(-1).reason, /^requestfailed/);
  console.log('PASS live forward: verbatim Host/Origin/body, answer delivered, page abort closed the upstream request after ' + lagMs + ' ms');
  await browser.close();
  upstream.close(); origin.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
