// AAOS adapter: the page runs in the prototype APK's WebView; the model runs natively (LlmBridge.java, LiteRT-LM Android).
const pending = new Map();
let seq = 0;
window.__attuneLlmCallback = (id, result) => { const p = pending.get(id); if (p) { pending.delete(id); p(result); } };
const call = (fn, ...args) => new Promise(resolve => { const id = 'c' + (++seq); pending.set(id, resolve); window.AttuneLlm[fn](id, ...args); });
export const androidLlm = {
  available: () => typeof window.AttuneLlm === 'object',
  info: () => JSON.parse(window.AttuneLlm.info()),
  async open(system) { const r = await call('open', system); if (!r.ok) throw new Error(r.error); return {id: r.sessionId, engineCreateMs: r.engineCreateMs}; },
  async send(h, text, {maxTokens = 96} = {}) { const r = await call('send', h.id, text, maxTokens); if (!r.ok) throw new Error(r.error); return r; },
  cancel(h) { if (h) window.AttuneLlm.cancel(h.id); },
  async close(h) { if (h) await call('close', h.id); },
};
