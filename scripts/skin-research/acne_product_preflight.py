"""Streaming, local-only browser replay of current product capture functions.

Static development images establish function equivalence, not camera stability
or an independent final test. No health records or production config are written.
"""
import base64, hashlib, json, subprocess, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from heavy_job_lease import HeavyJobLease

ROOT = Path(__file__).resolve().parents[2]
AG = ROOT.parent/'attune-antigravity-skin'
OUT = ROOT/'audit-results/acne-takeover-20261015'
COMMIT = 'd90ff95434c44b4e73ae77a7f1d5d6b2e167c987'

def read(path): return json.loads(path.read_text('utf8'))
def sha(path): return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()

class LocalAssets(BaseHTTPRequestHandler):
    worker_program=b''
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/': data=b'<!doctype html><title>Local acne capture replay</title>'; kind='text/html'
        elif self.path == '/worker.mjs':data=self.worker_program;kind='text/javascript'
        elif self.path == '/vision_bundle.js':data=(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.js').read_bytes();kind='text/javascript'
        elif self.path == '/vision_bundle.mjs': data=(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs').read_bytes();kind='text/javascript'
        elif self.path.startswith('/mediapipe/'):
            p=(ROOT/'apps/vehicle-app/public'/self.path.lstrip('/')).resolve()
            if not p.is_relative_to((ROOT/'apps/vehicle-app/public/mediapipe').resolve()): self.send_error(403);return
            data=p.read_bytes();kind='application/wasm' if p.suffix=='.wasm' else 'text/javascript' if p.suffix=='.js' else 'application/octet-stream'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=read(OUT/'inputs/train-data-engineering-reviewed-20261013.json')
    rows={r['sha256']:r for r in data['rows']}
    cohort=read(OUT/'inputs/controlled_train_cohort.json')
    scope=read(OUT/'inputs/annotation-scope-manifest.json')
    scope_shas=[r['sha256'] for r in scope['images'] if r.get('inScopeTruthCount') or r['isNegative']]
    # All canonical target/negative photos; retain exact prior 28 control cohort.
    scope_shas=list(dict.fromkeys(scope_shas))
    selected=list(dict.fromkeys(cohort['pilotControlShas']+scope_shas))
    for s in cohort['pilotTrainShas']:
        if len([x for x in selected if x in cohort['pilotTrainShas']])>=12:break
        selected.append(s)
    # Diagnose every explicitly reviewed TRAIN clean control. Never infer clean
    # status from a generated polygon or from a model's low lesion confidence.
    selected=list(dict.fromkeys(selected+[s for s in cohort['pilotTrainShas'] if rows[s].get('negativeROI') and not rows[s].get('annotations')]))
    sources=[]
    for s in selected:
        r=rows[s];p=Path(r['absolutePath']);assert sha(p)==s
        sources.append(dict(sha256=s,path=str(p),group=r['group'],split=r['split'],cohort='heldout-train' if s in cohort['pilotControlShas'] else 'scope-B-development' if s in scope_shas else 'pilot-train-diagnosis'))
    (OUT/'source-selection.json').write_text(json.dumps(sources,indent=2),'utf8')
    import psutil
    deadline=time.monotonic()+60
    while psutil.virtual_memory().available/2**20<1600 and time.monotonic()<deadline:time.sleep(1)
    with HeavyJobLease('CDC-acne-current-product-browser-preflight',peak_mib=1350,minimum_available_mib=1600,include_children=True,memory_metric='private') as lease:
        from playwright.sync_api import sync_playwright
        subprocess.run(['C:/nvm4w/nodejs/node.exe','scripts/skin-research/bundle_periorbital_browser.cjs'],cwd=ROOT,check=True,capture_output=True)
        bundle=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8')
        worker='self.window=self;importScripts("/vision_bundle.js");self.__auditMediaPipe=Vision;'+bundle+'''(async()=>{
const A=__auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer;
await A.getFaceLandmarker();self.postMessage({ready:A.isMediaPipeReady()});
self.onmessage=e=>{const f=e.data;try{const c=new OffscreenCanvas(f.width,f.height),x=c.getContext('2d');x.drawImage(f,0,0);self.postMessage({alignment:A.assessAlignment(x,f.width,f.height)});}catch(e){self.postMessage({error:String(e)})}finally{f.close()}};})().catch(e=>self.postMessage({error:String(e)}));'''
        LocalAssets.worker_program=worker.encode('utf8')
        server=ThreadingHTTPServer(('127.0.0.1',8879),LocalAssets);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        results=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
                try:
                    context=browser.new_context();page=context.new_page();page.on('console',lambda m:print(json.dumps(dict(browserConsole=m.type,text=m.text[:1600])),flush=True) if m.type in ['error','warning'] else None);page.goto('http://127.0.0.1:8879/')
                    page.add_script_tag(content=bundle)
                    page.evaluate('async()=>{window.__auditMediaPipe=await import("/vision_bundle.mjs")}')
                    page.evaluate('''async()=>{window.worker=new Worker('/worker.mjs');await new Promise((ok,no)=>{const timer=setTimeout(()=>no(Error('worker timeout')),30000);worker.onerror=e=>no(Error(e.message));worker.onmessage=e=>{clearTimeout(timer);if(e.data.ready)ok();else no(Error(e.data.error||'MediaPipe not ready'));}})}''')
                    for item in sources:
                        lease.check();s=item['sha256'];dest=OUT/'product-inputs'/s;dest.mkdir(parents=True,exist_ok=True)
                        result=page.evaluate('''async source=>{
const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts');const im=new Image();im.src=source;await im.decode();
const native=document.createElement('canvas');native.width=im.naturalWidth;native.height=im.naturalHeight;native.getContext('2d').drawImage(im,0,0);
const ratio=Math.min(1,640/native.width),c=document.createElement('canvas');c.width=Math.round(native.width*ratio);c.height=Math.round(native.height*ratio);const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(native,0,0,c.width,c.height);
const frame=await createImageBitmap(c);const a=await new Promise((ok,no)=>{worker.onmessage=e=>e.data.error?no(Error(e.data.error)):ok(e.data.alignment);worker.postMessage(frame,[frame]);});
const quality=R('skinAnalyzer').SkinAnalyzer.checkQuality(ctx,c.width,c.height,a.faceDetected,a.box);
const angle=R('skinMultiAngle').SKIN_ANGLES.find(p=>R('skinMultiAngle').matchesSkinAngle(a,p))||null;
let snapshot=null,error=null,eyePhoto=null;try{if(a.landmarks?.length){snapshot=R('skinSnapshot').snapshotRawSkinFrame(native,a,angle||'FRONT');const box=R('skinEyewear').eyewearCrop(a.landmarks,native.width,native.height),eye=document.createElement('canvas');eye.width=eye.height=112;eye.getContext('2d').drawImage(native,box.x,box.y,box.width,box.height,0,0,112,112);eyePhoto=eye.toDataURL('image/png');}}catch(e){error=String(e)}
return {width:native.width,height:native.height,analysisWidth:c.width,analysisHeight:c.height,alignment:a,quality,matchedAngle:angle,poseEligible:!!angle,qualityPoseEligible:!!angle&&quality.isValid,snapshot,snapshotError:error,eyePhoto};
}''','data:image/jpeg;base64,'+base64.b64encode(Path(item['path']).read_bytes()).decode())
                        snap=result.get('snapshot')
                        if snap:
                            uri=snap.pop('dataUrl');(dest/'snapshot.png').write_bytes(base64.b64decode(uri.split(',',1)[1]));result['snapshotSHA256']=sha(dest/'snapshot.png')
                        result.update(item);(dest/'preflight.json').write_text(json.dumps(result),'utf8');results.append(result)
                        (OUT/'browser-progress.json').write_text(json.dumps(dict(completed=len(results),total=len(sources),last=s)),'utf8')
                        print(json.dumps(dict(completed=len(results),sha=s[:8],angle=result['matchedAngle'],quality=result['quality']['status'])),flush=True)
                    hashes=read(ROOT/'.runtime/periorbital-v5-browser-support/source-hashes.json')
                    (OUT/'browser-preflight.json').write_text(json.dumps(dict(schema='current-product-static-browser-replay-v1',productionHEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceHashes=hashes,actualBrowserMediaPipe=True,physicalCameraStabilityVerified=False,fullEyewearPending=True,rows=results,resource=lease.receipt()),indent=2),'utf8')
                finally:browser.close()
        finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
