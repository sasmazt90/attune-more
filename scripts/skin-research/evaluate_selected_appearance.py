"""Actual product arithmetic on licensed photos and disclosed auxiliary controls.

Natural reviewed positives/negatives are separate from repeatability and synthetic
illumination/quality probes. This never writes records or reads user photographs.
"""
import base64,hashlib,json,subprocess,sys
import cv2,numpy as np
from selected_sources import ROOT,OUT,write,sha
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A

def run(payload,bgr,quality=None):
 p={**payload};ok,raw=cv2.imencode('.png',bgr);assert ok
 p['photo']='data:image/png;base64,'+base64.b64encode(raw).decode()
 p['photoId']=hashlib.sha256(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
 if quality is not None:p['qualityValid']=quality
 response=A.analyze_skin(p)
 return dict(photoId=p['photoId'],skinType=response['general']['skinType'],measurements=response['general']['measurements'],modelInference=response['general'].get('modelInference'),regionMeasurements=response['measurements'])

def main():
 cv2.setNumThreads(1);rows=[]
 for index in [0,1,3,5]:
  p=json.loads((ROOT/f'audit-results/all-health-20261010/natural-skin/{index}-payload-private.json').read_text('utf8'));bgr,_=A.decode_photo(p['photo']);base=run(p,bgr);repeat=run(p,bgr)
  variants={}
  for name,factor in [('exposure-85',.85),('exposure-110',1.10)]:variants[name]=run(p,np.clip(bgr.astype(float)*factor,0,255).astype('uint8'))
  variants['capture-not-gradable']=run(p,cv2.GaussianBlur(bgr,(31,31),15),False)
  values=lambda d:{v['id']:v['value'] for v in d['measurements']}
  a,b=values(base),values(repeat);differences={k:abs(a[k]-b[k]) if a[k] is not None and b[k] is not None else None for k in a}
  assert max((v for v in differences.values() if v is not None),default=0)<1e-6
  assert all(v['value'] is None and v['status']=='unavailable' for v in variants['capture-not-gradable']['measurements'])
  rows.append(dict(sourceIndex=index,naturalSource='previously exposed licensed NASA portrait' if index<2 else 'previously exposed licensed video frame, same person for indices3/5',independentTest=False,base=base,repeatMaximumDifference=max((v for v in differences.values() if v is not None),default=0),auxiliaryControls={k:dict(values=values(v),status={i['id']:i['status'] for i in v['measurements']},syntheticNotNaturalPerformance=True) for k,v in variants.items()}))
 loaded=sorted({v['modelHash'] for r in rows for v in (r['base']['modelInference'] or {}).values() if v.get('modelHash')})
 write('appearance-controls.json',dict(rows=rows,physicalUserAcceptance=False,syntheticControlsDoNotEstablishNaturalPerformance=True,acceptedModelLoadedHashes=loaded,proxyMethodsVersion=A.VERSION,transport='original-dimension PNG; native source hash; no resizing'))
 review_file=OUT/'review/candidates.json'
 if review_file.exists() and (OUT/'review/decisions.json').exists():
  from train_selected_local import reviewed
  source=reviewed();meshes=json.loads(subprocess.check_output(['node','scripts/skin-research/focused_meshes.cjs'],input=json.dumps(source).encode(),cwd=ROOT));natural=[]
  partial=OUT/'natural-appearance-review-partial.json'
  if partial.exists():
   natural=json.loads(partial.read_text('utf8'))['rows']
   for prior in natural:
    match=next(r for r in source if r['source']==prior['source'] and r['sha256']==prior['sha256']);assert match['reviewDecision']['appearanceLabels']==prior['engineeringAppearanceLabels'],'REVIEW_CHANGED'
  done={(r['source'],r['sha256']) for r in natural}
  for r,m in zip(source,meshes):
   if (r['source'],r['sha256']) in done:continue
   im=cv2.imread(r['absolutePath']);gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);a,b,c,d=r['crop'];crop=gray[b:d,a:c];alignment=m['alignment'];conditions={k:alignment[k] for k in ('yaw','pitch','roll','scaleRatio')};conditions.update(avgLuminance=float(crop.mean()),blurScore=float(cv2.Laplacian(crop,cv2.CV_32F).var()))
   visible={k:v for k,v in m['meshes'].items() if len(v['points'])>=3}
   p=dict(pose='FRONT',landmarks=r['landmarks'],meshes=visible,exclusions=[],qualityValid=40<=crop.mean()<=220 and r['width']>=180 and abs(alignment['yaw'])<.35,conditions=conditions)
   try:result=run(p,im);rejection=None
   except ValueError as error:
    if str(error) not in ['PHOTO_LIMIT','INVALID_PHOTO']:raise
    result=None;rejection=str(error)
   natural.append(dict(source=r['source'],sha256=r['sha256'],group=r['group'],engineeringAppearanceLabels=r['reviewDecision'].get('appearanceLabels',{}),reviewNotes=r['reviewDecision']['notes'],result=result,captureRejectedReason=rejection,missingAnatomicalRegions=[k for k in m['meshes'] if k not in visible],expertLabels=False,independentTest=False))
   if len(natural)%10==0:
    write('natural-appearance-review-partial.json',dict(rows=natural,completed=False));print('Natural reviewed',len(natural),'/',len(source),flush=True)
  write('natural-appearance-review.json',dict(rows=natural,naturalImages=len(natural),engineeringLabels=True,expertValidated=False,independentFinal=False))
 print('Appearance controls ready',len(rows),'licensed original sources; no physical acceptance',flush=True)

if __name__=='__main__':main()
