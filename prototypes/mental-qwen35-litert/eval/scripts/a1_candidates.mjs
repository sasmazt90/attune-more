// A1: the 94 shared candidate lines (read-only fixture of the base commit). Product validator + on-device verifier.
// Verifier: fresh Engine per case (no state from another case), greedy, one word.
import fs from 'node:fs';
import {hostLlm, hostValidate} from '../../web/adapters/hostLlm.js';
import {verifierPrompt, VERIFIER_SYSTEM} from '../../web/core/prompts.js';
const [fixturePath, outPath] = process.argv.slice(2);
const fx = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const out = [];
for (const c of fx.cases) {
  const user = fx.users[c.user];
  const messages = user.map(content => ({role: 'user', content}));
  const v = await hostValidate(c.candidate, c.language, messages);
  const h = await hostLlm.open(VERIFIER_SYSTEM);
  const r = await hostLlm.send(h, verifierPrompt(user, c.candidate), {maxTokens: 4});
  await hostLlm.close(h);
  const answer = /\bYES\b/i.test(r.text) ? 'YES' : /\bNO\b/i.test(r.text) ? 'NO' : 'UNCLEAR';
  const rec = {id: c.id, language: c.language, user, candidate: c.candidate, fixtureFormal: c.formal, content: c.content, knownLimitation: !!c.knownLimitation,
    conservativeReject: !!c.conservativeReject, validatorStatus: v.status, validatorAccepts: v.status === null, verifier: answer, verifierRaw: r.text, verifierMs: r.totalMs,
    combinedAccepts: v.status === null && answer === 'NO'};
  out.push(rec); console.log(c.id, '| val', v.status ?? 'ACCEPT', '| ver', answer, '| content', c.content);
  fs.writeFileSync(outPath, JSON.stringify({platform: 'HOST-linux-cpu (verifier) + product validator', fixture: fixturePath, cases: out}, null, 1));
}
