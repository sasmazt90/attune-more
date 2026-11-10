// Speech benchmarks in the browser (no LLM). Results go to window.__result for the Playwright runner.
import {createPiper, createWhisper, decodeTo16k, createVad, wavBytes} from '../dist/speech.js';
import {createPyValidator} from '../adapters/pyValidator.js';
const q = new URLSearchParams(location.search), mode = q.get('mode');
const R = window.__result = {mode, done: false, items: []};
const out = document.getElementById('out'); const log = s => { out.textContent += s + '\n'; console.log('[bench] ' + s); };
const VOICES = {tr: 'tr_TR-dfki-medium', en: 'en_US-kristin-medium', de: 'de_DE-kerstin-medium'};
const b64 = u8 => { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode(...u8.subarray(i, i + 0x8000)); return btoa(s); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function tts() {
  const items = JSON.parse(decodeURIComponent(q.get('items') || '[]'));  // [{lang, id, text}]
  const voices = {};
  for (const it of items) {
    voices[it.lang] ||= await createPiper({voice: VOICES[it.lang]});
    const v = voices[it.lang];
    const first = await v.synthesize(it.text);
    const again = await v.synthesize(it.text);   // warm repeat
    const wav = wavBytes(first.pcm, first.sampleRate);
    R.items.push({...it, voice: v.voice, voiceLoadMs: Math.round(v.loadMs), inputNames: v.inputNames, phonemes: first.phonemes,
      idsMatchPhonemizer: JSON.stringify(first.idsUsed) === JSON.stringify(first.idsFromPhonemizer),
      firstMs: Math.round(first.totalMs), phonemizeMs: Math.round(first.phonemizeMs), warmMs: Math.round(again.totalMs), audioMs: Math.round(first.audioMs), wavBase64: b64(wav)});
    log(`${it.id}: ${Math.round(first.totalMs)} ms (warm ${Math.round(again.totalMs)}) for ${Math.round(first.audioMs)} ms audio`);
  }
}

async function stt() {
  const manifest = await (await fetch('/models/fleurs-eval/manifest.json')).json();
  const langs = (q.get('langs') || 'tr,en,de').split(',');
  const w = await createWhisper({model: q.get('model') || 'onnx-community/whisper-small'});
  R.model = w.model; R.loadMs = Math.round(w.loadMs);
  for (const m of manifest.filter(m => langs.includes(m.lang))) {
    const audio = await decodeTo16k(await (await fetch('/models/' + m.file)).arrayBuffer());
    const r = await w.transcribe(audio, m.lang);
    R.items.push({lang: m.lang, index: m.index, file: m.file, reference: m.transcription, hypothesis: r.text, ms: Math.round(r.ms), audioS: m.durationS});
    log(`${m.lang}#${m.index} ${Math.round(r.ms)} ms: ${r.text}`);
  }
}

// Plays PCM through a MediaStream into the real-time VAD and records its events on one clock.
async function playIntoVad(ctx, pcm, sampleRate, redemptionMs) {
  const dest = ctx.createMediaStreamDestination();
  const ev = [];
  const vad = await createVad({audioContext: ctx, redemptionMs, getStream: async () => dest.stream,
    onSpeechStart: () => ev.push({type: 'start', t: ctx.currentTime}), onSpeechEnd: audio => ev.push({type: 'end', t: ctx.currentTime, samples: audio.length, audio}),
    onMisfire: () => ev.push({type: 'misfire', t: ctx.currentTime})});
  await vad.start();
  const buf = ctx.createBuffer(1, pcm.length, sampleRate); buf.copyToChannel(pcm, 0);
  const src = ctx.createBufferSource(); src.buffer = buf; src.connect(dest);
  const t0 = ctx.currentTime + 0.2; src.start(t0);
  await sleep((pcm.length / sampleRate + 0.4) * 1000);
  await vad.pause(); await vad.destroy();
  return {t0, events: ev.map(e => ({...e, rel: Math.round((e.t - t0) * 1000)}))};
}
function concat(parts) { const n = parts.reduce((a, p) => a + p.length, 0), o = new Float32Array(n); let k = 0; for (const p of parts) { o.set(p, k); k += p.length; } return o; }

async function vadPauses() {
  const items = JSON.parse(decodeURIComponent(q.get('items') || '[]'));   // [{lang, id, a, b}]
  const pauses = (q.get('pauses') || '400,700,1000,1500').split(',').map(Number);
  const redemptionMs = Number(q.get('redemption') || 1100);
  const ctx = new AudioContext({sampleRate: 16000}); await ctx.resume();
  const voices = {};
  for (const it of items) {
    voices[it.lang] ||= await createPiper({voice: VOICES[it.lang]});
    const a = await voices[it.lang].synthesize(it.a), b = await voices[it.lang].synthesize(it.b), sr = a.sampleRate;
    for (const pause of pauses) {
      const lead = new Float32Array(Math.round(0.3 * sr)), mid = new Float32Array(Math.round(pause / 1000 * sr)), tail = new Float32Array(Math.round(2.5 * sr));
      const pcm = concat([lead, a.pcm, mid, b.pcm, tail]);
      const aEnd = (lead.length + a.pcm.length) / sr * 1000, bStart = aEnd + pause, speechEnd = (lead.length + a.pcm.length + mid.length + b.pcm.length) / sr * 1000;
      const r = await playIntoVad(ctx, pcm, sr, redemptionMs);
      const ends = r.events.filter(e => e.type === 'end');
      const cut = ends.some(e => e.rel < bStart);
      const final = ends.find(e => e.rel >= bStart);
      R.items.push({...it, pauseMs: pause, redemptionMs, aEndMs: Math.round(aEnd), bStartMs: Math.round(bStart), speechEndMs: Math.round(speechEnd),
        events: r.events.map(({audio, ...e}) => e), cutInsidePause: cut, endDetectedAfterSpeechEndMs: final ? final.rel - Math.round(speechEnd) : null});
      log(`${it.id} pause ${pause}: cut=${cut} endDelay=${final ? final.rel - Math.round(speechEnd) : 'none'}`);
    }
  }
}

async function validatorParity() {
  const fx = await (await fetch('/generated/product/tests/unit/fixtures/mental_spoken_summary_cases.json')).json();
  const v = await createPyValidator(); R.loadMs = Math.round(v.loadMs);
  for (const c of fx.cases) {
    const t0 = performance.now();
    const r = await v.validate(c.candidate, c.language, fx.users[c.user].map(content => ({role: 'user', content})));
    R.items.push({id: c.id, status: r.status, accepted: r.status === null, ms: +(performance.now() - t0).toFixed(1)});
  }
}

(async () => {
  try { if (mode === 'validator') await validatorParity(); else if (mode === 'tts') await tts(); else if (mode === 'stt') await stt(); else if (mode === 'vad') await vadPauses(); else throw new Error('mode?'); }
  catch (e) { R.error = String(e && (e.stack || e.message) || e); log('ERROR ' + R.error); }
  R.done = true;
})();
