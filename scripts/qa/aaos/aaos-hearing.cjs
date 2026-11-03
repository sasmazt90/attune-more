'use strict';
// Hearing on the real AAOS WebView: 24 scored DIN trials with PCM completion observed from
// the Web Audio node and guest mixer state sampled during output. The listener is
// synthetic, so this is a functional result: no human hearing or calibration claim.
const assert = require('node:assert/strict');
const W = require('./webview.cjs');

(async () => {
  const language = process.argv[2] || 'tr';
  const {out, r, check} = W.report('hearing-' + language);
  r.boundary = 'Real Android WebView, real Web Audio output into the guest mixer, native gates. Synthetic listener; no physical speaker or human listening.';
  const tr = W.translator(language);
  let session, stopRecording;
  try {
    session = await W.attach();
    const {page} = session;
    if (process.env.ATTUNE_QA_RECORD === '1') stopRecording = W.recording(out, 'hearing-' + language);
    page.on('pageerror', error => r.errors.push(String(error)));
    await W.setLanguage(page, language);
    await W.enter(page, 'hearing', tr);
    const shape = await W.layout(page);
    check('Entry fits 1280x720 without sideways scroll', !shape.overflow, shape);
    await W.onScreen(page, out, 'entry', check);
    const before = await page.evaluate(() => JSON.parse(localStorage.getItem('attune_hearing_history_v1') || '[]').map(row => row.id));
    await page.evaluate(() => {
      window.__qaPcm = [];
      const start = AudioBufferSourceNode.prototype.start;
      AudioBufferSourceNode.prototype.start = function (...args) { const b = this.buffer; if (b) { const row = {frames: b.length, rate: b.sampleRate, channels: b.numberOfChannels, ended: false}; window.__qaPcm.push(row); this.addEventListener('ended', () => { row.ended = true; }); } return start.apply(this, args); };
      const random = crypto.getRandomValues.bind(crypto);
      crypto.getRandomValues = function (a) { const value = random(a); if (a instanceof Uint32Array && a.length === 1) window.__qaSeed = a[0]; return value; };
    });
    const button = name => page.getByRole('button', {name: tr(name), exact: true});
    await button('Ses hazırlığını başlat').click();
    await button('Sol kanalı dinle').waitFor({timeout: 40000});
    await page.waitForFunction(label => [...document.querySelectorAll('[data-hearing-page] button')].some(b => b.textContent === label && !b.disabled), tr('Sol kanalı dinle'), {timeout: 40000});
    for (const [play, confirm] of [['Sol kanalı dinle', 'Yalnız sol kulağımda duydum.'], ['Sağ kanalı dinle', 'Yalnız sağ kulağımda duydum.']]) {
      const box = page.getByRole('checkbox', {name: tr(confirm), exact: true});
      check('Confirmation is disabled before the channel played: ' + play, await box.isDisabled());
      await button(play).click();
      const mixer = W.audioFlinger();
      await box.check({timeout: 10000});
      check('Channel sample reached the guest mixer: ' + play, mixer.standbyNo || mixer.startedPlayers.length > 0, mixer);
    }
    await button(language === 'tr' ? 'Gürültüde Türkçe sayılar' : 'Gürültüde seçilen dilin sayıları').click();
    let seed = await page.evaluate(() => window.__qaSeed);
    assert.equal(typeof seed, 'number');
    const random = () => { seed = (1664525 * seed + 1013904223) >>> 0; return seed / 4294967296; };
    const answer = page.getByRole('textbox', {name: tr('Üç sayı yanıtı'), exact: true});
    const replies = [];
    r.mixerDuringDigits = [];
    for (let i = 0; i < 24; i++) {
      await page.waitForFunction(() => { const e = document.querySelector('input[inputmode=numeric]'); return e && !e.disabled; }, null, {timeout: 45000});
      if (i % 8 === 0) r.mixerAfterPlayback = W.audioFlinger();
      const digits = Array.from({length: 3}, () => Math.floor(random() * 10));
      random();
      const response = i % 2 ? digits.map(d => (d + 1) % 10) : digits;
      assert.equal(Number(await page.locator('[data-din-progress] [role=progressbar]').getAttribute('aria-valuenow')), i);
      if (i === 0) {
        // Real touch and hardware keys through Android input, not DOM events.
        await answer.focus();
        W.shell('input', 'text', response.join(''));
        await page.waitForFunction(value => document.querySelector('input[inputmode=numeric]').value === value, response.join(''), {timeout: 8000});
        check('Android input service typed into the DIN field', true, response.join(''));
      } else await answer.fill(response.join(''));
      replies.push({digits, response});
      await button('Yanıtı Gönder').click();
      await page.waitForTimeout(250);
      if (i % 8 === 1) r.mixerDuringDigits.push(W.audioFlinger());
    }
    await page.locator('[data-hearing-result]').waitFor({timeout: 15000});
    await page.waitForFunction(ids => JSON.parse(localStorage.getItem('attune_hearing_history_v1') || '[]').filter(row => !ids.includes(row.id)).length === 1, before, {timeout: 15000});
    const created = await page.evaluate(ids => JSON.parse(localStorage.getItem('attune_hearing_history_v1')).filter(row => !ids.includes(row.id)), before);
    check('Exactly one saved record', created.length === 1, created.map(row => row.id));
    const row = created[0];
    r.recordId = row.id;
    check('24 valid trials, 24 scored presentations', row.validTrials === 24 && row.presentations?.length === 24, {validTrials: row.validTrials, presentations: row.presentations?.length});
    check('Scored answers equal what was submitted', row.history.every((h, i) => JSON.stringify(h.digits) === JSON.stringify(replies[i].digits) && JSON.stringify(h.answer) === JSON.stringify(replies[i].response)));
    check('12/24 triplets correct as submitted', row.history.filter(h => h.correct).length === 12, row.history.filter(h => h.correct).length);
    const expected = {tr: ['tr-TR-AhmetNeural', 'tr-TR'], en: ['Andrew', 'en-US'], de: ['Stefan', 'de-DE']}[language];
    check('Selected language bank and voice', row.bankVoice === expected[0] && row.bankLocale === expected[1], {voice: row.bankVoice, locale: row.bankLocale});
    const pcm = await page.evaluate(() => window.__qaPcm);
    check('26 PCM outputs started and ended (2 channel samples + 24 trials)', pcm.length === 26 && pcm.every(p => p.ended && p.channels === 2 && p.rate === 48000), {count: pcm.length, ended: pcm.filter(p => p.ended).length});
    check('Guest mixer active during DIN output', r.mixerDuringDigits.some(m => m.standbyNo || m.startedPlayers.length), r.mixerDuringDigits);
    const cards = await page.locator('[data-din-scorecards]').innerText();
    check('Localized score cards', ['Doğru sayı', 'Tam üçlü', 'Geçerli deneme'].every(title => cards.includes(tr(title))), cards);
    await W.onScreen(page, out, 'result', check);
    await page.getByRole('link', {name: tr('Sağlık Geçmişim'), exact: true}).click();
    const saved = page.locator(`[data-record-id="${row.id}"]`);
    await saved.getByRole('button', {name: tr('Sonucu Aç'), exact: true}).click();
    const dialog = page.getByRole('dialog');
    await dialog.waitFor();
    check('Reopened saved DIN result', (await dialog.innerText()).length > 40);
    await W.onScreen(page, out, 'reopen', check);
    await page.getByRole('button', {name: tr('Sonuç penceresini kapat'), exact: true}).click();
    await dialog.waitFor({state: 'hidden'});
    await saved.getByRole('button', {name: new RegExp(tr('Sil') + '|' + tr('sil'), 'i')}).click();
    await page.getByRole('button', {name: tr('Evet, sil'), exact: true}).click();
    await saved.waitFor({state: 'detached'});
    await page.reload();
    await page.locator('#attune-language').waitFor();
    check('Deletion survives reload', !(await page.evaluate(id => JSON.parse(localStorage.getItem('attune_hearing_history_v1') || '[]').some(item => item.id === id), row.id)));
    r.errors.length ? check('No page errors', false, r.errors) : check('No page errors', true);
    r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
    try { W.shot(out, 'failure'); } catch {}
  } finally {
    if (stopRecording) await stopRecording().catch(error => { r.recordingError = String(error); });
    r.finished = new Date().toISOString();
    require('node:fs').writeFileSync(out + '/assertions.json', JSON.stringify(r, null, 1));
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, checks: r.checks.length, failed: r.checks.filter(item => !item.pass).map(item => item.what), error: r.error}));
    process.exit(process.exitCode || 0);
  }
})();
