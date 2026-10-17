"""Read-only observation of the real native session; never changes its outputs."""
import base64,hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent/'cdc-progress/dental-technical-closeout-20261017'
sys.path.insert(0,str(ROOT/'services/core-api'))
import onnxruntime as ort
import dental_analysis as dental
from dental_upload import analyze_upload,decode_upload,upload_roi
inputs=json.loads((OUT/'inputs.json').read_text('utf8'));source=Path(inputs['partial']);data=source.read_bytes();photo='data:image/jpeg;base64,'+base64.b64encode(data).decode()
image,photo_id,_,_=decode_upload(photo);mouth,*_=upload_roi(image);tensor,ratio,origin=dental.prepare_model_input(image,mouth,320)
trace={};Native=ort.InferenceSession
class Observe:
 def __init__(self,*a,**kw):self.session=Native(*a,**kw)
 def run(self,*a):
  result=self.session.run(*a);actual=a[1]['images'];raw=result[0]
  assert np.array_equal(actual,tensor)
  score=(raw[0,:,4:5]*raw[0,:,5:]).max(axis=1)
  trace.update(input=dict(shape=list(actual.shape),dtype=str(actual.dtype),sha256=hashlib.sha256(actual.tobytes()).hexdigest(),min=float(actual.min()),max=float(actual.max()),channels='BGR',padding=114,placement='top-left'),raw=dict(shape=list(raw.shape),dtype=str(raw.dtype),sha256=hashlib.sha256(raw.tobytes()).hexdigest(),finite=bool(np.isfinite(raw).all()),objClsRange=[float(raw[:,:,4:].min()),float(raw[:,:,4:].max())],aboveThreshold=int((score>=.35).sum())))
  return result
ort.InferenceSession=Observe
result=analyze_upload(dict(photo=photo));view=result['views'][0]
browser=json.loads((OUT/'upload-partial.json').read_text('utf8'))
assert view['photoId']==photo_id==browser['view']['photoId']
assert view['caries']['candidates']==browser['view']['caries']['candidates']
trace.update(sourceSha256=hashlib.sha256(data).hexdigest(),orientedRgbaSha256=photo_id,sourceDimensions=[image.shape[1],image.shape[0]],cropOrigin=list(origin),letterboxRatio=ratio,classes=['D','d'],confidenceThreshold=.35,nmsThreshold=.45,sourceCandidates=view['caries']['candidates'],browserSourceBoxesEqual=True,modelHash=view['caries']['modelHash'],clinicalAccuracyClaim=False,physicalCameraAcceptance=False)
t=OUT/'native-chain.tmp';t.write_text(json.dumps(trace,indent=2),'utf8');t.replace(OUT/'native-chain.json');print(json.dumps(dict(raw=trace['raw']['shape'],candidates=len(trace['sourceCandidates']),browserSourceBoxesEqual=True)))
