// Drives the compatibility probe in Chromium. Blocks every request that does not go to the loopback server and
// records it, samples the browser's total RSS, and writes the page's own result plus the console log.
// Usage: node tools/run_probe.cjs <pageUrl> <outJson> <mode: cpu|gpu-swiftshader|gpu-default> [timeoutSec]
const {chromium} = require('playwright');
const fs = require('fs');
const {execSync} = require('child_process');
const [pageUrl, outJson, mode = 'cpu', timeoutSec = '1800'] = process.argv.slice(2);
const args = ['--no-sandbox', '--js-flags=--max-old-space-size=8192'];
if (mode === 'gpu-swiftshader') args.push('--enable-unsafe-webgpu', '--enable-features=Vulkan,WebGPU', '--use-angle=swiftshader', '--use-webgpu-adapter=swiftshader', '--ignore-gpu-blocklist');
if (mode === 'gpu-default') args.push('--enable-unsafe-webgpu', '--ignore-gpu-blocklist');
function browserRssMb() {
  try { const out = execSync("ps -eo rss,comm | awk '/chrome|headless_shell/ {s+=$1} END {print s}'").toString().trim(); return Math.round(Number(out) / 1024); } catch { return null; }
}
(async () => {
  const t0 = Date.now();
  const browser = await chromium.launch({headless: true, args, executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'});
  const ctx = await browser.newContext();
  const blocked = [], console_ = [];
  await ctx.route('**/*', route => { const u = route.request().url(); if (u.startsWith('http://127.0.0.1:')) return route.continue(); blocked.push(u); return route.abort(); });
  const page = await ctx.newPage();
  page.on('console', m => console_.push(`${((Date.now()-t0)/1000).toFixed(1)}s ${m.type()} ${m.text()}`.slice(0, 2000)));
  page.on('pageerror', e => console_.push(`pageerror ${e}`));
  page.on('crash', () => console_.push('PAGE CRASHED'));
  const rss = []; const sampler = setInterval(() => rss.push({t: Math.round((Date.now()-t0)/1000), mb: browserRssMb()}), 2000);
  await page.goto(pageUrl);
  let result = null;
  const deadline = Date.now() + Number(timeoutSec) * 1000;
  while (Date.now() < deadline) {
    try { result = await page.evaluate(() => window.__result); } catch (e) { console_.push('evaluate failed: ' + e); break; }
    if (result && result.done) break;
    await new Promise(r => setTimeout(r, 2000));
  }
  clearInterval(sampler);
  const record = {mode, launchArgs: args, browserVersion: browser.version(), wallSeconds: Math.round((Date.now()-t0)/1000), result,
    timedOut: !(result && result.done), blockedExternalRequests: blocked, peakBrowserRssMb: Math.max(...rss.map(r => r.mb || 0)), rssSamples: rss, console: console_};
  fs.writeFileSync(outJson, JSON.stringify(record, null, 1));
  console.log(JSON.stringify({mode, wall: record.wallSeconds, timedOut: record.timedOut, stages: result && result.stages, reply: result && result.reply, peakRss: record.peakBrowserRssMb, blocked: blocked.length, env: result && result.env}, null, 1));
  await browser.close();
})();
