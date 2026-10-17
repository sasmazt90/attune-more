"""Actual source adapters: newest record and invalid/null measurements stay honest."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_newest_measured_share_never_exports_old_or_invalid_values():
 script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict');
global.window=new EventTarget();global.localStorage={data:new Map(),getItem(k){return this.data.get(k)??null},setItem(k,v){this.data.set(k,String(v))},removeItem(k){this.data.delete(k)}};
const {measuredShareSection}=require('./apps/vehicle-app/src/utils/healthShare.ts');
const old={id:'old',date:'2026-10-01T12:00:00Z',value:-8,quality:'valid',validTrials:24};
const fresh={...old,id:'new',date:'2026-10-17T12:00:00Z',value:-3};
for(const rows of [[fresh,old],[old,fresh]]){
 localStorage.setItem('attune_hearing_history_v1',JSON.stringify(rows));
 assert(measuredShareSection('hearing').text.includes('-3 dB SNR'));
 assert(!measuredShareSection('hearing').text.includes('-8 dB SNR'));
}
for(const quality of ['invalid','unreliable','insufficient']){
 localStorage.setItem('attune_hearing_history_v1',JSON.stringify([{...fresh,quality,value:0}]));
 assert(measuredShareSection('hearing').text.includes('kararlı eşik bulunamadı'));
 assert(!measuredShareSection('hearing').text.includes('0 dB SNR'));
}
localStorage.setItem('attune_hearing_history_v1',JSON.stringify([{...fresh,thresholds:[{ear:'left',frequency:1000,value:-30,status:'upper-limit'}]}]));
assert(measuredShareSection('hearing').text.includes('eşik bulunamadı'));
const dental=(id,date,value,quality)=>({id,date,sourceType:'upload',measurements:[{pose:'FRONT',caries:{value,quality},accumulation:{value:null,quality:'insufficient'}}]});
localStorage.setItem('attune_dental_history_v1',JSON.stringify([dental('d-new',fresh.date,4,'valid'),dental('d-old',old.date,9,'valid')]));
assert(measuredShareSection('dental').text.includes('4 görünür aday'));assert(!measuredShareSection('dental').text.includes('9 görünür aday'));
localStorage.setItem('attune_dental_history_v1',JSON.stringify([dental('d-bad',fresh.date,0,'invalid')]));
assert(measuredShareSection('dental').text.includes('Çürük adayı değerlendirilemiyor'));assert(!measuredShareSection('dental').text.includes('0 görünür aday'));
'''
 subprocess.run(['node','-e',script],cwd=ROOT,check=True)
