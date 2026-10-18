"""Licensed actual video pixels through actual face/hand models and source tracker.
This is a controlled inference measurement, not physical depth/user acceptance.
"""
import json,subprocess,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
FIX=Path('audit-fixtures');OUT=Path('audit-results/vision-usable');OUT.mkdir(parents=True,exist_ok=True)
assert hashlib.sha1((FIX/'head-shake.webm').read_bytes()).hexdigest()=='fb35a2ecbf0771ab818c2ca336142c30b515a414'
names=['skinAnalyzer','spokenVision','visionFrameQuality','visionTracking']
compiler="""const fs=require('fs'),ts=require('typescript');for(const name of %s){let s=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;s=s.replaceAll("from '@mediapipe/tasks-vision'","from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/+esm'");for(const dep of %s)s=s.replaceAll("'./"+dep+"'","'./vision-probe-"+dep+".js'");fs.writeFileSync('audit-fixtures/vision-probe-'+name+'.js',s);}"""%(json.dumps(names),json.dumps(names))
subprocess.run(['node','-e',compiler],check=True)
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader']);p=b.new_page()
 p.route('**/vision-pixel-probe',lambda r:r.fulfill(content_type='text/html',body='<canvas width="640" height="480"></canvas>'))
 for name in names:p.route('**/vision-probe-'+name+'.js',lambda r,request,n=name:r.fulfill(path=str(FIX/('vision-probe-'+n+'.js')),content_type='text/javascript'))
 p.route('**/motion-frame-*',lambda r:r.fulfill(path=str(FIX/'head-shake-frames'/('frame-'+r.request.url.rsplit('-',1)[1]+'.jpg')),content_type='image/jpeg'))
 p.goto('http://127.0.0.1:3000/vision-pixel-probe')
 p.evaluate("""async()=>{const M=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/+esm');const files=await M.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm');window.face=await M.FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',delegate:'CPU'},runningMode:'IMAGE',numFaces:2,outputFaceBlendshapes:true});window.hand=await M.HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',delegate:'CPU'},runningMode:'IMAGE',numHands:2});window.T=(await import('./vision-probe-visionTracking.js')).VisionTracker;window.tracker=new T();window.measure=async(index,time)=>{const image=new Image();image.src='./motion-frame-'+String(index).padStart(3,'0');await image.decode();const c=document.querySelector('canvas'),ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0,640,480);const start=performance.now(),f=face.detect(c),h=hand.detect(c),categories=f.faceBlendshapes[0]?.categories||[];return tracker.assess(ctx,640,480,{landmarks:f.faceLandmarks,hands:h.landmarks,blinkRight:categories.find(v=>v.categoryName==='eyeBlinkRight')?.score??null,blinkLeft:categories.find(v=>v.categoryName==='eyeBlinkLeft')?.score??null,inferenceMs:performance.now()-start,frameTime:time},time,null);};}""")
 baseline=[p.evaluate('([i,t])=>measure(i,t)',[1,100+i*100]) for i in range(14)]
 rows=[]
 for i,_ in enumerate(sorted((FIX/'head-shake-frames').glob('frame-*.jpg')),1):
  a=p.evaluate('([i,t])=>measure(i,t)',[i,1600+i*100]);rows.append({'frame':i,'seconds':(i-1)/10,'conditions':a['conditions'],'ratios':a['distanceRatios'],'pose':{k:a['alignment'][k] for k in ['yaw','pitch','roll']},'quality':a['quality'],'inferenceMs':a['inferenceMs']})
 p.screenshot(path=str(OUT/'motion-source.png'));b.close()
 valid=[r for r in rows if r['conditions']['relativeScaleChange'] is not None]
 summary={'delegate':'CPU','controlledPixels':True,'physicalCamera':False,'realDepthChange':False,'source':'https://commons.wikimedia.org/wiki/File:Head_Shake.webm','license':'CC BY-SA 4.0','author':'NMu11er','baselineReady':any(a['conditions']['positionValid'] for a in baseline),'minRelativeScale':min((r['conditions']['relativeScaleChange'] for r in valid),default=None),'maxRelativeScale':max((r['conditions']['relativeScaleChange'] for r in valid),default=None),'states':{s:sum(r['conditions']['distanceState']==s for r in rows) for s in ['stable','near','far','unknown']},'closedEyeFrames':{s:sum(r['conditions'][s]['state']=='closed' for r in rows) for s in ['right','left']},'rows':rows}
 summary['coveredEyeFrames']={s:sum(r['conditions'][s]['state']=='covered' for r in rows) for s in ['right','left']}
 (OUT/'motion-pixels.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in summary.items() if k!='rows'}));assert summary['baselineReady'],'Actual source baseline did not become ready'
 assert not any(summary['coveredEyeFrames'].values()),'Natural open-eye motion incorrectly classified as an opaque cover'
