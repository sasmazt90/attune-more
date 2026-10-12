import json,subprocess,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A

def node(code):
    p=subprocess.run(['node','-e',"require('./tests/unit/ts_loader.js');"+code],cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=30)
    assert p.returncode==0,p.stdout+p.stderr

def test_central_labels_all_views_preserve_correct_and_corrupt_history():
    node(r"""
const assert=require('assert/strict'),V=require('./apps/vehicle-app/src/utils/skinOverview.ts'),I=require('./apps/vehicle-app/src/utils/skinIndicators.ts');
assert.equal(I.SIGN_LABELS.tone,'Ton eşitsizliği');assert.equal(I.SIGN_LABELS.oil,'Yağlı görünüm');assert.equal(I.SIGN_LABELS.redness,'Kızarıklık eğilimi');assert.equal(I.SIGN_LABELS.acne,'Sivilce görünümü');
for(const corrupt of [false,true]){
 const make=(id,scope)=>({id,label:corrupt?Buffer.from(I.skinCriterionLabel(id,scope),'utf8').toString('latin1'):I.skinCriterionLabel(id,scope),score:7,method:'preserved',unit:'%',reason:'çğıİöşü'});
 const r={indicators:Object.fromEntries(V.SKIN_VIEW_ORDER.slice(1).map(id=>[id,I.indicatorIds(id).map(x=>make(x,'regional'))])),general:{indicators:Object.keys(I.SIGN_LABELS).map(x=>make(x,'whole-face'))}};
 r.general.indicators.push({id:'future-unknown',label:'çğıİöşü / 体',score:4});const before=JSON.stringify(r);
 for(const id of V.SKIN_VIEW_ORDER){const rows=V.buildSkinViewModel(id,r).indicators;for(const row of rows){assert.equal(row.label,row.id==='future-unknown'?'çğıİöşü / 体':I.skinCriterionLabel(row.id,id==='overview'?'whole-face':'regional'));assert.equal(row.score,row.id==='future-unknown'?4:7);}}
 assert.equal(JSON.stringify(r),before);
}
""")

def test_closed_eye_cells_fill_without_changing_visible_edges_or_other_rois():
    node(r"""
const assert=require('assert/strict'),M=require('./apps/vehicle-app/src/utils/skinMesh.ts'),S=require('./apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts');
const m={points:[{x:0,y:0},{x:20,y:0},{x:20,y:20},{x:0,y:20}],edges:[[0,1],[1,2],[2,3],[3,0]],major:[],boundary:[],excluded:[],bagCells:[[0,1,2,3]]},before=JSON.stringify(m);
assert.equal(S.meshTriangles(m).length,0);assert.equal(S.meshTriangles(m,true).length,2);assert.equal(JSON.stringify(m),before);
assert.equal(M.bagCellTriangles({...m,edges:m.edges.slice(1)}).length,0);
assert.equal(M.bagCellTriangles({...m,bagCells:[[0,2,1,3]]}).length,0);
""")
    mesh=dict(points=[dict(x=10,y=10),dict(x=30,y=10),dict(x=30,y=30),dict(x=10,y=30)],edges=[[0,1],[1,2],[2,3],[3,0]],bagCells=[[0,1,2,3]])
    old=A.polygon_mask((50,50),mesh,1);new=A.bag_support_mask((50,50),mesh,1)
    assert not old.any() and new[10:31,10:31].all()
    assert not new[:10].any() and not new[:,31:].any()
    with pytest.raises(ValueError,match='UNSUPPORTED_BAG_CELL'):A.bag_support_mask((50,50),{**mesh,'edges':mesh['edges'][1:]},1)

def test_sampling_versions_block_delta_and_split_history_within_same_v5():
    node(r"""
const assert=require('assert/strict'),I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts');
const row=s=>({id:'bags',label:'old label',score:7,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:'contour-fold-local-support-v5',unit:'contour-fold-index-0-100',value:7,quality:'valid',components:{samplingSupportVersion:s}},measurement:{scope:'regional',region:'periorbital',methodVersion:'appearance-cv-6',unit:'contour-fold-index-0-100',rawValue:7,modelHash:null,quality:'valid',validation:'appearance-proxy'}});
const old={id:'old',date:'2026-10-11T10:00:00Z',indicators:{periorbital:[row('tracked-center-eligible-v1')]}},now={id:'new',date:'2026-10-12T10:00:00Z',indicators:{periorbital:[row('tracked-center-closed-cells-v2')]}},bytes=JSON.stringify(old);
assert(I.canCompareIndicator(old.indicators.periorbital[0],structuredClone(old.indicators.periorbital[0])));assert(!I.canCompareIndicator(now.indicators.periorbital[0],old.indicators.periorbital[0]));A.compareAppearance(now.indicators.periorbital[0],old.indicators.periorbital[0],true,'old');assert.equal(now.indicators.periorbital[0].referenceDelta,undefined);
const series=H.buildHistorySeries('skin',[old,now]).filter(x=>x.criterion==='bags');assert.equal(series.length,2);for(const s of series)assert.equal(s.points.filter(p=>p.value!==null).length,1);assert.equal(JSON.stringify(old),bytes);
const overview=(r,id)=>{const copy=structuredClone(r.indicators.periorbital[0]);copy.measurement.scope='whole-face';copy.measurement.region='overview';copy.appearance.region='overview';copy.appearance.components={sourceRegion:'periorbital',sourceComponents:copy.appearance.components};return {id,date:r.date,indicators:{},general:{indicators:[copy]}};};
const a=overview(old,'old-general'),b=overview(now,'new-general'),prior=JSON.stringify(a);
assert(!I.canCompareIndicator(b.general.indicators[0],a.general.indicators[0]));A.compareAppearance(b.general.indicators[0],a.general.indicators[0],true,'old-general');assert.equal(b.general.indicators[0].referenceDelta,undefined);assert.equal(H.buildHistorySeries('skin',[a,b]).filter(s=>s.region==='overview'&&s.criterion==='bags').length,2);assert.equal(JSON.stringify(a),prior);
""")

def test_closed_cells_do_not_turn_capture_failure_into_healthy_zero():
    from test_local_appearance_health import photo,landmarks
    image=np.full((320,320,3),150,np.uint8);url,digest=photo(image)
    mesh=dict(points=[dict(x=5,y=5),dict(x=315,y=5),dict(x=315,y=315),dict(x=5,y=315)],edges=[[0,1],[1,2],[2,3],[3,0]],bagCells=[[0,1,2,3]])
    result=A.analyze_skin(dict(photo=url,photoId=digest,landmarks=landmarks(),meshes={'periorbital':mesh},exclusions=[],pose='FRONT',qualityValid=False,conditions=dict(yaw=0.,pitch=0.)))
    bag=next(v for v in result['measurements']['periorbital'] if v['id']=='bags')
    assert bag['value'] is None and bag['limitationCode']=='CAPTURE_QUALITY'
    assert bag['components']['samplingSupportVersion']=='tracked-center-closed-cells-v2'
    assert 'periorbital:bags' not in result['maps']
