"""Finalize finite evidence, including a frozen-method counterfactual on fresh payloads."""
import hashlib,inspect,json,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-proposal-tracking-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
import instant_appearance as I

def read(path):return json.loads(path.read_text('utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def scalars(result):
 return {region+':'+v['id']:{k:v[k] for k in ['value','quality','limitationCode','normalizationVersion']} for region,values in [*result['measurements'].items(),('overview',result['general']['measurements'])] for v in values}

saved={name:sys.modules.get(name) for name in ['instant_appearance','skin_general']};loaded={}
for name in ['instant_appearance','skin_general','appearance_analysis']:
 data=subprocess.check_output(['git','show','5a40a1276c9eccc6bd099d42775dcd7eb4e3e604:services/core-api/'+name+'.py'],cwd=ROOT)
 alias=name if name!='appearance_analysis' else 'tracking_delivery_frozen_baseline'
 module=type(sys)(alias);module.__file__=str(ROOT/'services/core-api'/(name+'.py'));sys.modules[alias]=module
 exec(compile(data,module.__file__,'exec'),module.__dict__);loaded[name]=module
for name,module in saved.items():
 if module is None:sys.modules.pop(name,None)
 else:sys.modules[name]=module
old_A=loaded['appearance_analysis'];old_I=loaded['instant_appearance']
fresh=[]
for prefix in ['f90e68f8','40d781eb','64b02ede']:
 path=OUT/'product'/prefix/(prefix+'-automatic-payload.json');payload=read(path);served=read(OUT/'product'/prefix/(prefix+'-automatic-api.json'))
 assert not payload['hostedProcessingConsent']
 old_profiles=[];original=old_I.curve_profile
 def capture(*args,**kwargs):
  q=original(*args,**kwargs);caller=inspect.currentframe().f_back
  if q is not None and caller.f_locals.get('region')=='chin':old_profiles.append(dict(residual=q['trackingResidual'],observedSamples=int(q['observedSamples'].sum()),foldSamples=int(q['support'].sum()),invalidSamples=int((~q['observedSamples']).sum())))
  return q
 old_I.curve_profile=capture
 try:before=old_A.analyze_skin(payload)
 finally:old_I.curve_profile=original
 local=A.analyze_skin(payload);b=scalars(before);s=scalars(served);current=scalars(local)
 assert current==s,'Actual served response must match working production method on the exact fresh payload'
 preserved={k:s[k]==v for k,v in b.items() if k not in ['chin:sag','overview:sag']};assert all(preserved.values())
 old_row=next(v for v in before['measurements']['chin'] if v['id']=='sag');new_row=next(v for v in served['measurements']['chin'] if v['id']=='sag')
 fresh.append(dict(source=prefix,payloadSHA256=sha(path),photoId=payload['photoId'],frozenBefore=b['chin:sag'],actualServedAfter=s['chin:sag'],oldProfiles=old_profiles,newSides=new_row['components'].get('sides',[]),anatomicalSourcePixelsBefore=old_row['components']['measurementROI']['anatomicalSourcePixels'],anatomicalSourcePixelsAfter=new_row['components']['measurementROI']['anatomicalSourcePixels'],otherMethodsUnchanged=preserved,servedEqualsCurrentOnSamePayload=current==s))

proposal=read(OUT/'region-proposal-receipt.json');protocol=read(OUT/'region-proposal-protocol.json')
label_path=ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json';labels=read(label_path)
assert protocol['labelsSHA256']==sha(label_path) and not proposal['classifierFitted'] and not proposal['proposalAcceptancePassed']
from trial_region_flake_proposal import PARAMETERS
assert protocol['parameters']==PARAMETERS
summary=[];objects=[];stage_hits={};small_wide=[]
for kind in ['pul','raw','old']:
 for scale in [1.,.5]:
  subsets=[r['resolutions'][int(scale==.5)] for r in proposal['rows'] if r['kind']==kind]
  obj=[o for s in subsets for o in s['objects'] if o['label']=='visible-material']
  summary.append(dict(kind=kind,scale=scale,materialObjects=len(obj),oldProposalHits=sum(o['stages']['oldAfterMAD']['objectHit'] for o in obj),newRegionHits=sum(o['stages']['new:poreSeparated']['objectHit'] for o in obj),reviewedNegativeSourcePixelsBefore=sum(s['negative']['productionAfterCompactness']['activeSourcePixels'] for s in subsets),reviewedNegativeSourcePixelsAfter=sum(s['negative']['new:poreSeparated']['activeSourcePixels'] for s in subsets)))
for r in proposal['rows']:
 for o in r['resolutions'][0]['objects']:
  if o['label']!='visible-material':continue
  for stage,v in o['stages'].items():stage_hits[stage]=stage_hits.get(stage,0)+int(v['objectHit'])
  stages=['new:stableRegions','new:geometry','new:ringContrast','new:boundaryEdges','new:poreSeparated']
  failure=next((k for k in stages if not o['stages'][k]['objectHit']),None)
  source=next(c for c in labels['controls'] if c['controlIndex']==r['controlIndex']);polygon=source['objects'][o['index']]['polygon'];x,y,_,_=source['roi']
  objects.append(dict(controlIndex=r['controlIndex'],objectIndex=o['index'],sourceSHA256=r['sourceSHA256'],group=r['group'],split=r['split'],kind=r['kind'],sizeClass=o['sizeClass'],sourcePolygon=[[a+x,b+y] for a,b in polygon],stages=o['stages'],newFirstFailedObjectHitStage=failure))
for size in ['small','wide']:
 rows=[o for o in objects if o['sizeClass']==size]
 small_wide.append(dict(sizeClass=size,objects=len(rows),oldProposalHits=sum(o['stages']['oldAfterMAD']['objectHit'] for o in rows),newRegionHits=sum(o['stages']['new:poreSeparated']['objectHit'] for o in rows)))

camera=[]
for prefix in ['f90e68f8','40d781eb','64b02ede']:
 path=ROOT/'output/playwright'/OUT.name/prefix/'camera-receipt.json';r=read(path)
 assert r['automaticScanCompleted'] and r['realMediaPipe'] and r['sourceMatches'] and r['historyBytesUnchanged'] and r['real200Accepted'] and not r['pageErrors'] and r['hostedCalls']==0
 for views in [r['resultViews'],r['historyViews']]:
  assert len(views)==7 and all(l['matches'] for v in views for l in v['labels'])
 camera.append({k:r[k] for k in ['sourceSHA256','cameraSHA256','capturePixelSHA256','buildId','automaticScanCompleted','realMediaPipe','pose','conditions','qualityValid','sourceMatches','targets','resultViews','historyViews','historyBytesUnchanged','real200Percent','real200Accepted','pageErrors','hostedCalls']})
history=read(OUT/'history-compatibility.json');delivery=read(OUT/'delivery.json');assert delivery['buildId']==history['buildId']==camera[0]['buildId']
history={k:v for k,v in history.items() if k not in ['v8','v9']}|{version:{k:v for k,v in read(OUT/'history-compatibility.json')[version].items() if k!='recordId'} for version in ['v8','v9']}
comparison=read(OUT/'actual-payload-comparison.json')
artifacts=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.glob('*.json'))]
result=dict(baselineSHA='5a40a1276c9eccc6bd099d42775dcd7eb4e3e604',productionMethodCommit='296ee550fd17cf3266ba15573f2d452426a93193',BUILD_ID=delivery['buildId'],
 scope='Single frozen region-proposal trial and chin residual correction; no source census, relabeling, classifier fit or new model',
 unchangedLabelsSHA256=sha(label_path),proposalProtocol=protocol,proposalProtocolSHA256=sha(OUT/'region-proposal-protocol.json'),
 nativeStageObjectHits=stage_hits,smallWideComparisons=small_wide,domainResolutionComparisons=summary,
 materialObjectGateAttribution=objects,reviewedNegativeChecks=proposal['negativeChecks'],
 proposalDecision=dict(nativeMaterialHits=proposal['nativeMaterialHits'],materialObjects=21,familiarValidationHits=proposal['familiarValidationHits'],familiarValidationObjects=8,independentFinalTest=False,acceptancePassed=proposal['proposalAcceptancePassed'],classifierFitted=False,productionActivated=False),
 baselineTrackingDiagnosis=read(OUT/'tracking-baseline-diagnosis.json'),fixedPayloadComparison=comparison,
 freshActualPayloadCounterfactual=fresh,camera=camera,historyCompatibility=history,delivery=delivery,artifactInventory=artifacts,
 productionChanges=['chin/overview normalization contour-fold-lower-chin-observed-runs-v9; tracked residual uses only observed contiguous fold runs',
                    'Frontend keeps v8 and v9 anatomical closed-cell rendering and separates historical versions'],
 preserved=['dry v3','cheek v7','bags impulse v3','lines v4','dark v4','expression/pose/exposure thresholds','hosted permission/config','source photos/colors','user records','voices','other health modules','AG workspace/processes'],
 noPixelDiceOrPrecision=True,clinicalSeverity=False,
 remainingObstacles=['Connected proposal still misses 11/21 material objects, including C8/C9 broad low-contrast material before stable-region extraction.',
                    'Familiar validation capture 2/8 and natural-origin half-resolution capture 0/9 are insufficient; no second gate fit or dry product promotion.',
                    'f90e68f8 and 64b02ede have only fragmented local fold support; no strong neutral chin-positive claim.'])
target=ROOT/'docs/dry-sag-proposal-tracking-evidence-20261013.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps(dict(publicReceipt=str(target.relative_to(ROOT)),bytes=target.stat().st_size,sha256=sha(target),nativeStageObjectHits=stage_hits,smallWide=small_wide,actualFreshChin=[dict(source=r['source'],before=r['frozenBefore'],after=r['actualServedAfter'],oldProfiles=r['oldProfiles']) for r in fresh])))
