'use strict';
// Real Android WebView only. The documented Android API sets WebView protocol
// options that desktop Chromium CDP attachment does not set. No browser launch,
// Android UI driver install, media grant, or Car UX override is performed here.
const readline = require('node:readline');
const { URL } = require('node:url');
const PACKAGE = 'more.attune.automotive.prototype.debug';
const ORIGIN = 'http://localhost:3000';
const ROUTES = new Set(['/', '/skin', '/dental', '/vision', '/hearing', '/mental', '/care', '/profile', '/privacy']);
const localized = require('./localized_webview.cjs');

function mediaConstraints(features) {
  if (features.microphone === 'true') return { audio: true, video: false };
  if (features.camera === 'true') return { audio: false, video: true };
  return null;
}

function allowedResource(value) {
  try {
    const url = new URL(value);
    return ['http://localhost:3000', 'http://localhost:8000', 'http://127.0.0.1:8000'].includes(url.origin)
      || ['data:', 'blob:'].includes(url.protocol);
  } catch { return false; }
}

async function navigate(page, routePath) {
  if (!ROUTES.has(routePath)) throw Error('Route outside the finite acceptance list');
  const language = await page.locator('#attune-language').inputValue();
  localized.validate(language);
  if (routePath === '/' && page.url() !== ORIGIN + '/') await page.locator('header a[href="/"]').first().click();
  if (routePath !== '/') {
    // Privacy is a footer destination; health modules are in the closed menu.
    const link = page.locator(`${routePath === '/privacy' ? 'footer' : 'nav'} a[href="${routePath}"]`);
    if (!await link.count()) {
      const menu = page.getByRole('button', { name: {tr:'Sağlık Merkezi',en:'Health Center',de:'Gesundheitszentrum'}[language], exact: true });
      if (await menu.getAttribute('aria-expanded') !== 'true') await menu.click();
    }
    await link.click();
  }
  await page.waitForURL(ORIGIN + routePath);
  const acceptName = {tr:'İzin ver ve devam et',en:'Allow and continue',de:'Erlauben und fortfahren'}[language];
  const accept = page.getByRole('button', { name: acceptName, exact: true });
  const gate = page.getByRole('dialog').filter({ has: accept });
  if (await gate.count()) {
    for (const box of await gate.getByRole('checkbox').all()) await box.check();
    await gate.getByRole('button', { name: acceptName, exact: true }).click();
    await gate.waitFor({ state: 'hidden' });
  }
  await page.locator('h1').first().waitFor({ state: 'visible' });
  const result = await page.evaluate(() => ({
    width: innerWidth, scroll: document.documentElement.scrollWidth,
    headings: [...document.querySelectorAll('h1')].map(e => e.textContent)
  }));
  if (result.scroll > result.width + 1) throw Error('Horizontal overflow: ' + JSON.stringify(result));
  return { path: routePath, status: 'PASS', ...result };
}

async function serve() {
  const { _android } = require(process.env.ATTUNE_PLAYWRIGHT_NODE_PACKAGE);
  let device, page, phase = 'connect';
  const events = [];
  function record(kind, text, url) {
    if (events.length < 400) events.push({ phase, kind, text: String(text).slice(0, 2000), ...(url ? { url: url.split('?')[0] } : {}) });
    else if (events.at(-1)?.kind !== 'console-overflow') events.push({ phase, kind: 'console-overflow', text: 'Console observation limit reached' });
  }
  async function dispatch(action, args) {
    if (action === 'connect') {
      const devices = await _android.devices({ omitDriverInstall: true });
      device = devices.find(d => d.serial() === 'emulator-5554');
      if (!device) throw Error('Required emulator-5554 is not available');
      device.setDefaultTimeout(15000);
      const webview = await device.webView({ pkg: PACKAGE, timeout: 15000 });
      page = await webview.page();
      if (!page) throw Error('WebView has no page target');
      page.setDefaultTimeout(10000);
      page.on('pageerror', error => record('pageerror', error.message));
      page.on('console', message => { if (message.type() === 'error') record('error', message.text(), message.location().url); });
      await page.route('**/*', route => {
        if (allowedResource(route.request().url())) return route.continue();
        record('external-request-blocked', route.request().url().split('?')[0], route.request().url());
        return route.abort('blockedbyclient');
      });
      await page.waitForURL(url => url.origin === ORIGIN);
      return { url: page.url(), pid: webview.pid(), pkg: webview.pkg() };
    }
    if (action === 'phase') return true;
    if (action === 'events') return true;
    if (action === 'quit') { if (device) await device.close(); return true; }
    if (!page) throw Error('No Android WebView has been connected');
    if (action === 'ready') {
      await page.locator('[data-vehicle-status]').waitFor({ state: 'visible', timeout: 20000 });
      await page.waitForFunction(() => document.querySelector('[data-vehicle-status]')?.textContent === 'PARK');
      if (!await page.evaluate(() => fetch('http://localhost:8000/api/vehicle/state').then(r => r.ok))) throw Error('WebView cannot fetch loopback backend');
      if (!(await page.title()).includes('Attune.more')) throw Error('Unexpected page title');
      return { url: page.url(), title: await page.title() };
    }
    if (action === 'wait-url') { await page.waitForURL(ORIGIN + args.route); return page.url(); }
    if (action === 'navigate') return navigate(page, args.route);
    if (action === 'localization-language') return localized.language(page,args.language);
    if (action === 'localization-recording') return localized.recording(page,args.language,args.module);
    if (action === 'localization-decode') return localized.decode(page);
    if (action === 'permission-start') {
      const constraints = mediaConstraints(args.features);
      if (!constraints) throw Error('No advertised media hardware to exercise an OS request');
      await page.evaluate(constraints => {
        window.__attuneQaPermission = 'pending';
        const button = document.createElement('button');
        button.id = 'attune-qa-denial'; button.textContent = 'QA deny media';
        button.onclick = () => {
          if (!navigator.mediaDevices?.getUserMedia) { window.__attuneQaPermission = 'UNSUPPORTED_API'; return; }
          navigator.mediaDevices.getUserMedia(constraints)
            .then(stream => { stream.getTracks().forEach(track => track.stop()); window.__attuneQaPermission = 'UNEXPECTED_GRANT'; })
            .catch(error => { window.__attuneQaPermission = error.name; });
        };
        document.body.prepend(button);
      }, constraints);
      try { await page.locator('#attune-qa-denial').click({ noWaitAfter: true }); }
      catch (error) { if (!page.isClosed()) throw error; }
      return { constraints, closed: page.isClosed() };
    }
    if (action === 'permission-state') {
      if (page.isClosed()) return 'closed';
      try { return await page.evaluate(() => window.__attuneQaPermission); }
      catch (error) { if (page.isClosed()) return 'closed'; throw error; }
    }
    throw Error('Unknown bounded WebView operation: ' + action);
  }
  const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of lines) {
    let request;
    try {
      request = JSON.parse(line); phase = request.phase || phase;
      const result = await dispatch(request.action, request.args || {});
      process.stdout.write(JSON.stringify({ id: request.id, result, events: events.splice(0) }) + '\n');
      if (request.action === 'quit') break;
    } catch (error) {
      process.stdout.write(JSON.stringify({ id: request?.id, error: String(error), events: events.splice(0) }) + '\n');
    }
  }
}

if (require.main === module) {
  if (process.argv.includes('--self-check')) {
    const api = require(process.env.ATTUNE_PLAYWRIGHT_NODE_PACKAGE);
    if (typeof api._android?.devices !== 'function') throw Error('Playwright Android API unavailable');
    console.log('PASS: Node/Playwright Android API import; no emulator contacted or driver installed');
  } else serve().catch(error => { console.error(error); process.exitCode = 1; });
}
module.exports = { mediaConstraints, allowedResource, ROUTES, navigate };
