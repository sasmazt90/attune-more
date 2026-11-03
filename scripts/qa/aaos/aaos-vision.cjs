'use strict';
// Vision in the real AAOS WebView, reported in two honest layers. The AVD has no camera
// and WebView has no recognizer, so (1) records the unmodified boundary and (2) injects a
// fixture camera and a recognizer that answers from the letter on screen: correct, wrong
// letter and "not visible" in a fixed plan. Real in (2): Android runtime, approved-audio
// output, MediaPipe gates, UI, storage. No clinical, camera-HAL or real-speech claim.
const fs = require('node:fs');
const path = require('node:path');
const W = require('./webview.cjs');
const {CAMERA, DIAGNOSTICS, RECOGNIZER, WORDS} = require('./vision-injection.cjs');

const HISTORY = 'togg_health_vision_history';
// The product allows one 'not visible' per assessment, so the default plan uses it once.
const PLAN = process.env.ATTUNE_QA_VISION_PLAN ? process.env.ATTUNE_QA_VISION_PLAN.split(',') : Array.from({length: 24}, (_, trial) => trial === 5 ? 'not-visible' : ['correct', 'correct', 'wrong-letter'][trial % 3]);
const DELEGATE = process.env.ATTUNE_QA_VISION_DELEGATE || '';
const CAMERA_WIDTH = Number(process.env.ATTUNE_QA_VISION_CAMERA_WIDTH || 640), CAMERA_FPS = Number(process.env.ATTUNE_QA_VISION_CAMERA_FPS || 5);
// A probe stops after this many seconds of assessment and reports frames only.
const PROBE_SECONDS = Number(process.env.ATTUNE_QA_VISION_PROBE_SECONDS || 0);
const STALL_MS = 240000;
const LETTER_PATHS = {A: 'M15 90L50 10L85 90M29 60H71', B: 'M20 90V10H55C85 10 85 50 55 50H20M55 50C90 50 90 90 55 90H20', E: 'M80 10H20V90H80M20 50H70', F: 'M80 10H20V90M20 50H70', P: 'M20 90V10H55C90 10 90 50 55 50H20', R: 'M20 90V10H55C90 10 90 50 55 50H20M55 50L85 90'};

(async () => {
  const language = process.argv[2] || 'en', framesDir = process.argv[3];
  const {out, r, check, save} = W.report('vision-' + language);
  r.testMode = 'Layer 1: unmodified boundary. Layer 2: INJECTED fixture camera + scripted recognizer in the real WebView; answers come from the on-screen letter by a fixed plan.';
  r.conditions = {plan: PLAN, delegate: DELEGATE || 'app default', cameraWidth: CAMERA_WIDTH, cameraFps: CAMERA_FPS, probeSeconds: PROBE_SECONDS};
  const tr = W.translator(language);
  const framesFile = path.join(out, 'frames.jsonl');
  let session;
  try {
    session = await W.attach();
    const {page} = session;
    page.on('pageerror', error => r.errors.push(String(error)));
    await W.startClean(page);
    r.guestAtStart = W.guestLoad();
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

    for (const script of [DIAGNOSTICS(DELEGATE), CAMERA(CAMERA_WIDTH, CAMERA_FPS), RECOGNIZER(WORDS[language], LETTER_PATHS, PLAN)]) await page.addInitScript(script);
    await page.reload();
    await page.locator('#attune-language').waitFor();
    await page.locator('[data-health-start]').waitFor();
    const images = {};
    for (const name of ['Front', 'Right', 'Left']) images[name] = 'data:image/jpeg;base64,' + fs.readFileSync(path.join(framesDir, 'vision' + name + '.jpg')).toString('base64');
    await page.evaluate(async images => {
      for (const [name, url] of Object.entries(images)) { const image = new Image(); image.src = url; await image.decode(); window.__qaVision.images[name] = image; }
    }, images);
    let frames = 0;
    const firstFrameRetries = [];
    const drain = async () => { const data = await page.evaluate(() => window.__qaDiag.drain()); frames += data.frames.length; fs.appendFileSync(framesFile, JSON.stringify(data) + '\n'); return data; };

    await page.getByRole('button', {name: tr('Başlat'), exact: true}).click();
    const stage = page.locator('[data-vision-stage]');
    let last = '', lastProgress = Date.now(), current = 'Front', lastDone = 0, nextGuest = 0, seen = false;
    const began = Date.now();
    r.states = []; r.guest = [];
    const end = Date.now() + 1800000;
    while (Date.now() < end) {
      const state = await stage.evaluate(e => ({stage: e.dataset.visionStage, trial: e.dataset.visionTrial, done: Number(e.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow') || 0)}));
      if (Date.now() >= nextGuest) { nextGuest = Date.now() + 30000; r.guest.push({at: new Date().toISOString(), host: W.hostLoad(), ...W.guestLoad(true)}); await drain(); save(); }
      if (state.stage === 'result') break;
      if (PROBE_SECONDS && Date.now() - began > PROBE_SECONDS * 1000) { r.probeEnded = {stage: state.stage, done: state.done}; break; }
      if (state.stage === 'error') throw Error('Vision error stage: ' + (await stage.innerText()).slice(0, 400));
      if (state.stage === 'idle' && seen) {
        await drain();
        const failure = await page.evaluate(() => document.querySelector('canvas[hidden]')?.dataset.visionFailure || 'no failure recorded');
        // A person would press Start again after the honest first-frame error. Reported, and bounded.
        if (firstFrameRetries.length < 2 && !frames && failure.includes('"stage":"frame"')) {
          firstFrameRetries.push({failure, host: W.hostLoad(), guest: W.guestLoad()});
          r.firstFrameRetries = firstFrameRetries; seen = false; lastProgress = Date.now();
          await page.getByRole('button', {name: tr('Başlat'), exact: true}).click();
          continue;
        }
        throw Error('Task returned to idle: ' + failure);
      }
      if (state.stage !== 'idle') seen = true;
      if (state.trial && state.trial !== last) { last = state.trial; r.states.push({trial: state.trial, at: new Date().toISOString(), target: current, done: state.done}); }
      if (state.done !== lastDone) { lastDone = state.done; lastProgress = Date.now(); }
      const target = ['idle', 'preparing'].includes(state.stage) ? 'Front' : state.done < 12 ? 'Right' : 'Left';
      if (target !== current) { current = target; await page.evaluate(value => { window.__qaVision.target = value; }, target); }
      if (Date.now() - lastProgress > STALL_MS) { r.lastState = {...state, text: (await stage.innerText()).slice(0, 700)}; throw Error(`Vision made no progress for ${STALL_MS / 1000} s at stage ${state.stage}, ${state.done}/24`); }
      await page.waitForTimeout(500);
    }
    await drain();
    if (PROBE_SECONDS && r.probeEnded) { r.status = 'PROBE'; }
    else {
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
      r.trialLedger = {valid: valid.length, invalid: record.trials.length - valid.length, reasons: record.trials.filter(t => !t.valid).reduce((all, t) => ({...all, [t.invalidReason]: (all[t.invalidReason] || 0) + 1}), {})};
      check('24 valid trials, 12 per eye', valid.length === 24 && valid.filter(t => t.eye === 'RIGHT').length === 12 && valid.filter(t => t.eye === 'LEFT').length === 12, r.trialLedger);
      const expected = valid.map((_, index) => PLAN[index % PLAN.length]);
      const scored = valid.map(t => t.notVisible ? 'not-visible' : t.combinedCorrect ? 'correct' : t.letterCorrect === false && t.orientationCorrect === true ? 'wrong-letter' : 'other');
      check('Each recognized answer scored by the plan: correct, wrong letter, not visible', expected.every((kind, index) => kind === scored[index]), {expected: expected.slice(0, 8), scored: scored.slice(0, 8)});
      check('Recognized answers were parsed into letter and transform', valid.filter(t => !t.notVisible).every(t => t.answer && t.answer.letter && t.answer.transform));
      r.sizes = valid.map(t => t.sizePx);
      if (PLAN.includes('correct')) check('Adaptive size moved with the answers', new Set(r.sizes).size > 1, [...new Set(r.sizes)]);
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

      // DRIVE during a letter: the native gate destroys the WebView and nothing is scored.
      await W.goHome(page);
      await page.getByRole('button', {name: tr('Sağlık Merkezi'), exact: true}).click();
      await page.locator('#health-centre-links a[href="/vision"]').click();
      await page.waitForURL('**/vision');
      await page.locator('[data-health-start]').waitFor();
      const beforeDrive = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY);
      await page.evaluate(async images => { for (const [name, url] of Object.entries(images)) { const image = new Image(); image.src = url; await image.decode(); window.__qaVision.images[name] = image; } window.__qaVision.target = 'Front'; }, images);
      await page.getByRole('button', {name: tr('Başlat'), exact: true}).click();
      const reached = await page.waitForFunction(() => { const s = document.querySelector('[data-vision-stage]')?.dataset.visionStage; if (['eye-instruction', 'eye-check'].includes(s)) window.__qaVision.target = 'Right'; return ['rendering', 'prompting', 'listening'].includes(s); }, null, {timeout: 120000, polling: 500}).then(() => true, () => false);
      r.driveBoundaryReachedLetter = reached;
      await W.setSpeed(75);
      await W.sleep(4000);
      await W.setSpeed(0);
      await session.browser.close().catch(() => {});
      session = await W.attach();
      check('DRIVE during the assessment: new WebView, nothing stored', !(await session.page.evaluate(() => !!window.__qaVision)) && (await session.page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]').length, HISTORY)) === beforeDrive, {reachedLetter: reached});
      r.status = r.checks.every(item => item.pass) ? 'PASS' : 'FAIL';
    }
  } catch (error) {
    r.status = 'FAIL';
    r.error = String(error);
    process.exitCode = 1;
    try { W.shot(out, 'failure'); } catch {}
    try { fs.appendFileSync(framesFile, JSON.stringify(await session.page.evaluate(() => window.__qaDiag?.drain())) + '\n'); } catch {}
    try { r.logcat = W.shell('logcat', '-d', '-t', '300', '-v', 'time', '*:E').split('\n').filter(line => /chromium|webview|attune|lowmemory|lmkd|FATAL|GL|gralloc/i.test(line)).slice(-40); } catch {}
  } finally {
    r.finished = new Date().toISOString();
    save();
    // Leave no injected camera or running task for the next journey on this WebView.
    await session?.page.goto(W.origin + '/').catch(() => {});
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({out, status: r.status, checks: r.checks.length, failed: r.checks.filter(item => !item.pass).map(item => item.what), error: r.error}));
    process.exit(process.exitCode || 0);
  }
})();
