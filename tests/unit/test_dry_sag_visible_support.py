"""Support contracts, not natural-photo accuracy claims."""
import json,subprocess,sys
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
from skin_contract_fixtures import observed_neutral_proxy
from skin_general import general_result
from test_local_appearance_health import photo,landmarks

def mesh():return dict(points=[dict(x=20,y=20),dict(x=300,y=20),dict(x=300,y=300),dict(x=20,y=300)],edges=[[0,1],[1,2],[2,3],[3,0]])

def test_missing_measurement_never_becomes_a_valid_zero():
 assert A.validated_measurement_value(0)==(0.,None)
 assert A.validated_measurement_value(None)==(None,'MEASUREMENT_UNAVAILABLE')
 assert A.validated_measurement_value(float('nan'))==(None,'MEASUREMENT_UNAVAILABLE')
 assert A.validated_measurement_value(12,'DETAIL_MISSING')==(None,'DETAIL_MISSING')
 source=(ROOT/'services/core-api/appearance_analysis.py').read_text('utf8')
 assert 'add(criterion,value or 0' not in source
 assert 'add(criterion,value,INSTANT_UNIT' in source

def test_closed_cells_require_real_convex_boundary_and_match_browser():
 m=mesh();assert A.polygon_mask((320,320),m,1,(0,0)).sum()==0
 assert A.closed_surface_mask((320,320),m,1,(0,0))[100,100]
 opened={**m,'edges':m['edges'][:-1]};assert not A.closed_surface_mask((320,320),opened,1,(0,0)).any()
 script="require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),s=require('./apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts');assert(s.closedSurfaceSupportEnabled('dry','eligible-flake-luma-union-v3'));assert(s.closedSurfaceSupportEnabled('sag','contour-fold-visible-region-unique-centers-v7'));assert(!s.closedSurfaceSupportEnabled('dry','eligible-flake-area-fixed-v2-shared'));assert(!s.closedSurfaceSupportEnabled('sag','contour-fold-target-roi-local-support-v6'));assert(!s.closedSurfaceSupportEnabled('sag'));assert(!s.closedSurfaceSupportEnabled('tone','eligible-flake-luma-union-v3'));console.log(JSON.stringify([s.meshTriangles("+json.dumps(m)+",false,true).length,s.meshTriangles("+json.dumps(opened)+",false,true).length]));"
 assert json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT))==[2,0]

def test_grayscale_texture_does_not_inherit_color_channel_clip_or_quality_override():
 def run(color,quality=True):
  image=np.empty((320,320,3),np.uint8);image[:]=color;url,digest=photo(image)
  return A.analyze_skin(dict(photo=url,photoId=digest,landmarks=landmarks(),meshes={'chin':mesh()},exclusions=[],pose='FRONT',qualityValid=quality,conditions=dict(yaw=0.,pitch=0.)))
 r=run((140,170,255));rows={v['id']:v for v in r['measurements']['chin']}
 assert rows['tone']['value'] is None and rows['tone']['limitationCode']=='GLARE_OR_EXPOSURE'
 assert rows['dry']['value']==0 and rows['dry']['quality']=='valid'
 for r in [run((255,255,255)),run((140,170,255),False)]:
  dry=next(v for v in r['measurements']['chin'] if v['id']=='dry');assert dry['value'] is None and 'chin:dry' not in r['maps']

def test_overview_unique_centers_and_visible_area_omit_missing_side():
 mask=np.ones((20,20),bool);zero=np.zeros((20,20));rows={}
 for region,value in [('rightCheek',20),('leftCheek',None),('chin',80)]:
  rows[region]=[dict(id='sag',value=value,quality='valid' if value is not None else 'insufficient',limitationCode=None if value is not None else 'ANATOMICAL_BAND_NOT_VISIBLE',methodVersion='appearance-cv-6',components={'sides':[dict(side=region,value=value)]},evaluatedArea={'analysisPixels':400})]
 measured=np.zeros_like(mask);measured[:5,:5]=True;centers={(1,1):.2,(2,2):.8}
 r=general_result(rows,{},mask,zero,zero,zero,zero,{'sourcePixels':400},{},True,sag_support=(centers,measured,.5))
 sag=next(v for v in r['measurements'] if v['id']=='sag')
 assert sag['value']==pytest.approx(50) and sag['components']['uniqueObservedCenters']==2
 assert sag['components']['partialCoverage'] and sag['evaluatedArea']['analysisPixels']==25 and sag['evaluatedArea']['sourcePixels']==100
 assert sag['components']['missingRegions']=={'leftCheek':'ANATOMICAL_BAND_NOT_VISIBLE'}
 assert sag['components']['appearanceSemantics']=='visible-lower-face-contour-fold-appearance-v1'
 assert sag['components']['clinicalSeverity'] is False and sag['components']['elasticity'] is False
 assert sag['components']['comparisonMode']=='same-person-compatible-capture-only'

def test_dry_and_sag_history_versions_separate_both_scopes_without_rewrite():
 script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts'),A=require('./apps/vehicle-app/src/utils/appearanceMeasurements.ts');
for(const criterion of ['dry','sag'])for(const scope of ['overview','chin']){
 const row=version=>({id:criterion,score:8,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:version,region:scope,unit:'appearance-score-0-100',value:8,quality:'valid',components:{samplingSupportVersion:version}},measurement:{scope:scope==='overview'?'whole-face':'regional',region:scope,methodVersion:'appearance-cv-6',unit:'appearance-score-0-100',rawValue:8,quality:'valid',modelHash:null,validation:'appearance-proxy'}});
 const record=(id,version)=>({id,date:'2026-10-13T00:00:00Z',indicators:scope==='overview'?{}:{chin:[row(version)]},...(scope==='overview'?{general:{indicators:[row(version)]}}:{})});
 const old=record('old','old'),now=record('new','new'),before=JSON.stringify(old),a=scope==='overview'?now.general.indicators[0]:now.indicators.chin[0],b=scope==='overview'?old.general.indicators[0]:old.indicators.chin[0];
 assert(!I.canCompareIndicator(a,b));A.compareAppearance(a,b,true,'old');assert.equal(a.referenceDelta,undefined);assert.equal(H.buildHistorySeries('skin',[old,now]).filter(v=>v.region===scope&&v.criterion===criterion).length,2);assert.equal(JSON.stringify(old),before);
}'''
 subprocess.run(['node','-e',script],cwd=ROOT,check=True,timeout=30)

@pytest.mark.parametrize('fold,edge,boundary',[(0,.04,.08),(.5,0,.08),(.5,.04,0)])
def test_fold_edge_and_independent_boundary_are_all_required(monkeypatch,fold,edge,boundary):
 import instant_appearance as IA
 def profile(*args,**kwargs):
  return dict(strength=fold,edge=edge,continuity=1.,coverage=1.,trackingResidual=0.,trackingQualityVersion='controlled-gate',tracked=np.tile([160.,160.],(64,1)),values=np.full(64,fold),edgeValues=np.full(64,edge),support=np.full(64,fold>0),observedSamples=np.ones(64,bool))
 monkeypatch.setattr(IA,'curve_profile',profile)
 monkeypatch.setattr(IA,'boundary_support',lambda *args:dict(value=boundary,coverage=1.,points=[],supported=[]))
 gray=np.full((320,320),.5,np.float32)
 value,components,field,_,reason=observed_neutral_proxy(gray,np.ones_like(gray,bool),landmarks(),'chin',dict(yaw=0.,pitch=0.),1,(0,0),gray.shape)
 assert reason is None and value==0 and not field.any()

def test_ordinary_mentolabial_crease_cannot_supply_lower_chin_index(monkeypatch):
 import instant_appearance as IA
 points=landmarks()
 for i,x,y in [(33,.3,.3),(263,.7,.3),(234,.1,.5),(454,.9,.5),(61,.38,.55),(291,.62,.55),(13,.5,.545),(14,.5,.555),
               (201,.42,.65),(200,.5,.65),(421,.58,.65),(170,.35,.78),(208,.43,.78),(199,.5,.78),(428,.57,.78),(395,.65,.78)]:
  points[i]={'x':x,'y':y,'z':0.}
 # Independent contour confirmation alone must not turn a normal lip/chin
 # separation into sag. Real photometric profiles are used for both fields.
 monkeypatch.setattr(IA,'boundary_support',lambda *args:dict(value=.08,coverage=1.,points=[],supported=[]))
 ys=np.arange(320)[:,None];mental=np.broadcast_to(.6-.18*np.exp(-((ys-208)/1.2)**2),(320,320)).astype('float32')
 lower=np.broadcast_to(.6-.18*np.exp(-((ys-249)/1.2)**2),(320,320)).astype('float32')
 def run(gray):return observed_neutral_proxy(gray,np.ones_like(gray,bool),points,'chin',dict(yaw=0.,pitch=0.),1.,(0,0),gray.shape)
 old_crease=run(mental);actual_lower=run(lower)
 assert old_crease[4] is None and old_crease[0]==0 and not old_crease[2].any()
 assert actual_lower[4] is None and actual_lower[0]>0 and actual_lower[2].any()
 assert actual_lower[1]['samplingSupportVersion']=='lower-chin-observed-fold-runs-unique-centers-v9'
 assert actual_lower[1]['appearanceSemantics']=='visible-lower-face-contour-fold-appearance-v1'
 assert actual_lower[1]['clinicalSeverity'] is False and actual_lower[1]['elasticity'] is False
 assert actual_lower[1]['comparisonMode']=='same-person-compatible-capture-only'

def test_v7_and_v8_history_and_render_support_remain_distinct():
 script=r'''
require('./tests/unit/ts_loader.js');const assert=require('assert/strict'),I=require('./apps/vehicle-app/src/utils/skinIndicators.ts'),H=require('./apps/vehicle-app/src/utils/healthHistorySeries.ts'),S=require('./apps/vehicle-app/src/utils/skinSurfaceAnalysis.ts');
for(const scope of ['overview','chin']){
 const row=(normalization,sampling)=>({id:'sag',score:8,method:'appearance-cv-6',unit:'%',appearance:{type:'appearance_proxy',methodVersion:'appearance-cv-6',normalizationVersion:normalization,region:scope,unit:'appearance-score-0-100',value:8,quality:'valid',components:{samplingSupportVersion:sampling}},measurement:{scope:scope==='overview'?'whole-face':'regional',region:scope,methodVersion:'appearance-cv-6',unit:'appearance-score-0-100',rawValue:8,quality:'valid',modelHash:null,validation:'appearance-proxy'}});
 const a=row('contour-fold-visible-region-unique-centers-v7','visible-region-unique-centers-v7'),b=row('contour-fold-lower-chin-visible-region-v8','lower-chin-visible-region-unique-centers-v8');assert(!I.canCompareIndicator(a,b));
 const record=(id,r)=>({id,date:'2026-10-13T00:00:00Z',indicators:scope==='overview'?{}:{chin:[r]},...(scope==='overview'?{general:{indicators:[r]}}:{})});const old=record('old',a),now=record('new',b),before=JSON.stringify(old);assert.equal(H.buildHistorySeries('skin',[old,now]).filter(r=>r.region===scope&&r.criterion==='sag').length,2);assert.equal(JSON.stringify(old),before);
 assert(S.closedSurfaceSupportEnabled('sag',a.appearance.normalizationVersion));assert(S.closedSurfaceSupportEnabled('sag',b.appearance.normalizationVersion));
}'''
 subprocess.run(['node','-e',script],cwd=ROOT,check=True,timeout=30)

@pytest.mark.parametrize('nearby_support,expected',[(0.,0.),(.08,50.)])
def test_remote_jaw_edge_cannot_confirm_unrelated_chin_fold(monkeypatch,nearby_support,expected):
 import instant_appearance as IA
 def profile(*args,**kwargs):
  return dict(strength=.5,edge=.04,continuity=1.,coverage=1.,trackingResidual=0.,trackingQualityVersion='controlled-local-pair',tracked=np.tile([160.,160.],(64,1)),values=np.full(64,.5),edgeValues=np.full(64,.04),support=np.ones(64,bool),observedSamples=np.ones(64,bool))
 monkeypatch.setattr(IA,'curve_profile',profile)
 monkeypatch.setattr(IA,'boundary_support',lambda *args:dict(value=.08,coverage=1.,points=[[160.,220.],[0.,220.]],supported=[True,True],_localSupport=[nearby_support,.08]))
 gray=np.full((320,320),.5,np.float32);visible=np.ones_like(gray,bool)
 value,components,field,_,reason=observed_neutral_proxy(gray,visible,landmarks(),'chin',dict(yaw=0.,pitch=0.),1.,(0,0),gray.shape,boundary_geometry=visible)
 assert reason is None and value==pytest.approx(expected)
 assert bool(field.any())==(nearby_support>0)
 assert '_localSupport' not in components['boundary']
