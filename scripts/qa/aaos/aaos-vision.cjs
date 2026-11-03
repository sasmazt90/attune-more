'use strict';
// Vision in the real AAOS WebView, reported in two honest layers. The AVD has no camera
// and WebView has no recognizer, so (1) records the unmodified boundary and (2) injects a
// fixture camera and a scripted "not visible" recognizer. Real in (2): Android runtime,
// approved-audio output, MediaPipe gates, UI, storage. No clinical or camera-HAL claim.
const fs = require('node:fs');
const path = require('node:path');
const W = require('./webview.cjs');

const HISTORY = 'togg_health_vision_history';
const INJECTED = `(()=>{window.__qaVision={target:'Front',images:{},recognitions:0};
 const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;const g=canvas.getContext('2d');
 setInterval(()=>{const image=window.__qaVision.images[window.__qaVision.target];if(image&&image.complete&&image.naturalWidth){if(canvas.width!==image.naturalWidth){canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;}g.drawImage(image,0,0);}else{g.fillStyle='#111';g.fillRect(0,0,canvas.width,canvas.height);}},66);
 const stream=canvas.captureStream(15);
 const real=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=c=>c&&c.video?Promise.resolve(new MediaStream(stream.getVideoTracks().map(t=>t.clone()))):real(c);
 class QaRecognition{constructor(){this.lang='';this.continuous=false;this.interimResults=false;this.maxAlternatives=1;}
  start(){window.__qaVision.recognitions++;this.timer=setTimeout(()=>{this.onstart&&this.onstart();this.timer=setTimeout(()=>{const item=Object.assign([{transcript:window.__qaVision.answer,confidence:.95}],{isFinal:true});this.onresult&&this.onresult({resultIndex:0,results:[item]});this.onend&&this.onend();},700);},40);}
  abort(){clearTimeout(this.timer);}stop(){clearTimeout(this.timer);}}
 window.SpeechRecognition=QaRecognition;window.webkitSpeechRecognition=QaRecognition;})();`;
const ANSWER = {tr: 'göremiyorum', en: 'i cannot see it', de: 'ich sehe es nicht'};
const EYE = {tr: [/Sağ göz\s*[·•]/, /Sol göz\s*[·•]/], en: [/Right eye\s*[·•]/, /Left eye\s*[·•]/], de: [/Rechtes Auge\s*[·•]/, /Linkes Auge\s*[·•]/]};

(async () => {
  const language = process.argv[2] || 'en', framesDir = process.argv[3];
  const {out, r, check, save} = W.report('vision-' + language);
  r.testMode = 'Layer 1: unmodified boundary. Layer 2: INJECTED fixture camera + scripted recognizer in the real WebView; every answer is a scripted not-visible response.';
  const tr = W.translator(language);
  let session;
  try {
    session = await W.attach();
    const {page} = session;
    page.on('pageerror', error => r.errors.push(String(error)));
    await W.setLanguage(page, language);
    await page.getByRole('link', {name: tr('Gizlilik & İzinler'), exact: true}).click();
    const save_ = page.getByRole('checkbox', {name: tr('Yön hizalama sonuçlarını bu cihazda sakla'), exact: true});
    if (!await save_.isChecked()) await save_.check();
    await W.enter(page, 'vision', tr);
    const shape = await W.layout(page);
    check('Entry fits 1280x720 without sideways scroll', !shape.overflow, shape);
    await W.onScreen(page, out, 'entry', check);
    const before = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').map(item => item.id), HISTORY);

    await page.getByRole('button', {name: tr('Başlat'), exact: true}).click();
    const message = page.getByRole('alert').filter({hasText: /\S/}).first();
    await message.waitFor({timeout: 20000});
    const alert = await message.innerText();
    check('No camera device: start stops with an honest error, nothing scored', alert.includes(tr('Kamera görüntüsü alınamadı. Kamera izinlerini ve cihazı kontrol edin.')), alert);
    check('No record from the failed start', (await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY)) === before.length);
    W.shot(out, 'no-camera-boundary');

    await page.addInitScript(INJECTED);
    await page.reload();
    await page.locator('#attune-language').waitFor();
    await page.locator('[data-health-start]').waitFor();
    const images = {};
    for (const name of ['Front', 'Right', 'Left']) images[name] = 'data:image/jpeg;base64,' + fs.readFileSync(path.join(framesDir, 'vision' + name + '.jpg')).toString('base64');
    await page.evaluate(async ({images, answer}) => {
      window.__qaVision.answer = answer;
      for (const [name, url] of Object.entries(images)) { const image = new Image(); image.src = url; await image.decode(); window.__qaVision.images[name] = image; }
    }, {images, answer: ANSWER[language]});

    await page.getByRole('button', {name: tr('Başlat'), exact: true}).click();
    const stage = page.locator('[data-vision-stage]');
    let last = '', lastProgress = Date.now(), current = 'Front';
    r.states = [];
    const end = Date.now() + 1200000;
    while (Date.now() < end) {
      const state = await stage.evaluate(e => ({stage: e.dataset.visionStage, trial: e.dataset.visionTrial, text: e.innerText.slice(0, 1400), voice: e.querySelector('[data-vision-voice]')?.getAttribute('data-vision-voice')}));
      if (state.stage === 'result') break;
      if (state.stage === 'error') throw Error('Vision error stage: ' + state.text.slice(0, 500));
      if (state.stage === 'idle' && r.states.length) throw Error('Task returned to idle: ' + await page.evaluate(() => document.querySelector('canvas[hidden]')?.dataset.visionFailure || 'no failure recorded'));
      if (state.trial && state.trial !== last) {
        last = state.trial; lastProgress = Date.now();
        const health = await page.evaluate(() => { const e = JSON.parse(document.querySelector('canvas[hidden]')?.dataset.visionEvidence || 'null'); return e && {inferenceMs: Math.round(e.inferenceMs), delegate: e.delegate, blocker: e.conditions?.blocker || null}; });
        r.states.push({trial: state.trial, at: new Date().toISOString(), target: current, ...health}); save();
      }
      let target = 'Front';
      if (!['idle', 'preparing'].includes(state.stage)) { if (EYE[language][0].test(state.text)) target = 'Right'; else if (EYE[language][1].test(state.text)) target = 'Left'; }
      if (target !== current) { current = target; await page.evaluate(value => { window.__qaVision.target = value; }, target); }
      if (Date.now() - lastProgress > 180000) { r.lastState = state; throw Error('Vision gate stalled for 180 s at stage ' + state.stage); }
      await page.waitForTimeout(600);
    }
    check('24-trial assessment reached the result stage', (await stage.getAttribute('data-vision-stage')) === 'result');
    const notice = page.getByRole('dialog');
    if (await notice.count()) await notice.getByRole('button', {name: tr('Tamam'), exact: true}).click();
    await W.onScreen(page, out, 'result', check);
    const records = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]'), HISTORY);
    const created = records.filter(item => !before.includes(item.id));
    check('Exactly one saved record', created.length === 1, created.length);
    const record = created[0];
    r.recordId = record.id;
    const valid = record.trials.filter(t => t.valid);
    check('24 valid trials, 12 per eye, all scripted not-visible', valid.length === 24 && valid.filter(t => t.eye === 'RIGHT').length === 12 && valid.filter(t => t.eye === 'LEFT').length === 12 && valid.every(t => t.notVisible), {valid: valid.length, invalid: record.trials.length - valid.length});
    check('Invalid presentations keep their reason', record.trials.filter(t => !t.valid).every(t => t.invalidReason));
    check('Device context is the AAOS display', record.deviceContext?.width === 1280 || record.deviceContext?.height === 720, record.deviceContext);
    for (const eye of ['RIGHT', 'LEFT']) check(`Result card for ${eye}`, await page.locator(`[data-letter-result] [data-eye-result=${eye}]`).count() === 1);
    await page.getByRole('link', {name: tr('Sağlık Geçmişim'), exact: true}).click();
    const row = page.locator(`[data-record-id="${record.id}"]`);
    await row.getByRole('button', {name: tr('Sonucu Aç'), exact: true}).click();
    const dialog = page.getByRole('dialog');
    await dialog.locator('[data-letter-result]').waitFor();
    check('History reopens the saved result', true);
    W.shot(out, 'reopen');
    await page.getByRole('button', {name: tr('Sonuç penceresini kapat'), exact: true}).click();
    await dialog.waitFor({state: 'hidden'});
    await row.getByRole('button', {name: new RegExp(tr('Sil'), 'i')}).click();
    await page.getByRole('button', {name: tr('Evet, sil'), exact: true}).click();
    await row.waitFor({state: 'detached'});
    await page.reload();
    await page.locator('#attune-language').waitFor();
    check('Deletion survives reload', !(await page.evaluate(({key, id}) => JSON.parse(localStorage.getItem(key) || '[]').some(item => item.id === id), {key: HISTORY, id: record.id})));
    check('No page errors', r.errors.length === 0, r.errors);
    r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
    try { W.shot(out, 'failure'); } catch {}
  } finally {
    r.finished = new Date().toISOString();
    save();
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, checks: r.checks.length, failed: r.checks.filter(item => !item.pass).map(item => item.what), error: r.error}));
  }
})();
