"""Actual source-only proxy arithmetic and train-only grade calibration.

Previously opened test rows are not final tests; this run excludes them entirely.
Matched photo grades never become regional/pixel target copies.
"""
import collections,json,subprocess,sys,time
from pathlib import Path
import cv2,numpy as np
from expanded_sources import ROOT,OUT,PREVIOUS,sha,write
from prepare_focused_data import TARGETS as GRADES
from calibrate_focused_appearance import isotonic_knots
from tone_candidate import tone_field
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
from evaluate_selected_appearance import run

def main():
 cv2.setNumThreads(1);old=A.local_color_signals;source=PREVIOUS.parent/'skin-followup-20261011/development-manifest-v2.json';m=json.loads(source.read_text('utf8'));rows=[r for r in m['rows'] if r.get('degreeEligible') and r['split']!='test'];folder=OUT/'tone';folder.mkdir(parents=True,exist_ok=True)
 receipt=folder/'graded-rows.json'
 if receipt.exists():print('Completed frozen tone development calibration preserved');return
 def candidate(image,valid):
  _,red,components=old(image,valid);tone,detail=tone_field(image,valid);return tone,red,{**components,'toneCandidate':detail}
 mesh=json.loads(subprocess.check_output(['node','scripts/skin-research/focused_meshes.cjs'],input=json.dumps(rows).encode(),cwd=ROOT));results=[];started=time.monotonic()
 for i,(r,s) in enumerate(zip(rows,mesh)):
  assert sha(Path(r['absolutePath']))==r['sha256'];bgr=cv2.imread(r['absolutePath']);a,b,c,d=r['crop'];crop=cv2.cvtColor(bgr[b:d,a:c],cv2.COLOR_BGR2GRAY);alignment=s['alignment'];conditions={k:alignment[k] for k in ['yaw','pitch','roll','scaleRatio']};conditions.update(avgLuminance=float(crop.mean()),blurScore=r['blur'])
  payload=dict(pose='FRONT',landmarks=r['landmarks'],meshes=s['meshes'],exclusions=[],qualityValid=40<=crop.mean()<=220 and r['blur']>=4 and abs(alignment['yaw'])<.35,conditions=conditions)
  values=[]
  for function in [old,candidate]:
   A.local_color_signals=function
   value=run(payload,bgr);tone=next(x for x in value['measurements'] if x['id']=='tone');values.append(dict(value=tone['value'],reason=tone.get('reason'),calibrationVersion=tone.get('calibrationVersion')))
  A.local_color_signals=old
  results.append(dict(sha256=r['sha256'],group=r['group'],split=r['split'],grade=r['grades'][GRADES.index('tone')],old=values[0],candidate=values[1],labelProtocolExpertVerified=False))
  if (i+1)%10==0:print('tone matched actual photos',i+1,len(rows),flush=True)
 paired=lambda split:[r for r in results if r['split']==split and r['grade'] is not None and r['candidate']['value'] is not None]
 tr=paired('train');va=paired('validation');calibration=dict(pairedTrainingGrades=len(tr),pairedValidationGrades=len(va),scope='matched whole-photo development grades only',testReuse=False)
 if len(tr)>=10 and len(va)>=10:
  x=np.array([r['candidate']['value'] for r in tr]);y=np.array([r['grade'] for r in tr]);knots=isotonic_knots(x,y);v=np.array([r['candidate']['value'] for r in va]);truth=np.array([r['grade'] for r in va]);prediction=np.interp(v,*knots);mae=float(np.abs(truth-prediction).mean());baseline=float(np.abs(truth-np.median(y)).mean());calibration.update(knots=dict(x=knots[0],y=knots[1]),MAE=mae,trainingMedianBaselineMAE=baseline,beatsTrainingMedianBaseline=mae<baseline)
 else:calibration.update(MAE=None,beatsTrainingMedianBaseline=False,reason='PAIRED_GLOBAL_VALIDATION_COVERAGE_INCOMPLETE')
 write('tone/graded-rows.json',dict(rows=results,sourceSHA256=sha(source),calibration=calibration,oldTestPixelsOpened=False,unusedFinal=False,naturalConfounderReviewComplete=False,installed=False,seconds=time.monotonic()-started));print(json.dumps(calibration),flush=True)

if __name__=='__main__':main()
