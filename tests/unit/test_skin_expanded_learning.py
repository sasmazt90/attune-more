"""Coverage, area balance and real acceptance decision boundaries."""
import copy, sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from selected_mask_model import masked_loss
from skin_acceptance import decide,require_promotion
from yolox_numeric import bounded_regression

def test_balanced_loss_known_positive_negative_unknown_and_area_independence():
 z=torch.zeros(1,7,20,20,requires_grad=True);y=torch.zeros_like(z);s=torch.zeros_like(z)
 y[:,0,:2,:2]=1;s[:,0,:2,:4]=1;y[:,1,:10,:10]=1;s[:,1,:10,:20]=1
 masked_loss(z,y,s,balanced=True).backward()
 assert torch.count_nonzero(z.grad[s==0])==0
 assert (z.grad[(y==1)&(s==1)]<0).all() and (z.grad[(y==0)&(s==1)]>0).all()
 # BCE contribution cannot grow 25x just because the target has 25x area.
 positive=[abs(float(z.grad[0,i][y[0,i]>0].sum())) for i in (0,1)]
 assert max(positive)/min(positive)<1.4
 n=torch.zeros(1,7,4,4,requires_grad=True);sup=torch.zeros_like(n);sup[:,0]=1
 masked_loss(n,torch.zeros_like(n),sup,balanced=True).backward();assert n.grad[:,0].min()>0

def passing_mask():
 return dict(data=dict(sourceReviewComplete=True,rightsReviewComplete=True,labelSemanticsMatched=True,splitRelationsResolved=True,unusedHoldout=True,naturalCameraDomainReviewed=True,engineeringLabelsDisclosed=True),metrics=dict(scope='independent-source-holdout',Dice=.7,IoU=.55,negativeFPR=.03,wholeVisibleROI=True,positiveROIs=40,negativeROIs=40),calibration=dict(pairedValidationGrades=20,MAE=.8,beatsTrainingMedianBaseline=True,confounderReviewComplete=True,testReuse=False),export=dict(sha256='a'*64,numericalParity=True,realImagePreprocessingParity=True,sourceCoordinateParity=True),product=dict(loadedModelSHA256='a'*64,captureApiResultMapHistory=True,cancelRescanLateResponse=True,sourceBuildServedJavaScriptMatch=True,activeCriterionMethodMatched=True))

def test_acceptance_is_a_real_decision_and_does_not_accept_file_existence():
 e=passing_mask();assert decide('mask',e)['accepted'];assert require_promotion('mask',e)['accepted']
 e['product']={};d=decide('mask',e);assert d['eligibleForStaging'] and not d['accepted']
 e=passing_mask();e['metrics']['Dice']=.64;assert not decide('mask',e)['eligibleForStaging']
 e=passing_mask();e['metrics']['scope']='development-validation';e['data']['unusedHoldout']=False;assert not decide('mask',e)['accepted']
 e=passing_mask();e['metrics']['negativeROIs']=0;assert not decide('mask',e)['accepted']


def test_native_regression_exp_overflow_is_bounded_before_backward():
 raw=torch.tensor([[[[.2]],[[.3]],[[137.129]], [[-137.129]]]],requires_grad=True)
 output=bounded_regression(raw,32);sizes=output[:,2:4].exp()*32
 assert torch.isfinite(sizes).all() and sizes.min()>=.0999 and sizes.max()<=768.001
 (sizes.sum()+output[:,:2].square().sum()).backward()
 assert torch.isfinite(raw.grad).all() and raw.grad[:,:2].abs().min()>0


def test_grade_gate_only_applies_to_matching_labels_and_grade_predictors():
 e=passing_mask();e.pop('calibration')
 d=decide('mask',e);assert d['stages']['localization']['status']=='passed'
 assert d['stages']['pairedGradeCalibration']['status']=='not_applicable' and d['accepted']
 e['method']={'functions':['localization','appearanceIndex']}
 d=decide('mask',e);assert d['stages']['localization']['status']=='passed'
 assert d['stages']['appearanceScale']['status']=='pending' and not d['accepted']
 assert 'GRADE_MAE' not in d['failures']
 e['method']={'functions':['localization','gradePrediction']}
 d=decide('mask',e);assert d['stages']['pairedGradeCalibration']['status']=='not_applicable'
 assert d['stages']['appearanceScale']['status']=='pending'
 e['data'].update(matchedGradesAvailable=True,gradeSemanticsMatched=True)
 e['calibration']={'pairedValidationGrades':20,'MAE':1.1,'rankConsistency':.6,'beatsTrainingMedianBaseline':True,'testReuse':False}
 d=decide('mask',e);assert d['stages']['localization']['status']=='passed'
 assert d['stages']['pairedGradeCalibration']['status']=='failed' and 'GRADE_MAE' in d['failures']


def test_development_missing_final_is_separate_from_localization_and_false_positives():
 e=passing_mask();e['metrics']['scope']='source-group-development';e['data']['unusedHoldout']=False
 d=decide('mask',e);assert d['stages']['localization']['status']=='passed'
 assert d['stages']['independentFinal']['status']=='pending' and not d['accepted']
 assert 'DEVELOPMENT_METRICS_NOT_FINAL_ACCEPTANCE' in d['pending'] and 'DEVELOPMENT_METRICS_NOT_FINAL_ACCEPTANCE' not in d['failures']
 assert not d['offlineFailures'] and d['offlinePending']
 e['metrics']['negativeFPR']=.051
 assert decide('mask',e)['stages']['localization']['status']=='failed'
 e['metrics'].update(negativeFPR=.03,wholeVisibleROI=None)
 d=decide('mask',e)
 assert d['stages']['localization']['status']=='pending' and not d['failures']
 assert 'MASK_KNOWN_TARGET_ROI_REVIEW' in d['pending']


def test_binary_presence_never_requires_pixels_or_grades_and_weak_type_stays_failed():
 e=passing_mask();e['metrics']={'scope':'independent-source-holdout','F1':.85,'precision':.9,'recall':.81,'negativeFPR':.04,'positiveGroups':50,'negativeGroups':50,'confusionMatrix':[[48,2],[9,41]]}
 e.pop('calibration');d=decide('presence',e)
 assert d['accepted'] and d['stages']['localization']['status']=='not_applicable'
 assert d['stages']['pairedGradeCalibration']['status']=='not_applicable'
 e['metrics']={'macroF1':.329,'scope':'source-group-development'}
 assert decide('type',e)['stages']['detectionPresence']['status']=='failed'


def test_analytic_index_without_grades_requires_real_appearance_controls():
 e=passing_mask();e['method']={'functions':['appearanceIndex'],'implementation':'analytic','version':'measured-area-v1'}
 e['appearance']={'indexVersion':'measured-area-v1','meaning':'visible affected area / reviewed visible ROI * 100','limits':'visible appearance, no physical moisture','measuredSignalNotConfidence':True,'naturalPositiveNegativeSeparation':True,'sameInputRepeatability':True,'confounderSensitivityReviewed':True,'anatomicalLocalityVerified':True,'scaleFitOnDevelopmentOnly':True,'gradientMatchesLocalSignal':True,'finalTestReuse':False}
 e['product']['activeMethodVersion']='measured-area-v1';d=decide('appearance',e)
 assert d['accepted'] and d['stages']['exportParity']['status']=='not_applicable'
 e['appearance']['measuredSignalNotConfidence']=False
 assert decide('appearance',e)['stages']['appearanceScale']['status']=='failed'


def test_sag_exposure_quality_is_bound_to_the_measured_corridor():
 import numpy as np
 sys.path.insert(0,str(ROOT/'services/core-api'))
 from skin_contract_fixtures import observed_neutral_proxy as instant_proxy
 points=[{'x':.5,'y':.5,'z':0} for _ in range(478)]
 locations={33:(.3,.35),263:(.7,.35),234:(.2,.5),454:(.8,.5),61:(.4,.7),291:(.6,.7),13:(.5,.7),14:(.5,.705),98:(.4,.5),205:(.35,.55),206:(.36,.6),216:(.37,.65),186:(.4,.74),172:(.3,.78),136:(.4,.82),132:(.25,.65),58:(.27,.72),150:(.45,.86)}
 for i,(x,y) in locations.items():points[i].update(x=x,y=y)
 gray=np.full((600,500),.5,np.float32);skin=np.ones(gray.shape,bool);clipped=np.zeros_like(skin);clipped[:100]=True
 conditions={'yaw':0.,'pitch':0.}
 v,c,_,_,reason=instant_proxy(gray,skin&~clipped,points,'rightCheek',conditions,1,(0,0),(600,500),context_skin=skin&~clipped,clipping=clipped,exposure_skin=skin)
 assert v==0 and reason is None and all(s['exposure']['clippedFraction']==0 for s in c['sides'])
 clipped[:]=True
 v,c,_,_,reason=instant_proxy(gray,skin,points,'rightCheek',conditions,1,(0,0),(600,500),context_skin=skin,clipping=clipped,exposure_skin=skin)
 assert v is None and reason=='GLARE_OR_EXPOSURE' and all(s['value'] is None for s in c['sides'])


def test_persistent_checkpoints_preserve_optimizer_rng_and_next_update(tmp_path):
 import random,numpy as np
 from training_checkpoint import checkpoint,resume
 torch.manual_seed(42);random.seed(42);np.random.seed(42)
 net=torch.nn.Linear(2,1);opt=torch.optim.AdamW(net.parameters(),lr=.001)
 def update(model,optimizer):
  x=torch.randn(4,2);optimizer.zero_grad();loss=model(x).square().mean();loss.backward();optimizer.step();return x
 update(net,opt);folder=tmp_path/'new-phase';folder.mkdir()
 for step in range(3):checkpoint(folder,net,opt,{'identity':'phase-v1','step':step})
 assert len(list(folder.glob('checkpoint-*')))==3
 expected_python=random.random();expected_numpy=np.random.rand(4);expected_x=update(net,opt);expected={k:v.clone() for k,v in net.state_dict().items()}
 clone=torch.nn.Linear(2,1);cloneopt=torch.optim.AdamW(clone.parameters(),lr=.001);state=resume(folder,clone,cloneopt,'phase-v1')
 assert state['step']==2 and random.random()==expected_python and np.array_equal(np.random.rand(4),expected_numpy)
 assert torch.equal(update(clone,cloneopt),expected_x)
 assert all(torch.equal(clone.state_dict()[k],v) for k,v in expected.items())


def test_in_bounds_native_box_dimensions_keep_learning_gradients():
 import math
 raw=torch.tensor([[[[0.]],[[0.]],[[math.log(12/8)]],[[math.log(20/8)]]]],requires_grad=True)
 sizes=bounded_regression(raw,8)[:,2:4].exp()*8
 target=torch.tensor([[[[14.]],[[18.]]]])
 (sizes-target).square().mean().backward()
 assert torch.isfinite(raw.grad).all() and raw.grad[:,2:4].abs().min()>0


def test_local_eye_quality_preserves_measurable_side_and_ignores_remote_glare():
 import numpy as np
 sys.path.insert(0,str(ROOT/'services/core-api'))
 from appearance_analysis import analyze_skin
 from test_local_appearance_health import photo
 h,w=280,320;p=[dict(x=.5,y=.5,z=0.) for _ in range(478)]
 oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
 for i,angle in zip(oval,np.linspace(-np.pi/2,3*np.pi/2,len(oval),endpoint=False)):p[i].update(x=.5+.49*np.cos(angle),y=.5+.48*np.sin(angle))
 locations={234:(0,150),454:(320,150),33:(40,70),133:(110,70),159:(75,64),163:(50,76),144:(60,80),145:(75,82),153:(90,83),154:(100,80),155:(105,76),263:(280,70),362:(210,70),386:(245,64),390:(270,76),373:(260,80),374:(245,82),380:(230,83),381:(220,80),382:(215,76),61:(110,165),291:(210,165),13:(160,165),14:(160,168)}
 for i,(x,y) in locations.items():p[i].update(x=x/w,y=y/h)
 mesh={'points':[{'x':0,'y':40},{'x':320,'y':40},{'x':320,'y':130},{'x':0,'y':130}],'edges':[[0,1],[1,2],[2,3],[3,0],[0,2]]}
 def result(image):
  url,digest=photo(image)
  return analyze_skin(dict(photo=url,photoId=digest,landmarks=p,meshes={'periorbital':mesh},exclusions=[],pose='FRONT',qualityValid=True,conditions=dict(yaw=0.,pitch=0.,roll=0.,scaleRatio=.6,avgLuminance=150.,blurScore=50.)))
 image=np.full((h,w,3),153,np.uint8);image[42:60]=255
 first=result(image);dark=next(v for v in first['measurements']['periorbital'] if v['id']=='dark')
 assert dark['value']==0 and dark['quality']=='valid' and not dark['components']['partialCoverage']
 # Strong clipping is inside the right target band; left stays observed.
 image[73:127,:155]=255
 second=result(image);dark=next(v for v in second['measurements']['periorbital'] if v['id']=='dark')
 assert dark['quality']=='valid' and dark['components']['partialCoverage']
 sides={v['side']:v for v in dark['components']['sides']}
 assert sides['right']['value'] is None and sides['right']['limitationCode']=='GLARE_OR_EXPOSURE'
 assert sides['left']['value']==0 and dark['evaluatedArea']['unknownSides']==['right']
 assert next(v for v in second['general']['measurements'] if v['id']=='dark')['quality']=='valid'


def test_tracking_quality_measures_displacement_not_anatomical_guide_bends():
 import numpy as np
 sys.path.insert(0,str(ROOT/'services/core-api'))
 from instant_appearance import tracking_residual
 x=np.arange(64,dtype=np.float32);guide=np.column_stack([x,20*np.sin(x/2)])
 assert tracking_residual(guide+np.array([3.,-2.]),guide,320)<1e-6
 noise=np.column_stack([10*(-1.)**x,np.zeros(64)])
 assert tracking_residual(guide+noise,guide,320)>2.5
 # The same displacement is measured independently of expected shape.
 straight=np.column_stack([x,np.zeros(64)])
 assert abs(tracking_residual(guide+noise,guide,320)-tracking_residual(straight+noise,straight,320))<1e-6
