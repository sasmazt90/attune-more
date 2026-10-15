"""Aggregate frozen A/B receipts; never rerun detection or alter the decision."""
import hashlib,importlib.metadata,json,statistics,sys
from pathlib import Path
from prepare_acne_classical_comparison import ROOT,OUT,BASE,read,sha
from heavy_job_lease import HeavyJobLease

def aggregate(rows):
 valid=[r for r in rows if r.get('valid')];metrics=[r['metrics'] for r in valid]
 timing=lambda field:[r[field]['full'] for r in valid]
 return dict(photos=len(rows),admissiblePhotos=len(valid),rejectedPhotos=len(rows)-len(valid),fixedTargets=sum(r['targetCount'] if not r.get('valid') else r['metrics']['targetCount'] for r in rows),measuredTargets=sum(m['targetCount'] for m in metrics),unmeasuredTargets=sum(r['targetCount'] for r in rows if not r.get('valid')),matched=sum(len(m['pairs']) for m in metrics),visibleTargets=sum(len(m['visibleTargets']) for m in metrics),visibleMatched=sum(len(m['visibleMatched']) for m in metrics),sourceBoxCenterHits=sum(len(m['centerHits']) for m in metrics),candidateCount=sum(r['candidateCount'] for r in valid),reviewedNegativePhotos=sum(m['verifiedNegativePixels']>0 for m in metrics),reviewedNegativeFP=sum(len(m['falseCandidates']) for m in metrics),reviewedNegativeArea80FP=sum(v['reviewedAreaFraction']>=.8 for m in metrics for v in m['falseCandidates']),scale={k:dict(targets=sum(m['scale'][k]['targets'] for m in metrics),matched=sum(m['scale'][k]['matched'] for m in metrics)) for k in ['micro','small','medium']},seconds=dict(firstAnalysisMedian=statistics.median(timing('seconds')) if valid else None,firstAnalysisMax=max(timing('seconds')) if valid else None,repeatMedian=statistics.median(timing('repeatSeconds')) if valid else None,repeatMax=max(timing('repeatSeconds')) if valid else None),deterministicPhotos=sum(r['deterministic'] for r in valid))

def main():
 manifest=read(OUT/'preregistered-manifest.json');data={k:read(OUT/k/'results.json') for k in ['A','B']};summary={};adjudication=read(OUT/'negative-visibility-adjudication.json')
 for k,d in data.items():
  assert d['manifestSHA256']==sha(OUT/'preregistered-manifest.json')
  rows=d['rows'];summary[k]=dict(scopeB=aggregate([r for r in rows if r['cohort']=='scope-B-development']),controls=aggregate([r for r in rows if r['cohort']=='heldout-train']),allAdmissible=aggregate(rows),torchImported=d['torchImported'])
 for k in ['A','B']:
  for cohort in ['scopeB','allAdmissible']:
   metric=summary[k][cohort];metric['automaticNegativeProjectionFP']=metric['reviewedNegativeFP'];metric['automaticProjectionArea80FP']=metric.pop('reviewedNegativeArea80FP');metric['reviewedNegativeFP']=adjudication['counts'][k]['known'];metric['unknownHairBorderCandidates']=adjudication['counts'][k]['unknown'];metric['reviewedNegativeFPPerPhoto']=metric['reviewedNegativeFP']/metric['reviewedNegativePhotos']
 a=summary['A'];b=summary['B'];sA=a['scopeB'];sB=b['scopeB']
 recall_gain=sB['matched']>sA['matched'] and sB['reviewedNegativeFP']<=sA['reviewedNegativeFP']
 precision_gain=sB['matched']==sA['matched'] and sB['reviewedNegativeFP']<sA['reviewedNegativeFP']
 gained_sources=[];lost_sources=[]
 for ra,rb in zip(data['A']['rows'],data['B']['rows']):
  assert ra['sha256']==rb['sha256'] and ra.get('valid')==rb.get('valid')
  if not ra.get('valid'):continue
  assert ra['metrics']['truth']==rb['metrics']['truth'] and ra['metrics']['visibleTargets']==rb['metrics']['visibleTargets']
  ma={p[0] for p in ra['metrics']['pairs']};mb={p[0] for p in rb['metrics']['pairs']}
  if mb-ma:gained_sources.append(ra['sha256'])
  if ma-mb:lost_sources.append(ra['sha256'])
 accepted=bool((recall_gain or precision_gain) and not lost_sources and b['controls']['matched']>=a['controls']['matched'] and (not recall_gain or len(gained_sources)>=2))
 # Acceptance cannot be inferred from this publisher-declared/private dataset alone.
 assert not accepted,'A separate rights-cleared product admission review would be required'
 protected=read(BASE/'protected-production-identity.json');protected_hashes={}
 # The existing baseline record may use a wrapper; preserve and check known paths explicitly.
 paths=['services/core-api/appearance_analysis.py','services/core-api/instant_appearance.py','services/core-api/product_dryness.py','services/core-api/skin_models.py','services/core-api/models/skin-focused.json','apps/vehicle-app/.next/BUILD_ID']
 for name in paths:protected_hashes[name]=sha(ROOT/name)
 for old in protected:assert protected_hashes[old['path']]==old['sha256'],('PROTECTED_PRODUCTION_CHANGED',old['path'])
 geometry={}
 for path,digest in manifest['geometrySourceHashes'].items():
  actual=sha(ROOT/path);assert actual==digest,('GEOMETRY_SOURCE_CHANGED',path);geometry[path]=actual
 config=read(ROOT/'services/core-api/models/skin-focused.json');assert config['models']['acne']['accepted'] is False and config['models']['acne']['file'] is None
 sources=read(ROOT/'audit-results/skin-selected-20261011/manifest.json')['sources'];source_rights=[v for v in sources if v['id'] in {r['source'] for r in manifest['rows']}]
 packages=[]
 for name in ['numpy','opencv-python','scikit-image']:
  dist=importlib.metadata.distribution(name);files=[]
  for f in dist.files or []:
   if 'license' in str(f).lower() and str(f).lower().endswith(('.txt','license')):
    p=Path(dist.locate_file(f))
    if p.is_file():files.append(dict(path=str(f),sha256=sha(p)))
  packages.append(dict(package=name,version=dist.version,existingDependency=True,licenseFiles=files))
 result=dict(version='acne-classical-comparison-evidence-v1',manifestSHA256=sha(OUT/'preregistered-manifest.json'),manifest={k:v for k,v in manifest.items() if k!='rows'},sourceIdentities=[{k:v for k,v in row.items() if k!='sourcePath'} for row in manifest['rows']],summary=summary,negativeVisibilityAdjudication=adjudication,decision=dict(measuredGain=accepted,productionActive=False,stop=True,nextExperimentAuthorized=False,reason='No source-box recall gain, reviewed-negative FP increases; no new threshold/method/training'),sourceTargetGainPhotos=gained_sources,sourceTargetLossPhotos=lost_sources,independentTest=False,redPaleSubtypeMetrics=None,physicalRepeatCaptureMeasured=False,multiFrameMeasured=False,normalAPIEndToEndMeasured=False,timingScope=manifest['metrics']['timing'],rights=dict(existingDatasetPublisherRecords=source_rights,individualPhotoConsentVerified=False,rightsClearedWebcamCohortAvailableInSelectedSources=False,modelWeights='No A/B weights. Existing geometry model unchanged; original clinical protocol preserved',code='New local comparison/DoG code; no copied new third-party algorithm',packages=packages,newDependencyOrNoticeRequired=False,uncertainty='Publisher CC-BY declarations do not independently establish photograph/person permissions; no images distributed'),comparisonCodeSHA256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),Path(__file__).with_name('evaluate_acne_classical.py'),Path(__file__).with_name('acne_lab_dog.py'),Path(__file__).with_name('acne-appearance-capture.html'),Path(__file__).with_name('verify_acne_capture_tool.py')]},protectedProductionHashes=protected_hashes,geometryHashes=geometry,artifacts={k:dict(resultsSHA256=sha(OUT/k/'results.json'),nativeOverlays='audit-results/acne-classical-comparison-20261015/'+k+'/<sourceSHA>-overlay.png',masks='same source SHA -map.png and -eligible.png',resource=data[k]['resource']) for k in ['A','B']},browser=read(OUT/'browser-check.json') if (OUT/'browser-check.json').exists() else None,remainingData=['Consented, eyewear-free native real webcam photos with device/light/pose/track settings, group and rights records','Explicit visible red/pale/white/skin-colored candidate boxes, reviewed mole/brown-spot/hair/glare negative ROI and UNKNOWN areas','Same-pose real repeat captures for light/distance/device stability; static determinism is insufficient','Independent source/person-group holdout; seen Scope B and 28 controls cannot serve as final test'])
 docs=ROOT/'docs/acne-classical-comparison-evidence-20261015.json';docs.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),'utf8')
 # Source images remain local. Green=original source boxes, orange=accepted same-list support.
 with HeavyJobLease('CDC-acne-classical-contact-sheet',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
  import cv2,numpy as np
  sheet=np.full((5*400,2*640,3),25,np.uint8)
  for i,prefix in enumerate(['4a1762ee','55d380f7','695ed248','36e4010b','0560bfd8']):
   for j,k in enumerate(['A','B']):
    path=next((OUT/k).glob(prefix+'*-overlay.png'));im=cv2.imread(str(path));ratio=min(630/im.shape[1],350/im.shape[0]);small=cv2.resize(im,None,fx=ratio,fy=ratio);y=i*400+40;x=j*640+(640-small.shape[1])//2;sheet[y:y+small.shape[0],x:x+small.shape[1]]=small;cv2.putText(sheet,k+' '+prefix,(j*640+10,i*400+25),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
  cv2.imwrite(str(OUT/'source-contact-sheet.jpg'),sheet);lease.check()
 print(json.dumps(dict(summary=summary,accepted=accepted,evidenceSHA256=sha(docs)),indent=2))
if __name__=='__main__':main()