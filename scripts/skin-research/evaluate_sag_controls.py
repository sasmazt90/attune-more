"""Engineering review of actual lower-face contours, never age-based labels.

No test, user photographs, downloads, expert grades or surgery labels are used.
Visible positive controls must expose both lower-cheek/jaw descent and folds.
"""
import json,sys,subprocess,shutil,datetime
from pathlib import Path
import cv2,numpy as np
from expanded_sources import ROOT,OUT,write,sha
sys.path.insert(0,str(ROOT/'.runtime/python-packages'))
sys.path.insert(0,str(ROOT/'services/core-api'))
from evaluate_selected_appearance import run

POS={47,57}
NEG={4,6,18,24,30,37,44,58}
RIGHTS={11,64}
COLLAGE={50}
CROPPED={1,2,3,8,13,17,36,38,40,41,42,43,45,46,48,51,52,54,55,60,62,63,65,66,68,69}
SMILE={0,5,7,12,15,16,20,21,22,23,25,26,27,28,29,31,32,33,34,49,56,59}

def main():
 cv2.setNumThreads(1);folder=OUT/'sag-controls'
 if (folder/'actual-results.json').exists():shutil.copy2(folder/'actual-results.json',folder/('actual-results-before-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S')+'.json'))
 first=json.loads((folder/'candidates.json').read_text('utf8'));second=json.loads((folder/'additional-candidates.json').read_text('utf8'));rows=first+second
 assert len(rows)==72 and all(r['split']!='test' for r in rows)
 reviewed=[]
 for i,r in enumerate(rows):
  reason='LOWER_FACE_APPEARANCE_UNCERTAIN_OR_OCCLUDED'
  if i in RIGHTS:reason='VISIBLE_PHOTOGRAPHER_OR_STOCK_NOTICE'
  elif i in COLLAGE:reason='MULTI_PANEL_COMPONENT_GROUP_PENDING'
  elif i in CROPPED:reason='LOWER_JAW_CROPPED_OR_PROCESSED_FACE_CUTOUT'
  elif i in SMILE:reason='EXPRESSION_POSE_OR_RETOUCH_CONFOUNDING'
  elif i in POS:reason='VISIBLE_LOWER_CHEEK_JAW_DESCENT_AND_MOUTH_SIDE_FOLDS'
  elif i in NEG:reason='VISIBLE_NEUTRAL_LOWER_CONTOUR_WITHOUT_TARGET_DESCENT'
  reviewed.append(dict(index=i,sha256=r['sha256'],group=r['group'],split=r['split'],visualReviewComplete=True,reason=reason,engineeringSagAppearance='positive' if i in POS else 'negative' if i in NEG else None,expertGrade=None,ageUsedAsTruth=False,rightsVerified=False))
 write('sag-controls/review.json',dict(rows=reviewed,boardsActuallyViewed=list(range(12)),naturalPositivePhotos=len(POS),naturalNegativePhotos=len(NEG),independentFinal=False))
 import mediapipe as mp
 from mediapipe.tasks.python import BaseOptions
 from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions
 detector=FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')),num_faces=2))
 selected=[];rejected=[]
 for i in sorted(POS|NEG):
  r=dict(rows[i]);assert sha(Path(r['absolutePath']))==r['sha256'];im=cv2.imread(r['absolutePath'])
  if not r.get('landmarks'):
   found=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
   if len(found.face_landmarks)!=1:rejected.append(dict(index=i,reason='SINGLE_FACE_LANDMARK_NOT_AVAILABLE'));continue
   r['landmarks']=[dict(x=p.x,y=p.y,z=p.z) for p in found.face_landmarks[0]]
  r['reviewIndex']=i;selected.append(r)
 detector.close()
 repeats=[]
 meshes=json.loads(subprocess.check_output(['node','scripts/skin-research/focused_meshes.cjs'],input=json.dumps(selected).encode(),cwd=ROOT));results=[]
 for r,m in zip(selected,meshes):
  im=cv2.imread(r['absolutePath']);gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY);alignment=m['alignment'];conditions={k:alignment[k] for k in ['yaw','pitch','roll','scaleRatio']};conditions.update(avgLuminance=float(gray.mean()),blurScore=float(cv2.Laplacian(gray,cv2.CV_32F).var()))
  payload=dict(pose='FRONT',landmarks=r['landmarks'],meshes=m['meshes'],exclusions=[],qualityValid=40<=gray.mean()<=220 and conditions['blurScore']>=4 and abs(alignment['yaw'])<.35,conditions=conditions)
  response=run(payload,im);repeat=run(payload,im);repeats.append(response['measurements']==repeat['measurements'] and response['regionMeasurements']==repeat['regionMeasurements']);globalrow=next(v for v in response['measurements'] if v['id']=='sag');local={region:[v for v in values if v['id']=='sag'] for region,values in response['regionMeasurements'].items()} if isinstance(response['regionMeasurements'],dict) else response['regionMeasurements']
  results.append(dict(index=r['reviewIndex'],sha256=r['sha256'],group=r['group'],engineeringSagAppearance='positive' if r['reviewIndex'] in POS else 'negative',globalMeasurement=globalrow,localMeasurements=local,alignment=alignment,expertGrade=None))
 positive=[r for r in results if r['engineeringSagAppearance']=='positive' and r['globalMeasurement']['value'] is not None];negative=[r for r in results if r['engineeringSagAppearance']=='negative' and r['globalMeasurement']['value'] is not None]
 write('sag-controls/actual-results.json',dict(rows=results,rejected=rejected,gradablePositivePhotos=len(positive),gradableNegativePhotos=len(negative),positiveMedian=float(np.median([r['globalMeasurement']['value'] for r in positive])) if positive else None,negativeMedian=float(np.median([r['globalMeasurement']['value'] for r in negative])) if negative else None,expertCalibrated=False,sameInputRepeatabilityPassed=bool(repeats) and all(repeats),appearanceSeparationAccepted=False if positive and negative and np.median([r['globalMeasurement']['value'] for r in positive])<=np.median([r['globalMeasurement']['value'] for r in negative]) else None,independentFinal=False))
 print(json.dumps(dict(gradablePositivePhotos=len(positive),gradableNegativePhotos=len(negative),rejected=rejected)),flush=True)

if __name__=='__main__':main()
