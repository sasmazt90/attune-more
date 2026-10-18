"""Licensed local development inputs through real browser MediaPipe/product crop.

An isolated profile, no SDK overrides, no hosted calls and no user storage.
Saved payloads are ignored evidence, never published with the report.
"""
import base64,hashlib,json,time,urllib.request,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/dry-sag-product-20261013'
PROFILE=ROOT/'output/playwright/dry-sag-product-20261013/capture-profile'
sources=json.loads((OUT/'source-selection.json').read_text('utf8'))
for source in sources:assert hashlib.sha256(Path(source['absolutePath']).read_bytes()).hexdigest()==source['sha256']
if any(not (OUT/(s['sha256'][:8]+'-browser.json')).exists() for s in sources):
 for name in ('appearance_analysis.py','instant_appearance.py','skin_general.py'):
  baseline=subprocess.check_output(['git','show','420d0e3814106a2ec77744a17e000ea1e8669cec:services/core-api/'+name],cwd=ROOT)
  assert (ROOT/'services/core-api'/name).read_bytes().replace(b'\r\n',b'\n')==baseline,'Fresh baseline capture requires the initial source; existing pinned captures remain preserved.'
deadline=time.monotonic()+60
while True:
 try:
  urllib.request.urlopen('http://127.0.0.1:3000/privacy',timeout=3)
  urllib.request.urlopen('http://127.0.0.1:8000/api/vehicle/state',timeout=3);break
 except OSError:
  if time.monotonic()>deadline:raise
  time.sleep(.5)
req=urllib.request.Request('http://127.0.0.1:8000/api/vehicle/speed',json.dumps({'speedKmH':0}).encode(),{'Content-Type':'application/json'})
urllib.request.urlopen(req).read()
with sync_playwright() as pw:
 context=pw.chromium.launch_persistent_context(str(PROFILE),channel='chrome',headless=False,viewport=dict(width=1400,height=950),args=['--enable-unsafe-swiftshader'])
 context.route('**/__audit/vision_bundle.mjs',lambda r:r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs'),content_type='text/javascript'))
 page=context.new_page();page.goto('http://127.0.0.1:3000/privacy')
 assert not page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True).is_checked()
 page.add_script_tag(content=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8'))
 page.evaluate("async()=>{window.__auditMediaPipe=await import('/__audit/vision_bundle.mjs');return !!await __auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer.getFaceLandmarker()}")
 pending=[]
 def capture(request):
  if '/api/local-health/skin' in request.url and request.method=='POST':pending.append(json.loads(request.post_data))
 page.on('request',capture)
 for source in sources:
  prefix=source['sha256'][:8];pending.clear()
  if (OUT/(prefix+'-browser.json')).exists():
   print(json.dumps({'source':prefix,'reusedPinnedBaselineCapture':True}),flush=True);continue
  url='data:image/jpeg;base64,'+base64.b64encode(Path(source['absolutePath']).read_bytes()).decode()
  result=page.evaluate('''async(photo)=>{
   const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'), A=R('skinAnalyzer').SkinAnalyzer;
   const im=new Image();im.src=photo;await im.decode();const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;const x=c.getContext('2d');x.drawImage(im,0,0);
   const align=A.assessAlignment(x,c.width,c.height);if(!align.isMediaPipeActive||align.faceCount!==1)return {unusableReason:'NO_SINGLE_FACE',faceCount:align.faceCount,mediaPipeActive:align.isMediaPipeActive};
   const quality=A.checkQuality(x,c.width,c.height,align.faceDetected,align.box);let snapshot;
   try{snapshot=R('skinSnapshot').snapshotRawSkinFrame(c,align,'FRONT')}catch(error){return {unusableReason:String(error.message),faceCount:align.faceCount,mediaPipeActive:align.isMediaPipeActive,quality};}
   snapshot.photoId=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',x.getImageData(0,0,c.width,c.height).data))).map(v=>v.toString(16).padStart(2,'0')).join('');
   const conditions={yaw:align.yaw,pitch:align.pitch,roll:align.roll,scaleRatio:align.scaleRatio,avgLuminance:quality.avgLuminance,blurScore:quality.blurScore};
   const response=await R('appearanceMeasurements').analyzeAppearance(snapshot,quality.isValid,conditions,[align.landmarks,align.landmarks,align.landmarks],()=>true);
   return {quality,conditions,response};
  }''',url)
  if result.get('unusableReason'):
   (OUT/(prefix+'-browser.json')).write_text(json.dumps(result,ensure_ascii=False),'utf8');print(json.dumps({'source':prefix,**result}),flush=True);continue
  assert len(pending)==1,(prefix,len(pending))
  (OUT/(prefix+'-payload.json')).write_text(json.dumps(pending[0],ensure_ascii=False),'utf8')
  (OUT/(prefix+'-browser.json')).write_text(json.dumps(result,ensure_ascii=False),'utf8')
  print(json.dumps({'source':prefix,'quality':result['quality']['isValid'],'dry':next(v for v in result['response']['general']['measurements'] if v['id']=='dry')['value'],'sag':next(v for v in result['response']['general']['measurements'] if v['id']=='sag')['value']}),flush=True)
 context.close()
(OUT/'capture-source-hashes.json').write_text(json.dumps({v['sha256']:hashlib.sha256(Path(v['absolutePath']).read_bytes()).hexdigest() for v in sources},indent=2),'utf8')
