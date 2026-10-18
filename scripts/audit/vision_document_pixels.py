"""Reprocess supplied document photographs with today's actual face/hand/tracker.
Old screenshots are only raw pixel inputs. This is NOT a new physical session,
not original camera coordinate proof, and a drawn occluder is explicitly a fixture.
Private user pixels stay in ignored audit-results and never leave this device.
"""
import json,subprocess,base64,io,hashlib
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/vision-document-pixels';OUT.mkdir(parents=True,exist_ok=True)
folder=ROOT/'audit-results/all-health-20261010/document-images/GÖZ SAĞLIĞI'
names=['skinAnalyzer','spokenVision','visionFrameQuality','visionTracking']
js="const fs=require('fs'),ts=require('typescript');let out={};for(const n of "+json.dumps(names)+"){out[n]=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;}process.stdout.write(JSON.stringify(out));"
modules=json.loads(subprocess.check_output(['node','-e',js],text=True,encoding='utf8'))
for n,s in modules.items():
 for dep in names:s=s.replace("'./"+dep+"'","'./"+dep+".js'")
 modules[n]=s.replace("from '@mediapipe/tasks-vision'","from './vision_bundle.mjs'")
photos={}
for mode,num,box in [('both-open',8,(174,173,820,855)),('closed-right',3,(184,213,830,891)),('palm-left',4,(184,363,830,1000))]:
 source=folder/f'image{num}.png';im=Image.open(source).crop(box).convert('RGB');buf=io.BytesIO();im.save(buf,format='PNG');photos[mode]=dict(data='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),source=str(source.relative_to(ROOT)),crop=box,sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest())
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True);p=b.new_page()
 def route(r):
  n=r.request.url.rsplit('/',1)[-1]
  if n=='index':r.fulfill(body='<canvas></canvas>',content_type='text/html')
  elif n.endswith('.js') and n[:-3] in modules:r.fulfill(body=modules[n[:-3]],content_type='text/javascript')
  elif n=='vision_bundle.mjs':r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision'/n),content_type='text/javascript')
  elif n.startswith('vision_wasm'):r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/wasm'/n),content_type='application/wasm' if n.endswith('.wasm') else 'text/javascript')
  else:r.continue_()
 p.route('**/audit/eye-pixels/**',route);p.goto('http://127.0.0.1:3000/audit/eye-pixels/index')
 p.evaluate('''async()=>{const V=await import('./vision_bundle.mjs'),F=await V.FilesetResolver.forVisionTasks('/audit/eye-pixels/wasm');window.face=await V.FaceLandmarker.createFromOptions(F,{baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',delegate:'CPU'},runningMode:'IMAGE',numFaces:2,outputFaceBlendshapes:true});window.hand=await V.HandLandmarker.createFromOptions(F,{baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',delegate:'CPU'},runningMode:'IMAGE',numHands:2});window.T=(await import('./visionTracking.js')).VisionTracker;window.load=async(data)=>{const im=new Image();im.src=data;await im.decode();window.im=im;};window.measure=(time,occlude=false)=>{const c=document.querySelector('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(im,0,0);if(occlude){const f=face.detect(c),a=f.faceLandmarks[0];if(a){const q=[362,385,387,263,373,380].map(i=>a[i]);const minX=Math.min(...q.map(v=>v.x))*c.width,maxX=Math.max(...q.map(v=>v.x))*c.width,minY=Math.min(...q.map(v=>v.y))*c.height,maxY=Math.max(...q.map(v=>v.y))*c.height;ctx.fillStyle='#354978';ctx.fillRect(minX-12,minY-13,maxX-minX+24,maxY-minY+26);}}const start=performance.now(),f=face.detect(c),h=hand.detect(c),s=f.faceBlendshapes[0]?.categories||[];return tracker.assess(ctx,c.width,c.height,{landmarks:f.faceLandmarks,hands:h.landmarks,blinkRight:s.find(v=>v.categoryName==='eyeBlinkRight')?.score??null,blinkLeft:s.find(v=>v.categoryName==='eyeBlinkLeft')?.score??null,inferenceMs:performance.now()-start,frameTime:time},time,null);};}''')
 cases=[]
 for mode in ['both-open','closed-right','palm-left','controlled-opaque-left']:
  p.evaluate('window.tracker=new T()');p.evaluate('load(data)',{'data':photos['both-open']['data']}) if False else p.evaluate('(data)=>load(data)',photos['both-open']['data'])
  baseline=[p.evaluate('(t)=>measure(t)',100+i*100) for i in range(16)]
  raw=photos['both-open' if mode=='controlled-opaque-left' else mode];p.evaluate('(data)=>load(data)',raw['data']);rows=[p.evaluate('([t,o])=>measure(t,o)',[1800+i*100,mode=='controlled-opaque-left']) for i in range(14)]
  result=dict(mode=mode,source={k:v for k,v in raw.items() if k!='data'},controlledDrawnOccluder=mode=='controlled-opaque-left',baselineReady=any(v['conditions']['positionValid'] for v in baseline),rows=rows,actualModels=True,physicalSession=False,sourceCameraCoordinates=False)
  p.locator('canvas').screenshot(path=str(OUT/(mode+'-private.png')));cases.append(result);print(json.dumps(dict(mode=mode,baseline=result['baselineReady'],last=rows[-1]['conditions'])),flush=True)
 b.close()
(OUT/'proof-private.json').write_text(json.dumps(dict(buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),scope='new actual inference on old raw photographs; no physical acceptance',cases=cases),indent=2),'utf8')
