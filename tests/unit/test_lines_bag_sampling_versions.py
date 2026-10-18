"""Sparse corrupt pixels, coherent folds and real history version separation."""
import subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import isolated_impulse_sampling

def test_sparse_impulses_removed_without_blurring_coherent_fold_or_skin_texture():
    source=np.full((40,60,3),150,np.uint8)
    source[20,10:45]=30  # a coherent fine dark fold must survive intact
    source[4,4]=0;source[30,50]=255
    source[32:35,12:15]=135  # normal low contrast texture remains
    before=source.copy();sampled,mask=isolated_impulse_sampling(source)
    assert np.array_equal(source,before)
    assert mask.sum()==2 and mask[4,4] and mask[30,50]
    assert np.all(sampled[4,4]==150) and np.all(sampled[30,50]==150)
    assert np.array_equal(sampled[~mask],before[~mask])
    assert np.array_equal(sampled[20,10:45],before[20,10:45])

def test_lines_v3_v4_and_bag_v2_v3_split_region_and_nested_overview_history():
    code=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict');
const I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts');
function row(id,norm,sampler,overview){const raw={samplingSupportVersion:sampler};return {id,label:'old label',score:7,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:norm,unit:'index',region:overview?'whole-face':'periorbital',value:7,quality:'valid',components:overview?{sourceComponents:raw}:raw},measurement:{scope:overview?'whole-face':'regional',region:overview?'whole-face':'periorbital',methodVersion:'appearance-cv-6',unit:'index',rawValue:7,modelHash:null,quality:'valid',validation:'appearance-proxy'}};}
for(const id of ['lines','bags']){
 const versions=id==='lines'?['outer-canthus-gabor-radiating-hair-excluded-v3','outer-canthus-gabor-radiating-hair-excluded-v4']:['contour-fold-local-support-v5','contour-fold-local-support-v5'];
 const samplers=id==='bags'?['tracked-center-closed-cells-v2','tracked-center-closed-cells-impulse-v3']:[null,null];
 const records=versions.map((norm,i)=>({id:'record'+i,date:`2026-10-${11+i}T10:00:00Z`,indicators:{periorbital:[row(id,norm,samplers[i],false)]},general:{indicators:[row(id,norm,samplers[i],true)]}}));
 const bytes=JSON.stringify(records[0]);
 for(const scope of ['overview','periorbital']){
  const get=r=>(scope==='overview'?r.general.indicators:r.indicators.periorbital)[0],old=get(records[0]),now=get(records[1]);assert.equal(I.canCompareIndicator(now,old),false);A.compareAppearance(now,old,true,records[0].id);assert.equal(now.referenceDelta,undefined);
  assert.equal(H.buildHistorySeries('skin',records).filter(s=>s.region===scope&&s.criterion===id).length,2);
 }
 assert.equal(JSON.stringify(records[0]),bytes);
}
'''
    subprocess.run(['node','-e',code],cwd=ROOT,check=True,capture_output=True,text=True,encoding='utf8')
