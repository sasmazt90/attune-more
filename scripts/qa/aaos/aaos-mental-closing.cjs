'use strict';
// Closing A/B/C bridge in the real AAOS WebView (cloudDemo APK, AAOS 15 emulator on the AWS AAOS host).
//
// Real: Android runtime and native gates (PARK/driving, background destroy), the WebView and its media pipeline with
// setMediaPlaybackRequiresUserGesture(true), Android's audio mixer, player states and focus, this branch's frontend code
// and the 45 committed WAVs. The product web-aaos service is not changed: every non-API request of the WebView origin is
// answered, through CDP interception, by a build of this branch on the AAOS host (CLOSING_BUILD_ORIGIN). Vehicle state
// requests go to the real backend unchanged, so web and native gates see the same state.
// Replayed (labelled, never upgraded): the recognizer (Android WebView has none), the conversation reply, the analysis
// (WEB real-path recordings in CLOSING_REPLAY_DIR, delivered after their measured delays) and, unless CLOSING_TTS=product,
// the female-calm-v1 speech. With CLOSING_TTS=product the closing speech is generated live through the existing product
// chain (WebView -> AAOS Caddy -> WEB Caddy mTLS -> web-aaos -> api-aaos -> resident worker); nothing is reconfigured.
//
// Instrumentation (no conversation text): page events (timing stages, vehicle reads, media play/pause/ended with element
// ids and short stacks, Audio creation, stream focus, guidance events) streamed to the host with guest timestamps and a
// measured guest/host clock offset; Android player states of the app process (dumpsys audio) and primary-output frame
// counters (dumpsys media.audio_flinger) sampled asynchronously; logcat lines of the audio and WebView stack.
//
// Usage: node scripts/qa/aaos/aaos-mental-closing.cjs   (env: ATTUNE_QA_AAOS_CONFIG, ATTUNE_QA_OUT, ATTUNE_QA_PLAYWRIGHT,
//        CLOSING_BUILD_ORIGIN, CLOSING_REPLAY_DIR, CLOSING_TTS=replay|product, CLOSING_RUN_LABEL, CLOSING_ONLY=case,case)
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const W = require('./webview.cjs');

const BUILD = process.env.CLOSING_BUILD_ORIGIN || 'http://127.0.0.1:3100';
const TTS_MODE = process.env.CLOSING_TTS === 'product' ? 'product' : 'replay';
const CONFIG = JSON.parse(fs.readFileSync(process.env.ATTUNE_QA_AAOS_CONFIG, 'utf8').replace(/^\uFEFF/, ''));
const {execFile} = require('node:child_process');
// Asynchronous adb so that page events keep arriving (with host receipt times) while the device is sampled.
const adbAsync = (...args) => new Promise(ok => execFile(CONFIG.adb, ['-s', CONFIG.serial, ...args], {encoding: 'utf8', timeout: 20000, maxBuffer: 32 * 1024 * 1024}, (error, stdout) => ok(error ? '' : stdout)));
const REPLAY = process.env.CLOSING_REPLAY_DIR;
const replay = JSON.parse(fs.readFileSync(path.join(REPLAY, 'realpath.json'), 'utf8'));
const LOCALE = {tr: 'tr-TR', en: 'en-US', de: 'de-DE'};
const REPLY = {tr: 'Anlıyorum. Bunu paylaştığınız için teşekkür ederim.', en: 'I understand. Thank you for sharing that.', de: 'Ich verstehe. Danke, dass Sie das teilen.'};
const sleep = ms => new Promise(ok => setTimeout(ok, ms));
const repository = path.resolve(__dirname, '../../..');

// Scripted recognizer (as in aaos-mental.cjs), the app's content-free timing events and media/focus/guidance/vehicle
// instrumentation. Every event is also streamed to the host as a console message ("__qa {...}").
const PAGE_SCRIPT = `(()=>{if(window.__closingQa)return;window.__closingQa=true;window.__qaUtterances=[];window.__timeline=[];window.__plays=[];
 const emit=(kind,data)=>{try{console.debug('__qa '+JSON.stringify(Object.assign({kind,at:Date.now(),pm:performance.now()},data)));}catch(e){}};
 addEventListener('attune-speech-timing',e=>{window.__timeline.push({stage:e.detail.stage,atMs:e.detail.atMs});emit('stage',{stage:e.detail.stage});});
 let seq=0;const ids=new WeakMap();const id=el=>{if(!ids.has(el))ids.set(el,++seq);return ids.get(el);};
 const stack=()=>String(new Error().stack||'').split('\\n').slice(2,7).map(l=>l.trim().replace(/https?:\\/\\/[^/]+/,'')).join(' | ').slice(0,600);
 const watched=new WeakSet();
 const watch=el=>{if(watched.has(el))return;watched.add(el);for(const t of ['playing','pause','ended','emptied','error'])el.addEventListener(t,()=>emit('media',{type:t,el:id(el),guidance:el.dataset.guidanceId||null,recording:el.dataset.recordingId||null}));};
 const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){watch(this);const entry={atMs:performance.now(),src:String(this.currentSrc||this.src||'').slice(0,12),guidance:this.dataset&&this.dataset.guidanceId||null,recording:this.dataset&&this.dataset.recordingId||null,el:id(this),stack:stack()};window.__plays.push(entry);emit('play',entry);const p=play.apply(this,arguments);if(p&&p.then)p.then(()=>emit('play-ok',{el:entry.el}),err=>emit('play-rejected',{el:entry.el,name:err&&err.name}));return p;};
 const pause=HTMLMediaElement.prototype.pause;HTMLMediaElement.prototype.pause=function(){if(!this.paused)emit('pause-call',{el:id(this),stack:stack()});return pause.apply(this,arguments);};
 const NativeAudio=window.Audio;const QaAudio=function(...a){const el=new NativeAudio(...a);emit('audio-created',{el:id(el),stack:stack()});return el;};QaAudio.prototype=NativeAudio.prototype;window.Audio=QaAudio;
 addEventListener('attune-guidance-event',e=>emit('guidance',{id:e.detail&&e.detail.id,event:e.detail&&e.detail.event}));
 addEventListener('attune-voice-unavailable',()=>emit('voice-unavailable',{}));
 const owners=new WeakMap();let oseq=0;addEventListener('attune-stream-focus',e=>{if(!e.owner)return;if(!owners.has(e.owner))owners.set(e.owner,++oseq);emit('focus',{owner:owners.get(e.owner),active:!!e.active});});
 document.addEventListener('visibilitychange',()=>emit('visibility',{hidden:document.hidden}));addEventListener('pagehide',()=>emit('pagehide',{}));
 const nativeFetch=window.fetch;window.fetch=function(input,init){const url=String(input&&input.url||input);const p=nativeFetch.apply(this,arguments);if(url.includes('/api/vehicle/state'))p.then(r=>r.clone().json()).then(d=>emit('vehicle',{moving:d.vehicleMoving,parked:d.vehicleParked,speed:d.currentSpeed})).catch(()=>{});return p;};
 class QaRecognition{constructor(){this.lang='';this.continuous=false;this.interimResults=false;this.maxAlternatives=1;}
  start(){this.timer=setTimeout(()=>{this.onstart&&this.onstart();this.timer=setTimeout(()=>{const text=window.__qaUtterances.shift();
   if(text){const item=Object.assign([{transcript:text,confidence:.9}],{isFinal:true});this.onresult&&this.onresult({resultIndex:0,results:[item]});}
   else if(this.onerror)this.onerror({error:'no-speech'});this.onend&&this.onend();},500);},40);}
  abort(){clearTimeout(this.timer);}stop(){clearTimeout(this.timer);}}
 window.SpeechRecognition=QaRecognition;window.webkitSpeechRecognition=QaRecognition;})();`;

// Host-side event log: every "__qa" console message with its host receipt time.
const pageEvents = [];
function listen(page) {
  page.on('console', message => {
    const text = message.text();
    if (!text.startsWith('__qa ')) return;
    try { pageEvents.push({host: Date.now(), ...JSON.parse(text.slice(5))}); } catch {}
  });
  page.on('close', () => pageEvents.push({host: Date.now(), kind: 'page-closed'}));
}
async function clockOffset(page) {
  const h0 = Date.now(), guest = await page.evaluate(() => Date.now()), h1 = Date.now();
  return {offsetMs: Math.round(guest - (h0 + h1) / 2), uncertaintyMs: Math.round((h1 - h0) / 2)};
}

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
        if (TTS_MODE === 'product' && body.speakerProfile === 'female-calm-v1') {
          // Live speech through the existing product AAOS chain; the response headers are recorded by the page listener.
          plan.requests.push({kind: 'tts-live', id, closing: true, at: Date.now()});
          return await route.continue();
        }
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
  listen(page);
  page.on('response', response => {
    if (!response.url().includes('/api/mental-neural-speech')) return;
    const h = response.headers();
    plan.requests.push({kind: 'tts-response', id: plan.id, at: Date.now(), status: response.status(), start: h['x-tts-start'] || null, serverSeconds: h['x-tts-seconds'] || null,
      serverTiming: h['server-timing'] || null, speaker: h['x-tts-speaker-profile'] || null});
  });
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

// Real Android touches (input tap). The screen-to-page mapping is measured, not assumed: two probe taps inside the WebView
// are caught by a capture-phase listener that swallows them (no app handler runs), and their page coordinates give the
// scale and offset per axis.
function screenSize() {
  const m = W.shell('wm', 'size').match(/(\d+)x(\d+)/g);
  const [w, h] = (m.at(-1) || '1280x800').split('x').map(Number);
  return {w, h};
}
function webViewBounds() {
  try {
    W.shell('uiautomator', 'dump', '/sdcard/attune-ui.xml');
    const xml = W.shell('cat', '/sdcard/attune-ui.xml');
    W.shell('rm', '-f', '/sdcard/attune-ui.xml');
    const m = xml.match(/class="android\.webkit\.WebView"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);
    if (m) return {x: Number(m[1]), y: Number(m[2]), right: Number(m[3]), bottom: Number(m[4]), source: 'uiautomator'};
  } catch {}
  const {w, h} = screenSize();
  return {x: 0, y: 0, right: w, bottom: h, source: 'wm size'};
}
let tapMap = null;
async function calibrateTap(page) {
  await page.evaluate(() => {
    window.__tapProbe = [];
    if (!window.__tapProbeInstalled) {
      window.__tapProbeInstalled = true;
      const handler = e => {
        if (!window.__tapCalibrating) return;
        const t = e.changedTouches && e.changedTouches[0];
        window.__tapProbe.push({type: e.type, x: t ? t.clientX : e.clientX, y: t ? t.clientY : e.clientY});
        e.preventDefault(); e.stopImmediatePropagation();
      };
      for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'touchstart', 'touchend']) addEventListener(type, handler, {capture: true, passive: false});
    }
    window.__tapCalibrating = true;
  });
  const view = webViewBounds(), got = [];
  const points = [[0.35, 0.3], [0.65, 0.7]].map(([fx, fy]) => [Math.round(view.x + (view.right - view.x) * fx), Math.round(view.y + (view.bottom - view.y) * fy)]);
  for (const [x, y] of points) {
    await page.evaluate(() => { window.__tapProbe = []; });
    W.shell('input', 'tap', String(x), String(y));
    await sleep(800);
    const seen = await page.evaluate(() => window.__tapProbe.find(e => e.type === 'pointerdown') || window.__tapProbe.find(e => e.type === 'touchstart') || window.__tapProbe[0] || null);
    got.push({screen: [x, y], page: seen});
  }
  await page.evaluate(() => { window.__tapCalibrating = false; });
  if (got.some(g => !g.page) || got[1].page.x === got[0].page.x || got[1].page.y === got[0].page.y) return {ok: false, view, got};
  const sx = (got[1].screen[0] - got[0].screen[0]) / (got[1].page.x - got[0].page.x), sy = (got[1].screen[1] - got[0].screen[1]) / (got[1].page.y - got[0].page.y);
  return {ok: true, view, got, sx, sy, ox: got[0].screen[0] - got[0].page.x * sx, oy: got[0].screen[1] - got[0].page.y * sy,
    dpr: await page.evaluate(() => devicePixelRatio)};
}
async function realTap(page, locator) {
  tapMap = await calibrateTap(page);
  if (!tapMap.ok) return {kind: 'adb input tap', calibrated: false, calibration: tapMap};
  const box = await locator.boundingBox();
  const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
  const x = Math.round(tapMap.ox + cx * tapMap.sx), y = Math.round(tapMap.oy + cy * tapMap.sy);
  W.shell('input', 'tap', String(x), String(y));
  return {kind: 'adb input tap', calibrated: true, x, y, target: {x: Math.round(cx), y: Math.round(cy)}, calibration: tapMap};
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

// Android side, sampled asynchronously: the app process's player states (AudioPlaybackConfiguration) and the primary
// output's frame counter. A player leaving 'started' is the end of the app's output; the frame counter keeps rising for
// the mixer's standby time afterwards (silence), which is reported separately and is not counted as audible output.
const appPid = () => { try { return W.shell('pidof', W.pkg).split(/\s+/)[0]; } catch { return ''; } };
async function sampleOutput(pid, ms) {
  const series = [], began = Date.now();
  for (let i = 0; Date.now() - began < ms; i++) {
    const t = Date.now(), audio = await adbAsync('shell', 'dumpsys', 'audio');
    const players = [...audio.matchAll(/AudioPlaybackConfiguration piid:(\d+)[^\n]*?u\/pid:\d+\/(\d+) state:(\w+)/g)].filter(m => m[2] === String(pid)).map(m => ({piid: m[1], state: m[3]}));
    const row = {host: t, dumpMs: Date.now() - t, started: players.filter(x => x.state === 'started').map(x => x.piid), states: players.map(x => x.piid + ':' + x.state)};
    if (i % 2 === 0) { const f = await adbAsync('shell', 'dumpsys', 'media.audio_flinger'); const m = f.match(/Frames written:\s*(\d+)/); row.frames = m ? Number(m[1]) : null; }
    series.push(row);
  }
  return series;
}
async function logcatSince(guestEpochMs) {
  const raw = await adbAsync('logcat', '-d', '-v', 'epoch', '-t', '1500');
  return raw.split('\n').filter(line => { const t = Number(line.trim().split(/\s+/)[0]); return t * 1000 >= guestEpochMs - 500; })
    .filter(line => /AudioTrack|AudioFlinger|MediaFocusControl|AudioService|PlaybackActivity|chromium|cr_|WebView|ActivityTaskManager|attune/i.test(line))
    .slice(0, 60).map(line => line.replace(/\s+/g, ' ').slice(0, 170));
}
// Times after the action, in ms on the host clock (guest event times converted with the measured offset).
function stopStages(actedAt, ackAt, events, series, offset) {
  const after = events.filter(e => e.kind !== 'page-closed' && e.at - offset.offsetMs >= actedAt - 50);
  const rel = e => e ? Math.round((e.kind === 'page-closed' ? e.host : e.at - offset.offsetMs) - actedAt) : null;
  let wasStarted = false, playerStopped = null, lastStarted = null;
  for (const row of series) { if (row.started.length) { wasStarted = true; lastStarted = row.host; } else if (playerStopped === null && (wasStarted || row === series[0])) playerStopped = row.host; }
  if (lastStarted !== null && playerStopped !== null && playerStopped < lastStarted) playerStopped = series.find(row => row.host > lastStarted && !row.started.length)?.host ?? null;
  const frames = series.filter(row => row.frames !== null && row.frames !== undefined);
  let lastIncrease = null;
  for (let i = 1; i < frames.length; i++) if (frames[i].frames > frames[i - 1].frames) lastIncrease = frames[i].host;
  const ms = t => t === null ? null : Math.round(t - actedAt);
  return {backendAcknowledgedMs: ackAt ? Math.round(ackAt - actedAt) : null,
    webSawMovingMs: rel(after.find(e => e.kind === 'vehicle' && e.moving)),
    closingAbortStageMs: rel(after.find(e => e.kind === 'stage' && /^(cleanup|closing-.*(cancel|abort|stopped))/.test(e.stage))),
    mediaPauseCallMs: rel(after.find(e => e.kind === 'pause-call')),
    mediaPausedEventMs: rel(after.find(e => e.kind === 'media' && ['pause', 'emptied'].includes(e.type))),
    hiddenMs: rel(after.find(e => e.kind === 'visibility' && e.hidden)),
    pageClosedMs: rel(events.find(e => e.kind === 'page-closed' && e.host >= actedAt)),
    appPlayerStoppedMs: ms(playerStopped), appPlayerWasStartedAtAction: series[0] ? series[0].started.length > 0 : null,
    lastFrameIncreaseMs: ms(lastIncrease), mixerTailAfterPlayerStopMs: lastIncrease !== null && playerStopped !== null ? Math.round(lastIncrease - playerStopped) : null,
    samplingMedianMs: series.length > 1 ? Math.round([...series.slice(1).map((row, i) => row.host - series[i].host)].sort((a, b) => a - b)[Math.floor((series.length - 1) / 2)]) : null,
    offset};
}
// Proposed criterion, fixed before these measurements (no repository or OEM requirement exists): the app's player leaves
// 'started' within 1000 ms of the stop condition (backend acknowledgement of driving, the key event, or the UI action).
const STOP_CRITERION_MS = 1000;

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
  const firstEvent = pageEvents.length;
  const tap = options.realTap ? await realTap(page, finish) : (await finish.click(), null);
  const row = {name: options.name, language, action: options.action || null, at: options.at || null, build, run: process.env.CLOSING_RUN_LABEL || null,
    tts: TTS_MODE, finishInput: tap || 'CDP click', turnTaps};
  if (tap) {
    row.realTapStartedClosing = tap.calibrated && await waitStage(page, 'closing-trigger', 6000).then(() => true, () => false);
    check(`${options.name}: a real Android touch (adb input tap, calibrated) on "end conversation" starts the closing`, row.realTapStartedClosing, tap);
    if (!row.realTapStartedClosing) {
      W.shot(out, options.name + '-tap-missed');
      r.cases.push(row);
      throw Error('real tap did not start the closing; the case is not continued with a CDP click');
    }
  }
  await waitStage(page, 'closing-A-playing', 20000).catch(() => {});
  row.mixerDuringA = await mixerDelta(1000);
  row.focusDuringA = focusOwners();
  if (options.action) {
    await waitStage(page, options.at, 90000);
    const actionPm = await page.evaluate(() => performance.now());
    const offset = await clockOffset(page), pid = appPid();
    const sampler = sampleOutput(pid, options.sampleMs || 8000);
    let ackAt = null;
    const actedAt = Date.now();
    if (options.action === 'drive') { await W.setSpeed(75); ackAt = Date.now(); }
    if (options.action === 'background') W.shell('input', 'keyevent', 'KEYCODE_HOME');
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
    row.actedAt = actedAt;
    const series = await sampler;
    if (options.action !== 'language') {
      row.stopStages = stopStages(actedAt, ackAt, pageEvents.slice(firstEvent), series, offset);
      row.playerSeries = series.map(x => ({ms: x.host - actedAt, started: x.started, frames: x.frames ?? null, dumpMs: x.dumpMs}));
      row.logcat = await logcatSince(actedAt + offset.offsetMs);
      const st = row.stopStages, reference = options.action === 'drive' ? st.backendAcknowledgedMs : 0;
      check(`${options.name}: the app's player left 'started' within ${STOP_CRITERION_MS} ms of the stop condition (proposed criterion, measured ${st.appPlayerStoppedMs === null ? 'n/a' : st.appPlayerStoppedMs - reference} ms)`,
        st.appPlayerWasStartedAtAction === true && st.appPlayerStoppedMs !== null && st.appPlayerStoppedMs - reference <= STOP_CRITERION_MS, st);
    }
    if (['drive', 'background'].includes(options.action)) {
      // The native shell destroys the WebView; wait past the replayed speech response, then come back.
      row.webViewProcessAfterAction = appPid();
      await sleep(Math.max(0, (options.waitMs || 35000) - (options.sampleMs || 8000)));
      if (options.action === 'drive') await W.setSpeed(0);
      session = await W.attach();
      page = session.page;
      await ensure(page);
      await page.evaluate(PAGE_SCRIPT).catch(() => {});
      await sleep(3000);
      row.afterReturn = {plays: await page.evaluate(() => window.__plays).catch(() => null), timeline: await page.evaluate(() => window.__timeline.map(e => e.stage)).catch(() => null), url: page.url()};
      row.requests = plan.requests.filter(q => q.id === options.name);
      row.pageEvents = pageEvents.slice(firstEvent).filter(e => e.kind !== 'vehicle' || e.moving);
      const closingPlays = (row.afterReturn.plays || []).filter(x => !x.guidance);
      check(`${options.name}: nothing of the closing plays later, also in the returned app (late speech response included)`,
        closingPlays.length === 0 && !(row.afterReturn.timeline || []).some(stage => stage.startsWith('closing-')), {afterReturn: row.afterReturn, requests: row.requests});
      W.shot(out, options.name + '-after');
      r.cases.push(row);
      return session;
    }
    const after = actionPm;
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
  // After the spoken closing nothing else should speak (the separate 'mental-complete' guidance would be a second
  // completion message in another voice). Watch 12 s more and record every play() with its source.
  const donePm = await page.evaluate(() => performance.now());
  await sleep(12000);
  row.playsAfterCompletion = await page.evaluate(t => window.__plays.filter(x => x.atMs > t), donePm);
  row.guidanceEventsAfterCompletion = pageEvents.slice(firstEvent).filter(e => ['guidance', 'voice-unavailable', 'play-rejected'].includes(e.kind) && e.pm > donePm);
  row.notice = await page.evaluate(() => [...document.querySelectorAll('[role=status],[role=alert]')].map(n => n.textContent).join(' | ').slice(0, 300));
  row.pageEvents = pageEvents.slice(firstEvent).filter(e => !['vehicle', 'stage'].includes(e.kind));
  check(`${options.name}: nothing else plays in the 12 s after the spoken closing (no second completion message)`, row.playsAfterCompletion.length === 0 && !row.guidanceEventsAfterCompletion.some(e => e.kind === 'voice-unavailable'),
    {plays: row.playsAfterCompletion, guidance: row.guidanceEventsAfterCompletion});
  if (TTS_MODE === 'product') row.liveSpeech = plan.requests.filter(q => q.id === options.name && ['tts-live', 'tts-response'].includes(q.kind));
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
  // Complete closings: CDP click and calibrated real Android touch, TR/EN/DE.
  {name: 'tr-complete-cold-cdp', language: 'tr', start: 'cold', conversation: 1},
  {name: 'en-complete-warm-cdp', language: 'en', start: 'warm', conversation: 1},
  {name: 'de-complete-warm-cdp', language: 'de', start: 'warm', conversation: 2},
  {name: 'tr-complete-warm-real-tap', language: 'tr', start: 'warm', conversation: 2, realTap: true},
  {name: 'en-complete-warm-real-tap', language: 'en', start: 'warm', conversation: 2, realTap: true},
  {name: 'de-complete-warm-real-tap', language: 'de', start: 'warm', conversation: 2, realTap: true},
  // Interruptions.
  {name: 'tr-cancel-during-B-then-new', language: 'tr', action: 'cancel', at: 'closing-B-playing', thenNewConversation: true},
  {name: 'en-cancel-during-summary', language: 'en', action: 'cancel', at: 'closing-summary-audio-start', waitMs: 15000},
  {name: 'en-mute-during-C', language: 'en', action: 'mute', at: 'closing-C-playing'},
  {name: 'de-consent-revoked-during-A', language: 'de', action: 'consent', at: 'closing-A-playing'},
  {name: 'tr-language-locked-during-B', language: 'tr', action: 'language', at: 'closing-B-playing', sampleMs: 1000},
  {name: 'tr-drive-during-C', language: 'tr', action: 'drive', at: 'closing-C-playing'},
  {name: 'en-drive-during-summary', language: 'en', action: 'drive', at: 'closing-summary-audio-start'},
  {name: 'de-drive-during-A', language: 'de', action: 'drive', at: 'closing-A-playing'},
  {name: 'de-background-during-B', language: 'de', action: 'background', at: 'closing-B-playing'},
  {name: 'tr-background-during-summary', language: 'tr', action: 'background', at: 'closing-summary-audio-start'},
];

(async () => {
  const {out, r, check, save} = W.report('mental-closing');
  r.testMode = TTS_MODE === 'product'
    ? 'Real AAOS WebView, APK, native gates and audio path; branch frontend served by CDP interception; recognizer scripted; reply and analysis replayed from WEB real-path recordings; closing speech LIVE through the existing product AAOS chain.'
    : 'Real AAOS WebView, APK, native gates and audio path; branch frontend served by CDP interception; recognizer scripted; reply, analysis and female-calm-v1 speech replayed from the WEB real-path recordings.';
  r.ttsMode = TTS_MODE;
  r.runLabel = process.env.CLOSING_RUN_LABEL || null;
  r.standbyTimeProperty = (() => { try { return W.shell('getprop', 'ro.audio.flinger_standbytime_ms') || 'unset (AudioFlinger default)'; } catch { return null; } })();
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
