"""Label/function-specific acceptance, with development and final readiness separate.
Unchanged frozen detection/FPR limits. This module never installs a candidate.
"""
import json, math
from pathlib import Path
GATES=json.loads((Path(__file__).parent/'selected-acceptance.json').read_text('utf8'))
PROTOCOL=json.loads((Path(__file__).parent/'label-function-acceptance-v2.json').read_text('utf8'))


def decide(kind,evidence):
 defaults={'type':['classification'],'detector':['detection','localization'],'mask':['localization'],'presence':['presence'],'appearance':['appearanceIndex'],'grade':['gradePrediction']}
 if kind not in defaults:raise ValueError('UNKNOWN_ACCEPTANCE_KIND')
 stages={};data=evidence.get('data',{});metric=evidence.get('metrics',{})
 method=evidence.get('method',{});export=evidence.get('export',{});product=evidence.get('product',{})
 functions=method.get('functions',defaults[kind])
 def stage(name,applicable=True):
  s=dict(status='passed' if applicable else 'not_applicable',failures=[],pending=[],scope=metric.get('scope'));stages[name]=s;return s
 def check(s,value,reason):
  if value is None:s['pending'].append(reason)
  elif not value:s['failures'].append(reason)
 def flag(s,m,k,reason):check(s,m.get(k) if isinstance(m.get(k),bool) else None,reason)
 def number(s,m,k,limit,reason,lower=True):
  v=m.get(k);check(s,None if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) else (v>=limit if lower else v<=limit),reason)
 def finish(s):
  if s['status']!='not_applicable':s['status']='failed' if s['failures'] else 'pending' if s['pending'] else 'passed'
 def reasons(s):return s['failures']+s['pending']
 detection=stage('detectionPresence',kind in ['type','detector','presence'])
 localization=stage('localization',kind in ['detector','mask'])
 scale=stage('appearanceScale',any(f in functions for f in ['appearanceIndex','gradePrediction']))
 if kind=='type':
  g=GATES['type'];number(detection,metric,'macroF1',g['macroF1'],'TYPE_MACRO_F1');cs=metric.get('classes')
  check(detection,None if cs is None else len(cs)==4,'TYPE_FOUR_CLASS_COVERAGE')
  for c in cs or []:
   for k,limit in [('F1',g['minimumClassF1']),('recall',0),('support',1)]:number(detection,c,k,limit,'TYPE_CLASS_'+k.upper())
  check(detection,None if 'confusionMatrix' not in metric else isinstance(metric['confusionMatrix'],list) and len(metric['confusionMatrix'])==4,'TYPE_CONFUSION_MATRIX')
  flag(detection,data,'sourceClassDistributionReviewed','TYPE_SOURCE_CLASS_DISTRIBUTION')
  number(detection,metric,'confidencePrecision',g['confidencePrecision'],'TYPE_CONFIDENT_PRECISION')
  number(detection,metric,'confidenceSupport',g['minimumConfidenceSupport'],'TYPE_CONFIDENT_SUPPORT')
 elif kind=='detector':
  for k in ['F1','precision','recall']:number(detection,metric,k,GATES['detectorSource'][k],'DETECTOR_SOURCE_'+k.upper())
  number(localization,metric,'AP50',0,'DETECTOR_AP50_REPORTED');number(localization,metric,'matchingIoU',GATES['detectorSource']['matchingIoU'],'DETECTOR_MATCHING_IOU')
  for k in ['falsePositive','falseNegative']:number(localization,metric,k,0,'DETECTOR_'+k.upper()+'_REPORTED')
  localization['failures'].extend(detection['failures']);localization['pending'].extend(detection['pending'])
  natural=evidence.get('naturalMetrics',{});g=GATES['detectorNaturalAcceptance']
  for k in ['F1','precision','recall']:number(detection,natural,k,g[k],'DETECTOR_NATURAL_'+k.upper())
  for key,gate in [('positivePhotos','minimumPositivePhotos'),('negativePhotos','minimumNegativePhotos'),('lesions','minimumLesions')]:number(detection,natural,key,g[gate],'DETECTOR_NATURAL_'+key.upper())
  number(detection,natural,'meanFalseCandidatesPerNegativePhoto',g['maximumMeanFalseCandidatesPerNegativePhoto'],'DETECTOR_NEGATIVE_FALSE_CANDIDATES',False)
 elif kind=='mask':
  g=GATES['mask']
  for k in ['Dice','IoU']:number(localization,metric,k,g[k],'MASK_'+k.upper())
  number(localization,metric,'negativeFPR',g['maximumNegativeFPR'],'MASK_NEGATIVE_FALSE_PIXELS',False)
  flag(localization,metric,'wholeVisibleROI','MASK_KNOWN_TARGET_ROI_REVIEW')
  for k in ['positiveROIs','negativeROIs']:number(localization,metric,k,1,'MASK_'+k.upper()+'_COVERAGE')
 elif kind=='presence':
  g=PROTOCOL['presence']
  for k in ['F1','precision','recall']:number(detection,metric,k,g[k],'PRESENCE_'+k.upper())
  number(detection,metric,'negativeFPR',g['maximumNegativeFPR'],'PRESENCE_NEGATIVE_FPR',False)
  for k in ['positiveGroups','negativeGroups']:number(detection,metric,k,1,'PRESENCE_'+k.upper()+'_COVERAGE')
  check(detection,None if 'confusionMatrix' not in metric else len(metric['confusionMatrix'])==2,'PRESENCE_CONFUSION_MATRIX')
 grade_applicable='gradePrediction' in functions and data.get('matchedGradesAvailable') is True and data.get('gradeSemanticsMatched') is True
 grade=stage('pairedGradeCalibration',grade_applicable)
 if 'gradePrediction' in functions and not grade_applicable:check(scale,None,'MATCHED_GRADE_LABELS_FOR_DECLARED_GRADE_PREDICTOR_PENDING')
 if grade_applicable:
  c=evidence.get('calibration',{});g=GATES['appearance']
  number(grade,c,'pairedValidationGrades',g['minimumPairedValidationGrades'],'PAIRED_GRADE_COVERAGE');number(grade,c,'MAE',g['maximumMAEOn0to5'],'GRADE_MAE',False)
  flag(grade,c,'beatsTrainingMedianBaseline','GRADE_MEDIAN_BASELINE');number(grade,c,'rankConsistency',0,'GRADE_RANK_CONSISTENCY_REPORTED')
  check(grade,None if 'testReuse' not in c else c['testReuse'] is False,'CALIBRATION_TEST_REUSE_OR_UNKNOWN')
  scale['failures'].extend(grade['failures']);scale['pending'].extend(grade['pending'])
 if 'appearanceIndex' in functions:
  a=evidence.get('appearance',{})
  for k in ['indexVersion','meaning','limits']:check(scale,bool(a[k]) if k in a else None,'APPEARANCE_'+k.upper())
  for k in ['measuredSignalNotConfidence','naturalPositiveNegativeSeparation','sameInputRepeatability','confounderSensitivityReviewed','anatomicalLocalityVerified','scaleFitOnDevelopmentOnly','gradientMatchesLocalSignal']:flag(scale,a,k,'APPEARANCE_'+k.upper())
  check(scale,None if 'finalTestReuse' not in a else a['finalTestReuse'] is False,'APPEARANCE_FINAL_TEST_REUSE')
 for s in [detection,localization,scale,grade]:finish(s)
 final=stage('independentFinal')
 for k,r in [('sourceReviewComplete','SOURCE_TARGET_REVIEW_INCOMPLETE'),('rightsReviewComplete','SOURCE_RIGHTS_REVIEW_INCOMPLETE'),('labelSemanticsMatched','LABEL_SEMANTICS_UNVERIFIED'),('splitRelationsResolved','CROP_COLLAGE_SPLIT_RELATIONS_UNRESOLVED'),('unusedHoldout','UNUSED_HOLDOUT_MISSING'),('naturalCameraDomainReviewed','NATURAL_CAMERA_DOMAIN_INCOMPLETE'),('engineeringLabelsDisclosed','ENGINEERING_LABEL_ORIGIN_MISSING')]:
  if data.get(k) is not True:check(final,None,r)
 if metric.get('scope')!='independent-source-holdout':check(final,None,'DEVELOPMENT_METRICS_NOT_FINAL_ACCEPTANCE')
 finish(final)
 parity=stage('exportParity',method.get('implementation','model')=='model')
 if parity['status']!='not_applicable':
  for k in ['numericalParity','realImagePreprocessingParity','sourceCoordinateParity']:flag(parity,export,k,'REAL_IMAGE_ONNX_'+k.upper())
 finish(parity)
 offline_failed=list(dict.fromkeys(r for name,s in stages.items() if name!='pairedGradeCalibration' for r in s['failures']));offline_pending=list(dict.fromkeys(r for name,s in stages.items() if name!='pairedGradeCalibration' for r in s['pending']));eligible=not (offline_failed or offline_pending)
 integrated=stage('productIntegration');expected=export.get('sha256')
 if method.get('implementation','model')=='model':check(integrated,None if not expected or not product.get('loadedModelSHA256') else product['loadedModelSHA256']==expected,'NORMAL_API_LOADED_MODEL_HASH_MISSING_OR_DIFFERENT')
 else:check(integrated,None if not method.get('version') or not product.get('activeMethodVersion') else product['activeMethodVersion']==method['version'],'NORMAL_API_ACTIVE_ANALYTIC_VERSION')
 for k in ['captureApiResultMapHistory','cancelRescanLateResponse','sourceBuildServedJavaScriptMatch','activeCriterionMethodMatched']:flag(integrated,product,k,'PRODUCT_'+k.upper())
 finish(integrated)
 ready=stage('userTestReadiness');ready['pending']=list(dict.fromkeys(offline_pending+integrated['pending']));ready['failures']=list(dict.fromkeys(r for s in [detection,localization,scale,parity,integrated] for r in s['failures']));finish(ready)
 return dict(kind=kind,functions=functions,stages=stages,eligibleForStaging=eligible,accepted=ready['status']=='passed',decisionVersion='label-function-separate-failure-pending-v2',offlineFailures=offline_failed,offlinePending=offline_pending,failures=list(dict.fromkeys(offline_failed+integrated['failures'])),pending=list(dict.fromkeys(offline_pending+integrated['pending'])),thresholdVersion=GATES['version'],protocolVersion=PROTOCOL['version'],modelSHA256=expected)


def require_promotion(kind,evidence):
 decision=decide(kind,evidence)
 if not decision['accepted']:raise ValueError('CANDIDATE_NOT_ACCEPTED:'+','.join(decision['failures']+decision['pending']))
 return decision
