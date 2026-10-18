"""Natural engineering controls for the actual current proxy versions.

Uses reviewed development photographs only. Paired exposure transforms are
auxiliary sensitivity probes, never newly labelled natural performance cases.
"""
import collections,json,subprocess,argparse
from pathlib import Path
import cv2,numpy as np
from expanded_sources import ROOT,OUT,PREVIOUS,sha,write
from evaluate_selected_appearance import run
import appearance_analysis as A

def reduced(result):
 return {region:{v['id']:dict(value=v['value'],quality=v['quality'],limitationCode=v.get('limitationCode'),normalizationVersion=v.get('normalizationVersion'),methodVersion=v['methodVersion'],evaluatedArea=v.get('evaluatedArea')) for v in values} for region,values in result['regionMeasurements'].items()}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output-name',default='current-proxy-controls');args=parser.parse_args();folder_name=args.output_name;assert folder_name.startswith('current-proxy-controls') and folder_name.replace('-','').isalnum()
 cv2.setNumThreads(1);folder=OUT/folder_name;folder.mkdir(exist_ok=True);sources=json.loads((PREVIOUS/'review/candidates.json').read_text('utf8'))['rows'];ds=json.loads((PREVIOUS/'review/decisions.json').read_text('utf8'))['rows'];by={(d['reviewIndex'],d['sha256']):d for d in ds};selected={}
 for r in sources:
  d=by[(r['reviewIndex'],r['sha256'])]
  if not d['naturalEligible'] or not d['rightsEligible'] or r['sha256'].startswith('0379'):continue
  labels={t:v for t,v in d['appearanceLabels'].items() if t!='sag' and v in ['positive','negative']}
  if labels:selected[r['sha256']]={**r,'engineeringLabels':labels}
 n=json.loads((OUT/'negative-expanded-mask-data.json').read_text('utf8'));nc=json.loads((OUT/'negative-expansion/candidates.json').read_text('utf8'))['rows'];nb={r['sha256']:r for r in nc}
 for r in n['preparedNegativePhotos']:
  if not r['targets']:continue
  selected[r['sha256']]={**nb[r['sha256']],**r,'engineeringLabels':{t:'negative' for t in r['targets']},'crop':[0,0,nb[r['sha256']]['width'],nb[r['sha256']]['height']]}
 selected=list(selected.values());assert all(r['split']!='test' for r in selected)
 meshes=json.loads(subprocess.check_output(['node','scripts/skin-research/focused_meshes.cjs'],input=json.dumps(selected).encode(),cwd=ROOT));done=[];partial=folder/'partial.json'
 if partial.exists():
  v=json.loads(partial.read_text('utf8'));assert v['sourceVersionSHA256']==sha(Path(A.__file__)) and v['instantVersionSHA256']==sha(ROOT/'services/core-api/instant_appearance.py');done=v['rows']
 prior={r['sha256'] for r in done}
 for r,m in zip(selected,meshes):
  if r['sha256'] in prior:continue
  assert sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath']);gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);a=m['alignment'];conditions={k:a[k] for k in ['yaw','pitch','roll','scaleRatio']};conditions.update(avgLuminance=float(gray.mean()),blurScore=float(cv2.Laplacian(gray,cv2.CV_32F).var()))
  payload=dict(pose='FRONT',landmarks=r['landmarks'],meshes={k:v for k,v in m['meshes'].items() if len(v['points'])>=3},exclusions=[],qualityValid=40<=gray.mean()<=220 and conditions['blurScore']>=4 and abs(a['yaw'])<.35,conditions=conditions)
  try:base=reduced(run(payload,im))
  except ValueError as error:
   if str(error) not in ['PHOTO_LIMIT','INVALID_PHOTO']:raise
   done.append(dict(sha256=r['sha256'],group=r['group'],source=r['source'],split=r['split'],engineeringLabels=r['engineeringLabels'],conditions=conditions,base={},sameInputExactValues=None,auxiliaryExposureControls={},captureRejectedReason=str(error),expertGrades=None,independentFinal=False));continue
  repeat=reduced(run(payload,im));assert base==repeat,'CURRENT_SIGNAL_REPEATABILITY_FAILED'
  variants={name:reduced(run(payload,np.clip(im.astype(np.float32)*factor,0,255).astype(np.uint8))) for name,factor in [('exposure85',.85),('exposure110',1.1)]}
  done.append(dict(sha256=r['sha256'],group=r['group'],source=r['source'],split=r['split'],engineeringLabels=r['engineeringLabels'],conditions=conditions,base=base,sameInputExactValues=True,auxiliaryExposureControls=variants,expertGrades=None,independentFinal=False))
  write(folder_name+'/partial.json',dict(rows=done,sourceVersionSHA256=sha(Path(A.__file__)),instantVersionSHA256=sha(ROOT/'services/core-api/instant_appearance.py'),complete=False))
  if len(done)%10==0:print('Current natural proxy controls',len(done),'/',len(selected),flush=True)
 summaries={}
 for t in ['acne','oil','dry','redness','tone','lines','dark','bags']:
  pos=[];neg=[];nulls=collections.Counter();drifts=[]
  for r in done:
   label=r['engineeringLabels'].get(t)
   if not label:continue
   vals=[v[t]['value'] for v in r['base'].values() if t in v and v[t]['value'] is not None]
   if vals:(pos if label=='positive' else neg).append(max(vals))
   else:nulls[label]+=1
   for region,values in r['base'].items():
    if t not in values or values[t]['value'] is None:continue
    for variant in r['auxiliaryExposureControls'].values():
     q=variant.get(region,{}).get(t,{})
     if q.get('value') is not None:drifts.append(abs(q['value']-values[t]['value']))
  auc=float(np.mean([[1 if p>n else .5 if p==n else 0 for n in neg] for p in pos])) if pos and neg else None
  summaries[t]=dict(gradablePositivePhotos=len(pos),gradableNegativePhotos=len(neg),unavailablePhotos=dict(nulls),positiveMedian=float(np.median(pos)) if pos else None,negativeMedian=float(np.median(neg)) if neg else None,rankAUC=auc,auxiliaryExposureAbsoluteDriftMedian=float(np.median(drifts)) if drifts else None,photoStatistic='maximum measured local index; not inferred whole-face severity',normalizationVersion=A.NORMALIZATION[t],calibrationAccepted=None,calibrationDecision='see label-function-current-decisions.json; summary statistics alone are not acceptance')
 write(folder_name+'/receipt.json',dict(rows=done,summary=summaries,protocolFrozenBeforeEvaluation=True,protocolSHA256=sha(OUT/'label-function-protocol-freeze.json'),sourceVersionSHA256=sha(Path(A.__file__)),instantVersionSHA256=sha(ROOT/'services/core-api/instant_appearance.py'),sameInputRepeatabilityPassed=True,coefficientsUnchanged=True,exposureTransformsAreAuxiliary=True,poseExpressionQualityFromActualLandmarks=True,independentFinal=False))
 print(json.dumps(summaries),flush=True)
if __name__=='__main__':main()
