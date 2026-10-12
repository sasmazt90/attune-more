"""Six bounded real development P/N source chains; no new validation round."""
import base64,json,sys,subprocess,shutil
from pathlib import Path
import cv2,numpy as np,onnxruntime as ort
from expanded_sources import ROOT,OUT,sha,write
from prepare_continuation_masks import TARGETS as DATA_TARGETS
sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'.runtime/python-packages'))
from skin_native_mask import CONTRACT,tensor
from skin_mask_staging import stage_mask
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions

def read(p):return json.loads(p.read_text('utf8'))
def main():
 cv2.setNumThreads(1);d=OUT/'interim-diagnosis';index=read(d/'selected-full-export-current.json');planpath=Path(index['planPath']);assert sha(planpath)==index['planSHA256'];plan=read(planpath);data=read(OUT/'scope-v4-mask-data.json');sources={}
 for p in [OUT/'candidates.json',OUT/'supplement/candidates.json',OUT/'negative-expansion/candidates.json',ROOT/'audit-results/skin-selected-20261011/review/candidates.json']:
  for r in read(p)['rows']:sources.setdefault(r['sha256'],r)
 selected=[]
 for target in ['oil','redness','tone']:
  for positive in [True,False]:
   pool=[r for r in data['rows'] if r['target']==target and r['split']=='validation' and (r['positivePixels']>0 if positive else not r['positivePixels'] and r.get('engineeringNegativeROIReviewed') is True)]
   row=sorted(pool,key=lambda r:(r['sha256'],r['id']))[0];selected.append(dict(target=target,positive=positive,sha256=row['sha256'],tensorID=row['id'],sourcePath=sources[row['sha256']]['absolutePath']))
 write('interim-diagnosis/mask-product-staging-selection.json',dict(rows=selected,selectionRule='first SHA-sorted suitable development positive and explicitly reviewed negative source per target; before inference',predictionsUsedForSelection=False,finalOpened=False))
 detector=FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')),num_faces=2));results=[];cache={};opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1
 try:
  for r in selected:
   path=Path(r['sourcePath']);assert sha(path)==r['sha256'];im=cv2.imread(str(path));found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
   if len(found.face_landmarks)!=1:results.append(dict(**r,available=False,reason='REAL_SINGLE_FACE_LANDMARKS_UNAVAILABLE'));continue
   points=[dict(x=p.x,y=p.y,z=p.z) for p in found.face_landmarks[0]];m=json.loads(subprocess.check_output([shutil.which('node'),str(ROOT/'scripts/skin-research/focused_meshes.cjs')],input=json.dumps([dict(sha256=r['sha256'],landmarks=points,width=im.shape[1],height=im.shape[0])]).encode(),cwd=ROOT))[0];v=plan['targets'][r['target']];export=v['export'];op=Path(export['onnxPath']);assert sha(op)==export['modelSHA256'] and export['numericalParity'];cache.setdefault(str(op),ort.InferenceSession(str(op),opt,providers=['CPUExecutionProvider']))
   metadata=dict(sha256=sha(op),fullWeightsSHA256=export['weightsSHA256'],channel=v['channel'],preprocessing=CONTRACT);photo=__import__('hashlib').sha256(cv2.cvtColor(im,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest();stage=stage_mask(im,points,m['meshes'],cache[str(op)],metadata,r['target'],photo);prediction=stage['output'].pop('mask');support=stage.pop('support');truth=np.zeros(im.shape[:2],bool);negative=np.zeros(im.shape[:2],bool)
   for row in data['rows']:
    if row['sha256']!=r['sha256'] or row['target']!=r['target'] or row['split']!='validation':continue
    a,b,c,e=row['rect'];j=DATA_TARGETS.index(r['target'])
    with np.load(OUT/data['tensorFolder']/row['id']) as f:
     y=f['truth'][j,:e-b,:c-a]>0;s=f['support'][j,:e-b,:c-a]>0;truth[b:e,a:c]|=y
     if row.get('engineeringNegativeROIReviewed') is True:negative[b:e,a:c]|=s&~y
   knownpositive=truth&support;knownnegative=negative&~truth&support
   metrics=dict(labelledPositivePixels=int(truth.sum()),visibleLabelledPositivePixels=int(knownpositive.sum()),capturedPositivePixels=int((prediction&knownpositive).sum()),positiveRecall=float(prediction[knownpositive].mean()) if knownpositive.any() else None,reviewedNegativePixels=int(knownnegative.sum()),reviewedNegativeFPR=float(prediction[knownnegative].mean()) if knownnegative.any() else None,fullROIDice=None,severityLabel=None,unknownOutsidePartialLabels=True)
   folder=d/'mask-product-staging';folder.mkdir(exist_ok=True);np.savez_compressed(folder/(r['target']+'-'+str(r['positive'])+'-support.npz'),prediction=prediction,support=support,truth=truth,reviewedNegative=negative)
   # Natural source pixels plus the actual production-format selected map payload.
   _,encoded=cv2.imencode('.png',im);stage.update(photoId=photo,dataUrl='data:image/png;base64,'+base64.b64encode(encoded).decode(),width=im.shape[1],height=im.shape[0],angle='FRONT',exclusions=[],landmarks=points)
   out=folder/(r['target']+'-'+str(r['positive'])+'.json');out.write_text(json.dumps(stage),'utf8')
   results.append(dict(**r,available=True,fullModelSHA256=export['weightsSHA256'],ONNXSHA256=metadata['sha256'],channel=v['channel'],contract=CONTRACT,sourcePixelSHA256=photo,metrics=metrics,regions=stage['rows'],mapKeys=sorted(stage['maps']),artifact=str(out),artifactSHA256=sha(out),tileCount=stage['output']['tileCount'],physicalCameraQualityValidated=False,normalAPIInstalled=False))
   print('MASK PRODUCT STAGING',r['target'],r['positive'],metrics,flush=True)
 finally:detector.close()
 write('interim-diagnosis/mask-product-staging-verification.json',dict(rows=results,codeSHA256=sha(ROOT/'services/core-api/skin_mask_staging.py'),planSHA256=sha(planpath),sourceNative256=True,oldEye128AdapterUsed=False,normalAPIInstalled=False,finalOpened=False))
if __name__=='__main__':main()
