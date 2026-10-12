"""Local coherent support and unchanged normalization with split history."""
import subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import coherent_line_signal,LINE_FREQUENCIES

def test_one_filter_cycle_preserves_fine_line_and_rejects_short_spots():
    signal=np.zeros((40,50),np.float32);eligible=np.ones(signal.shape,bool)
    cycle=int(np.ceil(1/min(LINE_FREQUENCIES)))
    signal[3:3+cycle,4]=.03;signal[22:25,20:23]=.2;signal[30,35:35+cycle-1]=.4
    before=signal.copy();actual=coherent_line_signal(signal,eligible)
    assert np.array_equal(signal,before)
    assert np.array_equal(actual[3:3+cycle,4],before[3:3+cycle,4])
    assert not actual[22:25,20:23].any() and not actual[30].any()

def test_unobserved_bridge_cannot_make_short_visible_support_coherent():
    signal=np.zeros((30,30),np.float32);signal[12,5:20]=.15
    eligible=np.ones(signal.shape,bool);eligible[12,10:15]=False
    actual=coherent_line_signal(signal,eligible)
    assert not actual.any()

def test_photometric_sampler_splits_lines_only_in_overview_and_region():
    code=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict');
const I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts');
function row(id,sampler,whole){const components={samplingSupportVersion:sampler};return {id,score:7,unit:'%',method:'appearance-cv-6',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',region:whole?'whole-face':'periorbital',normalizationVersion:id==='lines'?'outer-canthus-gabor-radiating-hair-excluded-v4':'contour-fold-local-support-v5',unit:'index',value:7,quality:'valid',components:whole?{sourceComponents:components}:components},measurement:{scope:whole?'whole-face':'regional',region:whole?'whole-face':'periorbital',methodVersion:'appearance-cv-6',unit:'index',rawValue:7,quality:'valid',modelHash:null,validation:'appearance-proxy'}};}
const records=[0,1].map(i=>({id:'own'+i,date:`2026-10-${12+i}T10:00:00Z`,indicators:{periorbital:[row('lines',i?'native-impulse-one-cycle-lines-v1':null,false),row('bags','tracked-center-closed-cells-impulse-v3',false)]},general:{indicators:[row('lines',i?'native-impulse-one-cycle-lines-v1':null,true),row('bags','tracked-center-closed-cells-impulse-v3',true)]}}));const bytes=JSON.stringify(records[0]);
for(const scope of ['overview','periorbital'])for(const id of ['lines','bags']){
 const get=r=>(scope==='overview'?r.general.indicators:r.indicators.periorbital).find(v=>v.id===id),now=get(records[1]),old=get(records[0]),changed=id==='lines';assert.equal(I.canCompareIndicator(now,old),!changed);A.compareAppearance(now,old,true,records[0].id);assert.equal(now.referenceDelta===undefined,changed);assert.equal(H.buildHistorySeries('skin',records).filter(s=>s.region===scope&&s.criterion===id).length,changed?2:1);
}assert.equal(JSON.stringify(records[0]),bytes);
'''
    subprocess.run(['node','-e',code],cwd=ROOT,check=True,capture_output=True,text=True,encoding='utf8')
