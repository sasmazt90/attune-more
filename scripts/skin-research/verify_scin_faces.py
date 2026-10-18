"""Existing product MediaPipe face geometry, not disease or expert annotation.
Haar false positives (ears/macro crops) cannot become whole-face training rows.
No photograph leaves this local browser; all requests are local routed assets.
"""
import argparse,base64,hashlib,json,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/skin-capabilities-20261008/scin'
MODEL_URL='https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repair-known-boxes',action='store_true');args=ap.parse_args()
 model=OUT/'face_landmarker.task'
 if not model.exists():
  with urllib.request.urlopen(MODEL_URL,timeout=60) as response:data=response.read(64*1024*1024+1)
  assert len(data)<64*1024*1024;model.write_bytes(data)
 assert hashlib.sha256(model.read_bytes()).hexdigest()=='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
 assert json.loads((ROOT/'node_modules/@mediapipe/tasks-vision/package.json').read_text())['version']=='1.0.1'
 rows=json.loads((OUT/('fullface-manifest.json' if args.repair_known_boxes else 'manifest.json')).read_text());candidates=[r for r in rows if r.get('fullFaceGeometry') is True] if args.repair_known_boxes else [r for r in rows if r['face_box']];results=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='chrome',headless=True);page=browser.new_page()
  def local(route):
   url=route.request.url
   if not url.startswith('http://127.0.0.1:6932/scin-review/'):route.abort();return
   name=url.rsplit('/',1)[-1]
   if name=='index':route.fulfill(body='<html></html>',content_type='text/html')
   elif name=='face.task':route.fulfill(path=str(model),content_type='application/octet-stream')
   elif name=='vision_bundle.mjs':route.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision'/name),content_type='text/javascript')
   elif name in ['vision_wasm_internal.js','vision_wasm_internal.wasm','vision_wasm_nosimd_internal.js','vision_wasm_nosimd_internal.wasm']:route.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/wasm'/name),content_type='application/wasm' if name.endswith('.wasm') else 'text/javascript')
   else:route.abort()
  page.route('**/*',local);page.goto('http://127.0.0.1:6932/scin-review/index')
  load=page.evaluate('''async()=>{const t=performance.now(),V=await import('./vision_bundle.mjs');window.faceModel=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('http://127.0.0.1:6932/scin-review/wasm'),{baseOptions:{modelAssetPath:'http://127.0.0.1:6932/scin-review/face.task',delegate:'CPU'},runningMode:'IMAGE',numFaces:2});return performance.now()-t;}''')
  for i,row in enumerate(candidates):
   data='data:image/png;base64,'+base64.b64encode((ROOT/row['image_path']).read_bytes()).decode()
   result=page.evaluate('''async(data)=>{const im=new Image();im.src=data;await im.decode();const scale=Math.min(1,640/Math.max(im.width,im.height)),c=document.createElement('canvas');c.width=Math.round(im.width*scale);c.height=Math.round(im.height*scale);c.getContext('2d').drawImage(im,0,0,c.width,c.height);const t=performance.now(),r=faceModel.detect(c),points=r.faceLandmarks[0];if(r.faceLandmarks.length!==1||!points||points.length<468)return {accepted:false,faces:r.faceLandmarks.length,ms:performance.now()-t};const ids=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109],outline=ids.map(i=>points[i]),width=Math.max(...outline.map(p=>p.x))-Math.min(...outline.map(p=>p.x));return {accepted:outline.every(p=>p.x>.018&&p.x<.982&&p.y>.018&&p.y<.982)&&width>.1&&Math.abs(points[33].x-points[263].x)*c.width>=15,faces:1,box:{x:Math.min(...outline.map(p=>p.x)),y:Math.min(...outline.map(p=>p.y)),w:width,h:Math.max(...outline.map(p=>p.y))-Math.min(...outline.map(p=>p.y))},ms:performance.now()-t};}''',data)
   if result['accepted']:
    b=result['box'];x,y=int(b['x']*row['width']),int(b['y']*row['height']);row['face_box']=[x,y,min(row['width']-x,int(b['w']*row['width'])),min(row['height']-y,int(b['h']*row['height']))]
   row['fullFaceGeometry']=result['accepted'];row['faceReview']='existing-product-model-geometry-only-not-expert-review';row['eligible']=row['eligible'] and result['accepted'];results.append(result)
   if i%50==0:print('Geometry checked',i,'/',len(candidates),flush=True)
  page.evaluate('faceModel.close()');browser.close()
 for row in rows:
  if row['face_box'] is None:row['fullFaceGeometry']=False
 counts={'imageCandidatesChecked':sum(r['face_box'] is not None for r in rows),'modelInferencesThisRun':len(candidates),'boxSource':'MediaPipe complete outline in native source coordinates','fullFaceGeometryCandidates':sum(r['fullFaceGeometry'] for r in rows),'expertGradableCaseFullFaceCandidates':sum(r['fullFaceGeometry'] and r['expertGradableCase'] for r in rows),'eligibleImages':sum(r['eligible'] for r in rows),'eligibleCases':len({r['case_id'] for r in rows if r['eligible']}),'eligibleAcneCases':len({r['case_id'] for r in rows if r['eligible'] and r['target']==1}),'eligibleNegativeProxyCases':len({r['case_id'] for r in rows if r['eligible'] and r['target']==0}),'expertVerifiedFaceImages':None,'localLesionLabels':False,'negativeAbsenceCertified':False,'modelURL':MODEL_URL,'modelSHA256':hashlib.sha256(model.read_bytes()).hexdigest(),'sdkVersion':'1.0.1','loadMs':load,'photoUploads':False,'clinicalGroundTruth':False}
 (OUT/'fullface-manifest.json').write_text(json.dumps(rows,indent=2),'utf8');(OUT/'fullface-counts.json').write_text(json.dumps(counts,indent=2),'utf8');print(json.dumps(counts),flush=True)
if __name__=='__main__':main()
