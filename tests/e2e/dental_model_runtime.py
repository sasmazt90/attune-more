"""Actual face worker + normal dental API on a declared NASA front fixture.
This is one visible-teeth front photo, not four physical camera poses or diagnosis.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

parser=argparse.ArgumentParser();parser.add_argument('--prepare-source-only',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/combined-health-20261008/dental-runtime';OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True,args=['--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+str(ROOT/'audit-fixtures/high-detail.y4m'),'--enable-unsafe-swiftshader'])
    context=browser.new_context(permissions=['camera']);context.add_init_script('''window.actualAlignment=null;window.sourceRequests=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(message,...rest){if(message.type==='frame'&&!this.alignmentObserved){this.alignmentObserved=true;this.addEventListener('message',({data})=>{if(data.alignment)window.actualAlignment=data.alignment;});}return post.call(this,message,...rest);};''')
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    context.request.post('http://127.0.0.1:8000/api/vehicle/speed',data={'speedKmH':0})
    page.goto('http://127.0.0.1:3000/dental');page.get_by_label('Kamerayı açıp fotoğraflarımı yalnız bu cihazda geçici işlemeyi kabul ediyorum.').check();page.get_by_role('button',name='Kamerayı aç ve taramayı başlat').click()
    page.wait_for_function('window.actualAlignment?.isMediaPipeActive&&window.actualAlignment?.faceDetected',timeout=60000)
    source=page.evaluate('''async()=>{const alignment=window.actualAlignment,video=document.querySelector('[data-dental-live-video]'),canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext('2d').drawImage(video,0,0);const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',pixels));return {processingConsent:true,captures:[{photo:canvas.toDataURL('image/png'),photoId:Array.from(digest).map(x=>x.toString(16).padStart(2,'0')).join(''),width:canvas.width,height:canvas.height,pose:'BITE',landmarks:alignment.landmarks,conditions:{yaw:alignment.yaw,pitch:alignment.pitch,roll:alignment.roll,scaleRatio:alignment.scaleRatio}}]};}''')
    # Exercise the actual TypeScript capture gate with a native browser Canvas,
    # actual production-worker landmarks, and the exact source sent to the API.
    # No pose or quality overrides, and no claim of a physical camera trial.
    capture_code=subprocess.check_output(['node','-e',"const fs=require('fs'),ts=require('typescript');process.stdout.write(ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/dentalCapture.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)"],cwd=ROOT,text=True,encoding='utf8')
    capture_gate=page.evaluate('''async({code,capture})=>{const exports={},module={exports};new Function('exports','module',code)(exports,module);const image=new Image();image.src=capture.photo;await image.decode();const canvas=document.createElement('canvas');canvas.width=capture.width;canvas.height=capture.height;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);return Object.fromEntries(['FRONT','BITE','RIGHT','LEFT'].map(pose=>[pose,exports.assessDentalCapture(ctx,window.actualAlignment,pose)]));}''',{'code':capture_code,'capture':source['captures'][0]})
    assert capture_gate['BITE']['valid'] and capture_gate['FRONT']['valid'],capture_gate
    assert not capture_gate['RIGHT']['valid'] and not capture_gate['LEFT']['valid'],'An actual frontal source cannot pass the two lateral-pose gates'
    page.get_by_role('button',name='İptal et',exact=True).click()
    result=page.evaluate('''async body=>{const response=await fetch('http://localhost:8000/api/local-health/dental',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok)throw Error('Dental API '+response.status);return response.json();}''',source)
    view=result['views'][0];assert view['photoId']==source['captures'][0]['photoId'] and view['quality']['valid'],view['quality']
    assert view['pose']=='BITE' and view['sourceWidth']==source['captures'][0]['width']
    if not args.prepare_source_only:
        manifest=json.loads((ROOT/'services/core-api/models/dental-yolox-s.json').read_text('utf8'))
        assert view['caries']['type']=='trained_prediction' and view['caries']['quality']=='valid'
        assert view['caries']['modelHash']==manifest['modelHash']
        assert view['caries']['runtimeVersions']==manifest['additionalDiagnostics']['libraryVersions']
        assert hashlib.sha256((ROOT/'services/core-api/models/dental-yolox-s.onnx').read_bytes()).hexdigest()==manifest['modelHash']
        for candidate in view['caries']['candidates']:
            assert candidate['classCode'] in manifest['classes'] and 0<=candidate['confidence']<=1
            box=candidate['bounds'];assert box['x']>=0 and box['y']>=0 and box['width']>0 and box['height']>0
            assert box['x']+box['width']<=view['sourceWidth']+.001 and box['y']+box['height']<=view['sourceHeight']+.001
    assert not errors,errors
    # Public licensed fixture only; never hardware/user-camera acceptance.
    (OUT/'front-fixture-request.json').write_text(json.dumps(source),'utf8')
    (OUT/'proof.json').write_text(json.dumps(dict(status='SOURCE_PREPARED' if args.prepare_source_only else 'PASS',buildId=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),actualProductionFaceWorker=True,actualFrontendCaptureGate=capture_gate,actualNormalDentalEndpoint=True,trainedModelRequired=not args.prepare_source_only,fixture='existing NASA visible-teeth front portrait',frontOnly=True,physicalCamera=False,clinicalValidation=False,result=result,pageErrors=errors),indent=2),'utf8')
    context.close();browser.close()
print('Prepared actual front-fixture source' if args.prepare_source_only else 'PASS actual hash-checked model through normal dental API; front fixture only')
