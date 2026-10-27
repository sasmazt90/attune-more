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


def test_inconclusive_findings_stay_visible_in_history():
    """Reviewer counter-examples: a finding this scan could not confirm is never hidden behind "no findings seen", and the
    detail lists it even when no record ever saw it (no "seen before" condition)."""
    run(PRELUDE + r'''
const ri=(x={})=>st('rosacea','nose','inconclusive',{causes:['ANGLE'],...x});
// (a) acne measured absent + rosacea inconclusive -> not "none-seen"; rosacea named as not confirmed
const a=rec('a','2026-10-21T10:00:00Z',[st('acne','forehead','notSeen'),ri()]);
let s=H.recordSummary(a,'tr-TR');assert.notEqual(s.state,'none-seen');assert.deepEqual(s.items,[]);assert.deepEqual(s.inconclusive,['rosacea']);
let rows=H.compareRecords(a,undefined);assert.deepEqual(rows.map(x=>[x.id,x.now.state,x.change.kind]),[['rosacea','inconclusive','none']]);   // no previous record: nothing to compare
// with a previous record where rosacea was measured absent (never seen): still listed
const prevNo=rec('p','2026-10-20T10:00:00Z',[st('acne','forehead','notSeen'),st('rosacea','nose','notSeen')]);
rows=H.compareRecords(a,prevNo);assert.equal(row(rows,'rosacea').now.state,'inconclusive');assert(!['up','down','same','new','gone'].includes(row(rows,'rosacea').change.kind));   // no change is claimed from an unknown state
// (b) acne seen count 3 + rosacea inconclusive -> summary shows acne 3 and rosacea not confirmed; detail has both
const b=rec('b','2026-10-22T10:00:00Z',[acne(3),ri()]);
s=H.recordSummary(b,'tr-TR');assert.equal(s.state,'measured');assert.deepEqual(s.items.map(x=>[x.id,x.value]),[['acne','3']]);assert.deepEqual(s.inconclusive,['rosacea']);
for(const prev of [undefined,prevNo]){rows=H.compareRecords(b,prev);assert.equal(row(rows,'acne').now.value,3);assert.equal(row(rows,'rosacea').now.state,'inconclusive');}
// a seen finding is not listed again as inconclusive; an unavailable analysis lists nothing as inconclusive
s=H.recordSummary(rec('c','2026-10-22T10:00:00Z',[acne(3),st('acne','nose','inconclusive')]),'tr-TR');assert.deepEqual(s.inconclusive,[]);
assert.deepEqual(H.compareRecords(rec('u','2026-10-22T10:00:00Z',[ri()],{status:'unavailable',reason:'FUSION_FAILED'}),undefined),[]);
// unchanged: only measured absences -> "none-seen"
assert.equal(H.recordSummary(rec('n','2026-10-22T10:00:00Z',[st('acne','forehead','notSeen'),st('rosacea','nose','notSeen')]),'tr-TR').state,'none-seen');
''')


def test_appearance_rounding_parity_server_client():
    """Reviewer counter-example: usablePx=40000, affectedPx=10201, intensity=8 -> 50.5 before rounding. Server (Python),
    record and screen (TypeScript) must carry the same score: one half-up rule in both."""
    import skin_appearance as SA
    cases = [(40000, 10201, 8.0), (1000, 300, 9.6), (1000, 150, 4.8), (3000, 30, 5.0), (987, 123, 7.333), (5000, 4999, 31.2),
             (1234, 0, 0.0), (77777, 1111, 3.005), (40000, 10201, 8.004), (12000, 2550, 12.345)]
    pools = [[0, 1], [0, 3, 4], [2, 6, 7], [8, 9]]
    py_regions = [SA.region(*c) for c in cases]
    py_pools = [SA.pool([py_regions[i] for i in p]) for p in pools]
    assert py_regions[0]['score'] == 51
    out = run(PRELUDE + r'''
const cases=''' + json.dumps(cases) + r''',pools=''' + json.dumps(pools) + r''';
// a region as the client receives it from the API (raw values), re-scored and re-pooled on the client
const reg=([u,a,i])=>{const inten=a?A.roundHalfUp(i,2):0;return {version:'appearance-v1',usablePx:u,affectedPx:a,areaPct:A.roundHalfUp(100*a/u,2),intensity:inten,score:A.appearanceScore(a/u,inten)};};
assert.equal(A.appearanceScore(10201/40000,8),51);
const one=A.poolAppearance([reg(cases[0])]);assert.equal(one.score,51);
// the record -> history -> screen path keeps 51
const r=rec('x','2026-10-22T10:00:00Z',[st('rosacea','nose','seen',{appearance:reg(cases[0])})]);
assert.equal(H.measureOf(H.resultOf(r),'rosacea',['nose']).value,51);assert.equal(H.formatValue(H.measureOf(H.resultOf(r),'rosacea',['nose']),'tr-TR'),'51');
console.log(JSON.stringify({regions:cases.map(reg),pools:pools.map(p=>A.poolAppearance(p.map(i=>reg(cases[i]))))}));
''')
    ts = json.loads(out.strip().splitlines()[-1])
    assert ts['regions'] == py_regions, (ts['regions'], py_regions)
    assert ts['pools'] == py_pools, (ts['pools'], py_pools)
    # the half-up rule itself, at exact halves
    assert [SA.round_half_up(x) for x in (50.5, 49.5, 0.5, 99.5)] == [51, 50, 1, 100]
