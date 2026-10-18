"""Licensed local development inputs through real browser MediaPipe/product crop.

An isolated profile, no SDK overrides, no hosted calls and no user storage.
Saved payloads are ignored evidence, never published with the report.
"""
import base64,hashlib,json,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/lines-bags-followup-20261012';OUT.mkdir(exist_ok=True)
PROFILE=ROOT/'output/playwright/lines-bags-followup-20261012/capture-profile'
manifest=json.loads((ROOT/'audit-results/skin-selected-20261011/manifest.json').read_text('utf8'))
prefixes=['a94f1646','02386f86','01955323']
sources=[]
for prefix in prefixes:
 source=next(v for v in manifest['rows'] if v['sha256'].startswith(prefix) and v['source'] in ('wrinkles','dc'))
 b=Path(source['absolutePath']).read_bytes();assert hashlib.sha256(b).hexdigest()==source['sha256']
 sources.append(source)
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
  url='data:image/jpeg;base64,'+base64.b64encode(Path(source['absolutePath']).read_bytes()).decode()
  result=page.evaluate('''async(photo)=>{
   const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'), A=R('skinAnalyzer').SkinAnalyzer;
   const im=new Image();im.src=photo;await im.decode();const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;const x=c.getContext('2d');x.drawImage(im,0,0);
   const align=A.assessAlignment(x,c.width,c.height);if(!align.isMediaPipeActive||align.faceCount!==1)throw Error('Real single face required');
   const quality=A.checkQuality(x,c.width,c.height,align.faceDetected,align.box), snapshot=R('skinSnapshot').snapshotRawSkinFrame(c,align,'FRONT');
   snapshot.photoId=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',x.getImageData(0,0,c.width,c.height).data))).map(v=>v.toString(16).padStart(2,'0')).join('');
   const conditions={yaw:align.yaw,pitch:align.pitch,roll:align.roll,scaleRatio:align.scaleRatio,avgLuminance:quality.avgLuminance,blurScore:quality.blurScore};
   const response=await R('appearanceMeasurements').analyzeAppearance(snapshot,quality.isValid,conditions,[align.landmarks,align.landmarks,align.landmarks],()=>true);
   return {quality,conditions,response};
  }''',url)
  assert len(pending)==1,(prefix,len(pending))
  (OUT/(prefix+'-payload.json')).write_text(json.dumps(pending[0],ensure_ascii=False),'utf8')
  (OUT/(prefix+'-browser.json')).write_text(json.dumps(result,ensure_ascii=False),'utf8')
  print(json.dumps({'source':prefix,'quality':result['quality']['isValid'],'lines':next(v for v in result['response']['measurements']['periorbital'] if v['id']=='lines')['value']}),flush=True)
 context.close()
(OUT/'source-selection.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),'utf8')
