// B3: crisis utterances take the product crisis path; the model must not be called (fake LLM throws on any call).
import fs from 'node:fs';
import {MentalSession} from '../../web/core/session.js';
import {makeCrisis} from '../../web/adapters/crisis.js';
const [corpusPath, outPath] = process.argv.slice(2);
const corpus = JSON.parse(fs.readFileSync(corpusPath, 'utf8'));
const msgs = JSON.parse(fs.readFileSync(new URL('../../../../shared/localization/messages.json', import.meta.url), 'utf8'));
let modelCalls = 0;
const llm = {open: async () => ({id: 'x'}), send: async () => { modelCalls++; throw new Error('model must not be called'); }, cancel() {}, close: async () => {}};
const out = [];
for (const c of corpus.crisis) for (const moving of [false, true]) {
  const before = modelCalls;
  const spoken = [];
  const s = new MentalSession({lang: c.language, llm, crisis: makeCrisis(c.language, msgs), validate: async () => ({}), speech: {speak: async t => { spoken.push(t); return {played: true}; }, stop() {}}});
  await s.start();
  const r = await s.userTurn(c.text, {moving});
  const after = await s.userTurn('Peki.');            // conversation must stay stopped
  const fin = await s.finish();
  out.push({id: c.id, moving, crisis: !!r.crisis, modelCalled: modelCalls > before, spoken, laterTurnSkipped: after.skipped === 'inactive', summary: fin.summary, reason: fin.reason});
}
fs.writeFileSync(outPath, JSON.stringify({results: out}, null, 1));
console.log(JSON.stringify(out.map(o => [o.id, o.moving, o.crisis, o.modelCalled, o.laterTurnSkipped, o.reason, o.spoken[0]?.slice(0, 50)])));
