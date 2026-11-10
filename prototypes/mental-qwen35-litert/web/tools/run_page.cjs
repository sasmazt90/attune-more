// Generic Playwright runner for bench pages: loopback only (every other request is blocked and recorded).
// Usage: node tools/run_page.cjs <url> <outJson> [timeoutSec] [--webgpu-swiftshader]
const {chromium} = require('playwright');
const fs = require('fs');
const [url, outJson, timeoutSec = '1800', ...flags] = process.argv.slice(2);
(async () => {
  const t0 = Date.now();
  const args = ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'];
  if (flags.includes('--webgpu-swiftshader')) args.push('--enable-unsafe-webgpu', '--enable-features=Vulkan,WebGPU', '--use-angle=swiftshader', '--use-webgpu-adapter=swiftshader');
  const browser = await chromium.launch({headless: true, args, executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'});
  const ctx = await browser.newContext();
  const blocked = [], con = [];
  await ctx.route('**/*', r => { const u = r.request().url(); if (u.startsWith('http://127.0.0.1:') || u.startsWith('data:') || u.startsWith('blob:')) return r.continue(); blocked.push(u); return r.abort(); });
  const page = await ctx.newPage();
  page.on('console', m => con.push(`${((Date.now() - t0) / 1000).toFixed(1)}s ${m.type()} ${m.text()}`.slice(0, 600)));
  page.on('pageerror', e => con.push('pageerror ' + e));
  await page.goto(url);
  let result = null; const end = Date.now() + Number(timeoutSec) * 1000;
  while (Date.now() < end) { result = await page.evaluate(() => window.__result).catch(() => null); if (result && result.done) break; await new Promise(r => setTimeout(r, 1000)); }
  fs.writeFileSync(outJson, JSON.stringify({url, browser: browser.version(), startedAt: new Date(t0).toISOString(), wallSeconds: Math.round((Date.now() - t0) / 1000),
    timedOut: !(result && result.done), blockedExternalRequests: blocked, result, console: con.slice(-60)}, null, 1));
  console.log(JSON.stringify({wall: Math.round((Date.now() - t0) / 1000), timedOut: !(result && result.done), blocked: blocked.length, error: result && result.error, items: result && result.items && result.items.length}));
  await browser.close();
})();
