import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';

const catalog=JSON.parse(fs.readFileSync(new URL('../../shared/localization/messages.json',import.meta.url),'utf8'));
const expected={
 Kuru:{en:'Dry',de:'Trocken'},
 Normal:{en:'Normal',de:'Normal'},
 Karma:{en:'Combination',de:'Mischhaut'},
 Sarkma:{en:'Sagging',de:'Erschlaffung'}
};
const normalize=text=>text.normalize('NFC').replace(/\s+/g,' ').trim();
for(const [tr,translations] of Object.entries(expected)){
 const id=crypto.createHash('sha256').update(normalize(tr)).digest('hex').slice(0,16);
 assert.deepEqual(catalog[id],{tr,...translations});
}
const overview=fs.readFileSync(new URL('../../apps/vehicle-app/src/utils/skinOverview.ts',import.meta.url),'utf8');
const indicators=fs.readFileSync(new URL('../../apps/vehicle-app/src/utils/skinIndicators.ts',import.meta.url),'utf8');
for(const label of ['Normal','Kuru','Yağlı','Karma'])assert(overview.includes(label));
assert(indicators.includes("sag:'Sarkma'"));
console.log('PASS: skin type and sag labels have stable EN/DE catalog entries');
