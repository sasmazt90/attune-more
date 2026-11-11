'use strict';
// Live AAOS closing (test only): the WebView's own request, byte for byte, to a real server, with the WebView's
// cancellation carried along.
//
// The harness intercepts the WebView's same-origin requests (CDP Fetch). For the closing's analysis and speech requests
// in live mode it does not build a request of its own: method, headers (Host and Origin included, as the WebView sent
// them to http://127.0.0.1:3000) and body are forwarded unchanged to `target` — the branch's Next server for
// /api/mental-neural-speech (the real product route: same-origin check, consent, language, size, bearer, loopback
// backend, answer checks) and the test API for /api/mental/analyze-session. When the WebView abandons the request
// (Playwright 'requestfailed', e.g. the closing is cancelled), the forwarded request is aborted, which closes its
// connection; the route then aborts its own backend request, and the API kills its worker.

const http = require('node:http');

const HOP_BY_HOP = new Set(['connection', 'keep-alive', 'proxy-connection', 'transfer-encoding', 'upgrade', 'te', 'trailer', 'content-length']);

// One AbortController per intercepted request; aborted when the page reports the request as failed or closes.
function cancellationRegistry(page) {
  const controllers = new Map();
  const abort = (request, reason) => {
    const entry = controllers.get(request);
    if (entry && !entry.controller.signal.aborted) { entry.abortedAt = Date.now(); entry.reason = reason; entry.controller.abort(); }
  };
  page.on('requestfailed', request => abort(request, 'requestfailed:' + (request.failure()?.errorText || '')));
  page.on('close', () => { for (const request of controllers.keys()) abort(request, 'page-closed'); });
  return {
    signalFor(request) {
      const entry = {controller: new AbortController(), abortedAt: null, reason: null};
      controllers.set(request, entry);
      return entry;
    },
    release(request) { controllers.delete(request); },
  };
}

// Forward the intercepted request unchanged to target (http://host:port); resolves {status, headers, body} or rejects
// with the abort reason. Host is kept as the WebView sent it, so the route's same-origin check sees the real origin.
function forwardVerbatim(request, target, signal, headersOverride) {
  return new Promise(async (resolve, reject) => {
    let headers, body;
    try {
      headers = headersOverride || await request.allHeaders();
      body = request.postDataBuffer() || Buffer.alloc(0);
    } catch (error) { reject(error); return; }
    const url = new URL(request.url()), to = new URL(target);
    const out = {};
    for (const [name, value] of Object.entries(headers)) if (!HOP_BY_HOP.has(name.toLowerCase()) && !name.startsWith(':')) out[name.toLowerCase()] = value;
    // The browser sends Host from the URL it requested; CDP does not always report it among the headers.
    if (!out.host) out.host = url.host;
    out['content-length'] = String(body.length);
    const upstream = http.request({host: to.hostname, port: to.port, method: request.method(), path: url.pathname + url.search, headers: out, signal}, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({status: response.statusCode, headers: response.headers, body: Buffer.concat(chunks)}));
      response.on('error', reject);
    });
    upstream.on('error', reject);
    upstream.end(body);
  });
}

// Response headers for route.fulfill: the server's own, minus hop-by-hop ones.
function fulfillHeaders(headers) {
  const out = {};
  for (const [name, value] of Object.entries(headers)) if (!HOP_BY_HOP.has(name.toLowerCase())) out[name] = Array.isArray(value) ? value.join(', ') : String(value);
  return out;
}

module.exports = {cancellationRegistry, forwardVerbatim, fulfillHeaders};
