'use strict';
// Mental lifecycle in the real AAOS WebView. Android WebView has no SpeechRecognition, so
// two layers are reported separately: the unmodified boundary (what a default build does
// here) and a scripted-recognizer + mocked-provider lifecycle. No paid request can leave.
const fs = require('node:fs');
const path = require('node:path');
const W = require('./webview.cjs');
const double = require('../e2e/mental-provider-double.cjs');

const HISTORY = 'togg_health_mental_history';
// Scripted recognizer: only stands in for the missing platform speech service.
const RECOGNIZER = `(()=>{window.__qaUtterances=[];window.__qaRecognitions=0;
 class QaRecognition{constructor(){this.lang='';this.continuous=false;this.interimResults=false;this.maxAlternatives=1;}
  start(){window.__qaRecognitions++;this.timer=setTimeout(()=>{this.onstart&&this.onstart();this.timer=setTimeout(()=>{const text=window.__qaUtterances.shift();
   if(text){const item=Object.assign([{transcript:text,confidence:.9}],{isFinal:true});this.onresult&&this.onresult({resultIndex:0,results:[item]});}
   else if(this.onerror)this.onerror({error:'no-speech'});this.onend&&this.onend();},500);},40);}
  abort(){clearTimeout(this.timer);}stop(){clearTimeout(this.timer);}}
 window.SpeechRecognition=QaRecognition;window.webkitSpeechRecognition=QaRecognition;})();`;

(async () => {
  const language = process.argv[2] || 'en';
  const {out, r, check, save} = W.report('mental-' + language);
  r.testMode = 'MOCKED PROVIDER + scripted recognizer in the real WebView. Real: Android runtime, native gates, WebView UI state machine, consent, localStorage. Not exercised: microphone-to-ASR, provider, neural TTS content.';
  const tr = W.translator(language);
  let session;
  try {
    session = await W.attach();
    let {page} = session;
    await W.setLanguage(page, language);
    const unmodified = await page.evaluate(() => ({speechRecognition: typeof window.SpeechRecognition, webkit: typeof window.webkitSpeechRecognition}));
    r.platformSpeech = unmodified;
    const state = await double.install(page);
    await W.enter(page, 'mental', tr);
    // Unmodified platform recognizer: a real microphone grant, no script, no provider.
    W.shell('pm', 'grant', '--user', W.shell('am', 'get-current-user'), W.pkg, 'android.permission.RECORD_AUDIO');
    const baseline = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY);
    await page.getByRole('button', {name: tr('Görüşmeyi Başlat'), exact: true}).click();
    await page.waitForFunction(() => ['error', 'listening'].includes(document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')), null, {timeout: 15000}).catch(() => {});
    await page.waitForTimeout(4000);
    const realPhase = await page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase');
    r.platformRecognizer = {phase: realPhase, text: (await page.locator('main').innerText()).slice(0, 320)};
    check('Platform recognizer boundary recorded; it never fabricates speech', await page.locator('[data-chat-author=USER]').count() === 0, r.platformRecognizer);
    W.shot(out, 'platform-recognizer');
    if (realPhase === 'listening') { await page.getByRole('button', {name: tr('Görüşmeyi Bitir'), exact: true}).click().catch(() => {}); await page.waitForTimeout(1000); }
    check('No record from the platform recognizer boundary', (await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY)) === baseline);

    await page.addInitScript(RECOGNIZER);
    await page.evaluate(RECOGNIZER);
    await page.reload();
    await page.locator('#attune-language').waitFor();
    const count = () => page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY);
    const ids = () => page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').map(item => item.id), HISTORY);
    await W.enter(page, 'mental', tr);
    const shape = await W.layout(page);
    check('Module fits 1280x720 without sideways scroll', !shape.overflow, shape);
    await W.onScreen(page, out, 'entry', check);
    const before = await ids();
    const say = text => page.evaluate(value => window.__qaUtterances.push(value), text);
    const phase = () => page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase');
    const waitPhase = name => page.locator(`[data-conversation-phase=${name}]`).waitFor({state: 'attached', timeout: 60000});
    const start = page.getByRole('button', {name: tr('Görüşmeyi Başlat'), exact: true});
    const finish = page.getByRole('button', {name: tr('Görüşmeyi Bitir'), exact: true});
    const playPending = async () => { const play = page.locator('[data-neural-play-response]'); if (await play.count() && await play.isEnabled()) await play.click(); };
    async function turn(text, index) {
      await say(text);
      const end = Date.now() + 90000;
      while (Date.now() < end) {
        await playPending();
        if (await page.locator('[data-chat-author=AI]').count() >= index && await phase() === 'listening') return;
        if (await phase() === 'error') throw Error('Unexpected error phase: ' + (await page.locator('main').innerText()).slice(0, 300));
        await page.waitForTimeout(300);
      }
      throw Error('Mental turn deadline');
    }

    await start.click();
    await waitPhase('listening');
    await turn('I felt calm today and took a short break.', 1);
    await turn('I want to keep a steady pace tomorrow.', 2);
    check('Two conversation turns reached listening again', await page.locator('[data-chat-author=USER]').count() === 2);
    await W.onScreen(page, out, 'conversation', check);
    await finish.click();
    await waitPhase('completed');
    check('Completed session saved exactly once, automatically', (await count()) === before.length + 1 && state.analyzeCalls === 1, {records: await count(), analyzeCalls: state.analyzeCalls});
    const records = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), HISTORY);
    const record = records.find(item => !before.includes(item.id));
    r.recordId = record.id;
    check('Raw transcript is not stored by default', !record.transcript && !record.transcriptConsented, {transcriptConsented: record.transcriptConsented ?? null});
    check('Summary record carries consent and completion', record.completed === true && record.consented === true && record.schemaVersion === 3);
    const summaryButtons = await page.locator('[data-mental-current-summary] button').allInnerTexts().catch(() => []);
    const allButtons = await page.locator('main button').allInnerTexts();
    check('No separate Save control after completion', !allButtons.some(text => /^(kaydet|save|speichern)$/i.test(text.trim())), {summaryButtons});
    const completion = page.getByRole('dialog');
    await completion.getByRole('button', {name: tr('Tamam'), exact: true}).click();
    W.shot(out, 'completed');
    // A re-render or a return to the module must not write a second record.
    await page.locator('nav a[href="/"]').first().click();
    await page.getByRole('button', {name: tr('Sağlık Merkezi'), exact: true}).click();
    await page.locator('#health-centre-links a[href="/mental"]').click();
    await page.waitForURL('**/mental');
    await start.waitFor();
    check('Returning to the module adds no duplicate', (await count()) === before.length + 1);

    await page.getByRole('link', {name: tr('Sağlık Geçmişim'), exact: true}).click();
    const row = page.locator(`[data-record-id="${record.id}"]`);
    await row.getByRole('button', {name: tr('Sonucu Aç'), exact: true}).click();
    const dialog = page.getByRole('dialog');
    await dialog.waitFor();
    check('History reopens the saved summary', (await dialog.innerText()).includes(record.summaryText.slice(0, 30)));
    W.shot(out, 'reopen');
    await page.getByRole('button', {name: tr('Sonuç penceresini kapat'), exact: true}).click();
    await dialog.waitFor({state: 'hidden'});
    check('Reopening adds no duplicate', (await count()) === before.length + 1);

    await page.getByRole('button', {name: tr('Sağlık Merkezi'), exact: true}).click();
    await page.locator('#health-centre-links a[href="/mental"]').click();
    await page.waitForURL('**/mental');
    state.delayAnalyzeMs = 3500;
    await start.click();
    await waitPhase('listening');
    await turn('A session whose summary I will cancel.', 1);
    await finish.click();
    await waitPhase('ending');
    await page.getByRole('button', {name: tr('Özet hazırlamayı iptal et'), exact: true}).click();
    await waitPhase('ready');
    await page.waitForTimeout(4500);
    check('Cancelled summary writes nothing, also after the late response', (await count()) === before.length + 1, {records: await count()});
    state.delayAnalyzeMs = 0;

    state.analyzeMode = 'fail503';
    await start.click();
    await waitPhase('listening');
    await turn('A session whose summary fails.', 1);
    await finish.click();
    await waitPhase('error');
    check('HTTP 503 summary saves no record and shows an error', (await count()) === before.length + 1);
    W.shot(out, 'summary-503');
    state.analyzeMode = 'success';

    state.converseMode = 'fail503';
    await start.click();
    await waitPhase('listening');
    await say('A turn whose reply fails.');
    await waitPhase('error');
    check('HTTP 503 reply stops the conversation in error', true);
    await finish.click().catch(() => {});
    await page.waitForTimeout(800);
    check('Failed conversation saves no record', (await count()) === before.length + 1);
    state.converseMode = 'success';

    await start.click();
    await waitPhase('listening');
    await page.getByRole('button', {name: tr('Duraklat'), exact: true}).click();
    await waitPhase('paused');
    const pausedCalls = await page.evaluate(() => window.__qaRecognitions);
    await page.waitForTimeout(1500);
    check('Pause stops listening', pausedCalls === await page.evaluate(() => window.__qaRecognitions), pausedCalls);
    await page.getByRole('button', {name: tr('Devam et'), exact: true}).click();
    await waitPhase('listening');
    await finish.click();
    await waitPhase('completed');
    check('An empty session is not stored', (await count()) === before.length + 1);
    await page.getByRole('dialog').getByRole('button', {name: tr('Tamam'), exact: true}).click();

    await start.click();
    await waitPhase('listening');
    await W.setSpeed(75);
    await W.sleep(4000);
    await W.setSpeed(0);
    await session.browser.close().catch(() => {});
    session = await W.attach();
    page = session.page;
    check('DRIVE during a conversation stores nothing (WebView was destroyed)', (await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY)) === before.length + 1);

    await page.getByRole('link', {name: tr('Sağlık Geçmişim'), exact: true}).click();
    const saved = page.locator(`[data-record-id="${record.id}"]`);
    await saved.getByRole('button', {name: new RegExp(tr('Sil'), 'i')}).click();
    await page.getByRole('button', {name: tr('Evet, sil'), exact: true}).click();
    await saved.waitFor({state: 'detached'});
    await page.reload();
    await page.locator('#attune-language').waitFor();
    check('Deletion survives reload', !(await page.evaluate(({key, id}) => JSON.parse(localStorage.getItem(key) || '[]').some(item => item.id === id), {key: HISTORY, id: record.id})));
    r.paidCalls = 0;
    r.providerCalls = {converse: state.converseCalls, analyze: state.analyzeCalls, speech: state.speechRequests.length, allIntercepted: true};
    r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
    try { W.shot(out, 'failure'); } catch {}
  } finally {
    await W.setSpeed(0).catch(() => {});
    r.finished = new Date().toISOString();
    save();
    fs.writeFileSync(path.join(out, 'assertions.json'), JSON.stringify(r, null, 1));
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, checks: r.checks.length, failed: r.checks.filter(item => !item.pass).map(item => item.what), error: r.error}));
  }
})();
