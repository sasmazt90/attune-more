"""Optional, accepted photo-only ONNX models. No download, training or pickle.

Models are pinned by a bundled manifest. RGB source/crop stays independent of
presentation zoom; all learned degrees are global, never local severity masks.
"""
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
import hashlib,json,threading,time
import cv2,numpy as np
from hosted_skin_type import infer_hosted_type,parse_hosted_type_response,get_inference_client
from local_skin_type import infer as infer_local_type
from skin_product_contract import generic_degree_target_policy

FOLDER=Path(__file__).parent/'models'
MANIFEST=FOLDER/'skin-focused.json'
CLASSES=['normal','dry','oily','combination']
MEAN=np.array([.485,.456,.406],np.float32)[:,None,None]
STD=np.array([.229,.224,.225],np.float32)[:,None,None]
LOCK=threading.Lock()
_SESSION_STATE={}


def session_status(used=(), reason=None):
    """Backend-only runtime provenance; configured, loaded and used are distinct."""
    try:models=json.loads(MANIFEST.read_text('utf8')).get('models',{})
    except (OSError,ValueError):return {}
    result={}
    for task,model in models.items():
        accepted=model.get('accepted') is True
        row=dict(fileHashVerified=False,sessionLoaded=False,loadedModelHash=None,
                 usedInResponse=False,status='not-loaded' if accepted else 'not-accepted',
                 inferenceKind='local-onnx',modelId=f"{task}:{model.get('version','unknown')}")
        cached=_SESSION_STATE.get(task,{})
        if cached.get('_manifest')==str(MANIFEST.resolve()):
            row.update({k:v for k,v in cached.items() if not k.startswith('_')})
        row['matchesConfiguredHash']=row['loadedModelHash']==model.get('sha256') if row['sessionLoaded'] else None
        row['usedInResponse']=task in used and row['sessionLoaded']
        if row['usedInResponse']:row['status']='used'
        elif row['sessionLoaded']:row['status']='not-used'
        if reason and not row['usedInResponse']:row['usageReason']=reason
        result[task]=row
    return result

def photo_input(bgr,points):
    p=np.array([[v['x'],v['y']] for v in points[:468]],np.float64)
    if p.shape!=(468,2) or not np.isfinite(p).all():raise ValueError('INVALID_MODEL_LANDMARKS')
    h,w=bgr.shape[:2];lo=p.min(0);hi=p.max(0);size=hi-lo
    start=np.maximum(0,lo-size*[.32,.35]);end=np.minimum(1,hi+size*[.32,.16])
    x,y=np.floor(start*[w,h]).astype(int);x1,y1=np.ceil(end*[w,h]).astype(int)
    if not 0<=x<x1<=w or not 0<=y<y1<=h:raise ValueError('INVALID_MODEL_CROP')
    rgb=cv2.resize(bgr[y:y1,x:x1,::-1],(224,224),interpolation=cv2.INTER_AREA)
    value=((rgb.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD)[None].copy()
    return value,dict(x=int(x),y=int(y),width=int(x1-x),height=int(y1-y),inputWidth=224,inputHeight=224,RGB=True,cropVersion='camera-crop-v1',coordinateSpace='source-pixels')

@lru_cache(maxsize=1)
def load():
    if not MANIFEST.exists():return {'manifest':None,'sessions':{}}
    import onnxruntime as ort
    manifest=json.loads(MANIFEST.read_text('utf8'));assert manifest['classOrder']==CLASSES
    assert manifest['preprocessing']=={'RGB':True,'size':[224,224],'mean':[.485,.456,.406],'std':[.229,.224,.225],'cropVersion':'camera-crop-v1'}
    sessions={};_SESSION_STATE.clear();options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    for task,m in manifest.get('models',{}).items():
        if not m.get('accepted'):continue
        path=FOLDER/m['file'];assert path.resolve().parent==FOLDER.resolve() and path.suffix=='.onnx'
        state=dict(_manifest=str(MANIFEST.resolve()),_expectedHash=m.get('sha256'),
                   fileHashVerified=False,sessionLoaded=False,loadedModelHash=None,
                   usedInResponse=False,status='load-failed',modelId=f"{task}:{m['version']}")
        _SESSION_STATE[task]=state
        model_bytes=path.read_bytes();actual_hash=hashlib.sha256(model_bytes).hexdigest()
        state['fileHashVerified']=actual_hash==m['sha256']
        assert state['fileHashVerified'],'MODEL_HASH_MISMATCH'
        # ORT receives the exact bytes hashed here, avoiding a path replacement
        # between verification and session creation. No site-package mutation.
        start=time.perf_counter();session=ort.InferenceSession(model_bytes,sess_options=options,providers=['CPUExecutionProvider'])
        metadata=MappingProxyType(dict(modelHash=actual_hash,modelVersion=m['version'],
                                      modelId=state['modelId'],fileHashVerified=True,sessionLoaded=True))
        state.update(sessionLoaded=True,loadedModelHash=actual_hash,status='not-used')
        sessions[task]={'session':session,'loadMs':(time.perf_counter()-start)*1000,'metadata':dict(m),'sessionMetadata':metadata}
    return {'manifest':manifest,'sessions':sessions}

def infer(bgr,points,quality_valid,hosted_consent=False,type_quality_valid=None):
    empty=dict(skinType=None,degrees={},models={},sourceTransform=None,modelRuntime=session_status(reason='not-used'))
    type_quality=quality_valid if type_quality_valid is None else type_quality_valid
    if not quality_valid and not type_quality:return {**empty,'modelRuntime':session_status(reason='QUALITY_NOT_ELIGIBLE')}
    try:
        with LOCK:loaded=load()
        x,transform=photo_input(bgr,points);result={**empty,'sourceTransform':transform}
        type_computed=False;used=set()
        for task,item in loaded['sessions'].items():
            if task not in ('type','degrees'):continue
            if task=='degrees' and not quality_valid or task=='type' and not type_quality:continue
            start=time.perf_counter();output=item['session'].run(None,{'rgb':x})[0][0];elapsed=(time.perf_counter()-start)*1000;m=item['metadata']
            if not np.isfinite(output).all():raise ValueError('NONFINITE_MODEL_OUTPUT')
            identity=item['sessionMetadata']
            result['models'][task]=dict(identity,loadedModelHash=identity['modelHash'],usedInResponse=True,loadMs=item['loadMs'],inferenceMs=elapsed)
            if task=='type':
                type_computed=True
                assert output.shape==(4,);v=output/float(m['temperature']);v-=v.max();p=np.exp(v);p/=p.sum();confidence=float(p.max());valid=confidence>=float(m['confidenceThreshold'])
                result['skinType']=dict(value=CLASSES[int(p.argmax())] if valid else None,quality='valid' if valid else 'insufficient',confidence=confidence,methodVersion=identity['modelVersion'],modelHash=identity['modelHash'],limitationCode=None if valid else 'LOW_MODEL_SUPPORT')
                used.add(task)
            elif task=='degrees':
                assert len(output)==len(m['targets'])
                policy=generic_degree_target_policy(m);result['degreeTargetPolicy']=policy
                for target,value in zip(m['targets'],output):
                    if target in policy['acceptedTargets']:result['degrees'][target]=dict(value=float(np.clip(value,0,5)*20),rawGrade=float(np.clip(value,0,5)),methodVersion=identity['modelVersion'],modelHash=identity['modelHash'],confidence=None,scope='whole-face',normalizationVersion='ordinal-0-5-times-20-v1')
                if result['degrees']:used.add(task)
        if type_quality and not type_computed:
            a,b=transform['x'],transform['y'];crop=bgr[b:b+transform['height'],a:a+transform['width']]
            local=infer_local_type(crop)
            result['models']['type']=dict(modelHash=local['modelHash'],modelVersion=local['methodVersion'],inferenceKind='local-onnx',loadMs=0.,inferenceMs=local.pop('inferenceMs'))
            result['skinType']=local
        result['modelRuntime']=session_status(used)
        if result['skinType'] and result['skinType'].get('inferenceKind')=='local-onnx':
            local=result['skinType'];result['modelRuntime']['type']=dict(modelId='local-pretrained:'+local.get('sourceModel','unavailable'),fileHashVerified=bool(local.get('fileHashVerified')),sessionLoaded=bool(local.get('sessionLoaded')),loadedModelHash=local.get('modelHash'),usedInResponse=local.get('quality')=='valid',status='used' if local.get('quality')=='valid' else 'unavailable',inferenceKind='local-onnx')
        return result
    except Exception:
        # Compact unavailable state; no old result, substitute weights or zeros.
        # Preserve the expected accepted targets so the product can make them
        # unavailable instead of silently substituting an analytic score.
        targets=[];unavailable_type=None;degree_policy=None
        try:
            manifest=json.loads(MANIFEST.read_text('utf8'))
            head=manifest.get('models',{}).get('degrees',{})
            degree_policy=generic_degree_target_policy(head)
            targets=list(degree_policy['acceptedTargets'])
            type_head=manifest.get('models',{}).get('type',{})
            if type_head.get('accepted'):
                unavailable_type=dict(value=None,quality='insufficient',confidence=None,methodVersion=type_head.get('version'),modelHash=None,limitationCode='ACCEPTED_MODEL_UNAVAILABLE')
        except (OSError,ValueError):pass
        return {**empty,'skinType':unavailable_type,'failure':'ACCEPTED_MODEL_UNAVAILABLE','unavailableTargets':targets,'degreeTargetPolicy':degree_policy,'modelRuntime':session_status(reason='ACCEPTED_MODEL_UNAVAILABLE')}

def _nms(boxes,threshold=.3):
    if not boxes:return []
    a=np.asarray(boxes,float);order=np.argsort(-a[:,4]);keep=[]
    while len(order):
        i=int(order[0]);keep.append(i);rest=order[1:]
        start=np.maximum(a[i,:2],a[rest,:2]);end=np.minimum(a[i,2:4],a[rest,2:4]);area=np.maximum(0,end-start).prod(1)
        total=np.maximum(0,a[i,2]-a[i,0])*np.maximum(0,a[i,3]-a[i,1])+np.maximum(0,a[rest,2]-a[rest,0])*np.maximum(0,a[rest,3]-a[rest,1])-area
        order=rest[area/np.maximum(1e-8,total)<=threshold]
    return a[keep].tolist()

def infer_acne(bgr,points,quality_valid):
    if not quality_valid:return None
    try:
        with LOCK:item=load()['sessions'].get('acne')
        if not item:return None
        _,transform=photo_input(bgr,points);x,y=transform['x'],transform['y'];x1=x+transform['width'];y1=y+transform['height'];size=384
        xs=sorted(set([*range(x,max(x+1,x1-size+1),288),max(x,x1-size)]));ys=sorted(set([*range(y,max(y+1,y1-size+1),288),max(y,y1-size)]))
        if len(xs)*len(ys)>64:return {'valid':False,'reason':'NATIVE_TILE_BUDGET_EXCEEDED'}
        boxes=[];started=time.perf_counter();meta=item['metadata']
        for a in xs:
            for b in ys:
                c=min(x1,a+size);d=min(y1,b+size);canvas=np.full((size,size,3),114,np.uint8);canvas[:d-b,:c-a]=bgr[b:d,a:c]
                pred=item['session'].run(None,{'native_bgr_tile':canvas.transpose(2,0,1)[None].astype(np.float32)})[0][0]
                assert pred.shape[1]==6 and np.isfinite(pred).all()
                for cx,cy,w,h,obj,cls in pred:
                    score=float(obj*cls)
                    if score<meta['confidenceThreshold']:continue
                    bx=max(a,float(cx-w/2+a));by=max(b,float(cy-h/2+b));ex=min(c,float(cx+w/2+a));ey=min(d,float(cy+h/2+b))
                    if ex>bx and ey>by:boxes.append([bx,by,ex,ey,score])
        identity=item['sessionMetadata']
        return dict(valid=True,boxes=_nms(boxes),modelHash=identity['modelHash'],modelVersion=identity['modelVersion'],tileCount=len(xs)*len(ys),loadMs=item['loadMs'],inferenceMs=(time.perf_counter()-started)*1000,coordinateSpace='source-pixels',mapType='detection-boxes')
    except Exception:return {'valid':False,'reason':'ACCEPTED_MODEL_UNAVAILABLE'}

def eye_rois(points,width,height):
    rois=[]
    for eye,ids in [('right',[33,133,145]),('left',[263,362,374])]:
        p=np.array([[points[i]['x']*width,points[i]['y']*height] for i in ids]);span=abs(p[1,0]-p[0,0]);cx=(p[0,0]+p[1,0])/2;cy=max(p[:,1]);rect=[int(max(0,cx-.7*span)),int(max(0,cy-.12*span)),int(min(width,cx+.7*span)),int(min(height,cy+.8*span))]
        a,b,c,d=rect
        if c-a>=12 and d-b>=8:rois.append({'eye':eye,'rect':rect})
    return rois

def infer_bags(bgr,points,quality_valid):
    if not quality_valid:return None
    try:
        with LOCK:item=load()['sessions'].get('bags')
        if not item:return None
        layers=[];start=time.perf_counter();m=item['metadata']
        for roi in eye_rois(points,bgr.shape[1],bgr.shape[0]):
            a,b,c,d=roi['rect'];rgb=cv2.resize(bgr[b:d,a:c,::-1],(128,128),interpolation=cv2.INTER_AREA);x=((rgb.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD)[None].copy();logits=item['session'].run(None,{'rgb_eye_roi':x})[0][0,0]
            assert logits.shape==(128,128) and np.isfinite(logits).all();probability=1/(1+np.exp(-np.clip(logits,-50,50)))
            layers.append({**roi,'mask':(probability>=m['probabilityThreshold']).astype(np.uint8),'mapType':'predicted-presence-mask','confidenceNotSeverity':True})
        identity=item['sessionMetadata']
        return dict(valid=len(layers)==2,layers=layers,modelHash=identity['modelHash'],modelVersion=identity['modelVersion'],loadMs=item['loadMs'],inferenceMs=(time.perf_counter()-start)*1000)
    except Exception:return {'valid':False,'reason':'ACCEPTED_MODEL_UNAVAILABLE'}

