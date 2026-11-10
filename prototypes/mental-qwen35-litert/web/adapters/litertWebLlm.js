// WEB adapter: Qwen3.5-2B inside the page with the LiteRT-LM JS runtime (@litert-lm/core 0.19.0).
// Backend: WebGPU (Backend.GPU). The WASM CPU path does not load this model (results/raw/web_probe_cpu*.json).
// One fresh Engine per conversation (LiteRT-LM #3165).
import {Engine, Backend, loadLiteRtLm} from '@litert-lm/core';
let loaded = null;
export function makeLitertWebLlm({modelUrl = '/models/qwen35-2b/Qwen3.5-2B_int8.litertlm', backend = 'GPU', wasm = '/node_modules/@litert-lm/core/wasm/'} = {}) {
  return {
    async open(system) {
      loaded ||= loadLiteRtLm(wasm);
      await loaded;
      const t0 = performance.now();
      const engine = await Engine.create({model: modelUrl, backend: Backend[backend], mainExecutorSettings: {maxNumTokens: 4096}, benchmarkEnabled: true});
      const conv = await engine.createConversation({preface: {messages: [{role: 'system', content: system}]}, sessionConfig: {samplerParams: {type: 3, k: 1, temperature: 0}}});
      return {engine, conv, engineCreateMs: Math.round(performance.now() - t0)};
    },
    async send(h, text, {maxTokens = 96} = {}) {
      const t0 = performance.now(); let first = null, out = '', cancelled = false;
      try {
        for await (const chunk of h.conv.sendMessageStreaming(text)) {
          for (const c of chunk.content || []) if (c.type === 'text') { if (first === null) first = performance.now() - t0; out += c.text; }
          if (out.length > maxTokens * 8) { h.conv.cancel(); break; }      // JS API has no per-message token cap
        }
      } catch (e) { if (/cancel/i.test(String(e))) cancelled = true; else throw e; }
      let contextTokens = null; try { contextTokens = await h.conv.getTokenCount(); } catch {}
      return {text: out, firstTokenMs: first && Math.round(first), totalMs: Math.round(performance.now() - t0), cancelled, contextTokens};
    },
    cancel(h) { try { h?.conv.cancel(); } catch {} },
    async close(h) { if (!h) return; try { await h.conv.delete(); } catch {} try { await h.engine.delete(); } catch {} },
  };
}
