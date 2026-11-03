'use strict';
// Hearing interrupted on the real AAOS WebView: HOME and DRIVE during a scored DIN trial. An
// interrupted assessment must not leave a record, and the module must start clean afterwards.
const fs = require('node:fs');
const path = require('node:path');
const W = require('./webview.cjs');

const HISTORY = 'attune_hearing_history_v1';

(async () => {
  const language = process.argv[2] || 'en';
  const {out, r, check} = W.report('hearing-boundaries-' + language);
  r.boundary = 'Real Android WebView, real native gate and background transitions. Synthetic listener; no human listening.';
  const tr = W.translator(language);
  let session;
  try {
    session = await W.attach();
    await W.startClean(session.page);
    await W.setLanguage(session.page, language);
    const records = page => page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY);
    const baseline = await records(session.page);
    async function reachDigits(page) {
      await W.enter(page, 'hearing', tr);
      const button = name => page.getByRole('button', {name: tr(name), exact: true});
      await button('Ses hazırlığını başlat').click();
      await button('Sol kanalı dinle').waitFor({timeout: 40000});
      await page.waitForFunction(label => [...document.querySelectorAll('[data-hearing-page] button')].some(b => b.textContent === label && !b.disabled), tr('Sol kanalı dinle'), {timeout: 40000});
      for (const [play, confirm] of [['Sol kanalı dinle', 'Yalnız sol kulağımda duydum.'], ['Sağ kanalı dinle', 'Yalnız sağ kulağımda duydum.']]) {
        await button(play).click();
        await page.getByRole('checkbox', {name: tr(confirm), exact: true}).check({timeout: 10000});
      }
      await button(language === 'tr' ? 'Gürültüde Türkçe sayılar' : 'Gürültüde seçilen dilin sayıları').click();
      await page.waitForFunction(() => { const e = document.querySelector('input[inputmode=numeric]'); return e && !e.disabled; }, null, {timeout: 60000});
    }

    await reachDigits(session.page);
    check('A scored DIN trial is open', await session.page.locator('[data-din-progress] [role=progressbar]').count() === 1);
    W.shot(out, 'din-open');
    W.shell('input', 'keyevent', 'KEYCODE_HOME');
    await W.sleep(3000);
    const top = W.shell('dumpsys', 'activity', 'top').split('ACTIVITY ').pop().slice(0, 160);
    check('HOME moves the app to the background', !top.includes(W.pkg), top.slice(0, 90));
    W.shell('am', 'start', '-W', '--user', 'current', '-n', W.component);
    await session.browser.close().catch(() => {});
    session = await W.attach();
    const afterHome = await session.page.evaluate(() => ({path: location.pathname, trialOpen: !!document.querySelector('input[inputmode=numeric]:not([disabled])'), text: document.querySelector('[data-hearing-page]')?.innerText.slice(0, 200) || ''}));
    r.afterHome = afterHome;
    check('Background ends the open trial: no answer field stays open', !afterHome.trialOpen, afterHome);
    check('Background during DIN stores nothing', (await records(session.page)) === baseline);
    W.shot(out, 'after-home');

    await W.startClean(session.page);
    await reachDigits(session.page);
    await session.page.evaluate(() => { window.__qaBeforeDrive = true; });
    await W.setSpeed(75);
    await W.sleep(4000);
    W.shot(out, 'drive');
    await W.setSpeed(0);
    await session.browser.close().catch(() => {});
    session = await W.attach();
    check('DRIVE destroyed the WebView: the page after PARK is a new instance', !(await session.page.evaluate(() => window.__qaBeforeDrive === true)));
    check('DRIVE during DIN stores nothing', (await records(session.page)) === baseline);
    await W.enter(session.page, 'hearing', tr);
    check('The module starts clean after DRIVE', await session.page.getByRole('button', {name: tr('Ses hazırlığını başlat'), exact: true}).isEnabled());
    W.shot(out, 'after-drive');
    r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
    try { W.shot(out, 'failure'); } catch {}
  } finally {
    await W.setSpeed(0).catch(() => {});
    r.finished = new Date().toISOString();
    fs.writeFileSync(path.join(out, 'assertions.json'), JSON.stringify(r, null, 1));
    await session?.page.goto(W.origin + '/').catch(() => {});
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, checks: r.checks.length, failed: r.checks.filter(item => !item.pass).map(item => item.what), error: r.error}));
    process.exit(process.exitCode || 0);
  }
})();
