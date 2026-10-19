'use strict';
// Cloud-only host smoke. Desktop Chromium is explicitly NOT AAOS acceptance.
// Starts only owned services, refuses occupied ports, uses fresh disposable data.
const { spawn } = require('node:child_process');
const net = require('node:net');
const fs = require('node:fs');
const path = require('node:path');
const { navigate, allowedResource, ROUTES } = require('./webview_driver.cjs');
const root = path.resolve(__dirname, '../..');

async function freePort(port) {
  await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => server.close(resolve));
  });
}
async function main() {
  if (process.env.ATTUNE_LOAD_LOCAL_ENV !== '0' || !process.env.ATTUNE_DATA_DIR ||
      ['OPENAI_API_KEY', 'ATTUNE_ROBOFLOW_API_KEY', 'ROBOFLOW_API_KEY'].some(k => process.env[k])) throw Error('Isolated, keyless environment required');
  const { chromium } = require(process.env.ATTUNE_PLAYWRIGHT_NODE_PACKAGE);
  const out = process.env.ATTUNE_AAOS_EVIDENCE;
  if (!out || !process.env.ATTUNE_QA_CHROME || !process.env.ATTUNE_QA_PYTHON) throw Error('Explicit evidence, Chrome and Python paths required');
  fs.mkdirSync(out, { recursive: true });
  for (const port of [3000, 8000]) await freePort(port);
  const children = [], streams = [];
  let browser;
  const report = { environment: 'Cloud desktop Chromium, NOT Android/AAOS', routes: [], backend: [] };
  try {
    for (const [name, executable, args] of [
      ['backend', process.env.ATTUNE_QA_PYTHON, ['-m', 'uvicorn', 'main:app', '--app-dir', 'services/core-api', '--host', '127.0.0.1', '--port', '8000']],
      ['frontend', 'npm', ['--workspace=apps/vehicle-app', 'run', 'start']]
    ]) {
      const fd = fs.openSync(path.join(out, 'host-' + name + '.log'), 'w'); streams.push(fd);
      children.push(spawn(executable, args, { cwd: root, env: process.env, detached: true, stdio: ['ignore', fd, fd] }));
    }
    for (const port of [3000, 8000]) {
      let ready = false;
      for (let i = 0; i < 60; i++) {
        if (children.some(c => c.exitCode !== null)) throw Error('Owned service exited during startup');
        try { if ((await fetch(`http://127.0.0.1:${port}/` + (port === 8000 ? 'api/health' : ''), { signal: AbortSignal.timeout(2000) })).ok) { ready = true; break; } } catch {}
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      if (!ready) throw Error('Owned service not ready: ' + port);
    }
    const state = async () => (await fetch('http://127.0.0.1:8000/api/vehicle/state')).json();
    const setSpeed = async speedKmH => {
      const response = await fetch('http://127.0.0.1:8000/api/vehicle/speed', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ speedKmH }) });
      if (!response.ok) throw Error('Backend simulation rejected');
    };
    if ((await state()).vehicleParked !== true) throw Error('Expected fresh initial Park');
    report.backend.push({ check: 'fresh Park', status: 'PASS' });
    await setSpeed(75);
    if ((await state()).vehicleParked !== false) throw Error('Moving state did not close backend gate');
    report.backend.push({ check: 'independent backend moving state', status: 'PASS' });
    await setSpeed(0);
    browser = await chromium.launch({ executablePath: process.env.ATTUNE_QA_CHROME, headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, permissions: [] });
    const page = await context.newPage();
    await page.route('**/*', route => allowedResource(route.request().url()) ? route.continue() : route.abort('blockedbyclient'));
    await page.goto('http://localhost:3000/');
    for (const route of ROUTES) {
      try {
        const result = await navigate(page, route);
        await page.screenshot({ path: path.join(out, 'host-route-' + (route.slice(1) || 'dashboard') + '.png'), fullPage: false });
        report.routes.push(result);
      } catch (error) { report.routes.push({ path: route, status: 'FAIL', detail: String(error) }); }
    }
    if (report.routes.some(r => r.status !== 'PASS')) throw Error('Host navigation preflight failed; see host-web-preflight.json');
    console.log('PASS: keyless owned backend transitions and nine routes using the same navigation helper; desktop host only, no AAOS claim');
  } finally {
    fs.writeFileSync(path.join(out, 'host-web-preflight.json'), JSON.stringify(report, null, 2));
    if (browser) await browser.close();
    for (const child of children) {
      if (child.exitCode === null) { try { process.kill(-child.pid, 'SIGTERM'); } catch {} }
    }
    for (const fd of streams) fs.closeSync(fd);
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
