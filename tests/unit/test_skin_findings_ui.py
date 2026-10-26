"""Result-screen findings states, per-photo markers, date range, history day boundaries and score bands (approved UI)."""
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def run(script):
    r = subprocess.run(['node', '-e', "require('./tests/unit/ts_loader.js');\n" + script], cwd=ROOT, text=True, capture_output=True, encoding='utf8', timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_findings_state_markers_and_bands():
    run(r'''
const assert=require('assert/strict');
const F=require('./apps/vehicle-app/src/utils/skinFindings.ts'),Rec=require('./apps/vehicle-app/src/utils/skinRecommendations.ts');
const O=require('./apps/vehicle-app/src/utils/skinOverview.ts');
// states: absent analysis, not measured, measured
assert.equal(F.findingsState(undefined).kind,'missing');
assert.equal(F.findingsState({version:'v',status:'unavailable',reason:'REQUIRED_POSES_MISSING',findings:[]}).kind,'unavailable');
const measured={version:'v',status:'measured',findings:[],unavailable:[{id:'acne',reason:'MODEL_NOT_AVAILABLE'},{id:'eyeBags',reason:'MODEL_NOT_AVAILABLE'}]};
assert.equal(F.findingsState(measured).kind,'measured');
assert.deepEqual(F.unmeasuredFindings(measured,'periorbital').map(u=>u.id),['eyeBags']);
assert(!F.validFindings({version:'v',status:'bogus',findings:[]}));
assert(!F.validFindings({version:'v',findings:[{id:'mole',region:'leftCheek',status:'seen',markers:[{x:NaN,y:1}]}]}));
const off=F.unavailableFindings('FUSION_FAILED');assert.equal(off.status,'unavailable');assert.equal(off.unavailable.length,Object.keys(F.FINDING_DEFS).length);
// markers keep their own photo when two regions of a page are merged (forehead from FRONT, nose from LEFT)
const all=[{id:'mole',region:'forehead',status:'seen',pose:'FRONT',markers:[{x:1,y:1}]},{id:'mole',region:'nose',status:'seen',pose:'LEFT',markers:[{x:2,y:2}]}];
const page=F.viewFindings(all,'forehead')[0];
assert.deepEqual(F.markersOnPhoto(page,'FRONT').map(m=>m.x),[1]);
assert.deepEqual(F.markersOnPhoto(page,'LEFT').map(m=>m.x),[2]);
assert.deepEqual(F.markersOnPhoto({id:'mole',region:'chin',status:'seen',markers:[{x:3,y:3}]},'FRONT'),[]);  // unknown photo: not drawn
// a missing score or count never selects the lowest band; single-band findings need no value
assert.equal(Rec.recommendationBand({id:'rosacea',region:'nose',status:'seen'}),null);
assert.equal(Rec.recommendationBand({id:'mole',region:'leftCheek',status:'seen'}),null);
assert.equal(Rec.recommendationBand({id:'acne',region:'chin',status:'seen',countRange:'??'}),null);
assert.equal(Rec.recommendationBand({id:'rosacea',region:'nose',status:'seen',severity:45}).index,2);
assert.equal(Rec.recommendationBand({id:'mole',region:'leftCheek',status:'seen',countRange:'4-10'}).index,1);
assert.equal(Rec.recommendationBand({id:'coldSore',region:'chin',status:'seen'}).index,0);
// the server findings travel into the overview record
const resp={photoId:'a'.repeat(64),sourceWidth:100,sourceHeight:100,measurements:{},maps:{},general:{skinType:{value:null,quality:'insufficient',confidence:null,methodVersion:'m',modelHash:null,limitationCode:null},measurements:[],normalizationVersion:'n',findings:measured}};
assert.deepEqual(O.overviewFromResponse(resp).findings,measured);
assert.equal(O.overviewFromResponse({...resp,general:{...resp.general,findings:{bad:1}}}).findings,undefined);
''')


def test_date_range_and_history_day_boundaries():
    run(r'''
const assert=require('assert/strict');
const D=require('./apps/vehicle-app/src/components/skin/SkinDateRangeDialog.tsx');
const d=(y,m,day,h=0)=>new Date(y,m,day,h);
// change the start, then the end can be chosen
let r=D.nextRange(d(2026,9,1),d(2026,9,10),d(2026,9,5));assert.equal(r.to,null);assert.equal(r.from.getDate(),5);
r=D.nextRange(r.from,r.to,d(2026,9,8));assert.equal(r.from.getDate(),5);assert.equal(r.to.getDate(),8);
r=D.nextRange(d(2026,9,5),null,d(2026,9,2));assert.equal(r.from.getDate(),2);assert.equal(r.to.getDate(),5);
// whole local days: nothing from the evening before the start day
const range={from:d(2026,9,5),to:d(2026,9,8)};
assert(!D.inDayRange(d(2026,9,4,18),range));assert(!D.inDayRange(d(2026,9,4,23),range));
assert(D.inDayRange(d(2026,9,5,0),range));assert(D.inDayRange(new Date(2026,9,8,23,59),range));assert(!D.inDayRange(d(2026,9,9,0),range));
''')


def test_panel_never_shows_nothing_found_without_measurement():
    run(r'''
const assert=require('assert/strict'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const {SkinFindingsPanel}=require('./apps/vehicle-app/src/components/skin/SkinFindingsPanel.tsx');
const props={scanAt:'2026-10-26T10:00:00Z',index:0,onIndex:()=>{},onGoToView:()=>{},onNavigateToCare:()=>{},overviewSel:null,onOverviewSel:()=>{}};
const html=(view,result)=>renderToStaticMarkup(React.createElement(SkinFindingsPanel,{...props,view,findings:result&&result.findings,findingsResult:result}));
const missing=html('overview',undefined);
assert(missing.includes('data-skin-findings-empty="missing"'));assert(!missing.includes('görülmedi'));
const off=html('overview',{version:'v',status:'unavailable',reason:'REQUIRED_POSES_MISSING',findings:[],unavailable:[{id:'mole',reason:'REQUIRED_POSES_MISSING'},{id:'acne',reason:'MODEL_NOT_AVAILABLE'}]});
assert(off.includes('data-skin-findings-empty="unavailable"'));assert(off.includes('data-skin-findings-unmeasured="2"'));assert(!off.includes('görülmedi'));
const none=html('chin',{version:'v',status:'measured',findings:[{id:'rosacea',region:'chin',status:'notSeen',pose:'FRONT'}],unavailable:[{id:'coldSore',reason:'MODEL_NOT_AVAILABLE'}]});
assert(none.includes('data-skin-findings-empty="measured"'));assert(none.includes('data-skin-findings-unmeasured="1"'));
// a seen finding without any score: no bar, no invented percentage or band
const seen=html('overview',{version:'v',status:'measured',findings:[{id:'rosacea',region:'nose',status:'seen',pose:'FRONT'},{id:'mole',region:'leftCheek',status:'seen',pose:'RIGHT'}],unavailable:[]});
assert(seen.includes('data-skin-overview-finding="rosacea"')&&seen.includes('data-skin-overview-finding="mole"'));
assert(!/%\d/.test(seen));assert(!seen.includes('role="meter"'));
''')
