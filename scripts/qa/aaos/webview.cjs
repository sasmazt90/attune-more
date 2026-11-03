'use strict';
// Real AAOS WebView session over the debug devtools socket. Evidence labels state which
// parts are real (Android runtime, native gates, WebView UI, storage, audio mixer) and
// which are injected (camera, recognizer, provider); a label is never upgraded.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const {chromium} = require(process.env.ATTUNE_QA_PLAYWRIGHT || 'playwright');

const config = JSON.parse(fs.readFileSync(process.env.ATTUNE_QA_AAOS_CONFIG, 'utf8').replace(/^﻿/, ''));
const serial = config.serial, pkg = config.package, adbPath = config.adb, port = config.devtoolsPort || 19226;
const component = pkg + '/more.attune.automotive.MainActivity';
const origin = 'http://localhost:3000', api = 'http://127.0.0.1:8000';
const repository = path.resolve(__dirname, '../../..');
const catalog = Object.values(JSON.parse(fs.readFileSync(path.join(repository, 'shared/localization/messages.json'), 'utf8')));
const sleep = ms => new Promise(ok => setTimeout(ok, ms));

function adb(...args) { return cp.execFileSync(adbPath, ['-s', serial, ...args], {encoding: 'utf8', timeout: 45000, maxBuffer: 32 * 1024 * 1024}).trim(); }
const shell = (...args) => adb('shell', ...args);
let displayId;
// AAOS exposes several displays; screencap needs the main one or it prints a warning instead of a PNG.
function displayIdOf() { displayId ??= shell('dumpsys', 'SurfaceFlinger', '--display-id').match(/Display (\d+)/)[1]; return displayId; }
function shot(out, name) {
  fs.writeFileSync(path.join(out, name + '.png'), cp.execFileSync(adbPath, ['-s', serial, 'exec-out', 'screencap', '-d', displayIdOf(), '-p'], {timeout: 30000, maxBuffer: 32 * 1024 * 1024}));
}
// Visible, focused and painting is what DOM automation alone cannot show. The capture is
// reported separately: with -gpu host the emulator can return a blank frame (gfxstream
// glReadPixels errors in its log) while the app keeps painting at full rate.
const LAUNCHER_FRAME_BYTES = 45000;
async function onScreen(page, out, name, check) {
  const state = await page.evaluate(() => new Promise(ok => { let frames = 0; const began = performance.now(); const tick = () => { frames++; if (performance.now() - began < 1000) requestAnimationFrame(tick); else ok({hidden: document.hidden, visibility: document.visibilityState, focused: document.hasFocus(), framesPerSecond: frames}); }; requestAnimationFrame(tick); setTimeout(() => ok({hidden: document.hidden, visibility: document.visibilityState, focused: document.hasFocus(), framesPerSecond: frames}), 2500); }));
  shot(out, name);
  const bytes = fs.statSync(path.join(out, name + '.png')).size;
  return check(`App is visible and painting: ${name}`, !state.hidden && state.focused && state.framesPerSecond >= 3, {...state, screenshotBytes: bytes, captureLooksValid: bytes > LAUNCHER_FRAME_BYTES});
}
// A real Android screen recording of the journey; ends with the returned stop function.
function recording(out, name) {
  const device = '/sdcard/attune-qa-recording.mp4';
  const child = cp.spawn(adbPath, ['-s', serial, 'shell', 'screenrecord', '--display-id', displayIdOf(), '--bit-rate', '1200000', '--time-limit', '175', device], {windowsHide: true, stdio: 'ignore'});
  return async () => {
    try { shell('pkill', '-2', 'screenrecord'); } catch {}
    await sleep(1500);
    child.kill();
    cp.execFileSync(adbPath, ['-s', serial, 'pull', device, path.join(out, name + '.mp4')], {timeout: 60000, stdio: 'ignore'});
    shell('rm', '-f', device);
  };
}
// Stops or restarts only the QA backend this checkout owns.
function backend(action) {
  const runtime = process.env.ATTUNE_QA_RUNTIME_CONFIG, workdir = process.env.ATTUNE_QA_SERVICE_DIR;
  const python = JSON.parse(fs.readFileSync(runtime, 'utf8').replace(/^\uFEFF/, '')).python;
  cp.execFileSync(python, [path.join(repository, 'scripts/qa/qa_services.py'), action, '--workdir', workdir, '--runtime-config', runtime], {timeout: 180000, stdio: 'ignore'});
}
async function vehicle() { return (await fetch(api + '/api/vehicle/state')).json(); }
async function setSpeed(speedKmH) { return (await fetch(api + '/api/vehicle/speed', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({speedKmH})})).json(); }

function report(name) {
  const out = path.join(process.env.ATTUNE_QA_OUT, 'aaos-' + name + '-' + Date.now());
  fs.mkdirSync(out, {recursive: true});
  const r = {module: name, platform: 'AAOS 15 native shell + Android WebView (emulator)', started: new Date().toISOString(), checks: [], errors: [], status: 'RUNNING',
    sourceCommit: process.env.ATTUNE_QA_SHA || cp.execFileSync('git', ['-C', repository, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim(),
    buildId: process.env.ATTUNE_QA_BUILD_ID || fs.readFileSync(path.join(repository, 'apps/vehicle-app/.next/BUILD_ID'), 'utf8').trim()};
  const save = () => fs.writeFileSync(path.join(out, 'assertions.json'), JSON.stringify(r, null, 1));
  const check = (what, pass, observed) => { r.checks.push({what, pass: !!pass, observed, at: new Date().toISOString()}); save(); console.log((pass ? 'PASS ' : 'FAIL ') + what); return !!pass; };
  save();
  return {out, r, save, check};
}

// Attaches to the running WebView; launches the activity when the gate destroyed it.
async function attach(timeout = 120000) {
  const end = Date.now() + timeout;
  let last;
  while (Date.now() < end) {
    try {
      const pid = shell('pidof', pkg).split(/\s+/)[0];
      if (!pid) { shell('am', 'start', '-W', '--user', 'current', '-n', component); await sleep(1500); continue; }
      adb('forward', 'tcp:' + port, 'localabstract:webview_devtools_remote_' + pid);
      const browser = await chromium.connectOverCDP('http://127.0.0.1:' + port, {timeout: 6000});
      const context = browser.contexts()[0];
      const page = context?.pages().find(candidate => !candidate.isClosed() && candidate.url().startsWith(origin));
      if (!page) { await browser.close().catch(() => {}); shell('am', 'start', '--user', 'current', '-n', component); await sleep(1500); continue; }
      await page.locator('#attune-language').waitFor({timeout: 8000});
      page.setDefaultTimeout(20000);
      return {browser, context, page};
    } catch (error) {
      last = error;
      try { shell('am', 'start', '--user', 'current', '-n', component); } catch {}
      await sleep(1500);
    }
  }
  throw Error('WebView not attachable: ' + String(last));
}

async function setLanguage(page, value) {
  await page.locator('#attune-language').selectOption(value);
  await page.waitForFunction(v => document.documentElement.lang === v, value);
  await page.evaluate(() => new Promise(ok => requestAnimationFrame(() => requestAnimationFrame(ok))));
}
const translator = language => text => language === 'tr' ? text : catalog.find(v => v.tr.trim() === text.trim())?.[language] || text;

// A slow guest may still be on the old route; its open menu would detach mid-click.
async function goHome(page) {
  await page.locator('nav a[href="/"]').first().click();
  await page.waitForFunction(() => location.pathname === '/', null, {timeout: 20000});
}
async function enter(page, module, tr) {
  await goHome(page);
  await page.getByRole('button', {name: tr('Sağlık Merkezi'), exact: true}).click();
  await page.locator('#health-centre-links a[href="/' + module + '"]').click();
  await page.waitForURL('**/' + module);
  const dialog = page.getByRole('dialog');
  if (await dialog.waitFor({timeout: 4000}).then(() => true, () => false)) {
    for (const box of await dialog.getByRole('checkbox').all()) await box.check();
    await dialog.getByRole('button', {name: tr('İzin ver ve devam et'), exact: true}).click();
    await dialog.waitFor({state: 'hidden'});
  }
  await page.locator('[data-health-start]').waitFor();
}

// 1280x720 fit in the real WebView: no sideways page scroll, touch-sized visible controls.
async function layout(page) {
  return page.evaluate(() => {
    const small = [];
    for (const element of document.querySelectorAll('main button,main a[href],main select,main input:not([type=checkbox])')) {
      const box = element.getBoundingClientRect();
      if (box.width && box.height && (box.height < 40 || box.width < 40)) small.push({text: (element.innerText || element.getAttribute('aria-label') || '').trim().slice(0, 40), width: Math.round(box.width), height: Math.round(box.height)});
    }
    return {width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth, overflow: document.documentElement.scrollWidth > innerWidth + 1, small};
  });
}

// Guest mixer view while output plays. Proves samples reached Android's audio path, not that
// a person heard them; the emulator has no physical speaker or headset in this boundary.
function audioFlinger() {
  const raw = shell('dumpsys', 'media.audio_flinger');
  const tracks = [...raw.matchAll(/Active\s*:\s*(\w+)|Standby:\s*(\w+)/g)].map(match => match[1] || match[2]);
  const players = shell('dumpsys', 'audio').split('\n').filter(line => /state:started|usage=USAGE_MEDIA.*started/.test(line)).slice(0, 4).map(line => line.trim().slice(0, 140));
  return {standbyNo: /Standby:\s*no/.test(raw), framesWritten: [...raw.matchAll(/Frames written:\s*(\d+)/g)].slice(0, 4).map(match => Number(match[1])), tracks: tracks.slice(0, 8), startedPlayers: players};
}

module.exports = {adb, backend, goHome, onScreen, recording, shell, shot, sleep, attach, enter, layout, report, setLanguage, translator, vehicle, setSpeed, audioFlinger, component, pkg, origin, api};
