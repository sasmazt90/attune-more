"""Pinned three-class pretrained ORT CPU inference plus explicit regional rule.
No training, remote client, downloads, sebum/hydration or clinical claims.
"""
import copy,hashlib,json,threading,time
from pathlib import Path
import numpy as np
from PIL import Image
CONFIG=Path(__file__).parent/'models/skin-type-local.json'
CLASSES=('dry','normal','oily')
RULE='combination-regional-user-v3-accepted-evidence'
LOCK=threading.Lock()
_CACHE=None

def unavailable(reason):
 return dict(value=None,quality='insufficient',confidence=None,methodVersion='local-pretrained-skin-type-v1',modelHash=None,limitationCode=reason,inferenceKind='local-onnx',inferenceMs=0.)

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
 """Derive combination only from accepted regional evidence, never raw proxies.
 Keep the original global model output for idempotent finalization and history.
 """
 from regional_skin_evidence import build_regional_map
 base=copy.deepcopy(base.get('basePrediction',base))
 if base.get('decisionTrace') is not None or base.get('value')=='combination':
  base=unavailable('LOCAL_TYPE_BASE_IDENTITY_UNAVAILABLE')
 for key in ['status','reason','modelVersion','calibrationVersion','coverage']:
  base.pop(key,None)
 measurements=measurements if isinstance(measurements,dict) else {}
 regional=build_regional_map(measurements)
 result=copy.deepcopy(base)
 trace=dict(version=RULE,scope='final-product-accepted-regional-evidence',
  definition='forehead, nose and chin oily; both cheeks supported normal or dry',
  regionalMeaning='appearance only; not sebum/hydration or sensitivity',
  complete=regional['complete'],combinationMatched=regional['combinationMatched'],
  baseValue=base.get('value'),baseConfidence=base.get('confidence'),
  baseModelHash=base.get('modelHash'),regions={})
 for region,summary in regional['regions'].items():
  rows=measurements.get(region,[])
  rows=rows if isinstance(rows,list) else []
  keys=['value','quality','methodVersion','normalizationVersion','evaluatedArea','limitationCode']
  inputs={criterion:next(({k:copy.deepcopy(row.get(k)) for k in keys} for row in rows
   if isinstance(row,dict) and row.get('id')==criterion),None) for criterion in ['oil','dry']}
  trace['regions'][region]=dict(state=None if summary['state']=='unknown' else summary['state'],
   reason=summary['reason'],oil=inputs['oil'],dry=inputs['dry'],inputs=inputs)
 usable=base.get('quality')=='valid' and base.get('value') in CLASSES and bool(base.get('modelHash'))
 if usable:
  result['methodVersion']=base['methodVersion']+'+'+RULE
  if regional['combinationMatched']:result.update(value='combination',confidence=None)
 trace['applied']=bool(usable and regional['combinationMatched'])
 result.update(basePrediction=base,decisionVersion=RULE,decisionTrace=trace,regionalMap=regional)
 return result


def finalize_product_type(result):
 """One endpoint boundary after native dryness and optional acne replacement.
 No inference or measurement changes; receipts describe the final decision.
 """
 skin_type=result.get('general',{}).get('skinType')
 if skin_type and skin_type.get('inferenceKind')=='local-onnx':
  result['general']['skinType']=regional_decision(skin_type,result.get('measurements',{}))
  result['general']['regionalSkinMap']=copy.deepcopy(result['general']['skinType']['regionalMap'])
 from skin_measurement_contract import attach_result_receipts
 return attach_result_receipts(result)

