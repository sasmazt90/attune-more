"""Tracking quality is evidence quality, not arbitrary argmax coordinates."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import instant_appearance as I

def test_unsupported_argmax_jumps_cannot_change_supported_run_residual():
 line=np.c_[np.arange(64),np.zeros(64)];selected=line.copy().astype(float)
 selected[8:20,1]=np.linspace(1,2,12);selected[35:48,1]=np.linspace(7,8,13)
 observed=np.ones(64,bool);supported=np.zeros(64,bool);supported[8:20]=True;supported[35:48]=True
 before=I.observed_fold_tracking(selected,line,320,observed,supported)
 selected[~supported,1]=np.where(np.arange(64)[~supported]%2,1000,-1000)
 after=I.observed_fold_tracking(selected,line,320,observed,supported)
 assert before['residual']==after['residual']
 assert after['residual']<.2 and after['trackedFoldSamples']==25
 assert [s['start'] for s in after['segments']]==[8,35]
 # The real unsupported jump can make the old all-point quality arbitrarily bad.
 assert I.tracking_residual(selected,line,320)>100

def test_invalid_hole_splits_runs_and_never_becomes_a_tracking_point():
 line=np.c_[np.arange(64),np.zeros(64)];selected=line.copy().astype(float)
 observed=np.ones(64,bool);observed[20:25]=False;selected[20:25]=np.nan
 result=I.observed_fold_tracking(selected,line,320,observed,np.ones(64,bool))
 assert result['residual']==0 and result['trackedFoldSamples']==59
 assert result['segments']==[dict(start=0,endExclusive=20,residual=0.),dict(start=25,endExclusive=64,residual=0.)]
 assert not result['accepted'][20:25].any()

def test_fragmented_support_and_no_fold_are_different_states():
 line=np.c_[np.arange(64),np.zeros(64)].astype(float);seen=np.ones(64,bool)
 assert I.observed_fold_tracking(line,line,320,seen,np.zeros(64,bool))['status']=='no-fold-observed'
 short=np.zeros(64,bool);short[1:4]=True;short[8:10]=True
 result=I.observed_fold_tracking(line,line,320,seen,short)
 assert result['status']=='fragmented-fold-support' and result['residual'] is None
 assert not result['accepted'].any()
 assert I.observed_fold_tracking(line,line,320,np.zeros(64,bool),short)['status']=='unobserved'

def test_real_profile_does_not_assign_invalid_argmax_source_coordinates():
 gray=np.full((128,128),.5,np.float32);all_seen=np.ones_like(gray,bool);guide=[[10,64],[110,64]]
 no_fold=I.curve_profile(gray,all_seen,guide,np.array([0,1]),np.arange(-10,11),320,all_seen,True)
 assert no_fold['coverage']==1 and no_fold['trackingStatus']=='no-fold-observed'
 assert no_fold['trackingResidual'] is None and np.isfinite(no_fold['tracked']).all()
 invisible=I.curve_profile(gray,all_seen,guide,np.array([0,1]),np.arange(-10,11),320,np.zeros_like(all_seen),True)
 assert invisible['coverage']==0 and invisible['trackingStatus']=='unobserved'
 assert np.isnan(invisible['tracked']).all() and not invisible['support'].any()

def test_v8_v9_history_and_mesh_support_are_distinct_without_rewrite():
 script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts'),S=require('./apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts'),A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts');
for(const scope of ['overview','chin']){
 const row=(norm,sampling)=>({id:'sag',score:8,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:norm,region:scope,unit:'appearance-score-0-100',value:8,quality:'valid',components:{samplingSupportVersion:sampling}},measurement:{scope:scope==='overview'?'whole-face':'regional',region:scope,methodVersion:'appearance-cv-6',unit:'appearance-score-0-100',rawValue:8,quality:'valid',modelHash:null,validation:'appearance-proxy'}});
 const a=row('contour-fold-lower-chin-visible-region-v8','lower-chin-visible-region-unique-centers-v8'),b=row('contour-fold-lower-chin-observed-runs-v9','lower-chin-observed-fold-runs-unique-centers-v9');assert(!I.canCompareIndicator(a,b));A.compareAppearance(b,a,true,'old');assert.equal(b.referenceDelta,undefined);
 const record=(id,r)=>({id,date:'2026-10-13T00:00:00Z',indicators:scope==='overview'?{}:{chin:[r]},...(scope==='overview'?{general:{indicators:[r]}}:{})});const old=record('old',a),now=record('new',b),before=JSON.stringify(old);assert.equal(H.buildHistorySeries('skin',[old,now]).filter(r=>r.region===scope&&r.criterion==='sag').length,2);assert.equal(JSON.stringify(old),before);
 assert(S.closedSurfaceSupportEnabled('sag',a.appearance.normalizationVersion));assert(S.closedSurfaceSupportEnabled('sag',b.appearance.normalizationVersion));
}
'''
 subprocess.run(['node','-e',script],cwd=ROOT,check=True,timeout=30)
