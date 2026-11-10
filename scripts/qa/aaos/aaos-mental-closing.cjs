'use strict';
// Closing A/B/C bridge in the real AAOS WebView (cloudDemo APK, AAOS 15 emulator on the AWS AAOS host).
//
// Real: Android runtime and native gates (PARK/driving, background destroy), the WebView and its media pipeline with
// setMediaPlaybackRequiresUserGesture(true), Android's audio mixer and focus, this branch's frontend code and the 45
// committed WAVs. The product web-aaos service is not changed: every non-API request of the WebView origin is answered,
// through CDP interception, by a build of this branch on the AAOS host (CLOSING_BUILD_ORIGIN). Vehicle state requests go
// to the real backend unchanged, so web and native gates see the same state.
// Replayed (labelled, never upgraded): the recognizer (Android WebView has none), the conversation reply, and the
// analysis and female-calm-v1 speech responses, which are the WEB real-path recordings (CLOSING_REPLAY_DIR/realpath.json
// and its WAVs) delivered after their measured delays.
//
// Usage: node scripts/qa/aaos/aaos-mental-closing.cjs   (env: ATTUNE_QA_AAOS_CONFIG, ATTUNE_QA_OUT, ATTUNE_QA_PLAYWRIGHT,
//        CLOSING_BUILD_ORIGIN, CLOSING_REPLAY_DIR, CLOSING_ONLY=comma list of case names)
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const W = require('./webview.cjs');

const BUILD = process.env.CLOSING_BUILD_ORIGIN || 'http://127.0.0.1:3100';
const REPLAY = process.env.CLOSING_REPLAY_DIR;
const replay = JSON.parse(fs.readFileSync(path.join(REPLAY, 'realpath.json'), 'utf8'));
const LOCALE = {tr: 'tr-TR', en: 'en-US', de: 'de-DE'};
const REPLY = {tr: 'Anlıyorum. Bunu paylaştığınız için teşekkür ederim.', en: 'I understand. Thank you for sharing that.', de: 'Ich verstehe. Danke, dass Sie das teilen.'};
const sleep = ms => new Promise(ok => setTimeout(ok, ms));
const repository = path.resolve(__dirname, '../../..');

// Scripted recognizer (as in aaos-mental.cjs), timeline of the app's content-free timing events, and a record of every
// media play() call so that late audio after a cancellation is visible even when it is short.
const PAGE_SCRIPT = `(()=>{if(window.__closingQa)return;window.__closingQa=true;window.__qaUtterances=[];window.__timeline=[];window.__plays=[];
 addEventListener('attune-speech-timing',e=>window.__timeline.push({stage:e.detail.stage,atMs:e.detail.atMs}));
 const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){window.__plays.push({atMs:performance.now(),src:String(this.currentSrc||this.src||'').slice(0,12),guidance:this.dataset&&this.dataset.guidanceId||null});return play.apply(this,arguments);};
 class QaRecognition{constructor(){this.lang='';this.continuous=false;this.interimResults=false;this.maxAlternatives=1;}
  start(){this.timer=setTimeout(()=>{this.onstart&&this.onstart();this.timer=setTimeout(()=>{const text=window.__qaUtterances.shift();
   if(text){const item=Object.assign([{transcript:text,confidence:.9}],{isFinal:true});this.onresult&&this.onresult({resultIndex:0,results:[item]});}
   else if(this.onerror)this.onerror({error:'no-speech'});this.onend&&this.onend();},500);},40);}
  abort(){clearTimeout(this.timer);}stop(){clearTimeout(this.timer);}}
 window.SpeechRecognition=QaRecognition;window.webkitSpeechRecognition=QaRecognition;})();`;

const analysis = (language, n) => replay.analyses.find(a => a.conversation === `${language}-c${n}` && a.status === 200);
const speech = (text, start) => replay.tts.find(t => t.status === 200 && t.text === text && t.scenarioStart === start) || replay.tts.find(t => t.status === 200 && t.text === text);
const wav = row => fs.readFileSync(path.join(REPLAY, row.label + '.wav'));

const plan = {language: 'tr', conversation: 1, start: 'warm', requests: [], late: []};
async function install(page) {
  const json = (route, body, status = 200) => route.fulfill({status, contentType: 'application/json', headers: {'Cache-Control': 'no-store'}, body: JSON.stringify(body)});
  await page.route(url => url.origin === W.origin, async route => {
    const request = route.request(), url = new URL(request.url());
    try {
      if (url.pathname.startsWith('/api/vehicle/')) return await route.continue();
      if (url.pathname === '/api/mental/provider-status') return await json(route, {isLiveLLM: true, apiKeyConfigured: true, providerName: 'replay of the WEB real-path run'});
      if (url.pathname === '/api/mental/compact-context') return await json(route, {memory: [], method: 'extractive-user-quotes-v1'});
      if (url.pathname === '/api/mental/converse') return await json(route, {reply: REPLY[plan.language], isCrisis: false, providerType: 'LIVE_OPENAI'});
      if (url.pathname === '/api/mental/analyze-session') {
        const body = request.postDataJSON(), a = analysis(plan.language, plan.conversation), id = plan.id;
        plan.requests.push({kind: 'analysis', id, spokenSummaryRequested: body.spokenSummary === true, at: Date.now(), delayMs: Math.round(a.seconds * 1000)});
        await sleep(a.seconds * 1000);
        return await json(route, {summaryText: a.summaryText, spokenSummary: a.spokenSummary, spokenSummaryStatus: a.spokenSummaryStatus, themes: [], moodTrend: a.moodTrend || 'STRESSED',
          professionalSupportSuggested: false, professionalSupportReason: null, providerType: 'LIVE_OPENAI'});
      }
      if (url.pathname === '/api/mental-neural-speech') {
        const body = request.postDataJSON(), id = plan.id;
        // Ordinary conversation turns are not under test: they get the second conversation's short recording.
        const row = body.speakerProfile === 'female-calm-v1' ? speech(body.text, plan.start) : replay.tts.find(t => t.status === 200 && t.label === `${plan.language}-c2-short-warm`);
        if (!row) { plan.requests.push({kind: 'tts', id, missing: crypto.createHash('sha256').update(body.text || '').digest('hex')}); return await route.fulfill({status: 503, body: '{}'}); }
        const delay = body.speakerProfile ? row.seconds * 1000 : 1500;
        plan.requests.push({kind: 'tts', id, closing: !!body.speakerProfile, label: row.label, at: Date.now(), delayMs: Math.round(delay)});
        await sleep(delay);
        const answered = {kind: 'tts-answered', id, label: row.label, at: Date.now()};
        plan.requests.push(answered);
        return await route.fulfill({status: 200, headers: {'Content-Type': 'audio/wav', 'Cache-Control': 'no-store', 'X-TTS-Source': 'chatterbox-multilingual-v3',
          'X-TTS-Locale': LOCALE[body.language] || LOCALE[plan.language], ...(body.speakerProfile ? {'X-TTS-Speaker-Profile': body.speakerProfile} : {})}, body: wav(row)});
      }
      if (url.pathname.startsWith('/api/')) return await route.continue();
      const response = await route.fetch({url: BUILD + url.pathname + url.search});
      return await route.fulfill({response});
    } catch (error) {
      // A destroyed WebView or a navigation can end the request first; nothing reaches the page then.
      plan.requests.push({kind: 'route-ended', path: url.pathname, error: String(error).slice(0, 80)});
    }
  });
}

// Each WebView page (a new one after the native shell destroyed the old) gets the page script and routes once.
const prepared = new WeakSet();
async function ensure(page) {
  if (prepared.has(page)) return;
  prepared.add(page);
  await page.addInitScript(PAGE_SCRIPT);
  await install(page);
}

async function open(page, language) {
  await ensure(page);
  await W.startClean(page);
  await page.evaluate(PAGE_SCRIPT);
  await W.setLanguage(page, language);
  await W.enter(page, 'mental', W.translator(language));
  const build = await page.evaluate(() => document.querySelector('script[src*="/_next/static/"]')?.getAttribute('src') || null);
  return build;
}

// Screen coordinates of an element for a real Android touch (input tap), via the WebView's bounds on screen.
function webViewBounds() {
  W.shell('uiautomator', 'dump', '/sdcard/attune-ui.xml');
  const xml = W.shell('cat', '/sdcard/attune-ui.xml');
  W.shell('rm', '-f', '/sdcard/attune-ui.xml');
  const m = xml.match(/class="android\.webkit\.WebView"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);
  if (!m) throw Error('WebView bounds not found');
  return {x: Number(m[1]), y: Number(m[2]), right: Number(m[3]), bottom: Number(m[4])};
}
async function realTap(page, locator) {
  const box = await locator.boundingBox(), dpr = await page.evaluate(() => devicePixelRatio), view = webViewBounds();
  const x = Math.round(view.x + (box.x + box.width / 2) * dpr), y = Math.round(view.y + (box.y + box.height / 2) * dpr);
  W.shell('input', 'tap', String(x), String(y));
  return {x, y, dpr, view};
}

// Frames the primary output wrote during a short window: > 0 means something is playing now. ("Standby: no" alone
// stays set for a while after playback and is not evidence of output.)
async function mixerDelta(ms = 2000) {
  const a = W.audioFlinger(); await sleep(ms); const b = W.audioFlinger();
  return {framesDelta: (b.framesWritten[0] || 0) - (a.framesWritten[0] || 0), windowMs: ms, standbyNo: b.standbyNo};
}

function focusOwners() {
  const raw = W.shell('dumpsys', 'audio');
  const stack = raw.split('Audio Focus stack entries')[1] || '';
  return stack.split('\n').slice(0, 6).map(line => line.trim()).filter(line => /source|pack|uid/.test(line)).map(line => line.slice(0, 160));
}

async function waitStage(page, stage, timeout = 60000) {
  await page.waitForFunction(s => window.__timeline.some(e => e.stage === s), stage, {timeout});
}

async function conversation(page, language, tr) {
  const phase = () => page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase');
  const taps = [];
  await page.evaluate(text => window.__qaUtterances.push(text), {
    tr: 'Son haftalarda işte tempo çok yoğun ve uykum sık sık bölünüyor.', en: 'Work has been very intense lately and my sleep keeps getting interrupted.',
    de: 'Bei der Arbeit ist es sehr intensiv und mein Schlaf wird oft unterbrochen.'}[language]);
  await page.getByRole('button', {name: tr('Görüşmeyi Başlat'), exact: true}).click();
  const end = Date.now() + 90000;
  while (Date.now() < end) {
    const play = page.locator('[data-neural-play-response]');
    if (await play.count() && await play.isEnabled()) { taps.push({at: Date.now(), phase: await phase()}); await play.click(); }
    if (await page.locator('[data-chat-author=AI]').count() >= 1 && await phase() === 'listening') return taps;
    await page.waitForTimeout(300);
  }
  throw Error('conversation turn deadline');
}

function metrics(events, t0) {
  const first = s => { const e = events.find(x => x.stage === s && x.atMs >= t0); return e ? Math.round(e.atMs - t0) : null; };
  const all = s => events.filter(x => x.stage === s && x.atMs >= t0).map(e => Math.round(e.atMs - t0));
  const m = {aPlaying: first('closing-A-playing'), aEnded: first('closing-A-ended'), bPlaying: first('closing-B-playing'), bEnded: first('closing-B-ended'),
    cPlaying: first('closing-C-playing'), cEnded: first('closing-C-ended'), verified: first('closing-bridge-verified'), summaryTextReady: first('closing-summary-text-ready'),
    firstPartReady: first('closing-summary-first-ready'), summaryPlaying: first('closing-summary-audio-start'), summaryComplete: first('closing-summary-complete'),
    noSpokenLine: first('closing-summary-no-spoken-line'), partPlaying: all('closing-summary-playing'), partEnded: all('closing-summary-ended'),
    gestureRequired: events.filter(e => e.atMs >= t0 && /gesture-required/.test(e.stage)).map(e => e.stage)};
  m.gaps = {aToB: m.bPlaying !== null && m.aEnded !== null ? m.bPlaying - m.aEnded : null, bToC: m.cPlaying !== null && m.bEnded !== null ? m.cPlaying - m.bEnded : null,
    cToSummary: m.summaryPlaying !== null && m.cEnded !== null ? m.summaryPlaying - m.cEnded : null, overlap: m.summaryPlaying !== null && m.cEnded !== null && m.summaryPlaying < m.cEnded};
  return m;
}

// One closing. action: null | cancel | mute | consent | language | drive | background ; at: timing stage that triggers it.
async function closing(session, language, options, check, out, r) {
  let {page} = session;
  const tr = W.translator(language);
  plan.language = language; plan.conversation = options.conversation || 1; plan.start = options.start || 'warm'; plan.id = options.name;
  const build = await open(page, language);
  const turnTaps = await conversation(page, language, tr);
  const t0 = await page.evaluate(() => performance.now());
  const finish = page.getByRole('button', {name: tr('Görüşmeyi Bitir'), exact: true});
  const tap = options.realTap ? await realTap(page, finish) : (await finish.click(), null);
  const row = {name: options.name, language, action: options.action || null, at: options.at || null, build, finishInput: tap ? {kind: 'adb input tap', ...tap} : 'CDP click', turnTaps};
  if (tap) {
    row.realTapStartedClosing = await waitStage(page, 'closing-trigger', 6000).then(() => true, () => false);
    check(`${options.name}: a real Android touch (adb input tap) on "end conversation" starts the closing`, row.realTapStartedClosing, row.finishInput);
    if (!row.realTapStartedClosing) { W.shot(out, options.name + '-tap-missed'); await finish.click(); }
  }
  await waitStage(page, 'closing-A-playing', 20000).catch(() => {});
  row.mixerDuringA = await mixerDelta(1000);
  row.focusDuringA = focusOwners();
  if (options.action) {
    await waitStage(page, options.at, 90000);
    const actedAt = Date.now();
    if (options.action === 'cancel') {
      // The control is "Özet hazırlamayı iptal et" until the summary is shown, then "Sesli kapanışı durdur".
      const stop = page.getByRole('button', {name: tr('Sesli kapanışı durdur'), exact: true}), cancel = page.getByRole('button', {name: tr('Özet hazırlamayı iptal et'), exact: true});
      const which = await stop.count() ? stop : cancel;
      row.cancelControl = await which.innerText();
      await which.click();
    }
    if (options.action === 'mute') await page.getByRole('button', {name: tr('Seslendirmeyi kapat'), exact: true}).click();
    if (options.action === 'consent') await page.evaluate(() => { const key = 'attune_health_processing_v1', d = JSON.parse(localStorage.getItem(key)); delete d.services.mental; localStorage.setItem(key, JSON.stringify(d)); dispatchEvent(new Event('attune-service-consent')); dispatchEvent(new Event('attune-privacy')); });
    if (options.action === 'language') {
      // The selector is locked during a running process; a change cannot reach the closing through the UI.
      row.languageSelector = await page.locator('#attune-language').evaluate(el => ({disabled: el.disabled, title: el.title, value: el.value}));
      check(`${options.name}: language selector is locked while the closing plays`, row.languageSelector.disabled === true, row.languageSelector);
    }
    if (options.action === 'drive') await W.setSpeed(75);
    if (options.action === 'background') W.shell('input', 'keyevent', 'KEYCODE_HOME');
    row.actedAt = actedAt;
    if (['drive', 'background'].includes(options.action)) {
      // The native shell destroys the WebView; wait past the replayed speech response, then come back.
      // Output frames every 250 ms for 8 s: when did the closing's sound stop after the action?
      const series = [];
      const began = Date.now();
      while (Date.now() - began < 8000) { series.push({ms: Date.now() - actedAt, frames: W.audioFlinger().framesWritten[0] || 0}); await sleep(250); }
      let lastIncreaseMs = null;
      for (let i = 1; i < series.length; i++) if (series[i].frames > series[i - 1].frames) lastIncreaseMs = series[i].ms;
      row.outputAfterAction = {lastFrameIncreaseMs: lastIncreaseMs, samples: series.length, quietTailMs: lastIncreaseMs === null ? series.at(-1).ms : series.at(-1).ms - lastIncreaseMs};
      row.pageAfterAction = await page.evaluate(() => ({stages: window.__timeline.map(e => e.stage).slice(-6), phase: document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase') || null, url: location.pathname})).catch(error => ({gone: String(error).slice(0, 80)}));
      row.webViewProcessAfterAction = (() => { try { return W.shell('pidof', W.pkg); } catch { return ''; } })();
      await sleep(Math.max(0, (options.waitMs || 35000) - 8000));
      if (options.action === 'drive') await W.setSpeed(0);
      session = await W.attach();
      page = session.page;
      await page.evaluate(PAGE_SCRIPT).catch(() => {});
      await sleep(3000);
      row.afterReturn = {plays: await page.evaluate(() => window.__plays).catch(() => null), timeline: await page.evaluate(() => window.__timeline.map(e => e.stage)).catch(() => null), url: page.url()};
      row.requests = plan.requests.filter(q => q.id === options.name);
      const closingPlays = (row.afterReturn.plays || []).filter(p => !p.guidance);
      check(`${options.name}: ${options.action} stops the closing's sound within 4 s and nothing of it plays later, also in the returned app`,
        (row.outputAfterAction.lastFrameIncreaseMs ?? 0) <= 4000 && row.outputAfterAction.quietTailMs >= 3500 && closingPlays.length === 0 && !(row.afterReturn.timeline || []).some(stage => stage.startsWith('closing-')),
        {outputAfterAction: row.outputAfterAction, pageAfterAction: row.pageAfterAction, afterReturn: row.afterReturn});
      W.shot(out, options.name + '-after');
      await ensure(page);
      r.cases.push(row);
      return session;
    }
    const after = await page.evaluate(() => performance.now());
    if (options.thenNewConversation) {
      // Start a new conversation at once (it only listens, so it plays nothing itself). The cancelled closing's
      // speech response arrives during it and must not play.
      await page.waitForFunction(() => ['ready', 'completed', 'error'].includes(document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase')), null, {timeout: 10000}).catch(() => {});
      plan.id = options.name + '-next';
      const dialog = page.getByRole('dialog');
      if (await dialog.count()) await dialog.getByRole('button', {name: tr('Tamam'), exact: true}).click().catch(() => {});
      const start = page.getByRole('button', {name: tr('Görüşmeyi Başlat'), exact: true});
      row.newConversationStarted = await start.count() && await start.isEnabled() ? (await start.click(), true) : false;
    }
    await sleep(options.waitMs || 35000);
    const events = await page.evaluate(() => window.__timeline);
    row.metrics = metrics(events, t0);
    row.stagesAfterAction = events.filter(e => e.atMs >= after).map(e => e.stage);
    row.playsAfterAction = await page.evaluate(t => window.__plays.filter(p => p.atMs > t), after);
    row.mixerAfter = await mixerDelta();
    row.phase = await page.locator('[data-conversation-phase]').getAttribute('data-conversation-phase', {timeout: 2000}).catch(() => 'panel-not-shown');
    row.notice = await page.evaluate(() => [...document.querySelectorAll('[role=status],[role=alert]')].map(n => n.textContent).join(' | ').slice(0, 300));
    row.requests = plan.requests.filter(q => q.id === options.name);
    row.lateSpeechResponses = row.requests.filter(q => q.kind === 'tts-answered' && q.at > actedAt).length;
    const closingPlaysAfter = row.playsAfterAction.filter(p => !p.guidance);
    if (options.action === 'language') {
      check(`${options.name}: the closing continues to its end in the session language`, row.metrics.summaryComplete !== null, row.metrics);
      W.shot(out, options.name); r.cases.push(row); return session;
    }
    check(`${options.name}: ${options.action} at ${options.at} stops the closing and no later closing audio starts${options.thenNewConversation ? ' (new conversation running)' : ''}`,
      closingPlaysAfter.length === 0 && row.metrics.summaryComplete === null && !row.stagesAfterAction.some(s => /closing-(summary-audio-start|summary-playing|[ABC]-playing)/.test(s)) && row.mixerAfter.framesDelta === 0,
      {playsAfterAction: row.playsAfterAction, stagesAfterAction: row.stagesAfterAction, lateSpeechResponses: row.lateSpeechResponses, mixer: row.mixerAfter, phase: row.phase});
    if (options.thenNewConversation) {
      const finish2 = page.getByRole('button', {name: tr('Görüşmeyi Bitir'), exact: true});
      if (await finish2.count() && await finish2.isEnabled()) await finish2.click().catch(() => {});
      await page.waitForTimeout(1500);
    }
    if (options.action === 'mute') await page.getByRole('button', {name: tr('Seslendirmeyi aç'), exact: true}).click().catch(() => {});
    W.shot(out, options.name);
    r.cases.push(row);
    return session;
  }
  // Complete closing: wait for its end, sampling the mixer while the personal summary plays.
  await waitStage(page, 'closing-summary-audio-start', 120000).catch(() => {});
  row.mixerDuringSummary = await mixerDelta(1000);
  row.focusDuringSummary = focusOwners();
  await page.waitForFunction(() => document.querySelector('[data-conversation-phase]')?.getAttribute('data-conversation-phase') === 'completed', null, {timeout: 120000});
  await page.waitForTimeout(500);
  const events = await page.evaluate(() => window.__timeline);
  row.metrics = metrics(events, t0);
  row.plays = await page.evaluate(() => window.__plays.length);
  row.notice = await page.evaluate(() => [...document.querySelectorAll('[role=status],[role=alert]')].map(n => n.textContent).join(' | ').slice(0, 300));
  row.requests = plan.requests.filter(q => q.id === options.name);
  const m = row.metrics;
  check(`${options.name}: A, B, C and the personal summary played in order without overlap`, m.aPlaying !== null && m.aEnded < m.bPlaying && m.bEnded < m.cPlaying && m.cEnded <= m.summaryPlaying && m.summaryComplete !== null, m);
  check(`${options.name}: no extra tap needed during the closing (one shared, gesture-unlocked element)`, m.gestureRequired.length === 0, m.gestureRequired);
  check(`${options.name}: Android mixer writes frames during A and during the summary`, row.mixerDuringA.framesDelta > 0 && row.mixerDuringSummary.framesDelta > 0, {a: row.mixerDuringA, summary: row.mixerDuringSummary});
  W.shot(out, options.name);
  const dialog = page.getByRole('dialog');
  if (await dialog.count()) await dialog.getByRole('button', {name: tr('Tamam'), exact: true}).click().catch(() => {});
  r.cases.push(row);
  return session;
}

async function assetParity(page, check, r) {
  const manifest = JSON.parse(fs.readFileSync(path.join(repository, 'apps/vehicle-app/public/audio/mental/closing-abc/v1/manifest.json'), 'utf8'));
  const urls = manifest.entries.map(e => ({url: e.audioPath, sha256: e.sha256}));
  const seen = await page.evaluate(async list => {
    const out = [];
    for (const item of list) {
      const response = await fetch(item.url, {cache: 'no-store'});
      const bytes = await response.arrayBuffer();
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
      out.push({url: item.url, status: response.status, bytes: bytes.byteLength, sha256: digest});
    }
    return out;
  }, urls);
  const mismatched = seen.filter((s, i) => s.status !== 200 || s.sha256 !== urls[i].sha256);
  r.assetParity = {count: seen.length, mismatched, totalBytes: seen.reduce((a, s) => a + s.bytes, 0)};
  check('All 45 committed closing recordings reach the AAOS WebView byte-identical to the manifest', seen.length === 45 && mismatched.length === 0, r.assetParity);
}

const CASES = [
  {name: 'tr-complete-cold', language: 'tr', start: 'cold', conversation: 1},
  {name: 'en-complete-warm', language: 'en', start: 'warm', conversation: 1},
  {name: 'de-complete-warm-real-tap', language: 'de', start: 'warm', conversation: 1, realTap: true},
  {name: 'tr-cancel-during-B-then-new', language: 'tr', action: 'cancel', at: 'closing-B-playing', thenNewConversation: true},
  {name: 'en-mute-during-C', language: 'en', action: 'mute', at: 'closing-C-playing'},
  {name: 'de-consent-revoked-during-A', language: 'de', action: 'consent', at: 'closing-A-playing'},
  {name: 'tr-language-locked-during-B', language: 'tr', action: 'language', at: 'closing-B-playing'},
  {name: 'en-cancel-during-summary', language: 'en', action: 'cancel', at: 'closing-summary-audio-start', waitMs: 15000},
  {name: 'tr-drive-during-C', language: 'tr', action: 'drive', at: 'closing-C-playing'},
  {name: 'de-background-during-B', language: 'de', action: 'background', at: 'closing-B-playing'},
];

(async () => {
  const {out, r, check, save} = W.report('mental-closing');
  r.testMode = 'Real AAOS WebView, APK, native gates and audio path; branch frontend served to the WebView origin by CDP interception; recognizer scripted; reply, analysis and female-calm-v1 speech replayed from the WEB real-path recordings.';
  r.replay = {runId: replay.runId, file: 'realpath.json'};
  r.buildOrigin = BUILD;
  r.cases = [];
  const only = (process.env.CLOSING_ONLY || '').split(',').filter(Boolean);
  let session;
  try {
    session = await W.attach();
    await W.setSpeed(0);
    await ensure(session.page);
    await W.startClean(session.page);
    await assetParity(session.page, check, r);
    save();
    for (const c of CASES.filter(c => !only.length || only.includes(c.name))) {
      try {
        session = await closing(session, c.language, c, check, out, r);
      } catch (error) {
        r.errors.push({case: c.name, error: String(error && error.stack || error).slice(0, 600)});
        check(`${c.name}: completed without harness error`, false, String(error).slice(0, 300));
        try { await W.setSpeed(0); session = await W.attach(); } catch {}
      }
      save();
    }
    r.status = r.checks.every(c => c.pass) && !r.errors.length ? 'PASS' : 'FAIL';
  } catch (error) {
    r.errors.push(String(error && error.stack || error).slice(0, 800));
    r.status = 'FAIL';
  } finally {
    try { await W.setSpeed(0); } catch {}
    r.finished = new Date().toISOString();
    save();
    await session?.browser.close().catch(() => {});
    console.log(JSON.stringify({status: r.status, out, checks: r.checks.length, failed: r.checks.filter(c => !c.pass).map(c => c.what)}));
    // A CDP connection to the WebView can keep the process alive after close; the report is saved.
    setTimeout(() => process.exit(0), 2000);
  }
})();
