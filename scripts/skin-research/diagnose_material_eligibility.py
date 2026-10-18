"""Bounded single 0.25MP source diagnosis; no model/encoder or photo pool."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import ast,base64,hashlib,json,sys,time
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';process=psutil.Process()
if psutil.virtual_memory().available<650*2**20:raise RuntimeError('Insufficient RAM for bounded source-local diagnosis')
import cv2,numpy as np
sys.path.insert(0,str(ROOT/'services/core-api'));import native_flake_support as F
cv2.setNumThreads(1);peak=0
def check():
    global peak
    peak=max(peak,process.memory_info().rss/2**20)
    if peak>250 or psutil.virtual_memory().available<400*2**20:raise RuntimeError('Source-local RSS/reserve budget exceeded')
namespace={'np':np,'cv2':cv2};tree=ast.parse((ROOT/'services/core-api/appearance_analysis.py').read_text('utf8'));functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ['polygon_mask','closed_surface_mask']]
exec(compile(ast.Module(body=functions,type_ignores=[]),'current-source-geometry','exec'),namespace)
payload=json.loads((ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json').read_text('utf8'));raw=base64.b64decode(payload['photo'].split(',')[1]);image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR);assert image.shape[0]*image.shape[1]<250000
assert hashlib.sha256(cv2.cvtColor(image,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()==payload['photoId'];h,w=image.shape[:2];p=payload['landmarks'];metric=abs(p[454]['x']-p[234]['x'])*w/640
points=np.array([[v['x'],v['y']] for m in payload['meshes'].values() for v in m['points']]);pad=max(48,int(np.ceil(40*metric)));a=max(0,int(np.floor(points[:,0].min()))-pad);b=max(0,int(np.floor(points[:,1].min()))-pad);c=min(w,int(np.ceil(points[:,0].max()))+pad+1);d=min(h,int(np.ceil(points[:,1].max()))+pad+1);crop=image[b:d,a:c];origin=(a,b);shape=crop.shape[:2];gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);g=gray.astype(np.float32)/255
anatomy=np.logical_or.reduce([namespace['closed_surface_mask'](shape,m,1,origin) for m in payload['meshes'].values()]);excluded=np.zeros(shape,np.uint8)
for box in payload['exclusions']:cv2.rectangle(excluded,(int(np.floor(box['x']-a)),int(np.floor(box['y']-b))),(int(np.ceil(box['x']+box['w']-a)),int(np.ceil(box['y']+box['h']-b))),1,-1)
for indices in [[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]:
    poly=np.array([[p[i]['x']*w-a,p[i]['y']*h-b] for i in indices],np.int32);cv2.fillPoly(excluded,[poly],1)
kernel=max(3,2*int(round(3*metric))+1);dark=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((kernel,kernel),np.uint8))>35;n,ids,stats,_=cv2.connectedComponentsWithStats(dark.astype(np.uint8),8);keep=np.zeros(n,bool)
for i in range(1,n):
    _,_,ww,hh,_=stats[i];keep[i]=max(ww,hh)>=max(3,8*metric) and max(ww,hh)/max(1,min(ww,hh))>=3
hair=cv2.dilate(keep[ids].astype(np.uint8),np.ones((max(3,2*int(round(2*metric))+1),)*2,np.uint8))>0;check();started=time.monotonic();field,_=F.native_field(crop,metric,check=check);seconds=time.monotonic()-started;targets=json.loads((ROOT/'audit-results/material-runtime-followup-20261013/source-location-correction.json').read_text('utf8'))['targets'];rows=[];preview=image.copy()
for target in targets:
    mask=np.zeros(image.shape[:2],np.uint8);cv2.fillPoly(mask,[np.asarray(target['polygon'],np.int32)],1);local=mask[b:d,a:c]>0;active=(field>.04)&local
    stages=[('proposal',np.ones(shape,bool)),('anatomy',anatomy),('anatomyAndExclusion',anatomy&(excluded==0)),('beforeHair',anatomy&(excluded==0)&(g>.12)&(g<.975)),('eligible',anatomy&(excluded==0)&~hair&(g>.12)&(g<.975))]
    counts={name:int((active&support).sum()) for name,support in stages};assert counts['proposal']==target['preAnatomyProposalPixels'] and counts['eligible']==target['eligibleProposalPixels']
    rows.append(dict(polygon=target['polygon'],counts=counts,outsideLocation='UNKNOWN',label='partial visible material location, etiology UNKNOWN'))
    cv2.polylines(preview,[np.asarray(target['polygon'],np.int32)],True,(255,0,255),1)
    ys,xs=np.where(active);colors=np.tile([0,255,255],(len(xs),1));colors[~anatomy[ys,xs]]=[255,80,0];colors[anatomy[ys,xs]&hair[ys,xs]]=[0,0,255];preview[ys+b,xs+a]=colors
cv2.imwrite(str(OUT/'24031977-anatomy-hair-stage.png'),preview);check();receipt=dict(source='24031977',photoId=payload['photoId'],sourceOrigin=list(origin),rows=rows,proposalSeconds=seconds,peakMeasuredRSSMiB=peak,sourcePoolSize=1,encoderCalls=0,geometryFromCurrentProductionSource=True,AGModified=False)
(OUT/'material-eligibility-diagnosis.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)
