// Browser compatibility probe: loads the pinned .litertlm file with the LiteRT-LM JS runtime INSIDE this page
// (no server-side inference) and asks one short question. Every stage is reported with its own timing/error.
import {Engine, Backend, loadLiteRtLm} from '@litert-lm/core';

const q = new URLSearchParams(location.search);
const backendName = (q.get('backend') || 'cpu').toUpperCase();
const modelUrl = q.get('model') || '/models/qwen35-2b/Qwen3.5-2B_int8.litertlm';
const prompt = q.get('prompt') || 'What is the capital of France? Answer in one short sentence.';
const out = document.getElementById('out');
const R = window.__result = {backendRequested: backendName, modelUrl, stages: [], done: false};
const now = () => performance.now();
const say = (s) => { out.textContent += s + '\n'; console.log('[probe] ' + s); };
async function stage(name, fn) {
  const t0 = now();
  try { const v = await fn(); R.stages.push({name, ok: true, ms: Math.round(now() - t0)}); say(`${name}: ok ${Math.round(now()-t0)} ms`); return v; }
  catch (e) { R.stages.push({name, ok: false, ms: Math.round(now() - t0), error: String(e && (e.stack || e.message) || e)}); say(`${name}: FAILED ${e}`); throw e; }
}
function mem() { const m = performance.memory; return m ? {usedJSHeapMB: Math.round(m.usedJSHeapSize/1048576), totalJSHeapMB: Math.round(m.totalJSHeapSize/1048576)} : null; }
(async () => {
  R.env = {userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, deviceMemory: navigator.deviceMemory ?? null,
           crossOriginIsolated: self.crossOriginIsolated, webgpu: !!navigator.gpu};
  if (navigator.gpu) {
    try {
      const a = await navigator.gpu.requestAdapter({powerPreference: 'high-performance'});
      R.env.adapter = a ? {info: a.info ? {vendor: a.info.vendor, architecture: a.info.architecture, device: a.info.device, description: a.info.description, isFallbackAdapter: a.info.isFallbackAdapter} : null,
        isFallbackAdapter: a.isFallbackAdapter ?? null, features: [...a.features], limits: {maxBufferSize: a.limits.maxBufferSize, maxStorageBufferBindingSize: a.limits.maxStorageBufferBindingSize}} : null;
    } catch (e) { R.env.adapterError = String(e); }
  }
  say(JSON.stringify(R.env));
  try {
    await stage('load-wasm-runtime', () => loadLiteRtLm(q.get('wasm') || '/node_modules/@litert-lm/core/wasm/'));
    const source = q.get('source') || 'url';
    R.source = source;
    const model = source === 'blob' ? await stage('fetch-model-as-blob', async () => (await fetch(modelUrl)).blob()) : modelUrl;
    const engine = await stage('engine-create', () => Engine.create({model, backend: Backend[backendName],
      mainExecutorSettings: {maxNumTokens: Number(q.get('maxTokens') || 4096)}, benchmarkEnabled: true}));
    R.memAfterEngine = mem();
    const conv = await stage('conversation-create', () => engine.createConversation({preface: {messages: [{role: 'system', content: 'Answer in one short sentence.'}]},
      sessionConfig: {samplerParams: {type: 3, k: 1, temperature: 0}}}).catch(() => engine.createConversation({preface: {messages: [{role: 'system', content: 'Answer in one short sentence.'}]}})));
    let first = null; const t0 = now(); let text = '';
    await stage('first-reply', async () => {
      const stream = conv.sendMessageStreaming(prompt);
      for await (const chunk of stream) { if (first === null) first = Math.round(now() - t0); for (const c of chunk.content || []) if (c.type === 'text') text += c.text; }
    });
    R.reply = text; R.firstChunkMs = first; R.replyMs = Math.round(now() - t0);
    try { R.benchmark = JSON.parse(JSON.stringify(await conv.getBenchmarkInfo())); } catch (e) { R.benchmarkError = String(e); }
    R.memEnd = mem();
    await conv.delete(); await engine.delete();
    say('reply: ' + text);
  } catch (e) { R.error = String(e && (e.stack || e.message) || e); }
  R.done = true; say('done');
})();
