"""Skin findings over time: states, comparability, averages, appearance score — including the reviewer's
counter-examples (each is a named regression check below). Pure functions, no model, no network."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))


def run(script):
    r = subprocess.run(['node', '-e', "require('./tests/unit/ts_loader.js');\n" + script], cwd=ROOT, text=True, capture_output=True, encoding='utf8', timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


PRELUDE = r'''
const assert=require('assert/strict'),H=require('./apps/vehicle-app/src/utils/skinHistorySummary.ts'),F=require('./apps/vehicle-app/src/utils/skinFindings.ts'),
 Rec=require('./apps/vehicle-app/src/utils/skinRecommendations.ts'),A=require('./apps/vehicle-app/src/utils/skinAppearance.ts');
const rec=(id,ts,findings,o={})=>({id,timestamp:ts,general:{skinType:{value:'combination',quality:'valid'},findings:{version:o.version||'skin-findings-v2',status:o.status||'measured',reason:o.reason,findings,unavailable:o.unavailable||[]}}});
const acne=(n,reg='forehead',x={})=>({id:'acne',region:reg,status:'seen',pose:'FRONT',count:n,...x});
const st=(id,reg,status,x={})=>({id,region:reg,status,...x});
const row=(rows,id)=>rows.find(r=>r.id===id);
'''


def test_reviewer_counter_examples():
    run(PRELUDE + r'''
// (1) previous 8, now inconclusive -> NOT "Görülmedi": the current state is unknown
const p8=rec('p','2026-10-20T10:00:00Z',[acne(8)]), inc=rec('c','2026-10-21T10:00:00Z',[st('acne','forehead','inconclusive',{causes:['ANGLE']})]);
let r=row(H.compareRecords(inc,p8),'acne');
assert.equal(r.now.state,'inconclusive');assert.equal(r.change.kind,'unknownNow');
// (2) the same two records: average 8 over the one measured scan (never (8+0)/2 = 4)
let avg=H.skinAverages([p8,inc]);let a=avg.rows.find(x=>x.id==='acne');assert.equal(a.value,8);assert.equal(a.used,1);
// (3) previous inconclusive, now 8 -> NOT "Yeni / önceki taramada yoktu": the previous state is unknown
r=row(H.compareRecords(rec('n','2026-10-22T10:00:00Z',[acne(8)]),inc),'acne');assert.equal(r.change.kind,'noPrevious');
// (4) previous rosacea severity 80, now area 20 -> different kinds: not compared, never averaged into "50"
const sev=rec('s','2026-10-20T10:00:00Z',[st('rosacea','nose','seen',{severity:80})]), area=rec('a','2026-10-21T10:00:00Z',[st('rosacea','nose','seen',{areaPct:20})]);
r=row(H.compareRecords(area,sev),'rosacea');assert.deepEqual([r.change.kind,r.change.why],['incomparable','DIFFERENT_MEASURE']);
a=H.skinAverages([sev,area]).rows.find(x=>x.id==='rosacea');assert.deepEqual([a.kind,a.value,a.used],['area',20,1]);
// (5) status unavailable (FUSION_FAILED, no findings) -> "not measured", never "no findings seen"
const failed=rec('f','2026-10-21T10:00:00Z',[],{status:'unavailable',reason:'FUSION_FAILED'});
assert.equal(H.recordSummary(failed,'tr-TR').state,'not-measured');assert.deepEqual(H.compareRecords(failed,p8).map(x=>[x.id,x.now.state,x.change.kind]),[['acne','unavailable','unknownNow']]);
assert.equal(H.skinAverages([failed]),null);
// an empty measured findings list is not a measured absence either
assert.equal(H.recordSummary(rec('e','2026-10-21T10:00:00Z',[]),'tr-TR').state,'not-measured');
assert.equal(H.recordSummary(rec('ns','2026-10-21T10:00:00Z',[st('acne','forehead','notSeen')]),'tr-TR').state,'none-seen');
// exact counts: 8 -> 3 = 5 fewer
r=row(H.compareRecords(rec('t','2026-10-22T10:00:00Z',[acne(3)]),p8),'acne');assert.deepEqual([r.change.kind,r.change.delta,r.change.previous.value],['down',5,8]);
''')


def test_states_scope_versions_and_legacy_counts():
    run(PRELUDE + r'''
// a measured absence on every region of the scope is the only "not seen"
const prevNo=rec('p','2026-10-20T10:00:00Z',[st('acne','forehead','notSeen'),st('acne','nose','notSeen')]);
const now=rec('c','2026-10-21T10:00:00Z',[acne(2),st('acne','nose','notSeen')]);
assert.equal(row(H.compareRecords(now,prevNo),'acne').change.kind,'new');
assert.equal(row(H.compareRecords(prevNo,now),'acne').change.kind,'gone');
// a region missing on one side: the counts cover different areas -> not compared (no fill-in from another region)
const partial=rec('q','2026-10-22T10:00:00Z',[acne(3),st('acne','nose','inconclusive')]);
let r=row(H.compareRecords(partial,now),'acne');assert.deepEqual([r.change.kind,r.change.why],['incomparable','PARTIAL_REGIONS']);
// different method version -> not compared
r=row(H.compareRecords(rec('v','2026-10-22T10:00:00Z',[acne(3),st('acne','nose','notSeen')],{version:'skin-findings-v3'}),now),'acne');
assert.deepEqual([r.change.kind,r.change.why],['incomparable','DIFFERENT_METHOD']);
// legacy "1+" records stay as stored, but give no exact difference, average or band
const legacy=rec('l','2026-10-19T10:00:00Z',[acne(1,'forehead',{countAtLeast:true}),st('acne','nose','notSeen')]);
r=row(H.compareRecords(now,legacy),'acne');assert.deepEqual([r.change.kind,r.change.why],['incomparable','NO_EXACT_COUNT']);
assert.equal(H.formatValue(H.measureOf(H.resultOf(legacy),'acne',['forehead','nose']),'tr-TR'),'1+');
const a=H.skinAverages([now,legacy]).rows.find(x=>x.id==='acne');assert.deepEqual([a.value,a.used],[2,1]);
assert.equal(Rec.recommendationBand({id:'acne',region:'forehead',status:'seen',count:1,countAtLeast:true}),null);
assert.equal(Rec.recommendationBand({id:'acne',region:'forehead',status:'seen',count:0}),null);   // no band covers 0
assert.equal(Rec.recommendationBand({id:'acne',region:'forehead',status:'seen',count:3,incomplete:['nose']}),null);
assert.equal(Rec.recommendationBand({id:'acne',region:'forehead',status:'seen',count:3}).index,1);
// a page with an unreadable region says so; a seen region that could not be counted gives no number
let page=F.viewFindings([acne(3),st('acne','nose','inconclusive')],'forehead')[0];assert.deepEqual(page.incomplete,['nose']);assert.equal(page.count,3);
page=F.viewFindings([acne(3),{id:'acne',region:'nose',status:'seen',countUnavailable:'COUNT_NOT_RUN'}],'forehead')[0];assert.equal(page.count,undefined);
// a measured absence averages as 0 for counts only; unknown scans are left out
const r1=rec('r1','2026-10-18T10:00:00Z',[acne(6),st('acne','nose','notSeen')]), r0=rec('r0','2026-10-19T10:00:00Z',[st('acne','forehead','notSeen'),st('acne','nose','notSeen')]);
const av=H.skinAverages([r1,r0,partial]).rows.find(x=>x.id==='acne');assert.deepEqual([av.value,av.used],[3,2]);
// percent and score formats per language
const m={kind:'severity',value:62};assert.equal(H.formatValue(m,'tr-TR'),'%62');assert.equal(H.formatValue(m,'en-US'),'62%');assert.equal(H.formatValue(m,'de-DE'),'62 %');
assert.equal(H.formatValue({kind:'appearance',value:62},'de-DE'),'62');
''')


def test_appearance_score_contract_and_comparison():
    out = run(PRELUDE + r'''
// fixed scale, monotone in area and intensity, 0 without affected pixels, no score without input
let prev=-1;for(const area of [0,.05,.1,.25,.5,.8]){let p2=-1;for(const i of [0,4,8,16,30]){const s=A.appearanceScore(area,i);assert(s>=p2&&s>=0&&s<=100);p2=s;}assert(A.appearanceScore(area,16)>=prev);prev=A.appearanceScore(area,16);}
assert.equal(A.appearanceScore(0,30),0);assert.equal(A.appearanceScore(.5,16),100);assert.equal(A.poolAppearance([]),null);
const reg=(u,a,i)=>({version:'appearance-v1',usablePx:u,affectedPx:a,areaPct:Math.round(10000*a/u)/100,intensity:i,score:A.appearanceScore(a/u,i)});
// pooled by pixel sums, never by adding regional percentages
const pooled=A.poolAppearance([reg(1000,200,10),reg(3000,0,0)]);assert.equal(pooled.areaPct,5);assert.equal(pooled.intensity,10);
// page: notSeen rows with raw values belong to the pool; an unmeasured region makes it partial (not comparable)
const rows=[st('rosacea','nose','seen',{appearance:reg(1000,400,12)}),st('rosacea','forehead','notSeen',{appearance:reg(3000,30,5)})];
let p=F.viewFindings(rows,'forehead')[0];assert.equal(p.appearance.partial,false);assert.equal(p.appearance.usablePx,4000);
p=F.viewFindings([rows[0],st('rosacea','forehead','inconclusive')],'forehead')[0];assert.equal(p.appearance.partial,true);assert.deepEqual(p.appearance.missing,['forehead']);
// the bar shows the score; the old bands are not applied to it
const seen={id:'rosacea',region:'nose',status:'seen',appearance:reg(1000,400,12),severity:70};
assert.equal(Rec.findingScore(seen),seen.appearance.score);assert.equal(Rec.recommendationBand(seen),null);
assert.equal(Rec.findingScore({id:'melasma',region:'leftCheek',status:'seen',areaPct:12,appearanceUnavailable:'AFFECTED_MASK_NOT_AVAILABLE'}),undefined);
// same method: 60 -> 30 = 30 points down; appearance vs the old area measure: not compared
// raw values that give exactly 60 (30 % area, +9.6 a*) and 30 (15 %, +4.8): the score always comes from the raw values
const mk=(id,ts,a,i)=>rec(id,ts,[st('rosacea','nose','seen',{appearance:reg(1000,a,i)})]);
assert.equal(A.appearanceScore(.3,9.6),60);assert.equal(A.appearanceScore(.15,4.8),30);
let c=H.compareRecords(mk('b','2026-10-22T10:00:00Z',150,4.8),mk('a','2026-10-21T10:00:00Z',300,9.6))[0];
assert.deepEqual([c.now.kind,c.change.kind,c.change.delta],['appearance','down',30]);
c=H.compareRecords(mk('b','2026-10-22T10:00:00Z',150,4.8),rec('o','2026-10-20T10:00:00Z',[st('rosacea','nose','seen',{areaPct:20})]))[0];
assert.deepEqual([c.change.kind,c.change.why],['incomparable','DIFFERENT_MEASURE']);
// parity input for the python implementation
console.log(JSON.stringify([[.0,0],[.1,6],[.25,10],[.5,16],[.33,7.5],[.9,40]].map(([a,i])=>A.appearanceScore(a,i))));
''')
    import skin_appearance as SA
    ts = json.loads(out.strip().splitlines()[-1])
    assert ts == [SA.score(a, i) for a, i in [(.0, 0), (.1, 6), (.25, 10), (.5, 16), (.33, 7.5), (.9, 40)]]
    assert SA.region(0, 0, 0) is None and SA.region(100, 120, 5) is None and SA.pool([None]) is None
    r = SA.region(1000, 200, 10.0)
    assert r['areaPct'] == 20.0 and r['score'] == SA.score(0.2, 10.0)
    p = SA.pool([SA.region(1000, 200, 10.0), SA.region(3000, 0, 0.0)])
    assert p['areaPct'] == 5.0 and p['intensity'] == 10.0
