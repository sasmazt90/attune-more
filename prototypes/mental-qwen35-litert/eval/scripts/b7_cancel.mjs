// B7a: cancel while the model generates, then a new utterance. The cancelled reply must never be spoken.
import fs from 'node:fs';
import {MentalSession} from '../../web/core/session.js';
import {hostLlm, hostValidate} from '../../web/adapters/hostLlm.js';
import {makeCrisis} from '../../web/adapters/crisis.js';
const [outPath, perLang = '10'] = process.argv.slice(2);
const msgs = JSON.parse(fs.readFileSync(new URL('../../../../shared/localization/messages.json', import.meta.url), 'utf8'));
const A = {tr: 'Bugün markete gittim ve uzun bir kuyruk vardı.', en: 'Today I went to the supermarket and there was a long queue.', de: 'Heute war ich im Supermarkt und die Schlange war lang.'};
const B = {tr: 'Aslında asıl anlatmak istediğim, akşam yürüyüşe çıktım.', en: 'Actually what I wanted to say is that I went for a walk in the evening.', de: 'Eigentlich wollte ich sagen, dass ich abends spazieren war.'};
const out = [];
for (const lang of ['tr', 'en', 'de']) {
  const s = new MentalSession({lang, llm: hostLlm, crisis: makeCrisis(lang, msgs), validate: hostValidate,
    speech: {speak: async (t, {isCurrent}) => { const ok = isCurrent(); spokenLog.push({t, ok}); return {played: ok}; }, stop() {}}});
  var spokenLog = [];
  await s.start();
  for (let i = 0; i < Number(perLang); i++) {
    spokenLog.length = 0;
    const delay = 150 + Math.round(Math.random() * 1500);
    const pA = s.userTurn(A[lang]);
    await new Promise(r => setTimeout(r, delay));
    s.cancel('user-barge-in');                    // the user starts speaking again
    const rA = await pA;
    const rB = await s.userTurn(B[lang]);
    const spokeA = spokenLog.some(x => x.ok && rA.raw && x.t === rA.spoken);
    out.push({lang, trial: i, cancelAfterMs: delay, aDiscarded: !!rA.discarded, aSpokenAfterCancel: spokeA, bSpoken: spokenLog.filter(x => x.ok).map(x => x.t), bSource: rB.source});
    console.log(lang, i, delay, 'A discarded', !!rA.discarded, 'A spoken', spokeA, '| B:', rB.spoken);
  }
  await s.end();
}
fs.writeFileSync(outPath, JSON.stringify({platform: 'HOST-linux-cpu model + Node timing harness', results: out}, null, 1));
