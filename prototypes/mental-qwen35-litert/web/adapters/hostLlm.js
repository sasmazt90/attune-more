// HOST-linux-cpu adapter (evaluation only): talks to host/llm_host_server.py on loopback. Not on-device.
import {verifierPrompt} from '../core/prompts.js';
const BASE = typeof window === 'undefined' ? 'http://127.0.0.1:8790' : '/llm';   // page: same-origin proxy of tools/serve.mjs
async function post(path, body) {
  const r = await fetch(BASE + path, {method: 'POST', body: JSON.stringify(body)});
  const j = await r.json(); if (!r.ok) throw new Error(`${path}: ${j.error || r.status}`); return j;
}
export const hostLlm = {
  async open(system) { const j = await post('/session', {systemPrompt: system}); return {id: j.sessionId, engineCreateMs: j.engineCreateMs}; },
  async send(h, text, {maxTokens = 96} = {}) { return post('/send', {sessionId: h.id, text, maxTokens}); },
  cancel(h) { if (h) post('/cancel', {sessionId: h.id}).catch(() => {}); },
  async close(h) { if (h) await post('/close', {sessionId: h.id}); },
};
export async function hostValidate(line, language, messages) { return post('/validate', {line, language, messages}); }
export async function hostVerify(h, userMessages, line) {
  const r = await hostLlm.send(h, verifierPrompt(userMessages, line), {maxTokens: 4});
  const answer = /\bYES\b/i.test(r.text) ? 'YES' : /\bNO\b/i.test(r.text) ? 'NO' : 'UNCLEAR';
  return {answer, raw: r.text, ms: r.totalMs};
}
