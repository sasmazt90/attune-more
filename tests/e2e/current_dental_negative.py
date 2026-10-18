"""Actual model/source gates and backend reject controlled source degradations."""
from pathlib import Path
import json,subprocess,base64,sys,cv2,numpy as np
from playwright.sync_api import sync_playwright
root=Path.cwd();out=root/'audit-results/followup-closure-20261010'
sys.path.insert(0,str(root/'services/core-api'));from dental_analysis import decode_photo,dental_quality,mouth_geometry
js=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/dentalCapture.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);"],text=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True);p=b.new_page()
 def route(r):
  name=r.request.url.rsplit('/',1)[-1]
  if name=='index':r.fulfill(body='<html></html>',content_type='text/html')
  elif name=='face.task':r.fulfill(path=str(root/'audit-results/skin-capabilities-20261008/scin/face_landmarker.task'),content_type='application/octet-stream')
  elif name=='vision_bundle.mjs':r.fulfill(path=str(root/'node_modules/@mediapipe/tasks-vision'/name),content_type='text/javascript')
  elif name.startswith('vision_wasm'):r.fulfill(path=str(root/'node_modules/@mediapipe/tasks-vision/wasm'/name),content_type='application/wasm' if name.endswith('wasm') else 'text/javascript')
  else:r.abort()
 p.route('**/*',route);p.goto('http://127.0.0.1:6932/index')
 p.evaluate("async()=>{const V=await import('./vision_bundle.mjs');window.m=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('http://127.0.0.1:6932/wasm'),{baseOptions:{modelAssetPath:'http://127.0.0.1:6932/face.task'},runningMode:'IMAGE',numFaces:1,outputFacialTransformationMatrixes:true});}")
 p.evaluate('(js)=>{window.dental={};new Function("exports",js)(dental);}',js)
 rows=[]
 import os
 payload=json.loads(Path(os.environ.get('DENTAL_CAPTURE_INPUT',str(out/'dental-camera/capture-request-private.json'))).read_text());capture=payload['captures'][0]
 original,_=decode_photo(capture['photo']);mouth,_,_,_=mouth_geometry(capture['landmarks'],original.shape)
 negative=out/'dental-negative';negative.mkdir(exist_ok=True)
 covered=original.copy();covered[cv2.dilate(mouth.astype(np.uint8),np.ones((15,15),np.uint8))>0]=(40,40,40)
 glare=original.copy();glare[cv2.dilate(mouth.astype(np.uint8),np.ones((15,15),np.uint8))>0]=(255,255,255)
 for name,image in [('original',original),('blur',cv2.GaussianBlur(original,(0,0),20)),('opaque-cover',covered),('clipped-glare',glare)]:
  path=negative/(name+'.png');cv2.imwrite(str(path),image);data='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
  frontend=p.evaluate("""async(data)=>{const im=new Image();im.src=data;await im.decode();const c=document.createElement('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d');ctx.drawImage(im,0,0);const small=document.createElement('canvas');small.width=640;small.height=Math.round(im.height*640/im.width);small.getContext('2d').drawImage(c,0,0,small.width,small.height);const result=m.detect(small),points=result.faceLandmarks[0];if(!points)return {valid:false,reasons:['NO_ACTUAL_FACE']};const a={landmarks:points,faceDetected:true,isMediaPipeActive:true,faceTransform:result.facialTransformationMatrixes[0]?.data};return dental.assessDentalCapture(ctx,a,'FRONT');}""",data)
  backend=dental_quality(image,capture['landmarks']);print(name,frontend['valid'],backend['valid'],backend['reasons'],flush=True)
  assert frontend['valid']==(name=='original') and backend['valid']==(name=='original')
  rows.append(dict(source=name,frontend=frontend,backend=backend,poseOrQualityOverride=False))
 (negative/'proof.json').write_text(json.dumps(dict(buildId=(root/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),status='PASS',controlledSourceDegradations=True,actualModel=True,physicalUserAcceptance=False,cases=rows),ensure_ascii=False,indent=2),'utf8');b.close()
