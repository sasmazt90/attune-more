// A2: for each of the 37 shared user inputs, run the prototype conversation (user messages as turns) and its closing.
import fs from 'node:fs';
import {MentalSession} from '../../web/core/session.js';
import {hostLlm, hostValidate, hostVerify} from '../../web/adapters/hostLlm.js';
import {makeCrisis} from '../../web/adapters/crisis.js';
const [fixturePath, outPath] = process.argv.slice(2);
const fx = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const msgs = JSON.parse(fs.readFileSync(new URL('../../../../shared/localization/messages.json', import.meta.url), 'utf8'));
const langOf = id => id.slice(0, 2);
const out = [];
for (const [id, user] of Object.entries(fx.users)) {
  const lang = langOf(id);
  const s = new MentalSession({lang, llm: hostLlm, crisis: makeCrisis(lang, msgs), validate: hostValidate, verify: hostVerify});
  await s.start();
  for (const u of user) await s.userTurn(u);
  const c = await s.finish({verify: true});
  out.push({id, language: lang, user, line: c.line, T: c.T});
  console.log(id, '|', c.line?.candidate, '|', c.line?.status, '|', c.line?.retryCandidate ?? '', c.line?.retryStatus ?? '', '| ver', c.line?.verifier, '| final', c.line?.accepted);
  fs.writeFileSync(outPath, JSON.stringify({platform: 'HOST-linux-cpu (not on-device)', results: out}, null, 1));
}
