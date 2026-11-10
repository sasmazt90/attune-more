// In-browser speech components of the KOL B prototype. Everything is served from this origin: no CDN, no cloud.
//  - VAD / end of turn: Silero VAD v5 (@ricky0123/vad-web 0.0.31, ONNX Runtime Web WASM)
//  - STT: Whisper (onnx-community ONNX, q8) with transformers.js 4.3.2 (WASM)
//  - TTS: Piper voices (rhasspy/piper-voices) with ONNX Runtime Web + piper_phonemize (espeak-ng) WASM
import {MicVAD} from '@ricky0123/vad-web';
import {pipeline, env as hfEnv} from '@huggingface/transformers';
import * as ort from 'onnxruntime-web/wasm';
// piper_phonemize.js is a classic Emscripten script (global createPiperPhonemize); loaded as-is from this origin.
let phonemizerReady = null;
function loadPhonemizer() {
  return phonemizerReady ||= new Promise((resolve, reject) => {
    const s = document.createElement('script'); s.src = '/node_modules/@diffusionstudio/piper-wasm/build/piper_phonemize.js';
    s.onload = () => resolve(globalThis.createPiperPhonemize); s.onerror = reject; document.head.appendChild(s);
  });
}

const ORT_WASM = '/node_modules/onnxruntime-web/dist/';
const HF_ORT_WASM = '/node_modules/@huggingface/transformers/node_modules/onnxruntime-web/dist/';
const now = () => performance.now();

// ---------- TTS (Piper) ----------
export async function createPiper({voice, base = '/models/piper/'}) {
  ort.env.wasm.wasmPaths = ORT_WASM; ort.env.wasm.numThreads = Math.min(4, navigator.hardwareConcurrency || 4);
  const t0 = now();
  const config = await (await fetch(`${base}${voice}.onnx.json`)).json();
  const session = await ort.InferenceSession.create(new Uint8Array(await (await fetch(`${base}${voice}.onnx`)).arrayBuffer()), {executionProviders: ['wasm']});
  const loadMs = now() - t0;
  const map = config.phoneme_id_map;
  const createPiperPhonemize = await loadPhonemizer();
  async function phonemize(text) {
    return new Promise((resolve, reject) => {
      createPiperPhonemize({
        print: data => { try { resolve(JSON.parse(data)); } catch (e) { reject(e); } },
        printErr: msg => { if (!/^\s*$/.test(msg)) console.warn('[phonemize]', msg); },
        locateFile: url => '/node_modules/@diffusionstudio/piper-wasm/build/' + url.split('/').pop(),
      }).then(m => m.callMain(['-l', config.espeak.voice, '--input', JSON.stringify([{text}]), '--espeak_data', '/espeak-ng-data']));
    });
  }
  function idsFromPhonemes(phonemes) {   // piper-phonemize: BOS, PAD, then each phoneme followed by PAD, then EOS
    const ids = [...map['^'], ...map['_']];
    for (const p of phonemes) if (map[p]) ids.push(...map[p], ...map['_']);
    ids.push(...map['$']);
    return ids;
  }
  async function synthesize(text) {
    const t0 = now();
    const ph = await phonemize(text.trim());
    const t1 = now();
    const phonemes = Array.isArray(ph.phonemes) ? ph.phonemes.flat().join('') : null;
    const ids = phonemes ? idsFromPhonemes([...phonemes]) : ph.phoneme_ids;
    const inf = config.inference;
    const feeds = {input: new ort.Tensor('int64', BigInt64Array.from(ids.map(BigInt)), [1, ids.length]),
      input_lengths: new ort.Tensor('int64', BigInt64Array.from([BigInt(ids.length)]), [1]),
      scales: new ort.Tensor('float32', Float32Array.from([inf.noise_scale, inf.length_scale, inf.noise_w]), [3])};
    if (session.inputNames.includes('sid')) feeds.sid = new ort.Tensor('int64', BigInt64Array.from([0n]), [1]);
    const out = await session.run(feeds);
    const pcm = out[session.outputNames[0]].data;
    const t2 = now();
    return {pcm, sampleRate: config.audio.sample_rate, phonemizeMs: t1 - t0, inferenceMs: t2 - t1, totalMs: t2 - t0,
      audioMs: pcm.length / config.audio.sample_rate * 1000, idsFromPhonemizer: ph.phoneme_ids, idsUsed: ids, phonemes};
  }
  return {voice, config, loadMs, inputNames: session.inputNames, synthesize};
}

export function wavBytes(pcm, sampleRate) {
  const b = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(b);
  const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); w(8, 'WAVE'); w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, 1, true); v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  w(36, 'data'); v.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, pcm[i])) * 32767, true);
  return new Uint8Array(b);
}

// ---------- STT (Whisper) ----------
export async function createWhisper({model = 'onnx-community/whisper-small'} = {}) {
  hfEnv.allowRemoteModels = false; hfEnv.allowLocalModels = true; hfEnv.localModelPath = '/models/stt/';
  hfEnv.backends.onnx.wasm.wasmPaths = HF_ORT_WASM; hfEnv.backends.onnx.wasm.numThreads = Math.min(4, navigator.hardwareConcurrency || 4);
  const t0 = now();
  const asr = await pipeline('automatic-speech-recognition', model, {device: 'wasm', dtype: {encoder_model: 'q8', decoder_model_merged: 'q8'}});
  const loadMs = now() - t0;
  const LANG = {tr: 'turkish', en: 'english', de: 'german'};
  async function transcribe(audio16k, lang) {
    const t0 = now();
    const r = await asr(audio16k, {language: LANG[lang], task: 'transcribe', chunk_length_s: 30});
    return {text: r.text.trim(), ms: now() - t0};
  }
  return {model, loadMs, transcribe};
}

export async function decodeTo16k(arrayBuffer) {
  const ctx = new OfflineAudioContext(1, 16000, 16000);
  const buf = await ctx.decodeAudioData(arrayBuffer.slice(0));
  const off = new OfflineAudioContext(1, Math.ceil(buf.duration * 16000), 16000);
  const src = off.createBufferSource(); src.buffer = buf; src.connect(off.destination); src.start();
  return (await off.startRendering()).getChannelData(0);
}

// ---------- VAD / end of turn (real-time path, any MediaStream) ----------
export async function createVad({getStream, audioContext, redemptionMs = 1100, onSpeechStart, onSpeechEnd, onMisfire, keepStream = false}) {
  // Default: pausing stops the microphone (nothing is captured while the assistant speaks) and resuming opens it again.
  // keepStream: a provided stream (test source) is kept across pause/resume instead of re-opening the microphone.
  const streamOptions = keepStream ? {pauseStream: async () => {}, resumeStream: async s => s} : {};
  return MicVAD.new({model: 'v5', baseAssetPath: '/node_modules/@ricky0123/vad-web/dist/', onnxWASMBasePath: ORT_WASM,
    getStream, audioContext, startOnLoad: false, processorType: 'AudioWorklet', ...streamOptions,
    positiveSpeechThreshold: 0.5, negativeSpeechThreshold: 0.35, redemptionMs, preSpeechPadMs: 300, minSpeechMs: 250,
    onSpeechStart: onSpeechStart || (() => {}), onSpeechEnd: onSpeechEnd || (() => {}), onVADMisfire: onMisfire || (() => {})});
}
export {ort};
