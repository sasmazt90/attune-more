"""Finite native browser capture with a streamed localhost-only artifact sink.

The product modules/task/quality/angle/snapshot contracts are current source.
Large PNGs bypass Playwright's return-value copy. Original pixels are not
resized. One owned browser and one source at a time; hosted calls are blocked.
"""
import json,sys,hashlib,subprocess,base64,time,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-closeout-20261013';OUT.mkdir(exist_ok=True);SOURCE=ROOT/'audit-results/native-camera-scope-20261013'
camera_only='--camera-only' in sys.argv
with HeavyJobLease('CDC-current-source-browser-capture',peak_mib=500 if camera_only else 600,minimum_available_mib=900 if camera_only else 1000,include_children=True,memory_metric='private') as lease:
    import cv2
    from playwright.sync_api import sync_playwright
    cv2.setNumThreads(1);names=['skinAnalyzer','skinMesh','skinSnapshot','cameraStability','skinMultiAngle'];compiler="const fs=require('fs'),ts=require('typescript');let out={};for(const n of "+json.dumps(names)+"){out[n]=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;}process.stdout.write(JSON.stringify(out));"
    modules=json.loads(subprocess.check_output(['C:/nvm4w/nodejs/node.exe','-e',compiler],cwd=ROOT,text=True,encoding='utf8'))
    for n,s in modules.items():
        s=s.replace("from '@mediapipe/tasks-vision'","from './vision_bundle.mjs'")
        for dep in names:s=s.replace("'./"+dep+"'","'./"+dep+".js'")
        modules[n]=s
    class Sink(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            allowed=['camera-native',*[s['sha256'][:8] for s in json.loads((SOURCE/'contour-probe-selection.json').read_text('utf8'))]];name=self.path.rsplit('/',1)[-1]
            count=int(self.headers.get('Content-Length','0'))
            if name not in allowed or not 0<count<=35000000:self.send_error(400);return
            path=OUT/(name+'-payload.json')
            with path.open('xb') as output:
                while count:
                    block=self.rfile.read(min(1048576,count))
                    if not block:raise RuntimeError('Incomplete own snapshot upload')
                    output.write(block);count-=len(block)
            self.send_response(200);self.send_header('Access-Control-Allow-Origin','http://localhost:18092');self.end_headers();self.wfile.write(b'{}')
        def do_OPTIONS(self):
            self.send_response(204);self.send_header('Access-Control-Allow-Origin','http://localhost:18092');self.send_header('Access-Control-Allow-Headers','Content-Type');self.send_header('Access-Control-Allow-Methods','POST');self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',18014),Sink);server_thread=threading.Thread(target=server.serve_forever);server_thread.start();rows=[]
    try:
        sources=[] if camera_only else [s for s in json.loads((SOURCE/'contour-probe-selection.json').read_text('utf8')) if not (SOURCE/(s['sha256'][:8]+'-current-capture-payload.json')).exists()]
        if camera_only:
            old=json.loads((ROOT/'audit-results/all-health-20261010/natural-skin/measurements-private.json').read_text('utf8'));ref=next(r for r in old if r['index']==0);file=ROOT/ref['source'];assert hashlib.sha256(file.read_bytes()).hexdigest()==ref['sourceSHA256'];image=cv2.imread(str(file));h,w=image.shape[:2];video=OUT/'camera-native.y4m'
            with video.open('wb') as output:output.write(f'YUV4MPEG2 W{w} H{h} F30:1 Ip A1:1 C420jpeg\n'.encode());output.write(b'FRAME\n');output.write(cv2.cvtColor(image,cv2.COLOR_BGR2YUV_I420).tobytes())
            del image;sources=[dict(sha256=ref['sourceSHA256'],absolutePath=str(file),camera=True,rights='previously recorded NASA/public-domain portrait fixture; virtual video device, not physical acceptance')]
        with sync_playwright() as pw:
            for source in sources:
                lease.check();prefix='camera-native' if camera_only else source['sha256'][:8]
                if (OUT/(prefix+'-capture.json')).exists():rows.append(json.loads((OUT/(prefix+'-capture.json')).read_text('utf8')));continue
                if not camera_only and (max(source['width'],source['height'])>4096 or source['width']*source['height']>8400000):
                    row=dict(source=source,captured=False,size=[source['width'],source['height']],status='EXISTING_API_SOURCE_SIZE_REJECTION',quality=None,acceptedAngles=[],reason='Existing decode_photo 4096-per-axis/8.4MP limit; no resize or healthy result')
                    (OUT/(prefix+'-capture.json')).write_text(json.dumps(row,indent=2),'utf8');rows.append(row);continue
                browser=pw.chromium.launch(channel='chrome',headless=True,args=['--disable-gpu',*(['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',f'--use-file-for-fake-video-capture={video}'] if camera_only else [])])
                try:
                    page=browser.new_page();page.set_default_timeout(30000)
                    def route(r):
                        name=r.request.url.rsplit('/',1)[-1]
                        if r.request.url.startswith('http://127.0.0.1:18014/'):r.continue_();return
                        if name=='index':r.fulfill(body='<html><video autoplay muted></video><canvas></canvas></html>',content_type='text/html')
                        elif name in [n+'.js' for n in names]:r.fulfill(body=modules[name[:-3]],content_type='text/javascript')
                        elif name=='face.task':r.fulfill(path=str(ROOT/'audit-results/skin-capabilities-20261008/scin/face_landmarker.task'),content_type='application/octet-stream')
                        elif name=='vision_bundle.mjs':r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision'/name),content_type='text/javascript')
                        elif name.startswith('vision_wasm'):r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/wasm'/name),content_type='application/wasm' if name.endswith('.wasm') else 'text/javascript')
                        else:r.abort()
                    page.route('**/*',route);page.goto('http://localhost:18092/audit/index');page.evaluate("""async()=>{const V=await import('./vision_bundle.mjs');window.model=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('/audit/wasm'),{baseOptions:{modelAssetPath:'/audit/face.task',delegate:'CPU'},runningMode:'IMAGE',numFaces:2,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true});window.S=(await import('./skinAnalyzer.js')).SkinAnalyzer;S.landmarkerInstance={detect:c=>(window.detection=model.detect(c))};window.snapshot=(await import('./skinSnapshot.js')).snapshotRawSkinFrame;window.matches=(await import('./skinMultiAngle.js')).matchesSkinAngle;}""");lease.check()
                    started=time.monotonic();track=None
                    if camera_only:
                        track=page.evaluate("""async()=>{window.stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1920},height:{ideal:1080},resizeMode:{ideal:'none'},facingMode:'user'}});const v=document.querySelector('video');v.srcObject=stream;await v.play();await new Promise(r=>v.requestVideoFrameCallback(r));const c=document.querySelector('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);const t=stream.getVideoTracks()[0];return {settings:t.getSettings(),capabilities:t.getCapabilities(),snapshotSize:[c.width,c.height],physicalUserCamera:false};}""")
                        decode_s=0
                    else:
                        file=Path(source['absolutePath']);assert hashlib.sha256(file.read_bytes()).hexdigest()==source['sha256'];data='data:image/jpeg;base64,'+base64.b64encode(file.read_bytes()).decode();decode_s=page.evaluate("""async(data)=>{const t=performance.now(),im=new Image();im.src=data;await im.decode();const c=document.querySelector('canvas');c.width=im.width;c.height=im.height;c.getContext('2d').drawImage(im,0,0);return (performance.now()-t)/1000;}""",data);del data
                    measured=page.evaluate("""async(prefix)=>{const c=document.querySelector('canvas'),ctx=c.getContext('2d',{willReadFrequently:true});let t=performance.now();const a=S.assessAlignment(ctx,c.width,c.height);const mpSeconds=(performance.now()-t)/1000;t=performance.now();const q=S.checkQuality(ctx,c.width,c.height,a.faceDetected,a.box);const qualitySeconds=(performance.now()-t)/1000;const angles=['FRONT','RIGHT','LEFT'].filter(p=>matches(a,p));const rgba=ctx.getImageData(0,0,c.width,c.height).data;const id=[...new Uint8Array(await crypto.subtle.digest('SHA-256',rgba))].map(v=>v.toString(16).padStart(2,'0')).join('');const scores=Object.fromEntries((detection.faceBlendshapes?.[0]?.categories||[]).map(r=>[r.categoryName,r.score]));let captured=false,snapshotSeconds=null;if(q.isValid&&angles.length){t=performance.now();const s=snapshot(c,a,angles[0]);snapshotSeconds=(performance.now()-t)/1000;const payload={processingConsent:true,hostedProcessingConsent:false,photo:s.dataUrl,photoId:id,pose:angles[0],meshes:s.meshes,exclusions:s.exclusions,landmarks:a.landmarks,qualityValid:q.isValid,conditions:{yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio,avgLuminance:q.avgLuminance,blurScore:q.blurScore},expressionObservation:{photoId:id,version:'local-mediapipe-expression-support-v1',scores}};const r=await fetch('http://127.0.0.1:18014/'+prefix,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok)throw Error('OWN_SNAPSHOT_SINK_FAILED');captured=true;}return {size:[c.width,c.height],photoId:id,quality:q,acceptedAngles:angles,alignment:{yaw:a.yaw,pitch:a.pitch,roll:a.roll,sourceFramed:a.sourceFramed,faceCount:a.faceCount},sourceFacePixels:a.landmarks?.length?Math.abs(a.landmarks[454].x-a.landmarks[234].x)*c.width:null,expression:scores,mpSeconds,qualitySeconds,snapshotSeconds,captured};}""",prefix)
                    row=dict(source=source,track=track,decodeSeconds=decode_s,captureSeconds=time.monotonic()-started,**measured);(OUT/(prefix+'-capture.json')).write_text(json.dumps(row,indent=2),'utf8');rows.append(row);print(json.dumps(dict(source=prefix,captured=row['captured'],quality=row['quality']['isValid'],angles=row['acceptedAngles'])),flush=True);lease.check()
                finally:browser.close()
    finally:
        server.shutdown();server.server_close();server_thread.join(2)
        (OUT/('camera-capture-receipt.json' if camera_only else 'remaining-capture-receipt.json')).write_text(json.dumps(dict(rows=rows,resource=lease.receipt(),normalUserRecordsWritten=False,globalSourceResize=False,hostedCalls=0,streamedLocalhostSink=True),indent=2),'utf8')
