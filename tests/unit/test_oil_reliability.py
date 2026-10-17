"""Oil support/quality contracts, not sebum or flash/cosmetic accuracy."""
import copy,json,subprocess,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from skin_general import general_result,OIL_REGIONS,OIL_SAMPLING

def sample():
    visible=np.ones((30,30),bool);skin=visible.copy();skin[:5]=False
    masks={n:skin.copy() for n in OIL_REGIONS};masks['periorbital']=~skin
    response={n:[dict(id='tone',quality='valid',value=0),dict(id='oil',quality='valid',value=0)] for n in OIL_REGIONS}
    return response,masks,visible

def run(response,masks,visible,signal,quality=True,scale=1):
    result=general_result(response,masks,visible,signal*0,signal*0,signal,signal*0,
        dict(sourcePixels=float(visible.sum()/scale**2),analysisPixels=int(visible.sum())),{},quality,analysis_scale=scale)
    return {r['id']:r for r in result['measurements']}

def test_unmeasured_eye_signal_cannot_create_whole_face_oil():
    response,masks,visible=sample();signal=np.zeros(visible.shape);signal[:5]=1
    result=run(response,masks,visible,signal)['oil']
    assert result['value']==0 and result['quality']=='valid'
    assert result['evaluatedArea']['analysisPixels']==750
    assert result['components']['samplingSupportVersion']==OIL_SAMPLING

@pytest.mark.parametrize('failure',['GLARE_OR_EXPOSURE','INSUFFICIENT_VISIBLE_AREA'])
def test_one_region_unavailable_is_not_normal_overview_or_other_region_failure(failure):
    response,masks,visible=sample()
    response['nose'][1].update(value=None,quality='insufficient',limitationCode=failure)
    before=copy.deepcopy(response);result=run(response,masks,visible,np.zeros(visible.shape))
    assert result['oil']['value'] is None and result['oil']['quality']=='insufficient'
    assert result['oil']['limitationCode']==('GLARE_OR_EXPOSURE' if failure=='GLARE_OR_EXPOSURE' else 'INSUFFICIENT_FRONT_COVERAGE')
    assert result['oil']['components']['missingRegions']=={'nose':failure}
    assert result['tone']['value']==0 and result['tone']['quality']=='valid'
    assert response==before and response['leftCheek'][1]['quality']=='valid'

def test_valid_highlight_uses_unique_measured_source_support_at_real_scale():
    response,masks,visible=sample();signal=np.zeros(visible.shape);signal[10:15]=.5
    result=run(response,masks,visible,signal,scale=.5)['oil']
    assert result['value']==pytest.approx(20.) # 150/750; overlapping meshes counted once.
    assert result['evaluatedArea']['sourcePixels']==3000
    assert result['components']['uniqueAnalysisPixels']==750

def test_missing_region_or_failed_capture_never_supplies_a_valid_zero():
    response,masks,visible=sample();del response['nose']
    assert run(response,masks,visible,np.zeros(visible.shape))['oil']['value'] is None
    response,masks,visible=sample()
    result=run(response,masks,visible,np.ones(visible.shape),quality=False)['oil']
    assert result['value'] is None and result['limitationCode']=='CAPTURE_QUALITY'

def test_oil_history_distinguishes_new_union_in_overview_and_regions_without_rewrite():
    script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts'),A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts');
for(const scope of ['overview','nose']){
 const row=(normalization,sampling)=>({id:'oil',score:8,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:normalization,region:scope,unit:'appearance-score-0-100',value:8,quality:'valid',components:sampling?{samplingSupportVersion:sampling}:{}},measurement:{scope:scope==='overview'?'whole-face':'regional',region:scope,methodVersion:'appearance-cv-6',unit:'appearance-score-0-100',rawValue:8,quality:'valid',modelHash:null,validation:'appearance-proxy'}});
 const record=(id,entry)=>({id,date:'2026-10-17T00:00:00Z',indicators:scope==='overview'?{}:{nose:[entry]},...(scope==='overview'?{general:{indicators:[entry]}}:{})});
 const oldRow=row('visible-specular-area-fixed-v1',null),newRow=row('visible-specular-area-fixed-v1+regional-quality-union-v2','oil-regional-quality-unique-visible-union-v2');
 const old=record('old',oldRow),now=record('new',newRow),before=JSON.stringify(old);
 assert(!I.canCompareIndicator(newRow,oldRow));A.compareAppearance(newRow,oldRow,true,'old');assert.equal(newRow.referenceDelta,undefined);
 assert.equal(H.buildHistorySeries('skin',[old,now]).filter(v=>v.region===scope&&v.criterion==='oil').length,2);assert.equal(JSON.stringify(old),before);
}'''
    subprocess.run(['node','-e',script],cwd=ROOT,check=True,timeout=30)
