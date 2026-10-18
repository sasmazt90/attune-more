"""Actual main-checkout geometry, two classical methods; no training or activation."""
import argparse,ast,base64,hashlib,json,sys,time
from pathlib import Path
from prepare_acne_classical_comparison import ROOT,OUT,BASE,read,sha,a_identity
from acne_lab_dog import CONFIG,VERSION,detect,match_boxes,candidate_result
from heavy_job_lease import HeavyJobLease
sys.path.insert(0,str(ROOT/'services/core-api'))

def production_context(payload):
 import appearance_analysis as production
 tree=ast.parse(Path(production.__file__).read_text('utf8'));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='analyze_skin');body=[]
 for node in fn.body:
  # Do not load other criteria/models. Keep original image/preprocessing/geometry statements.
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['trained_acne','trained_bags'] for t in node.targets):
   node.value=ast.Constant(None)
  body.append(node)
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='acne_skin' for t in node.targets):break
 else:raise ValueError('PRELUDE_CHANGED')
 body.append(ast.Return(ast.Call(ast.Name('locals',ast.Load()),[],[])));fn.body=body
 namespace=dict(vars(production));exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(production.__file__),'exec'),namespace)
 return namespace['analyze_skin'](payload)

def run(photo,entry,method):
 import cv2,numpy as np
 started=time.perf_counter();snap=entry['snapshot'];a=entry['alignment'];image=cv2.imdecode(np.frombuffer(photo,np.uint8),cv2.IMREAD_COLOR)
 pixel_id=hashlib.sha256(cv2.cvtColor(image,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
 payload=dict(photo='data:image/png;base64,'+base64.b64encode(photo).decode(),photoId=pixel_id,landmarks=a['landmarks'],meshes=snap['meshes'],exclusions=snap['exclusions'],qualityValid=entry['quality']['isValid'],conditions={k:a[k] for k in ['yaw','pitch','roll','scaleRatio']})
 decoded=time.perf_counter();ctx=production_context(payload);prepared=time.perf_counter()
 # Both methods must own the SAME current mesh support, not different envelopes.
 regions={k:v for k,v in ctx['masks'].items() if k in ['forehead','rightCheek','leftCheek','nose','chin']}
 eligible=ctx['overall']&ctx['acne_skin']&np.logical_or.reduce(list(regions.values()))
 origin=ctx['origin'];scale=ctx['scale'];transform=np.array([[1/scale,0,origin[0]],[0,1/scale,origin[1]]],np.float32)
 native_eligible=cv2.warpAffine(eligible.astype(np.uint8),transform,(image.shape[1],image.shape[0]),flags=cv2.INTER_NEAREST)>0
 from skin_models import photo_input
 _,crop=photo_input(image,a['landmarks']);x,y,w,h=[crop[k] for k in ['x','y','width','height']]
 crop_scope=np.zeros(native_eligible.shape,bool);crop_scope[y:y+h,x:x+w]=True;native_eligible&=crop_scope
 if method=='A':
  from appearance_analysis import acne_candidates
  from skin_scan_baseline.blemishes import blemish_map
  baseline=blemish_map(ctx['image'],{k:(v*255).astype(np.uint8) for k,v in ctx['masks'].items()})
  frozen,_=acne_candidates(ctx['red'],ctx['gray'],ctx['saturation'],ctx['high'],ctx['local_contrast'],baseline,ctx['overall'])
  objects=[];rejected=0
  for bx,by,bw,bh,count,blob in frozen:
   owners=[k for k in ['forehead','rightCheek','leftCheek','nose','chin'] if k in regions and regions[k][blob].mean()>=.65]
   if not owners or not eligible[blob].all():rejected+=1;continue
   objects.append(dict(x=bx,y=by,width=bw,height=bh,areaPixels=count,region=owners[0],pixels=np.column_stack(np.where(blob))[:,::-1]))
  result,mask=candidate_result(objects,eligible.shape,origin,scale)
  native_map=cv2.warpAffine(mask.astype(np.uint8),transform,(image.shape[1],image.shape[0]),flags=cv2.INTER_NEAREST)>0
  diagnostics=dict(valid=True,originalComponents=len(frozen),sharedScopeRejected=rejected)
 else:
  objects,_,diagnostics=detect(image[y:y+h,x:x+w],native_eligible[y:y+h,x:x+w],ctx['face_pixels'])
  native_regions={k:cv2.warpAffine(v.astype(np.uint8),transform,(image.shape[1],image.shape[0]),flags=cv2.INTER_NEAREST)>0 for k,v in regions.items()}
  accepted=[]
  for obj in objects:
   obj={**obj,'x':obj['x']+x,'y':obj['y']+y,'pixels':obj['pixels']+[x,y]};pixels=obj['pixels']
   owners=[k for k in ['forehead','rightCheek','leftCheek','nose','chin'] if k in native_regions and native_regions[k][pixels[:,1],pixels[:,0]].mean()>=.65]
   if owners:obj['region']=owners[0];accepted.append(obj)
  result,native_map=candidate_result(accepted,native_eligible.shape)
 native_map&=native_eligible
 result.update(method=method,version='frozen-acne-candidates-analysis320' if method=='A' else VERSION,diagnostics=diagnostics,sourceResolution=list(image.shape[1::-1]),analysisResolution=list(ctx['gray'].shape[::-1]),sourceFacePixels=ctx['face_pixels'],sourceTransform=dict(origin=list(origin),scale=scale),photoInputCrop=crop,activeSourcePixels=int(native_map.sum()),sourceMapSHA256=hashlib.sha256(native_map.tobytes()).hexdigest(),firstScanIndependent=True)
 # Serialize inside the measured end-to-end classical analysis, no result cache.
 json.dumps(result,allow_nan=False);finished=time.perf_counter()
 result['seconds']=dict(decode=decoded-started,preprocessing=prepared-decoded,detectionMapSerialization=finished-prepared,full=finished-started)
 return result,image,native_map,native_eligible

def measure(result,truth,clean,eligible):
 import numpy as np
 pred=[[v['x'],v['y'],v['x']+v['width'],v['y']+v['height']] for v in result['candidates']];pairs=match_boxes(truth,pred);matched={p[0] for p in pairs}
 visible=[]
 for i,(x,y,ex,ey) in enumerate(truth):
  cx,cy=int((x+ex)/2),int((y+ey)/2)
  if 0<=cy<eligible.shape[0] and 0<=cx<eligible.shape[1] and eligible[cy,cx]:visible.append(i)
 false=[]
 for i,(x,y,ex,ey) in enumerate(pred):
  if i in {v[1] for v in pairs}:continue
  cx,cy=int((x+ex)/2),int((y+ey)/2);area=clean[max(0,int(y)):min(clean.shape[0],int(np.ceil(ey))),max(0,int(x)):min(clean.shape[1],int(np.ceil(ex)))]
  if 0<=cy<clean.shape[0] and 0<=cx<clean.shape[1] and clean[cy,cx]:false.append(dict(candidate=i,reviewedAreaFraction=float(area.mean()) if area.size else 0))
 # Secondary box-center coverage, one candidate cannot satisfy multiple targets.
 used=set();center_hits=[]
 for ti,(x,y,ex,ey) in enumerate(truth):
  for pi,(bx,by,bex,bey) in enumerate(pred):
   if pi not in used and x<=(bx+bex)/2<=ex and y<=(by+bey)/2<=ey:used.add(pi);center_hits.append([ti,pi]);break
 return dict(targetCount=len(truth),truth=truth,pairs=pairs,missed=[i for i in range(len(truth)) if i not in matched],visibleTargets=visible,visibleMatched=[i for i in visible if i in matched],centerHits=center_hits,verifiedNegativePixels=int(clean.sum()),falseCandidates=false,scale={k:dict(targets=sum((max(b[2]-b[0],b[3]-b[1])<8 if k=='micro' else 8<=max(b[2]-b[0],b[3]-b[1])<16 if k=='small' else max(b[2]-b[0],b[3]-b[1])>=16) for b in truth),matched=sum((max(truth[i][2]-truth[i][0],truth[i][3]-truth[i][1])<8 if k=='micro' else 8<=max(truth[i][2]-truth[i][0],truth[i][3]-truth[i][1])<16 if k=='small' else max(truth[i][2]-truth[i][0],truth[i][3]-truth[i][1])>=16) for i in matched)) for k in ['micro','small','medium']})

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--method',choices=['A','B'],required=True);args=parser.parse_args()
 manifest=read(OUT/'preregistered-manifest.json');assert manifest['A']==a_identity();assert manifest['B']['config']==CONFIG and manifest['B']['implementationSHA256']==sha(Path(__file__).with_name('acne_lab_dog.py'))
 for name,digest in manifest['inputs'].items():assert sha(BASE/name)==digest
 output=OUT/args.method;output.mkdir(exist_ok=True)
 if (output/'results.json').exists():raise RuntimeError('COMPLETED_COMPARISON_NOT_REPEATED')
 with HeavyJobLease('CDC-acne-classical-'+args.method,peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
  import cv2,numpy as np
  cv2.setNumThreads(2)
  pre={r['sha256']:r for r in read(BASE/'browser-preflight.json')['rows']};original={r['sha256']:r for r in read(BASE/'inputs/original-reviewed-detector-data.json')['rows']};scope={r['sha256']:r for r in read(BASE/'inputs/annotation-scope-manifest.json')['images']};rows=[]
  for selected in manifest['rows']:
   lease.check();s=selected['sha256'];entry=pre[s];r=original[s];annotations=r.get('annotations',[])
   if entry['cohort']=='scope-B-development':annotations=[v for v in scope[s]['annotations'] if v['scopeCategory']=='IN_SCOPE_VISIBLE_REGION']
   truth=[a['box'] for a in annotations]
   if not selected['staticProductPass']:
    rows.append(dict(sha256=s,cohort=entry['cohort'],valid=False,targetCount=len(truth),quality=entry['quality']['status'],poseRejected=not entry['poseEligible'],reason='PRODUCT_CAPTURE_REJECTED',candidates=None));continue
   path=BASE/'product-inputs'/s/'snapshot.png';assert sha(path)==selected['snapshotSHA256'] and sha(Path(selected['sourcePath']))==selected['sourceFileSHA256']
   t=time.perf_counter();photo=path.read_bytes();read_seconds=time.perf_counter()-t
   result,image,mask,eligible=run(photo,entry,args.method);lease.check();repeat,_,repeat_mask,_=run(photo,entry,args.method)
   assert result['candidates']==repeat['candidates'] and np.array_equal(mask,repeat_mask),'NON_DETERMINISTIC'
   if not result['diagnostics']['valid']:
    rows.append(dict(sha256=s,cohort=entry['cohort'],valid=False,targetCount=len(truth),reason=result['diagnostics']['reason'],candidates=None));continue
   clean=np.zeros(image.shape[:2],bool)
   if r.get('negativeROI') and not r.get('annotations'):
    from source_skin_support import known_skin_scope
    clean=(known_skin_scope({**r,'landmarks':entry['alignment']['landmarks']},image)>0)&eligible
   result.update(sha256=s,cohort=entry['cohort'],valid=result['diagnostics']['valid'],group=r['group'],metrics=measure(result,truth,clean,eligible),repeatSeconds=repeat['seconds'],fileReadSeconds=read_seconds,deterministic=True)
   overlay=image.copy();overlay[mask]=(overlay[mask]*.35+np.array([0,120,255])*.65).astype(np.uint8)
   for x,y,ex,ey in truth:cv2.rectangle(overlay,(int(x),int(y)),(int(ex),int(ey)),(0,255,0),1)
   for obj in result['candidates']:
    x,y,w,h=[obj[k] for k in ['x','y','width','height']];cv2.rectangle(overlay,(int(x),int(y)),(int(x+w),int(y+h)),(0,120,255),1)
   cv2.imwrite(str(output/(s+'-overlay.png')),overlay);cv2.imwrite(str(output/(s+'-map.png')),mask.astype(np.uint8)*255);cv2.imwrite(str(output/(s+'-eligible.png')),eligible.astype(np.uint8)*255)
   (output/(s+'.json')).write_text(json.dumps(result,indent=2,allow_nan=False),'utf8');rows.append(result)
   print(json.dumps(dict(method=args.method,sha=s[:8],hits=len(result['metrics']['pairs']),targets=len(truth),fp=len(result['metrics']['falseCandidates']),count=result['candidateCount'],seconds=result['seconds']['full'])),flush=True)
  report=dict(method=args.method,manifestSHA256=sha(OUT/'preregistered-manifest.json'),rows=rows,resource=lease.receipt(),productionActive=False,torchImported='torch' in sys.modules)
  (output/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False),'utf8')
if __name__=='__main__':main()