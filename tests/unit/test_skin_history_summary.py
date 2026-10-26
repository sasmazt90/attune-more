"""Sağlık Geçmişim skin presentation: module-card averages, table summary and comparison with the previous scan."""
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def run(script):
    r = subprocess.run(['node', '-e', "require('./tests/unit/ts_loader.js');\n" + script], cwd=ROOT, text=True, capture_output=True, encoding='utf8', timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_averages_and_comparison():
    run(r'''
const assert=require('assert/strict'),H=require('./apps/vehicle-app/src/utils/skinHistorySummary.ts');
const rec=(id,ts,findings,unavailable=[],type='combination')=>({id,timestamp:ts,general:{skinType:{value:type,quality:'valid'},findings:{version:'v',status:'measured',findings,unavailable}}});
const acne=n=>({id:'acne',region:'forehead',status:'seen',pose:'FRONT',count:n});
const ros=s=>({id:'rosacea',region:'nose',status:'seen',pose:'FRONT',severity:s});
const a=rec('a','2026-10-19T10:00:00Z',[acne(11),ros(40),{id:'coldSore',region:'chin',status:'seen',count:1,countAtLeast:true}]);
const b=rec('b','2026-10-23T22:00:00Z',[acne(4),ros(55)],[{id:'mole',reason:'MODEL_NOT_AVAILABLE'}]);
const c=rec('c','2026-10-26T10:00:00Z',[acne(7),ros(62),{id:'mole',region:'leftCheek',status:'seen',pose:'RIGHT',count:2}]);
const old={id:'legacy',timestamp:'2026-10-01T10:00:00Z',indicators:{}};
// newest first, legacy records without findings ignored
assert.deepEqual(H.findingsRecords([a,old,c,b]).map(r=>r.id),['c','b','a']);
// card: last 3 scans; counts averaged over scans that measured them; scores over scans where seen
const avg=H.skinAverages([a,b,c,old]);
assert.equal(avg.scans,3);assert.equal(avg.skinType,'Karma');
const by=Object.fromEntries(avg.rows.map(r=>[r.id,r]));
assert.equal(Math.round(by.acne.metric*10)/10,7.3);assert.equal(by.rosacea.metric,(40+55+62)/3);
assert.equal(by.mole.metric,1);   // 2 in c, 0 in a (measured, not seen), b: unavailable -> not counted
// detail: compared with the scan just before (b), never an average
const {rows,gone}=H.compareWithPrevious(c,b,'tr-TR');
const ch=Object.fromEntries(rows.map(r=>[r.id,r.change]));
assert.deepEqual([ch.acne.kind,ch.acne.delta,ch.acne.previous],['up',3,'4']);
assert.deepEqual([ch.rosacea.kind,ch.rosacea.delta,ch.rosacea.previous],['up',7,'%55']);
assert.equal(ch.mole.kind,'none');   // unavailable in b: unknown, not "new"
const back=H.compareWithPrevious(b,a,'tr-TR');
assert.equal(back.rows.find(r=>r.id==='acne').change.kind,'down');
assert.deepEqual(back.gone.map(g=>[g.id,g.change.kind,g.change.previous]),[['coldSore','gone','1+']]);
assert.equal(H.compareWithPrevious(a,undefined,'tr-TR').rows.every(r=>r.change.kind==='none'),true);
// table summary values
assert.deepEqual(H.findingRows(c).slice(0,2).map(r=>[r.label,H.formatMetric(r,'tr-TR')]),[['Sivilce','7'],['Rozasea eğilimi','%62']]);
assert.equal(H.skinTypeLabel({general:{skinType:{value:'dry',quality:'insufficient'}}}),null);
const pct={id:'rosacea',kind:'severity',metric:62};assert.equal(H.formatMetric(pct,'tr-TR'),'%62');assert.equal(H.formatMetric(pct,'en-US'),'62%');assert.equal(H.formatMetric(pct,'de-DE'),'62\u00a0%');
''')
