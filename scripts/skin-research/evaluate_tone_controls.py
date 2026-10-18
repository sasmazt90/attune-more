"""Paired old/new tone arithmetic on already visually reviewed source photos.

Keeps unavailable rows, source groups, source notices and local support explicit.
Engineering appearance labels do not become expert severity or pixel truth.
"""
import collections,json,subprocess
import cv2,numpy as np
from expanded_sources import ROOT,OUT,write
from train_selected_local import reviewed
from tone_candidate import tone_field
from evaluate_selected_appearance import A,run

def main():
 cv2.setNumThreads(1);original=A.local_color_signals;norm=A.NORMALIZATION['tone'];source=[r for r in reviewed() if r['reviewDecision']['appearanceLabels'].get('tone') in ['positive','negative'] and r['sha256']!='0379be8d4d89fd7f8f3757c9e0e0dc4487c9be46d714d187db3aeaf87de9e43b']
 meshes=json.loads(subprocess.check_output(['node','scripts/skin-research/focused_meshes.cjs'],input=json.dumps(source).encode(),cwd=ROOT));partial=OUT/'tone/natural-paired-controls-partial.json';rows=json.loads(partial.read_text('utf8'))['rows'] if partial.exists() else [];done={(r['source'],r['sha256']) for r in rows}
 def candidate(im,valid):
  _,red,detail=original(im,valid);tone,components=tone_field(im,valid);return tone,red,{**detail,'toneCandidate':components}
 try:
  for r,m in zip(source,meshes):
   if (r['source'],r['sha256']) in done:continue
   im=cv2.imread(r['absolutePath']);a,b,c,d=r['crop'];gray=cv2.cvtColor(im[b:d,a:c],cv2.COLOR_BGR2GRAY);conditions={k:m['alignment'][k] for k in ['yaw','pitch','roll','scaleRatio']};conditions.update(avgLuminance=float(gray.mean()),blurScore=float(cv2.Laplacian(gray,cv2.CV_32F).var()));visible={k:v for k,v in m['meshes'].items() if len(v['points'])>=3};payload=dict(pose='FRONT',landmarks=r['landmarks'],meshes=visible,exclusions=[],qualityValid=40<=gray.mean()<=220 and abs(conditions['yaw'])<.35,conditions=conditions);values=[]
   for func,version in [(original,norm),(candidate,'offline-lab-pigment-detrended-v1')]:
    A.local_color_signals=func;A.NORMALIZATION['tone']=version;response=run(payload,im);v=next(x for x in response['measurements'] if x['id']=='tone');values.append(dict(value=v['value'],reason=v.get('reason'),methodVersion=v.get('methodVersion'),calibrationVersion=v.get('calibrationVersion')))
   rows.append(dict(source=r['source'],sha256=r['sha256'],group=r['group'],split=r['split'],engineeringAppearance=r['reviewDecision']['appearanceLabels']['tone'],old=values[0],candidate=values[1],expertSeverityGrade=None))
   write('tone/natural-paired-controls-partial.json',dict(rows=rows,completed=False));print('paired tone controls',len(rows),len(source),flush=True)
 finally:A.local_color_signals=original;A.NORMALIZATION['tone']=norm
 summary={}
 for method in ['old','candidate']:
  groups=collections.defaultdict(dict);missing=collections.Counter()
  for r in rows:
   v=r[method]
   if v['value'] is None:missing[v['reason']]+=1;continue
   groups[r['engineeringAppearance']].setdefault(r['group'],[]).append(v['value'])
  arrays={k:np.array([np.median(v) for v in groups[k].values()]) for k in ['positive','negative']};pos,neg=arrays['positive'],arrays['negative'];summary[method]=dict(groupLevels={k:dict(groups=len(v),median=float(np.median(v)) if len(v) else None) for k,v in arrays.items()},positiveAboveNegativePairFraction=float(((pos[:,None]>neg).astype(float)+.5*(pos[:,None]==neg)).mean()) if len(pos) and len(neg) else None,unavailable=dict(missing))
 write('tone/natural-paired-controls.json',dict(rows=rows,summary=summary,scoreInverted=False,annotationLookup=False,thresholdFit=False,oldTestOpened=False,previouslyExposedDevelopment=True,expertCalibration=False,installed=False,explicitNewRightsNoticeExcluded=True))
 print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
