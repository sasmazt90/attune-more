"""Local, hash-pinned FrameFind eye-ROI classifier. No downloads or storage."""
import hashlib,math,threading
from pathlib import Path
import cv2,numpy as np
VERSION='glasses-free-skin-capture-v1'
MODEL_HASH='66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9'
EYE_REGION=(33,133,159,145,158,153,144,163,7,246,362,263,386,374,385,380,373,390,249,466,70,63,105,66,107,336,296,334,293,300,168,6,197,195)
_session=None
_lock=threading.Lock()

def session():
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort
            path=Path(__file__).with_name('models')/'skin-eyewear-framefind-v1.onnx'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=MODEL_HASH:raise ValueError('SKIN_EYEWEAR_MODEL_IDENTITY')
            opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
            created=ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider'])
            if created.get_inputs()[0].name!='input' or created.get_inputs()[0].shape[1:]!=[3,112,112] or created.get_outputs()[0].name!='logit':raise ValueError('SKIN_EYEWEAR_MODEL_CONTRACT')
            _session=created
        return _session

def classify_roi(rgb):
    if rgb.shape!=(112,112,3):raise ValueError('SKIN_EYEWEAR_CROP')
    x=(rgb.astype(np.float32)/255-np.array([.485,.456,.406],np.float32))/np.array([.229,.224,.225],np.float32)
    logit=float(session().run(['logit'],{'input':x.transpose(2,0,1)[None]})[0][0])
    if not math.isfinite(logit):raise ValueError('SKIN_EYEWEAR_INVALID_OUTPUT')
    probability=1/(1+math.exp(-max(-40,min(40,logit))))
    return dict(version=VERSION,modelHash=MODEL_HASH,probability=probability,status='EYEWEAR_PRESENT' if probability>=.5 else 'CLEAR' if probability<=.3 else 'UNCERTAIN')

def crop_bounds(points,width,height):
    if len(points) not in [468,478]:raise ValueError('SKIN_EYEWEAR_LANDMARKS')
    xy=np.array([[points[i]['x']*width,points[i]['y']*height] for i in EYE_REGION],float)
    if not np.isfinite(xy).all():raise ValueError('SKIN_EYEWEAR_LANDMARKS')
    low=xy.min(0);high=xy.max(0);side=float((high-low).max()*1.25);center=(low+high)/2
    if side<24:raise ValueError('SKIN_EYEWEAR_DETAIL')
    x0,y0=np.maximum(0,center-side/2).astype(int);x1,y1=np.minimum([width,height],center+side/2).astype(int)
    if min(x1-x0,y1-y0)<24:raise ValueError('SKIN_EYEWEAR_CROP')
    return int(x0),int(y0),int(x1),int(y1)

def classify_source(image,points):
    h,w=image.shape[:2];x0,y0,x1,y1=crop_bounds(points,w,h)
    roi=cv2.cvtColor(cv2.resize(image[y0:y1,x0:x1],(112,112),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)
    return {**classify_roi(roi), 'crop':[x0,y0,x1-x0,y1-y0]}
