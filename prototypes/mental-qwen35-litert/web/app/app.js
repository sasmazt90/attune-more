// KOL B prototype page: VAD -> Whisper -> session core (product crisis check, Qwen, checks) -> Piper.
// ?llm=web (LiteRT-LM JS, WebGPU) | android (native bridge in the prototype APK) | host (evaluation only, NOT on-device)
import {createPiper, createWhisper, createVad, decodeTo16k, wavBytes} from '../dist/speech.js';
import {MentalSession} from '../core/session.js';
import {BRIDGE} from '../core/prompts.js';
import {makeCrisis} from '../adapters/crisis.js';
import {createPyValidator} from '../adapters/pyValidator.js';

const q = new URLSearchParams(location.search);
const $ = id => document.getElementById(id);
const VOICES = {tr: 'tr_TR-dfki-medium', en: 'en_US-kristin-medium', de: 'de_DE-kerstin-medium'};
const T = window.__trace = [];                          // content-free stage timings (also used by tests)
const mark = (stage, extra = {}) => T.push({stage, t: Math.round(performance.now()), ...extra});
const log = s => { $('log').textContent += s + '\n'; };
let parked = $('parkSim').checked, session = null, vad = null, speech = null, whisper = null, busy = false, lang = 'tr';
window.__attuneParked = p => { parked = !!p; $('parkSim').checked = parked; if (!parked) stopAll('Sürüş: görüşme güvenle kapatıldı.'); };
window.__attuneBackground = () => stopAll('Uygulama arka plana alındı: görüşme durduruldu.');
$('parkSim').onchange = e => window.__attuneParked(e.target.checked);
$('consent').onchange = e => { if (!e.target.checked) stopAll('Onay geri çekildi: görüşme ve ses durduruldu.'); };
$('mute').onchange = e => { if (e.target.checked) speech?.stop(); };
document.addEventListener('visibilitychange', () => { if (document.hidden) window.__attuneBackground(); });
const gates = () => parked && $('consent').checked && !document.hidden;

async function makeLlm() {
  const kind = q.get('llm') || 'web';
  $('llmBadge').textContent = {web: 'LLM: tarayıcı içi (LiteRT-LM JS, WebGPU)', android: 'LLM: cihaz içi (LiteRT-LM Android, CPU)', host: 'LLM: HOST — cihaz içi DEĞİL (yalnız değerlendirme)'}[kind];
  if (kind === 'android') return (await import('../adapters/androidLlm.js')).androidLlm;
  if (kind === 'host') return (await import('../adapters/hostLlm.js')).hostLlm;
  return (await import('../adapters/litertWebLlm.js')).makeLitertWebLlm({backend: q.get('backend') || 'GPU'});
}

// One <audio> element for every output; a late result of a superseded turn can never start playing.
function makeSpeech(piper) {
  const audio = new Audio(); let url = null, cache = new Map();
  const stop = () => { audio.pause(); audio.removeAttribute('src'); audio.load(); if (url) URL.revokeObjectURL(url); url = null; };
  const prepare = async text => { mark('tts-start'); const r = cache.get(text) || await piper.synthesize(text); mark('tts-ready', {audioMs: Math.round(r.audioMs)}); return r; };
  const play = (clip, {isCurrent}) => new Promise(resolve => {
    if (!isCurrent() || $('mute').checked) { resolve({played: false}); return; }
    stop(); url = URL.createObjectURL(new Blob([wavBytes(clip.pcm, clip.sampleRate)], {type: 'audio/wav'}));
    audio.onplaying = () => mark('playing'); audio.onended = () => { mark('ended'); resolve({played: true}); };
    audio.onerror = () => resolve({played: false, error: true}); audio.src = url;
    audio.play().catch(() => resolve({played: false, blocked: true}));
  });
  return {stop, prepare, play, async speak(text, o) { const c = await prepare(text); return o.isCurrent() ? play(c, o) : {played: false}; },
    async preload(text) { cache.set(text, await piper.synthesize(text)); }};
}

async function onUtterance(audio16k) {
  if (!session || busy || !gates()) return;
  busy = true; await vad?.pause(); mark('vad-end', {samples: audio16k.length});
  try {
    const stt = await whisper.transcribe(audio16k, lang); mark('stt-done', {sttMs: Math.round(stt.ms)});
    if (!stt.text) return;
    log('Sen: ' + stt.text);
    const r = await session.userTurn(stt.text, {moving: !parked});
    mark('turn-done', {source: r.source, modelMs: r.modelMs, firstTokenMs: r.firstTokenMs, crisis: !!r.crisis, discarded: !!r.discarded});
    if (r.spoken && !r.discarded) log('Asistan: ' + r.spoken);
    if (r.crisis) { $('state').textContent = 'Normal görüşme durduruldu.'; return; }
  } finally { busy = false; if (session?.active && gates()) await vad?.start(); }
}

async function start(streamOverride) {
  if (!gates()) { $('state').textContent = 'Park halinde ve onay verilmiş olmalı.'; return; }
  lang = $('lang').value; $('lang').disabled = true; $('state').textContent = 'Yükleniyor…'; mark('start');
  const messages = await (await fetch('/generated/product/shared/localization/messages.json')).json();
  const [llm, piper, w, validator] = await Promise.all([makeLlm(), createPiper({voice: VOICES[lang]}), whisper || createWhisper({model: q.get('stt') || 'onnx-community/whisper-small'}),
    q.get('validator') === 'host' ? import('../adapters/hostLlm.js').then(m => ({validate: m.hostValidate})) : createPyValidator()]);
  whisper = w; speech = makeSpeech(piper); await speech.preload(BRIDGE[lang]);
  session = new MentalSession({lang, llm, crisis: makeCrisis(lang, messages), validate: validator.validate, speech, gates});
  await session.start(); mark('engine-ready');
  vad = await createVad({getStream: streamOverride || (() => navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}})),
    audioContext: window.__testAudioContext, keepStream: !!streamOverride, redemptionMs: Number(q.get('redemption') || 1100), onSpeechEnd: onUtterance,
    onSpeechStart: () => mark('vad-start')});
  await vad.start(); $('state').textContent = 'Dinliyor'; mark('listening');
}

async function finish() {
  if (!session) return;
  await vad?.pause(); $('state').textContent = 'Kapanış'; mark('closing-trigger');
  const r = await session.finish(); mark('closing-done');
  window.__closing = r;
  if (r.line) log('Kişisel kapanış: ' + (r.line.accepted || '(doğrulamadan geçmedi — kişisel cümle söylenmedi)'));
  renderSummary(r.summary); $('state').textContent = 'Tamamlandı'; $('lang').disabled = false; await vad?.destroy(); vad = null; session = null;
}
function renderSummary(s) {
  const el = $('summary'); el.innerHTML = '';
  if (!s) { el.textContent = 'Özet yok.'; return; }
  for (const g of s.groups) {
    const d = document.createElement('div'); d.className = 'grp';
    d.innerHTML = `<b></b> <small>(${g.quotes.length} mesaj)</small><ul></ul>`; d.querySelector('b').textContent = g.label;
    for (const x of g.quotes) { const li = document.createElement('li'); li.textContent = '“' + x.text + '”'; d.querySelector('ul').appendChild(li); }
    el.appendChild(d);
  }
  if (s.replaced.length) { const p = document.createElement('p'); p.textContent = 'Sonradan düzelttiğin ifade özete alınmadı: ' + s.replaced.map(r => '“' + r.text + '”').join(', '); el.appendChild(p); }
}
async function stopAll(reason) {
  if (!session) return;
  speech?.stop(); await vad?.destroy(); vad = null;
  await session.end('stop'); session = null; busy = false; $('lang').disabled = false; $('state').textContent = reason; mark('stopped', {reason});
}
$('start').onclick = () => start(); $('end').onclick = () => finish(); $('cancel').onclick = () => stopAll('Görüşme iptal edildi.');
window.__app = {start, finish, stopAll, getSession: () => session, onUtterance, decodeTo16k};
if (q.get('autotest')) {
  const corpus = await (await fetch('/eval-corpus/conversations.json')).json();
  const conversation = corpus.conversations.find(c => c.id === q.get('autotest'));
  const {run} = await import('../bench/chain-driver.js');
  run({conversation, app: window.__app});
}
