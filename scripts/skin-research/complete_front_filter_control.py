"""Two preselected additional positives for the missing filter retention proof.
No repeats of the finished four-source diagnosis, no product installation.
"""
import base64,json,shutil,subprocess,sys
from pathlib import Path
import cv2,numpy as np,torch
from safetensors.torch import load_file
from expanded_sources import ROOT,OUT,sha,write
from complete_saved_diagnosis import match
from train_focused_local import yolo_model
from yolox_numeric import install_bounds
sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'.runtime/python-packages'))
import skin_models as M
from appearance_analysis import analyze_skin,decode_photo
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions

def main():
 torch.set_num_threads(1);cv2.setNumThreads(1);d=OUT/'interim-diagnosis';old=json.loads((d/'detector-source-selection.json').read_text())['rows'];exclude={r['sha256'] for r in old};data=json.loads((OUT/'negative-expanded-detector-data.json').read_text())['rows'];selected=sorted([r for r in data if r['split']=='validation' and r['sha256'] not in exclude and len(r['annotations'])>=5 and min(r['width'],r['height'])>=640],key=lambda r:r['sha256'])[:2]
 write('interim-diagnosis/front-filter-selection.json',dict(rule='first two SHA-sorted unused development box-positive sources with >=5 labels and native dimensions >=640; before inference',rows=[dict(sha256=r['sha256'],sourcePath=r['absolutePath'],sourceFileSHA256=sha(Path(r['absolutePath'])),group=r['group'],split=r['split'],labelCount=len(r['annotations'])) for r in selected],predictionsUsedForSelection=False,finalOpened=False))
 snap=json.loads((d/'start.json').read_text())['phaseSnapshots']['negative-yolox'];assert sha(Path(snap['snapshot']))==snap['modelSHA256'];net=yolo_model();net.load_state_dict(load_file(snap['snapshot']));install_bounds(net);net.eval()
 class Session:
  def __init__(self):self.cache={}
  def run(self,outputs,inputs):
   x=inputs['native_bgr_tile'];k=__import__('hashlib').sha256(x.tobytes()).hexdigest()
   if k not in self.cache:
    with torch.inference_mode():self.cache[k]=net(torch.from_numpy(x)).numpy()
   return [self.cache[k]]
 session=Session();saved=M.load;M.load=lambda:{'sessions':{'acne':dict(session=session,metadata=dict(sha256=snap['modelSHA256'],version='isolated-front-retention-control',confidenceThreshold=.7),loadMs=0)}};task=ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task';detector=FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(task)),num_faces=2));results=[]
 try:
  for r in selected:
   assert sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath']);found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
   if len(found.face_landmarks)!=1:results.append(dict(sha256=r['sha256'],scope='unavailable',reason='single real face landmarks unavailable'));continue
   points=[dict(x=v.x,y=v.y,z=v.z) for v in found.face_landmarks[0]];mesh=json.loads(subprocess.check_output([shutil.which('node'),str(ROOT/'scripts/skin-research/focused_meshes.cjs')],input=json.dumps([dict(sha256=r['sha256'],landmarks=points,width=r['width'],height=r['height'])]).encode(),cwd=ROOT))[0]
   candidate=M.infer_acne(im,points,True);truth=[a['box'] for a in r['annotations'] if a['classId']==0];before=match(candidate['boxes'],truth);_,encoded=cv2.imencode('.png',im);photo='data:image/png;base64,'+base64.b64encode(encoded.tobytes()).decode();decoded,capture=decode_photo(photo);assert np.array_equal(decoded,im)
   analysis=analyze_skin(dict(photo=photo,photoId=capture,pose='FRONT',landmarks=points,meshes=mesh['meshes'],exclusions=[],qualityValid=True,conditions={}));measurements={k:[v for v in rs if v['id']=='acne'] for k,rs in analysis['measurements'].items()};bounds=[b for rs in measurements.values() for v in rs for b in v['components'].get('bounds',[])];after=match([[b['x'],b['y'],b['x']+b['width'],b['y']+b['height'],b['confidence']] for b in bounds],truth)
   results.append(dict(sha256=r['sha256'],modelSHA256=snap['modelSHA256'],alignment=mesh['alignment'],landmarks=points,decoder=before,afterProductFilter=after,sourceLabels=truth,removedMatchedTruth=sorted(set(before['matchedTruth'])-set(after['matchedTruth'])),actualProductMeasurements=measurements,engineeringQualityOnly=True,physicalCameraQualityValidated=False,normalAPIInstalled=False))
   print('FRONT RETENTION',r['sha256'][:12],mesh['alignment']['isAligned'],len(before['matchedTruth']),len(after['matchedTruth']),flush=True)
 finally:M.load=saved;detector.close()
 write('interim-diagnosis/front-filter-control.json',dict(rows=results,maximumAdditionalSourcePhotos=2,thresholdUnchanged=True,completedDiagnosisNotRepeated=True,finalOpened=False,productionRegistryUnchanged=True))
if __name__=='__main__':main()
