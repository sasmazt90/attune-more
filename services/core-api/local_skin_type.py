"""Pinned three-class pretrained ORT CPU inference plus explicit regional rule.
No training, remote client, downloads, sebum/hydration or clinical claims.
"""
import copy,hashlib,json,math,threading,time
from pathlib import Path
import numpy as np
from PIL import Image
CONFIG=Path(__file__).parent/'models/skin-type-local.json'
CLASSES=('dry','normal','oily')
RULE='combination-regional-user-v1-visible-support-v1'
LOCK=threading.Lock()
_CACHE=None

def unavailable(reason):
 return dict(value=None,quality='insufficient',confidence=None,methodVersion='local-pretrained-skin-type-v1+'+RULE,modelHash=None,limitationCode=reason,inferenceKind='local-onnx',inferenceMs=0.)

def preprocess(bgr):
 if not isinstance(bgr,np.ndarray) or bgr.dtype!=np.uint8 or bgr.ndim!=3 or bgr.shape[2]!=3 or min(bgr.shape[:2])<16:raise ValueError('INVALID_TYPE_IMAGE')
 # Exact declared ViTImageProcessor contract, PIL bilinear RGB 224, [0,1], .5/.5.
 image=Image.fromarray(bgr[:,:,::-1]).resize((224,224),Image.Resampling.BILINEAR)
 rgb=np.asarray(image).astype(np.float64)*(1/255.)
 rgb=rgb.astype(np.float32)
 return np.ascontiguousarray(((rgb-.5)/.5).transpose(2,0,1)[None])

def load():
 global _CACHE
 raw=CONFIG.read_bytes();signature=hashlib.sha256(raw).hexdigest()
 with LOCK:
  if _CACHE and _CACHE['signature']==signature:return _CACHE
  config=json.loads(raw)
  if config.get('enabled') is not True:raise ValueError('LOCAL_TYPE_DISABLED')
  if config.get('classOrder')!=list(CLASSES) or config.get('preprocessing')!={'RGB':True,'size':[224,224],'resample':'PIL-bilinear','rescale':1/255,'mean':[.5,.5,.5],'std':[.5,.5,.5]}:raise ValueError('LOCAL_TYPE_CONFIG_INVALID')
  path=(CONFIG.parent/config['file']).resolve()
  if not path.is_relative_to(CONFIG.parent.resolve()) or path.suffix!='.onnx':raise ValueError('LOCAL_TYPE_PATH_INVALID')
  data=path.read_bytes();actual=hashlib.sha256(data).hexdigest()
  if actual!=config['sha256']:raise ValueError('LOCAL_TYPE_HASH_MISMATCH')
  import onnxruntime as ort
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.enable_cpu_mem_arena=False
  start=time.perf_counter();session=ort.InferenceSession(data,sess_options=options,providers=['CPUExecutionProvider'])
  if session.get_providers()!=['CPUExecutionProvider'] or session.get_inputs()[0].shape!=[1,3,224,224]:raise ValueError('LOCAL_TYPE_GRAPH_INVALID')
  _CACHE=dict(signature=signature,config=config,session=session,loadMs=(time.perf_counter()-start)*1000,modelHash=actual)
  return _CACHE

def infer(bgr):
 start=time.perf_counter()
 try:
  x=preprocess(bgr);loaded=load();logits=loaded['session'].run(None,{'rgb':x})[0]
  if logits.shape!=(1,3) or not np.isfinite(logits).all():raise ValueError('LOCAL_TYPE_INVALID_OUTPUT')
  values=logits[0].astype(np.float64);p=np.exp(values-values.max());p/=p.sum()
  index=int(values.argmax());config=loaded['config']
  return dict(value=CLASSES[index],quality='valid',confidence=float(p[index]),methodVersion=config['version'],modelHash=loaded['modelHash'],limitationCode=None,inferenceKind='local-onnx',inferenceMs=(time.perf_counter()-start)*1000,sourceModel=config['sourceModel'],classOrder=list(CLASSES),logits=values.tolist(),fileHashVerified=True,sessionLoaded=True)
 except (OSError,ValueError,KeyError,RuntimeError) as error:
  reason=str(error) if isinstance(error,ValueError) else 'LOCAL_TYPE_UNAVAILABLE'
  return unavailable(reason)
 except Exception:return unavailable('LOCAL_TYPE_UNAVAILABLE')

def regional_decision(base,measurements):
 """Measured absence is distinct from missing support; global argmax cannot
 overrule an observed T-oily/rest-normal-or-dry pattern. No cheek classifier.
 Native existing oil >.12 and flake >.04 pixel gates already produced values;
 this rule tests presence/absence of that accepted support, not a fitted scale.
 """
 result=copy.deepcopy(base);trace=dict(version=RULE,definition='T oily and remaining face normal OR dry',regionalMeaning='visible-support proxy, not sebum/hydration',thresholdPolicy='existing oil>.12 and flake>.04 pixel gates; any accepted area support vs measured zero; no threshold fit',regions={})
 def observed(region,criterion):
  row=next((r for r in measurements.get(region,[]) if r.get('id')==criterion),None)
  if not row:return None
  value=row.get('value');area=row.get('evaluatedArea',{})
  if row.get('quality')!='valid' or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100 or area.get('analysisPixels',0)<100 or area.get('sourcePixels',0)<=0:return None
  return dict(value=value,evaluatedArea=copy.deepcopy(area),methodVersion=row.get('methodVersion'),normalizationVersion=row.get('normalizationVersion'))
 t=observed('nose','oil');forehead=observed('forehead','oil')
 # The existing nose oil ROI is already forehead union nose: never add the
 # forehead area twice. Require actual visible support in both anatomy parts.
 t_valid=t is not None and forehead is not None and t['evaluatedArea'].get('foreheadSourcePixels',0)>0 and t['evaluatedArea'].get('noseSourcePixels',0)>0
 trace['tZone']=dict(observation=t,valid=t_valid,anatomy='existing forehead-union-nose ROI; no duplicate forehead sum')
 states=[]
 for region in ['leftCheek','rightCheek','chin']:
  oil,dry=observed(region,'oil'),observed(region,'dry')
  state=None if oil is None or dry is None else 'oily' if oil['value']>0 else 'dry' if dry['value']>0 else 'normal'
  trace['regions'][region]=dict(state=state,oil=oil,dry=dry);states.append(state)
 complete=t_valid and all(s is not None for s in states)
 matches=complete and t['value']>0 and all(s in ('normal','dry') for s in states)
 trace.update(complete=complete,combinationMatched=matches,baseValue=base.get('value'),baseConfidence=base.get('confidence'),baseModelHash=base.get('modelHash'))
 usable=base.get('quality')=='valid' and base.get('value') in CLASSES and bool(base.get('modelHash'))
 if usable:
  result['methodVersion']=base['methodVersion']+'+'+RULE
  if matches:result.update(value='combination',confidence=None)
 trace['applied']=bool(usable and matches)
 result.update(decisionVersion=RULE,decisionTrace=trace)
 return result
