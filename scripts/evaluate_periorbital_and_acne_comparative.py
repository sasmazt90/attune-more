"""Bounded frozen-AG eye integration proof through the normal product API.

Only five named, previously exposed development sources plus one transformed
regression. No detector override, hosted request, training or AG worktree read.
"""
import argparse,ast,base64,hashlib,json,math,os,subprocess,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];LIVE_TEST=ROOT
OUT=ROOT/'audit-results/periorbital-v5-integration-20261012'
FROZEN=ROOT/'.runtime/ag-periorbital-frozen-20261012'
PREFIXES=('20031f35','36e4010b','beda0290','4b13b16a','e0ee9f0c','5bd42346')
sys.path[:0]=[str(ROOT/'services/core-api'),str(ROOT/'tests/unit'),str(ROOT/'.runtime/python-packages')]
from test_local_appearance_health import photo
import appearance_analysis as A

def load_frozen_payload_helpers():
 # Preparation needs the explicitly extracted immutable AG source; map helpers
 # and unit regressions remain importable without ignored runtime evidence.
 source=(FROZEN/'scripts/evaluate_periorbital_and_acne_comparative.py').read_text('utf8')
 lines=source.splitlines(keepends=True)
 for node in ast.parse(source).body:
  if isinstance(node,ast.FunctionDef) and node.name in ('get_mesh_and_alignment','build_production_payload'):
   exec(compile(''.join(lines[node.lineno-1:node.end_lineno]),str(FROZEN/node.name),'exec'),globals())

def compute_sha256(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()

def half_up_round(v):return None if v is None else int(math.floor(v+.5))

def decode_map_overlay(layer,shape):
 """Project analysis-grid PNG using the real source-pixel step contract."""
 out=np.zeros((*shape[:2],3),np.uint8)
 if not layer:return out
 rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)
 size=(max(1,round(rgba.shape[1]*layer['step'])),max(1,round(rgba.shape[0]*layer['step'])))
 patch=cv2.resize(rgba,size,interpolation=cv2.INTER_NEAREST);x,y=round(layer['x']),round(layer['y']);a,b=max(0,x),max(0,y);c,d=min(shape[1],x+size[0]),min(shape[0],y+size[1])
 if c>a and d>b:
  p=patch[b-y:d-y,a-x:c-x];out[b:d,a:c]=(p[:,:,:3]*(p[:,:,3:4]/255)).astype(np.uint8)
 return out

def project_map_alpha(layer,shape):
 """Every nonzero-alpha source cell, without 8-bit color-floor loss."""
 out=np.zeros(shape[:2],np.uint8)
 if not layer:return out
 rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)
 size=(max(1,round(rgba.shape[1]*layer['step'])),max(1,round(rgba.shape[0]*layer['step'])))
 patch=cv2.resize(rgba[:,:,3],size,interpolation=cv2.INTER_NEAREST);x,y=round(layer['x']),round(layer['y']);a,b=max(0,x),max(0,y);c,d=min(shape[1],x+size[0]),min(shape[0],y+size[1])
 if c>a and d>b:out[b:d,a:c]=patch[b-y:d-y,a-x:c-x]
 return out

def save(name,value):OUT.mkdir(parents=True,exist_ok=True);(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')

def prepare():
 load_frozen_payload_helpers()
 import mediapipe as mp
 from mediapipe.tasks.python import BaseOptions
 from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions,RunningMode
 mf=ROOT/'audit-results/skin-selected-20261011/manifest.json';data=json.loads(mf.read_text());selected=[]
 for prefix in PREFIXES:
  rows=[r for r in data['rows'] if r['sha256'].startswith(prefix)];assert len(rows)==1,prefix;r=rows[0];p=Path(r['absolutePath']);assert p.is_file() and compute_sha256(p)==r['sha256'];selected.append(r)
 del data
 ledger=ROOT/'audit-results/skin-expanded-20261011/scope-v4-mask-data.json';scope=json.loads(ledger.read_text())['rows'];records=[];sources=[]
 model=ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
 with FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model)),running_mode=RunningMode.IMAGE,num_faces=1)) as detector:
  for r in selected:
   image=cv2.imread(r['absolutePath']);assert image is not None;result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)));assert result.face_landmarks
   landmarks=[dict(x=float(p.x),y=float(p.y),z=float(p.z)) for p in result.face_landmarks[0]]
   records.append(dict(sha256=r['sha256'],landmarks=landmarks,width=image.shape[1],height=image.shape[0]))
 meshes=get_mesh_and_alignment(records)
 for r,geometry,m in zip(selected,records,meshes):
  image=cv2.imread(r['absolutePath']);payload=build_production_payload(image,r['sha256'],geometry['landmarks'],m['alignment'],m['meshes']);payload.update(processingConsent=True,hostedProcessingConsent=False)
  sha=r['sha256'];prefix=sha[:8];review=[v for v in scope if v['sha256']==sha and v['target']=='bags'];category='transformed_noisy_regression' if prefix=='5bd42346' else 'development_positive_polygon' if prefix in PREFIXES[:2] else 'natural_reviewed_negative'
  if category=='natural_reviewed_negative':assert any(v.get('engineeringNegativeROIReviewed') for v in review)
  metadata={k:r.get(k) for k in ('source','path','absolutePath','sha256','split','groupExposed','reviewExposed','rights','naturalRGB')};metadata.update(sampleCategory=category,scopeLedgerRows=review,partialAnnotations=[a for a in r.get('annotations',[]) if any(t in a.get('label','').lower() for t in ('bag','circle','wrinkle'))],selectionRationale='Previously exposed development positive; source partial polygon, outside remains unknown' if prefix in PREFIXES[:2] else 'Transformed/rotated/noisy regression only; excluded from natural-negative claims' if prefix=='5bd42346' else 'Existing bags-specific engineering-reviewed negative support only; unreviewed pixels remain unknown')
  sources.append(metadata);save(prefix+'-payload.json',payload)
  baseline=ROOT/'.runtime/ag-periorbital-baseline-20261012/services/core-api'
  code="import sys,json;sys.path[:0]="+repr([str(baseline),str(ROOT/'services/core-api'),str(ROOT/'.runtime/python-packages')])+";import appearance_analysis as a;print(json.dumps(a.analyze_skin(json.loads(sys.stdin.read()))))"
  env={k:v for k,v in os.environ.items() if k not in ('ATTUNE_ROBOFLOW_API_KEY','ROBOFLOW_API_KEY','ATTUNE_LOAD_LOCAL_ENV')}
  ran=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=ROOT,env=env);assert ran.returncode==0,ran.stderr;save(prefix+'-baseline.json',json.loads(ran.stdout))
 save('sources.json',dict(frozenAGCommit='ff0b161bd807fe81d2ba5ee6283d4f5b26f6a102',baselineCommit='d596873c363a57324d38dc974e5ad65186ea9866',sourceInventorySHA256=compute_sha256(mf),scopeLedgerSHA256=compute_sha256(ledger),mediapipeModelSHA256=compute_sha256(model),sources=sources,actualMediaPipe=True,cloudRequests=0))
 print(json.dumps(dict(prepared=len(sources),actualMediaPipe=True,baselineFrozen=True)))

def request(url,data):
 req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as response:return json.loads(response.read())

def anatomy(layer,payload,source_shape,criterion):
 if not layer:return dict(activeAnalysisPixels=0,outsideEyeBandAnalysisPixels=0,outsideSelectedRegionAnalysisPixels=0,activeSourcePixels=0,outsideEyeBandSourcePixels=0,outsideSelectedRegionSourcePixels=0)
 rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED);active=rgba[:,:,3]>0
 # The actual roll-aware lower-eye band and actual production triangulated mesh.
 # Rasterize once on the exact production analysis frame, then crop. Rebuilding
 # polygons at map-local origin changes integer truncation at negative vertices.
 face=abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*source_shape[1]
 scale=min(1.,A.LIMITS['analysisFacePixels']/max(face,1))
 points=np.asarray([[v['x'],v['y']] for m in payload['meshes'].values() for v in m['points']],np.float32)
 pad=max(20,face*.1);x0=max(0,int(points[:,0].min()-pad));y0=max(0,int(points[:,1].min()-pad));x1=min(source_shape[1],int(points[:,0].max()+pad+1));y1=min(source_shape[0],int(points[:,1].max()+pad+1))
 whole_shape=(round((y1-y0)*scale),round((x1-x0)*scale));mx=round((layer['x']-x0)*scale);my=round((layer['y']-y0)*scale)
 band=A.eye_skin_bands(payload['landmarks'],whole_shape,scale,(x0,y0),source_shape)[criterion][my:my+active.shape[0],mx:mx+active.shape[1]]
 region_mask=A.bag_support_mask if criterion=='bags' else A.polygon_mask
 region=region_mask(whole_shape,payload['meshes']['periorbital'],scale,(x0,y0))[my:my+active.shape[0],mx:mx+active.shape[1]]
 native=project_map_alpha(layer,source_shape)>0;native_band=A.eye_skin_bands(payload['landmarks'],source_shape[:2],1,(0,0),source_shape)[criterion];native_region=region_mask(source_shape[:2],payload['meshes']['periorbital'],1)
 legacy_visible=((rgba[:,:,:3]*(rgba[:,:,3:4]/255)).astype(np.uint8).sum(axis=2)>0)
 return dict(activeAnalysisPixels=int(active.sum()),weightedRGB8bitVisibleAnalysisPixels=int(legacy_visible.sum()),insideEyeBandAnalysisPixels=int((active&band).sum()),outsideEyeBandAnalysisPixels=int((active&~band).sum()),insideSelectedRegionAnalysisPixels=int((active&region).sum()),outsideSelectedRegionAnalysisPixels=int((active&~region).sum()),activeSourcePixels=int(native.sum()),insideEyeBandSourcePixels=int((native&native_band).sum()),outsideEyeBandSourcePixels=int((native&~native_band).sum()),insideSelectedRegionSourcePixels=int((native&native_region).sum()),outsideSelectedRegionSourcePixels=int((native&~native_region).sum()),sourceStep=layer['step'],sourceGridMeaning='Analysis-cell native projection uses nearest-neighbor; strict native edge counts include cell rasterization boundaries; active means PNG alpha >0',verification='Actual eye_skin_bands and production mesh triangle union; no y-only heuristic')

def known_roi(source,shape,channel_order,positive=False):
 mask=np.zeros(shape[:2],np.uint8)
 for r in source['scopeLedgerRows']:
  if not positive and not r.get('engineeringNegativeROIReviewed'):continue
  p=ROOT/'audit-results/skin-expanded-20261011/scope-v4-native/tensors'/r['id'];channel=channel_order.index(r['target'])
  with np.load(p,allow_pickle=False) as z:
   target=z['truth'][channel];known=z['support'][channel];bits=(known>0)&((target>0) if positive else (target<=0));bits=np.squeeze(bits).astype(np.uint8)
  x,y,x1,y1=r['rect'];patch=cv2.resize(bits,(x1-x,y1-y),interpolation=cv2.INTER_NEAREST);mask[y:y1,x:x1]|=patch
 return mask>0

def api(url):
 request(url+'/api/vehicle/speed',{'speedKmH':0});source_data=json.loads((OUT/'sources.json').read_text());rows=[]
 channel_order=json.loads((ROOT/'audit-results/skin-expanded-20261011/scope-v4-mask-data.json').read_text())['targets']
 for source in source_data['sources']:
  prefix=source['sha256'][:8];payload=json.loads((OUT/(prefix+'-payload.json')).read_text());baseline=json.loads((OUT/(prefix+'-baseline.json')).read_text());actual=request(url+'/api/local-health/skin',payload);assert actual['photoId']==payload['photoId'];save(prefix+'-api.json',actual)
  image=cv2.imread(source['absolutePath']);targets={}
  for target in ('bags','dark','lines'):
   old=next(v for v in baseline['measurements']['periorbital'] if v['id']==target);new=next(v for v in actual['measurements']['periorbital'] if v['id']==target);layer=actual['maps'].get('periorbital:'+target);proof=anatomy(layer,payload,image.shape,target)
   assert proof['outsideEyeBandAnalysisPixels']==0,(prefix,target,proof)
   assert proof['outsideSelectedRegionAnalysisPixels']==0,(prefix,target,proof)
   if new['value'] in (0,None):assert proof['activeAnalysisPixels']==0
   targets[target]=dict(baseline={k:old.get(k) for k in ('value','quality','limitationCode','normalizationVersion')},product={k:new.get(k) for k in ('value','quality','limitationCode','normalizationVersion')},uiScore=half_up_round(new['value']),mapAnatomy=proof)
  assert targets['bags']['product']['normalizationVersion']=='contour-fold-local-support-v5'
  lower=[]
  for region in ('rightCheek','leftCheek','chin'):
   old=next(v for v in baseline['measurements'][region] if v['id']=='sag');new=next(v for v in actual['measurements'][region] if v['id']=='sag');assert old==new,(prefix,region,'Lower-face method drift');assert baseline['maps'].get(region+':sag')==actual['maps'].get(region+':sag');lower.append(region)
  row=dict(source=source,qualityValid=payload['qualityValid'],conditions=payload['conditions'],sourcePhotoId=payload['photoId'],targets=targets,lowerFaceExactlyPreserved=lower,api='normal product /api/local-health/skin',hostedProcessingConsent=False)
  if source['sampleCategory']=='natural_reviewed_negative':
   reviewed=known_roi(source,image.shape,channel_order);active=project_map_alpha(actual['maps'].get('periorbital:bags'),image.shape)>0;row['reviewedNegativeROI']=dict(pixels=int(reviewed.sum()),activePixels=int((active&reviewed).sum()),unknownOutsidePixels=int((~reviewed).sum()),outsideUnknownIsNegative=False)
  rows.append(row);print(json.dumps(dict(source=prefix,bags=targets['bags']['product']['value'],dark=targets['dark']['product']['value'],lines=targets['lines']['product']['value'],active=targets['bags']['mapAnatomy']['activeAnalysisPixels'])),flush=True)
 save('comparative-results.json',dict(executedAt=datetime.now(timezone.utc).isoformat(),frozenSource=source_data,backendHashes={n:compute_sha256(ROOT/'services/core-api'/n) for n in ('appearance_analysis.py','instant_appearance.py','skin_general.py','skin_models.py','hosted_skin_type.py')},rows=rows,scope='Five previously exposed real sources; transformed sixth regression separate, not general application accuracy',newTraining=False,newHostedCalls=False,rejectedModelsEnabled=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--api-url');args=parser.parse_args();cv2.setNumThreads(1)
 if args.prepare:prepare()
 elif args.api_url:api(args.api_url)
 else:parser.error('Choose --prepare or --api-url')
