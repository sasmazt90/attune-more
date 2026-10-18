"""Overview provenance, legacy compatibility and no duplicated source weighting."""
from pathlib import Path
import json,subprocess,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_general import general_result

def test_union_score_not_average_of_overlapping_region_scores():
    valid=np.ones((20,20),bool);masks={k:valid for k in ['forehead','rightCheek','leftCheek','chin','nose']}
    tone=np.zeros((20,20),np.float32);tone[:10]=20
    result=general_result({},masks,valid,tone,tone,tone/100,tone/100,{'sourcePixels':400,'analysisPixels':400},{},True)
    rows={r['id']:r for r in result['measurements']}
    assert rows['tone']['value']==10 and rows['tone']['components']['uniqueAnalysisPixels']==400
    assert rows['sag']['value'] is None and rows['bags']['value'] is None
    assert result['skinType']['value'] is None
    invalid=general_result({},masks,valid,tone,tone,tone/100,tone/100,{'sourcePixels':400},{},False)
    assert all(r['value'] is None for r in invalid['measurements'])

def test_new_overview_and_old_six_views_stay_distinct():
    script=r'''
require('./tests/unit/ts_loader.js');
const assert=require('assert/strict'),v=require('./apps/vehicle-app/src/utils/skinOverview.ts');
const old={schemaVersion:3,indicators:{}};assert.equal(v.skinViewOrder(old).length,6);assert.equal(old.general,undefined);
const legacy={indicators:{forehead:[{id:'sag',score:.02,appearance:{type:'longitudinal_measurement',unit:'normalized-contour-ratio'}}]}};
const oldBytes=JSON.stringify(legacy),display=v.buildSkinViewModel('forehead',legacy).indicators;
assert.equal(display[0].label,'Sarkma');assert.equal(JSON.stringify(legacy),oldBytes);
assert.equal(v.buildSkinViewModel('forehead',legacy).indicators[0].score,.02);
assert.equal(v.skinViewOrder(legacy).length,6);assert.equal(legacy.general,undefined);
const general={schemaVersion:1,analysisId:'analysis-a',captureId:'a'.repeat(64),pose:'FRONT',normalizationVersion:'fixed-v1',sourceTransform:{sourceWidth:1280,sourceHeight:720,coordinateSpace:'source-pixels'},skinType:{value:null,quality:'insufficient',confidence:null,methodVersion:'unavailable',modelHash:null},indicators:['tone','oil','redness','acne','sag','dry','lines','dark','bags'].map(id=>({id,score:null,measurement:{scope:'whole-face',region:'overview',methodVersion:'source-v1',rawValue:null,quality:'insufficient',unavailableReason:'NO_SUPPORT'}}))};
const current={...old,id:'analysis-a',general};assert.equal(v.skinViewOrder(current).length,7);assert.equal(v.skinViewOrder(current)[0],'overview');
assert.equal(v.buildSkinViewModel('overview',current).index,1);assert.equal(v.buildSkinViewModel('forehead',current).index,2);assert.equal(v.buildSkinViewModel('forehead',old).index,1);
assert(v.validSkinOverview(general,'analysis-a'));assert(!v.validSkinOverview(general,'analysis-b'));
general.skinType.value='oily';assert(!v.validSkinOverview(general,'analysis-a'));general.skinType.value=null;
general.indicators[0].score=NaN;assert(!v.validSkinOverview(general,'analysis-a'));
'''
    result=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr

def test_eye_only_coverage_and_failed_accepted_method_are_not_whole_face_fallbacks():
    valid=np.ones((20,20),bool);signal=np.ones((20,20),np.float32)
    eye=dict(id='dark',value=19.,quality='valid',methodVersion='relative-eye-v1',components={},evaluatedArea={'sourcePixels':400})
    failed=dict(id='bags',value=None,quality='insufficient',methodVersion='accepted-mask-v1',components={'analyticSubstitutionBlocked':True},limitationCode='ACCEPTED_MODEL_UNAVAILABLE')
    value=general_result({'periorbital':[eye,failed]},{'periorbital':valid},valid,signal,signal,signal,signal,{'sourcePixels':400},{},True)
    rows={r['id']:r for r in value['measurements']}
    assert rows['dark']['value']==19 and rows['dark']['evaluatedArea']['sourcePixels']==400
    assert rows['bags']['value'] is None and rows['bags']['limitationCode']=='ACCEPTED_MODEL_UNAVAILABLE'
    assert all(rows[k]['value'] is None for k in ['tone','oil','redness','sag','dry','acne'])


def test_whole_photo_grade_cannot_inherit_a_different_pixel_calibration(monkeypatch):
    import appearance_analysis as A
    from test_local_appearance_health import skin_input
    def degree(*args,**kwargs):return dict(skinType=None,degrees={'redness':dict(value=60.,rawGrade=3.,methodVersion='accepted-photo-grade-v1',modelHash='a'*64,normalizationVersion='ordinal-0-5-times-20-v1')},models={},sourceTransform=None)
    monkeypatch.setattr(A,'infer_skin_models',degree)
    result=A.analyze_skin(skin_input(np.full((400,500,3),(100,130,175),np.uint8)))
    red=next(r for r in result['general']['measurements'] if r['id']=='redness')
    assert red['value']==60 and red['localMap'] is None
    assert 'overview:redness' not in result['maps']
    assert result['activeCriterionMethods']['criteria']['redness']['overview']['methodVersion']=='accepted-photo-grade-v1'
    for layer in result['maps'].values():
        owner=next(r for r in result['measurements'].get(layer['region'],result['general']['measurements']) if r['id']==layer['criterion'])
        assert layer['calibrationVersion']==owner['calibrationVersion']


def test_partial_lower_face_is_measured_without_inventing_hidden_side_or_duplicating_folds():
 valid=np.ones((20,20),bool);signal=np.zeros((20,20),np.float32)
 def row(region,value,sides,quality='valid'):
  return dict(id='sag',region=region,value=value,quality=quality,methodVersion='target-roi-v3',components={'sides':sides},evaluatedArea={'sourcePixels':40},limitationCode=None if quality=='valid' else 'ANATOMICAL_BAND_NOT_VISIBLE')
 right=row('rightCheek',12,[{'side':'right','value':8},{'side':'lower-right','value':16}])
 chin=row('chin',16,[{'side':'lower-right','value':16},{'side':'lower-left','value':None}])
 left=row('leftCheek',None,[],'insufficient')
 result=general_result({'rightCheek':[right],'leftCheek':[left],'chin':[chin]},{'rightCheek':valid},valid,signal,signal,signal,signal,{}, {},True)
 sag=next(r for r in result['measurements'] if r['id']=='sag')
 assert sag['value']==12 and sag['components']['partialCoverage']
 assert sag['components']['missingRegions']=={'leftCheek':'ANATOMICAL_BAND_NOT_VISIBLE'}
 assert sag['components']['measuredSides']=={'right':8,'lower-right':16}
 assert sag['components']['wholeFaceInference'] is False
