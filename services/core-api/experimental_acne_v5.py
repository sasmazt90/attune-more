"""Opt-in local photo preview. No training imports, downloads, storage or activation."""
import ast,hashlib,json,math,os,sys,threading,time
from functools import lru_cache
from pathlib import Path
import cv2,numpy as np
from acne_v5_features import candidate_features,VERSION as FEATURE_VERSION
from acne_box_support_staging import principled_accepted_boxes
from skin_models import photo_input,_nms
ROOT=Path(__file__).resolve().parents[2]
DEFAULT_FOLDER=Path(__file__).with_name('models')/'acne-v5-preview'
V5_HASH='0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb'
STEP0_HASH='18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
THRESHOLD=.15628215094908582
_LOCK=threading.Lock();_loaded=None
class PreviewUnavailable(RuntimeError):pass
class PreviewRejected(ValueError):pass

os.environ.setdefault('ATTUNE_EXPERIMENTAL_ACNE_V5', '1')
def enabled():return os.getenv('ATTUNE_EXPERIMENTAL_ACNE_V5')=='1'
def folder():return Path(os.getenv('ATTUNE_ACNE_V5_MODEL_DIR',str(DEFAULT_FOLDER))).resolve()
def digest(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def configuration():
 base=folder();available=all((base/n).is_file() for n in ['manifest.json','verifier-v5.json','step0-with-features-stable-silu.onnx'])
 return dict(enabled=enabled(),experimental=True,scope='photo-only',status='available' if enabled() and available else 'disabled' if not enabled() else 'model-unavailable',productionAccepted=False,historyStorage=False,verifierSHA256=V5_HASH)

def load():
 global _loaded
 if not enabled():raise PreviewUnavailable('EXPERIMENTAL_ACNE_V5_DISABLED')
 with _LOCK:
  base=folder()
  if _loaded and _loaded['folder']==str(base):return _loaded,0.
  started=time.perf_counter()
  try:
   manifest=json.loads((base/'manifest.json').read_text('utf8'));verpath=base/manifest['verifier']['file'];netpath=base/manifest['detector']['file']
   if verpath.parent.resolve()!=base or netpath.parent.resolve()!=base:raise ValueError()
   if digest(verpath)!=V5_HASH or manifest['verifier']['sha256']!=V5_HASH or manifest['detector']['sourceStep0SHA256']!=STEP0_HASH:raise ValueError()
   if manifest['verifier']['threshold']!=THRESHOLD or manifest['detector']['confidenceThreshold']!=.30 or manifest['detector']['nms']!=.30:raise ValueError()
   graph=netpath.read_bytes();actual=hashlib.sha256(graph).hexdigest()
   if actual!=manifest['detector']['sha256']:raise ValueError()
   model=json.loads(verpath.read_text('utf8'))
   if model['threshold']!=THRESHOLD or model['featureVersion']!=FEATURE_VERSION:raise ValueError()
   mean=np.asarray(model['standardizer']['mean'],np.float64);scale=np.asarray(model['standardizer']['scale'],np.float64);coef=np.asarray(model['model']['coef'],np.float64);bias=float(model['model']['intercept'])
   if any(a.shape!=(1920,) or not np.isfinite(a).all() for a in [mean,scale,coef]) or np.any(scale<=0) or not math.isfinite(bias):raise ValueError()
   import onnxruntime as ort
   opts=ort.SessionOptions();opts.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL;opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
   session=ort.InferenceSession(graph,opts,providers=['CPUExecutionProvider']);del graph
   if session.get_inputs()[0].name!='native_bgr_tile' or session.get_inputs()[0].shape!=[1,3,384,384] or [v.name for v in session.get_outputs()]!=['decoded_boxes','p2','p3','p4','p5']:raise ValueError()
   _loaded=dict(folder=str(base),session=session,manifest=manifest,mean=mean,scale=scale,coef=coef,bias=bias,graphHash=actual)
   return _loaded,(time.perf_counter()-started)*1000
  except Exception as error:raise PreviewUnavailable('EXPERIMENTAL_ACNE_V5_MODEL_UNAVAILABLE') from error

def rectangles(bgr,points):
 _,t=photo_input(bgr,points);x,y=t['x'],t['y'];ex=x+t['width'];ey=y+t['height']
 xs=sorted(set([*range(x,max(x+1,ex-384+1),288),max(x,ex-384)]));ys=sorted(set([*range(y,max(y+1,ey-384+1),288),max(y,ey-384)]))
 if len(xs)*len(ys)>64:raise PreviewRejected('NATIVE_TILE_BUDGET_EXCEEDED')
 return [[int(a),int(b),int(min(ex,a+384)),int(min(ey,b+384))] for a in xs for b in ys],t

@lru_cache(maxsize=1)
def context_function():
 # Execute the current product's exact prelude, as in the frozen research chain.
 # No copied mask geometry, mutable monkey patch, trained model injection or hosted call.
 import appearance_analysis as production
 source=Path(production.__file__).read_text('utf8');tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='analyze_skin');body=[]
 for statement in fn.body:
  body.append(statement)
  if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='acne_skin' for t in statement.targets):break
 else:raise PreviewUnavailable('EXPERIMENTAL_ACNE_SUPPORT_CONTRACT_CHANGED')
 body.append(ast.Return(value=ast.Call(func=ast.Name(id='locals',ctx=ast.Load()),args=[],keywords=[])));fn.body=body;module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));namespace=dict(vars(production));exec(compile(module,str(production.__file__),'exec'),namespace);return namespace['analyze_skin']

def gate(payload,bgr):
 points=payload['landmarks'];pre=payload.get('capturePreflight',{});q=pre.get('quality',{})
 if payload.get('qualityValid') is not True or pre.get('engine')!='browser-mediapipe' or pre.get('faceCount')!=1 or q.get('isValid') is not True:raise PreviewRejected('EXPERIMENTAL_CAPTURE_QUALITY_FAILED')
 values=[q.get('avgLuminance'),q.get('blurScore')]
 if not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) for x in values) or not 40<=values[0]<=220 or values[1]<4:raise PreviewRejected('EXPERIMENTAL_CAPTURE_QUALITY_FAILED')
 xy=np.asarray([[p['x'],p['y']] for p in points],float);h,w=bgr.shape[:2]
 if np.any(xy.min(0)<=.005) or np.any(xy.max(0)>=.995):raise PreviewRejected('EXPERIMENTAL_CAPTURE_FRAME_FAILED')
 nose=points[1];le,re=points[362],points[133];fh=max(.1,abs(points[152]['y']-points[10]['y']));eye=max(.05,abs(le['x']-re['x']))
 # JS Math.round semantics, including negative half values.
 round2=lambda a:math.floor(a*100+.5)/100
 yaw=round2((nose['x']-(le['x']+re['x'])/2)/(eye*.8));pitch=round2((nose['y']-(points[10]['y']+fh*.6))/(fh*.5));roll=round2(math.atan2(le['y']-re['y'],le['x']-re['x']));pose=payload.get('pose')
 allowed=abs(pitch)<=.22 and abs(roll)<=.15 and (abs(yaw)<=.20 if pose=='FRONT' else -1.15<=yaw<=-.25 if pose=='RIGHT' else .25<=yaw<=1.15 if pose=='LEFT' else False)
 if not allowed:raise PreviewRejected('EXPERIMENTAL_CAPTURE_POSE_FAILED')
 regions=set(payload['meshes']);expected={'forehead','nose','chin','periorbital','rightCheek','leftCheek'} if pose=='FRONT' else {'leftCheek' if pose=='RIGHT' else 'rightCheek'}
 if regions!=expected:raise PreviewRejected('EXPERIMENTAL_VISIBLE_REGION_MISMATCH')
 return dict(pose=pose,yaw=yaw,pitch=pitch,roll=roll,quality=q)

def memory():
 import psutil
 m=psutil.Process().memory_info();return dict(processRSSBytes=m.rss,processPrivateBytes=getattr(m,'private',None),processPeakRSSBytes=getattr(m,'peak_wset',m.rss))

def analyze(payload,check=lambda:None,*,with_context=False):
 from appearance_analysis import decode_photo
 started=time.perf_counter();check();bgr,photoid=decode_photo(payload['photo'])
 if photoid!=payload['photoId']:raise PreviewRejected('SOURCE_MISMATCH')
 preflight=gate(payload,bgr);item,loadms=load();check();rects,transform=rectangles(bgr,payload['landmarks']);boxes=[];metadata=[];maps=[];infer0=time.perf_counter()
 peaks=[memory()]
 for tile_id,(a,b,c,d) in enumerate(rects):
  check();tile=np.full((384,384,3),114,np.uint8);patch=bgr[b:d,a:c];tile[:patch.shape[0],:patch.shape[1]]=patch
  output=item['session'].run(None,{'native_bgr_tile':tile.transpose(2,0,1)[None].astype(np.float32)})
  if len(output)!=5 or output[0].shape!=(1,12240,6) or not all(np.isfinite(v).all() for v in output):raise PreviewUnavailable('EXPERIMENTAL_ACNE_V5_NONFINITE_OUTPUT')
  pred=output[0][0];maps.append([m[0] for m in output[1:]]);score=pred[:,4]*pred[:,5]
  for anchor in np.where(score>=.30)[0].tolist():
   cx,cy,bw,bh=pred[anchor,:4].astype(float);box=[max(a,float(cx+a-bw/2)),max(b,float(cy+b-bh/2)),min(c,float(cx+a+bw/2)),min(d,float(cy+b+bh/2))]
   if box[2]<=box[0] or box[3]<=box[1]:continue
   s=float(score[anchor]);boxes.append(box+[s]);metadata.append(dict(tile=tile_id,anchor=anchor,box=box,confidence=s))
  peaks.append(memory())
 selected=_nms(boxes,threshold=.30);lookup={tuple(v['box']+[v['confidence']]):v for v in metadata};nms_meta=[lookup[tuple(b)] for b in selected];inference_ms=(time.perf_counter()-infer0)*1000;check();support0=time.perf_counter();context=context_function()(payload)
 assigned,rejected=principled_accepted_boxes(selected,context['acne_envelopes'],context['acne_skin'],context['hair'],context['acne_exclusion'],photoid,context['scale'],context['origin'],visible_regions=list(payload['meshes']),landmarks=payload['landmarks'],source_shape=bgr.shape[:2],bgr=bgr)
 final=[b for rows in assigned.values() for b in rows];trace_lookup={tuple(round(x,4) for x in m['box'])+(round(m['confidence'],6),):m for m in metadata};F=[];identities=[]
 for box in final:
  coords=[box['x'],box['y'],box['x']+box['width'],box['y']+box['height']];meta=trace_lookup[tuple(round(x,4) for x in coords)+(round(box['confidence'],6),)];a,b=rects[meta['tile']][:2];F.append(candidate_features(maps[meta['tile']],(coords[0]+coords[2])/2-a,(coords[1]+coords[3])/2-b));identities.append(meta)
 features=np.stack(F) if F else np.zeros((0,1920),np.float32);z=((features.astype(np.float64)-item['mean'])/item['scale'])@item['coef']+item['bias'];p=1/(1+np.exp(-z));keep=p>=THRESHOLD;by={k:[] for k in assigned}
 for box,yes in zip(final,keep):
  if yes:by[box['region']].append({k:v for k,v in box.items() if k not in ['confidence']})
 flat=[box for rows in by.values() for box in rows];unique={b['candidateId']:b for b in flat};by['overview']=list(unique.values());check();peaks.append(memory());elapsed=(time.perf_counter()-started)*1000
 result=dict(experimental=True,scope='photo-only',status='ok',productionAccepted=False,historyStorage=False,requestId=payload.get('requestId'),photoId=photoid,sourceWidth=bgr.shape[1],sourceHeight=bgr.shape[0],candidateCount=len(unique),acneCandidates=by,preflight=preflight,model=dict(version='experimental-step0-verifier-v5-local-preview-v1',step0SHA256=STEP0_HASH,onnxSHA256=item['graphHash'],verifierSHA256=V5_HASH,featureVersion=FEATURE_VERSION,threshold=THRESHOLD,accepted=False,runtime='onnxruntime-numpy'),sourceTransform=transform,timing=dict(modelLoadMs=loadms,subsequentAnalysisMs=elapsed-loadms,inferenceMs=inference_ms,supportFilterVerifierMs=(time.perf_counter()-support0)*1000,totalAnalysisMs=elapsed),resources=dict(processPeakRSSBytes=max(m['processPeakRSSBytes'] for m in peaks),processPrivateBytes=max((m['processPrivateBytes'] or 0) for m in peaks),processRSSBytes=max(m['processRSSBytes'] for m in peaks),trainingFrameworkLoaded='torch' in sys.modules),tileCount=len(rects),detectorForwardCount=len(rects))
 if payload.get('includeRuntimeTrace') is True and os.getenv('ATTUNE_ACNE_V5_VALIDATION')=='1':
  result['validationTrace']=dict(rects=rects,nms=selected,nmsMetadata=nms_meta,preVerifier=final,identities=identities,features=features.tolist(),probabilities=p.tolist(),keep=keep.tolist(),rejected=rejected)
 return (result,context) if with_context else result
