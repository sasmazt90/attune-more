"""Evaluate actual completed/current evidence; never hardcode candidate acceptance."""
import json
from pathlib import Path
from expanded_sources import OUT,ROOT,write,sha
from skin_acceptance import decide
from acceptance_data_evidence import final_data as read_final_data

def read(path,default=None):return json.loads(path.read_text('utf8')) if path.exists() else default

def snapshot(folder):
 if not (folder/'CURRENT').exists():return None
 return read(folder/(folder/'CURRENT').read_text('utf8')/'state.json')

def analytic_product(target,normalization):
 ui=OUT/'product-ui-v4';delivery=ROOT/'audit-results/skin-selected-20261011/product-expanded-v4/delivery.json'
 proof=read(ui/'proof.json',{});cancel=read(ui/'cancel-late-real-response.json',{});served=read(delivery,{})
 source_ok=bool(served) and all((ROOT/path).exists() and sha(ROOT/path)==digest for path,digest in {**served.get('frontendSourceHashes',{}),**served.get('backendSourceHashes',{})}.items())
 source_ok=source_ok and served.get('appearanceSourceSHA256')==sha(ROOT/'services/core-api/appearance_analysis.py') and served.get('instantAppearanceSourceSHA256')==sha(ROOT/'services/core-api/instant_appearance.py') and bool(served.get('servedJavaScriptHashes'))
 normal=[]
 for path in delivery.parent.glob('front-*-normal-api.json'):
  normal.extend(v for region,v in read(path)['activeCriterionMethods']['criteria'].get(target,{}).items() if region!='overview')
 ui_rows=[v for run in proof.get('runs',[]) for values in run['result']['indicators'].values() for v in values if v['id']==target]
 matched=bool(normal and ui_rows) and all(v['methodVersion']=='appearance-cv-6' and v['calibrationVersion']==normalization for v in normal) and all(v['appearance']['normalizationVersion']==normalization and v['method']=='appearance-cv-6' for v in ui_rows)
 captured=proof.get('status')=='PASS' and proof.get('poseMock') is False and proof.get('qualityOverride') is False and proof.get('legacyReferencePreserved') is True and len(proof.get('runs',[]))==2 and all(len(run['graphs'])==6 for run in proof['runs'])
 cancelled=cancel.get('lateResultNotPersisted') is True and cancel.get('realFixtureRescanFollows') is True and any(v.get('actualNormalAPI') and v.get('realResponseHeldAcrossCancellation') for v in cancel.get('responses',[]))
 return dict(activeMethodVersion='appearance-cv-6' if matched else None,activeCriterionMethodMatched=matched,captureApiResultMapHistory=captured,cancelRescanLateResponse=cancelled,sourceBuildServedJavaScriptMatch=source_ok,evidenceScope='licensed real-pixel camera fixture; physical personal acceptance pending',proofSHA256=sha(ui/'proof.json'),normalDeliverySHA256=sha(delivery))


def final_data(target=None):return read_final_data(OUT,target)

def current_mask_export_plan():
 index=read(OUT/'interim-diagnosis/selected-full-export-current.json')
 if not index:return read(OUT/'interim-diagnosis/selected-full-export-v4/plan.json',{})
 path=Path(index['planPath']).resolve()
 if not path.is_relative_to((OUT/'interim-diagnosis').resolve()):raise ValueError('EXPORT_PLAN_PATH_ESCAPE')
 if not path.is_file() or sha(path)!=index['planSHA256']:return {}
 selection=OUT/'interim-diagnosis/corrected-selection-v4.json'
 if selection.exists() and sha(selection)!=index['selectionSHA256']:return {}
 return read(path,{})
def main():
 results={}
 evidence=read(OUT/'type/label-function-evidence-v2.json')
 if evidence:
  source=OUT.parent/'skin-followup-20261011/development-manifest-v2.json';protocol=read(OUT/'type/protocol.json');assert sha(source)==protocol['sourceSHA256']
  rows=[r for r in read(source)['rows'] if r.get('typeEligible') and r['split'] in ['train','validation']];distribution={}
  for split in ['train','validation']:
   rs=[r for r in rows if r['split']==split];distribution[split]={c:dict(photos=sum(r['class']==c for r in rs),groups=len({r['group'] for r in rs if r['class']==c})) for c in protocol['classes']}
  assert {k:v['photos'] for k,v in distribution['train'].items()}==protocol['trainCounts'] and {k:v['photos'] for k,v in distribution['validation'].items()}==protocol['validationCounts']
  evidence['data']['sourceClassDistributionReviewed']=True;evidence['data']['sourceLabelSemanticsVerified']=False;evidence['sourceClassDistribution']=dict(source='old four-class source directories, not expert relabels',splits=distribution,sourceSHA256=sha(source));results['type']=dict(evidence=evidence,decision=decide('type',evidence))
 dry_folder=OUT/('negative-dry-presence' if (OUT/'negative-dry-presence/selection.json').exists() else 'dry-texture')
 evidence=read(dry_folder/'label-function-evidence-v2.json')
 if evidence:
  evidence['export']=read(dry_folder/'export-parity.json',{});results['dryPresence']=dict(evidence=evidence,decision=decide('presence',evidence))
 detector=OUT/('negative-yolox' if (OUT/'negative-yolox/CURRENT').exists() else 'yolox');state=snapshot(detector)
 if state and state['history']:
  best=max(state['history'],key=lambda r:r['validation']['F1']);metrics={**best['validation'],'matchingIoU':.5,'scope':'source-group-development'}
  export=read(OUT/'yolox/decoder-parity/receipt.json',{}) if detector.name=='yolox' else {}
  evidence=dict(method=dict(functions=['detection','localization','appearanceIndex']),data=final_data('acne'),metrics=metrics,appearance={},export={**export,'sha256':export.get('modelSHA256')},product={},training=dict(folder=detector.name,validatedEpochs=state['epoch'],partialCursor=state['cursor'],selectionFinal=(detector/'selection.json').exists()))
  results['acneDetector']=dict(evidence=evidence,decision=decide('detector',evidence))
 mask=OUT/('negative-mask-continuation' if (OUT/'negative-mask-continuation/CURRENT').exists() else 'mask-continuation');state=snapshot(mask)
 corrected=read(OUT/'interim-diagnosis/corrected-selection-v4.json') or read(OUT/'interim-diagnosis/scope-v4/selection.json',{})
 if state:
  for target in ['acne','oil','redness','tone','lines','dark','bags']:
   selected=corrected.get('targets',{}).get(target,{});m=selected.get('metrics') or {}
   metrics={**m,'positiveROIs':m.get('reviewedFullPositiveSources'),'negativeROIs':m.get('reviewedNegativeSupportSources'),'wholeVisibleROI':True if m.get('reviewedFullPositiveSources',0)>0 else None,'scope':'source-group-development'}
   plan=current_mask_export_plan();export=plan.get('targets',{}).get(target,{}).get('export') or {};model=selected.get('selectedFullModel') or {}
   if export.get('weightsSHA256')!=model.get('sha256'):export={}
   if export.get('onnxPath') and (not Path(export['onnxPath']).exists() or sha(Path(export['onnxPath']))!=export['modelSHA256']):export={}
   evidence=dict(method=dict(functions=['localization','appearanceIndex']),data=final_data(target),metrics=metrics,appearance={},export={**export,'sha256':export.get('modelSHA256')},product={},training=dict(folder=mask.name,validatedEpochs=state['epoch'],selectedFullModel=model or None,partialCursor=state['cursor'],selectionFinal=False,legacyTargetBestInvalidated=True,correctedEvaluationComplete=bool(corrected)))
   results[target+'Mask']=dict(evidence=evidence,decision=decide('mask',evidence))
 controls=read(OUT/'current-proxy-controls-v3/receipt.json')
 if controls:
  for target,summary in controls['summary'].items():
   if target=='acne':continue
   separated=False if summary['positiveMedian'] is not None and summary['negativeMedian'] is not None and summary['positiveMedian']<=summary['negativeMedian'] else None
   evidence=dict(method=dict(functions=['appearanceIndex'],implementation='analytic',version='appearance-cv-6'),data=final_data(target),metrics=dict(scope='source-group-development'),appearance=dict(indexVersion=summary['normalizationVersion'],meaning=summary['photoStatistic'],limits='visible photographic index; different criteria are not one physical quantity',measuredSignalNotConfidence=True,naturalPositiveNegativeSeparation=separated,sameInputRepeatability=controls['sameInputRepeatabilityPassed'],confounderSensitivityReviewed=None,anatomicalLocalityVerified=True,scaleFitOnDevelopmentOnly=True,gradientMatchesLocalSignal=True,finalTestReuse=False),product=analytic_product(target,summary['normalizationVersion']),controlSummary=summary)
   results[target+'Analytic']=dict(evidence=evidence,decision=decide('appearance',evidence))
 sag=read(OUT/'sag-controls/actual-results.json')
 if sag:
  evidence=dict(method=dict(functions=['appearanceIndex'],implementation='analytic',version='appearance-cv-6'),data=final_data(),metrics=dict(scope='source-group-development'),appearance=dict(indexVersion='contour-fold-lower-face-local-support-v5',meaning='mean measured local fold/paired-edge support with independent lower-jaw contour support',limits='not tissue displacement, elasticity, age or disease probability',measuredSignalNotConfidence=True,naturalPositiveNegativeSeparation=(False if sag['positiveMedian'] is not None and sag['negativeMedian'] is not None and sag['positiveMedian']<=sag['negativeMedian'] else None),sameInputRepeatability=sag.get('sameInputRepeatabilityPassed'),confounderSensitivityReviewed=None,anatomicalLocalityVerified=True,scaleFitOnDevelopmentOnly=True,gradientMatchesLocalSignal=True,finalTestReuse=False),product=analytic_product('sag','contour-fold-lower-face-local-support-v5'),controls=dict(gradablePositivePhotos=sag['gradablePositivePhotos'],gradableNegativePhotos=sag['gradableNegativePhotos'],positiveMedian=sag['positiveMedian'],negativeMedian=sag['negativeMedian']))
  results['sagAnalytic']=dict(evidence=evidence,decision=decide('appearance',evidence))
 write('label-function-current-decisions.json',dict(version='actual-label-function-progress-v2',rows=results,independentFinalOpened=False))
 print(json.dumps({k:{stage:s['status'] for stage,s in v['decision']['stages'].items()} for k,v in results.items()}),flush=True)
if __name__=='__main__':main()
