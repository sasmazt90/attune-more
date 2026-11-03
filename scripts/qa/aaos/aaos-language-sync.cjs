'use strict';
// Native toolbar language after real navigations from the shell's own Home button. A native
// language read lost to navigation must not freeze the labels for the rest of the WebView.
const W = require('./webview.cjs');
const LABEL = {en: 'Back', de: 'Zurück', tr: 'Geri'};
const dump = () => { W.shell('uiautomator', 'dump', '/sdcard/attune-qa-window.xml'); return W.shell('cat', '/sdcard/attune-qa-window.xml'); };
const texts = xml => [...xml.matchAll(/ text="([^"]+)"/g)].map(match => match[1]);
function tapHome(xml) {
  const node = [...xml.matchAll(/<node [^>]*>/g)].map(match => match[0]).find(item => item.includes('text="Attune.more"') && item.includes('clickable="true"'));
  const [x0, y0, x1, y1] = node.match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/).slice(1).map(Number);
  W.shell('input', 'tap', String((x0 + x1) >> 1), String((y0 + y1) >> 1));
}
(async () => {
  const rounds = Number(process.argv[2] || 12), budget = Number(process.argv[3] || 15000);
  const {out, r, check, save} = W.report('language-sync');
  const session = await W.attach();
  const {page} = session;
  await W.startClean(page);
  r.rounds = [];
  try {
    await W.setLanguage(page, 'tr');
    for (let i = 0; i < rounds; i++) {
      const target = i % 2 ? 'tr' : (i % 4 === 2 ? 'de' : 'en');
      tapHome(dump());
      // Immediately after the navigation request, as a user changing language would.
      await page.locator('#attune-language').waitFor();
      await W.setLanguage(page, target);
      const began = Date.now();
      let seen = false, labels = [];
      while (Date.now() - began < budget) {
        labels = texts(dump());
        if (labels.includes(LABEL[target])) { seen = true; break; }
        await W.sleep(400);
      }
      r.rounds.push({round: i, target, seen, seconds: (Date.now() - began) / 1000, toolbar: labels.slice(0, 1)});
      save();
      console.log(JSON.stringify(r.rounds.at(-1)));
    }
    check('Native toolbar reached the selected language in every round', r.rounds.every(row => row.seen), r.rounds.filter(row => !row.seen));
    r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
  } finally {
    await W.setLanguage(page, 'tr').catch(() => {});
    r.finished = new Date().toISOString();
    save();
    await session.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, error: r.error}));
    process.exit(process.exitCode || 0);
  }
})();
