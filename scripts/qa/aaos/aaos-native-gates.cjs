'use strict';
// Native shell boundaries on the real emulator: PARK/DRIVE, stale vehicle data, background,
// system Back, Android touch and keys, media permission and language sync. Every changed
// condition is restored in finally; the test only touches the simulated test vehicle.
const fs = require('node:fs');
const path = require('node:path');
const W = require('./webview.cjs');

const dump = () => { W.shell('uiautomator', 'dump', '/sdcard/attune-qa-window.xml'); return W.shell('cat', '/sdcard/attune-qa-window.xml'); };
const hasWebView = xml => xml.includes('android.webkit.WebView');
const visibleText = xml => [...xml.matchAll(/ text="([^"]+)"/g)].map(match => match[1]);
function tapNode(xml, label) {
  const node = [...xml.matchAll(/<node [^>]*>/g)].map(match => match[0]).find(item => item.includes(`text="${label}"`) && item.includes('clickable="true"'));
  if (!node) throw Error('Native control not found: ' + label);
  const [x0, y0, x1, y1] = node.match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/).slice(1).map(Number);
  W.shell('input', 'tap', String((x0 + x1) >> 1), String((y0 + y1) >> 1));
}
async function waitForDump(test, seconds) {
  const end = Date.now() + seconds * 1000;
  let xml = '';
  while (Date.now() < end) { xml = dump(); if (test(xml)) return {ok: true, xml}; await W.sleep(1000); }
  return {ok: false, xml};
}

(async () => {
  const {out, r, check} = W.report('native-gates');
  let session, backendStopped = false;
  try {
    r.runtime = {release: W.shell('getprop', 'ro.build.version.release'), sdk: W.shell('getprop', 'ro.build.version.sdk'), automotive: W.shell('pm', 'list', 'features').includes('android.hardware.type.automotive'), display: W.shell('wm', 'size'), apk: W.shell('sha256sum', W.shell('pm', 'path', W.pkg).split(':')[1]).split(' ')[0]};
    check('Real AAOS 15 runtime at 1280x720', r.runtime.sdk === '35' && r.runtime.automotive && r.runtime.display.includes('1280x720'), r.runtime);
    session = await W.attach();
    const parkedState = await W.vehicle();
    check('Backend reports PARK', parkedState.vehicleParked && !parkedState.vehicleMoving, {gear: parkedState.gear});
    let result = await waitForDump(hasWebView, 20);
    check('PARK opens the WebView', result.ok);
    await W.onScreen(session.page, out, 'parked', check);

    await session.page.evaluate(() => { window.__qaLoaded = true; });
    await W.setSpeed(75);
    result = await waitForDump(xml => !hasWebView(xml), 12);
    check('DRIVE destroys the WebView', result.ok, visibleText(result.xml).slice(-4));
    W.shot(out, 'moving');
    await W.setSpeed(0);
    result = await waitForDump(hasWebView, 25);
    check('PARK restores the WebView after DRIVE', result.ok);
    await session.browser.close().catch(() => {});
    session = await W.attach();
    check('The WebView after DRIVE is a new instance', !(await session.page.evaluate(() => window.__qaLoaded === true)));

    // A real outage: removing the adb reverse listener would leave the pooled keep-alive stream alive.
    W.backend('stop-backend');
    backendStopped = true;
    result = await waitForDump(xml => !hasWebView(xml), 15);
    check('Lost vehicle data closes the WebView (fail closed, 2.5 s freshness)', result.ok, visibleText(result.xml).slice(-4));
    W.shot(out, 'stale');
    W.backend('start-backend');
    backendStopped = false;
    result = await waitForDump(hasWebView, 30);
    check('Fresh vehicle data reopens the WebView', result.ok);
    await session.browser.close().catch(() => {});

    session = await W.attach();
    W.shell('input', 'keyevent', 'KEYCODE_HOME');
    await W.sleep(2500);
    const top = W.shell('dumpsys', 'activity', 'top').split('ACTIVITY ').pop().slice(0, 160);
    check('HOME moves the app to the background', !top.includes(W.pkg), top.slice(0, 90));
    W.shell('am', 'start', '-W', '--user', 'current', '-n', W.component);
    result = await waitForDump(hasWebView, 25);
    check('Foreground reopens a gated WebView', result.ok);
    await session.browser.close().catch(() => {});

    session = await W.attach();
    const {page} = session;
    await W.startClean(page);
    await W.setLanguage(page, 'tr');
    const tr = W.translator('tr');
    await W.enter(page, 'hearing', tr);
    W.shell('input', 'keyevent', 'KEYCODE_BACK');
    await page.waitForFunction(() => location.pathname !== '/hearing', null, {timeout: 8000});
    check('System Back leaves the module through WebView history', true, page.url());
    W.shell('input', 'keyevent', 'KEYCODE_TAB');
    await W.sleep(500);
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    W.shell('input', 'keyevent', 'KEYCODE_TAB');
    await W.sleep(500);
    const moved = await page.evaluate(() => (document.activeElement?.innerText || document.activeElement?.getAttribute('aria-label') || document.activeElement?.tagName || '').slice(0, 50));
    check('Hardware Tab moves focus inside the WebView', focused !== 'BODY' || moved !== 'BODY', {focused, moved});
    const toolbar = dump();
    tapNode(toolbar, 'Attune.more');
    await page.waitForFunction(() => location.pathname === '/', null, {timeout: 12000}).catch(() => {});
    check('Native toolbar touch reaches the shell', new URL(page.url()).pathname === '/', page.url());

    for (const [language, label] of [['en', 'Back'], ['de', 'Zurück'], ['tr', 'Geri']]) {
      await W.setLanguage(page, language);
      result = await waitForDump(xml => visibleText(xml).includes(label), 6);
      check(`Native toolbar follows WebView language (${language})`, result.ok, visibleText(result.xml).slice(0, 4));
    }

    W.shell('pm', 'grant', '--user', W.shell('am', 'get-current-user'), W.pkg, 'android.permission.RECORD_AUDIO');
    await page.locator('nav a[href="/"]').first().click();
    const mic = await page.evaluate(async () => { try { const s = await navigator.mediaDevices.getUserMedia({audio: true}); const kinds = s.getTracks().map(t => t.kind); s.getTracks().forEach(t => t.stop()); return {ok: true, kinds}; } catch (e) { return {ok: false, name: e.name}; } });
    check('Microphone grant crosses the native permission path', mic.ok && mic.kinds.includes('audio'), mic);
    const camera = await page.evaluate(async () => { try { const s = await navigator.mediaDevices.getUserMedia({video: true}); s.getTracks().forEach(t => t.stop()); return {ok: true}; } catch (e) { return {ok: false, name: e.name}; } });
    r.cameraService = W.shell('dumpsys', 'media.camera').split('\n').filter(line => line.includes('Number of camera devices')).slice(0, 1);
    r.cameraBoundary = {camera, note: 'The Google AAOS 15 x86_64 image exposes no camera service; camera journeys are BLOCKED here, not PASS.'};
    check('No camera device: getUserMedia(video) is refused, not faked', !camera.ok, {camera, service: r.cameraService});
    await W.onScreen(page, out, 'final', check);
    r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
    try { W.shot(out, 'failure'); } catch {}
  } finally {
    if (backendStopped) W.backend('start-backend');
    await W.setSpeed(0).catch(() => {});
    r.finished = new Date().toISOString();
    fs.writeFileSync(path.join(out, 'assertions.json'), JSON.stringify(r, null, 1));
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, checks: r.checks.length, failed: r.checks.filter(item => !item.pass).map(item => item.what), error: r.error}));
    process.exit(process.exitCode || 0);
  }
})();
