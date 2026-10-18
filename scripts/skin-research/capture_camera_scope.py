"""Current product capture modules, local actual Chrome/MediaPipe, finite sources.

The video track is a disclosed virtual device containing unchanged native video
pixels. This verifies constraints/snapshot behavior, not a physical user's camera.
No result fixtures, hosted calls, normal profile writes or forced pose acceptance.
"""
import json,sys,hashlib,subprocess,base64,time
from pathlib import Path
from heavy_job_lease import HeavyJobLease
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013'
with HeavyJobLease('CD-current-camera-and-contour-probe',peak_mib=1000,minimum_available_mib=1400,include_children=True) as lease:
    import cv2
    from playwright.sync_api import sync_playwright
    cv2.setNumThreads(1)
    fixture=json.loads((OUT/'camera-fixture-selection.json').read_text('utf8'))['nativeVideoSource']
    if '--camera-nasa' in sys.argv:
        previous=json.loads((ROOT/'audit-results/all-health-20261010/natural-skin/measurements-private.json').read_text('utf8'));source=next(r for r in previous if r['index']==0)
        fixture=dict(sourcePath=str(ROOT/source['source']),sourceSHA256=source['sourceSHA256'],previouslyLicensedLocalSource=True,role='native licensed natural portrait virtual camera; not contour positive or held-out accuracy test')
    file=Path(fixture['sourcePath']);assert hashlib.sha256(file.read_bytes()).hexdigest()==fixture['sourceSHA256']
    image=cv2.imread(str(file));h,w=image.shape[:2];assert w%2==h%2==0
    yuv=cv2.cvtColor(image,cv2.COLOR_BGR2YUV_I420);video=OUT/'native-camera.y4m'
    with video.open('wb') as output:output.write(f'YUV4MPEG2 W{w} H{h} F30:1 Ip A1:1 C420jpeg\n'.encode());output.write(b'FRAME\n');output.write(yuv.tobytes())
    del image,yuv;lease.check()
    names=['skinAnalyzer','skinMesh','skinSnapshot','cameraStability','skinMultiAngle']
    compiler="const fs=require('fs'),ts=require('typescript');let out={};for(const n of "+json.dumps(names)+"){out[n]=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;}process.stdout.write(JSON.stringify(out));"
    modules=json.loads(subprocess.check_output(['C:/nvm4w/nodejs/node.exe','-e',compiler],cwd=ROOT,text=True,encoding='utf8'))
    for n,s in modules.items():
        s=s.replace("from '@mediapipe/tasks-vision'","from './vision_bundle.mjs'")
        for dep in names:s=s.replace("'./"+dep+"'","'./"+dep+".js'")
        modules[n]=s
    hashes={n:hashlib.sha256((ROOT/f'apps/vehicle-app/src/utils/{n}.ts').read_bytes()).hexdigest() for n in names};rows=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream',f'--use-file-for-fake-video-capture={video}','--disable-dev-shm-usage'])
        try:
            page=browser.new_page();page.set_default_timeout(30000);lease.check()
            def route(r):
                name=r.request.url.rsplit('/',1)[-1]
                if name=='index':r.fulfill(body='<html><video autoplay muted></video><canvas></canvas></html>',content_type='text/html')
                elif name in [n+'.js' for n in names]:r.fulfill(body=modules[name[:-3]],content_type='text/javascript')
                elif name=='face.task':r.fulfill(path=str(ROOT/'audit-results/skin-capabilities-20261008/scin/face_landmarker.task'),content_type='application/octet-stream')
                elif name=='vision_bundle.mjs':r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision'/name),content_type='text/javascript')
                elif name.startswith('vision_wasm'):r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/wasm'/name),content_type='application/wasm' if name.endswith('.wasm') else 'text/javascript')
                else:r.abort()
            page.route('**/*',route);page.goto('http://localhost:18092/audit/scope/index')
            page.evaluate("""async()=>{const V=await import('./vision_bundle.mjs');window.model=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('/audit/scope/wasm'),{baseOptions:{modelAssetPath:'/audit/scope/face.task'},runningMode:'IMAGE',numFaces:2,outputFaceBlendshapes:true,outputFacialTransformationMatrixes:true});window.S=(await import('./skinAnalyzer.js')).SkinAnalyzer;S.landmarkerInstance=model;window.snapshot=(await import('./skinSnapshot.js')).snapshotRawSkinFrame;window.matches=(await import('./skinMultiAngle.js')).matchesSkinAngle;
            window.probe=async()=>{const c=document.querySelector('canvas'),ctx=c.getContext('2d',{willReadFrequently:true});const a=S.assessAlignment(ctx,c.width,c.height),q=S.checkQuality(ctx,c.width,c.height,a.faceDetected,a.box);const detected=model.detect(c);const expression=Object.fromEntries((detected.faceBlendshapes?.[0]?.categories||[]).map(r=>[r.categoryName,r.score]));const angles=['FRONT','RIGHT','LEFT'].filter(p=>matches(a,p));const rgba=ctx.getImageData(0,0,c.width,c.height).data;const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',rgba))].map(v=>v.toString(16).padStart(2,'0')).join('');let payload=null,snapshotError=null; if(angles.length&&q.isValid){try{const s=snapshot(c,a,angles[0]);payload={processingConsent:true,photo:s.dataUrl,photoId:digest,pose:angles[0],meshes:s.meshes,exclusions:s.exclusions,landmarks:a.landmarks,qualityValid:q.isValid,conditions:{yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio,avgLuminance:q.avgLuminance,blurScore:q.blurScore},expressionObservation:{photoId:digest,version:'local-mediapipe-expression-support-v1',scores:expression}};}catch(e){snapshotError=String(e);}}return {size:[c.width,c.height],photoId:digest,alignment:{...a,landmarks:undefined},quality:q,expression,acceptedAngles:angles,snapshotError,payload,sourceFacePixels:a.landmarks?.length?Math.abs(a.landmarks[454].x-a.landmarks[234].x)*c.width:null};};}""")
            lease.check()
            track=page.evaluate("""async()=>{const constraints={video:{width:{ideal:1920},height:{ideal:1080},resizeMode:{ideal:'none'},facingMode:'user'}};window.stream=await navigator.mediaDevices.getUserMedia(constraints);const v=document.querySelector('video');v.srcObject=stream;await v.play();await new Promise(r=>v.requestVideoFrameCallback(r));const c=document.querySelector('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);const t=stream.getVideoTracks()[0];return {constraints,settings:t.getSettings(),capabilities:t.getCapabilities(),videoSize:[v.videoWidth,v.videoHeight],deviceKind:'controlled native video virtual device; not physical user camera',snapshotPreservesTrackDimensions:true};}""")
            measured=page.evaluate('()=>probe()');payload=measured.pop('payload');row=dict(kind='actual-virtual-camera-track',source=fixture,track=track,**measured);rows.append(row)
            (OUT/'camera-contour-probe-progress.json').write_text(json.dumps(rows,indent=2),'utf8')
            if payload:(OUT/'camera-1280-native-payload.json').write_text(json.dumps(payload),'utf8')
            page.evaluate('()=>stream.getTracks().forEach(t=>t.stop())');lease.check()
            sources=[] if '--camera-only' in sys.argv else json.loads((OUT/'contour-probe-selection.json').read_text('utf8'))
            for source in sources:
                lease.check();path=Path(source['absolutePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
                data='data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode();measured=page.evaluate("""async(data)=>{const im=new Image();im.src=data;await im.decode();const c=document.querySelector('canvas');c.width=im.width;c.height=im.height;c.getContext('2d').drawImage(im,0,0);return await probe();}""",data)
                payload=measured.pop('payload');row=dict(kind='targeted-natural-local-photo',source=source,**measured);rows.append(row)
                if payload:(OUT/f"{source['sha256'][:8]}-current-capture-payload.json").write_text(json.dumps(payload),'utf8')
                (OUT/'camera-contour-probe-progress.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps(dict(source=source['sha256'][:8],quality=measured['quality']['isValid'],angles=measured['acceptedAngles'],snapshot=payload is not None)),flush=True);del data,payload
        finally:
            failure=sys.exc_info()[1]
            partial=dict(rows=rows,sourceHashes=hashes,complete=False,failure=str(failure) if failure else None,normalProductRecordsWritten=False,forcedPose=False,physicalUserAcceptance=False,maximumResidentSources=1,hostedCalls=0,resource=lease.receipt())
            (OUT/'camera-contour-probe.json').write_text(json.dumps(partial,indent=2),'utf8');browser.close()
    receipt=dict(rows=rows,sourceHashes=hashes,normalProductRecordsWritten=False,forcedPose=False,physicalUserAcceptance=False,maximumResidentSources=1,hostedCalls=0,resource=lease.receipt())
    (OUT/'camera-contour-probe.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(dict(camera=rows[0],resource=receipt['resource'])),flush=True)
