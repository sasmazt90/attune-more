// Runs corpus conversations through the prototype core with the HOST adapter (content evaluation; not on-device).
// Usage: node run_conversations.mjs <corpus.json> <out.json> [idFilter] [--verify]
import fs from 'node:fs';
import {MentalSession} from '../../web/core/session.js';
import {hostLlm, hostValidate, hostVerify} from '../../web/adapters/hostLlm.js';
import {makeCrisis} from '../../web/adapters/crisis.js';
const [corpusPath, outPath, filter = '', ...flags] = process.argv.slice(2);
const corpus = JSON.parse(fs.readFileSync(corpusPath, 'utf8'));
const messages = JSON.parse(fs.readFileSync(new URL('../../../../shared/localization/messages.json', import.meta.url), 'utf8'));
const verify = flags.includes('--verify');
const results = [];
for (const c of corpus.conversations.filter(c => !filter || c.id.includes(filter))) {
  const s = new MentalSession({lang: c.language, llm: hostLlm, crisis: makeCrisis(c.language, messages), validate: hostValidate, verify: verify ? hostVerify : null});
  const t0 = performance.now();
  await s.start();
  const turns = [];
  for (const u of c.turns) turns.push(await s.userTurn(u));
  const closing = await s.finish({verify});
  const rec = {id: c.id, language: c.language, category: c.category, engineCreateMs: s.events.find(e => e.type === 'engine-ready')?.engineCreateMs,
    turns: turns.map(t => ({user: t.user, raw: t.raw, spoken: t.spoken, source: t.source, issues: t.issues, firstTokenMs: t.firstTokenMs, modelMs: t.modelMs, bench: t.bench, contextTokens: t.contextTokens})),
    closing: {line: closing.line, groupsRaw: closing.groupsRaw, groupsModelMs: closing.groupsModelMs, summary: closing.summary, T: closing.T}, wallMs: Math.round(performance.now() - t0)};
  results.push(rec);
  console.log(`\n=== ${c.id} (${rec.wallMs} ms, engine ${rec.engineCreateMs} ms)`);
  for (const t of rec.turns) console.log(`U: ${t.user}\nA[${t.source}${t.issues?.length ? ' ' + t.issues : ''}] ${t.spoken}   (raw: ${t.raw === t.spoken ? '=' : t.raw}) ${t.modelMs}ms ctx=${t.contextTokens}`);
  console.log('LINE:', JSON.stringify(rec.closing.line));
  console.log('GROUPS:', rec.closing.groupsRaw);
  console.log('SUMMARY:', JSON.stringify(rec.closing.summary?.groups.map(g => [g.label, g.quotes.map(q => q.turn)])), 'replaced', JSON.stringify(rec.closing.summary?.replaced.map(r => r.turn)), rec.closing.summary?.issues);
  fs.writeFileSync(outPath, JSON.stringify({platform: 'HOST-linux-cpu (not on-device)', model: 'Qwen3.5-2B_int8.litertlm sha256 c2438cb9…', runtime: 'litert-lm-api 0.19.1', verify, results}, null, 1));
}
