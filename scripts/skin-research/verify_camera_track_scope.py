"""Local, metadata-only physical track check. Never saves camera pixels."""
import hashlib,json,time
from pathlib import Path
from heavy_job_lease import HeavyJobLease,HeavyJobUnavailable

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/material-closeout-20261013'
OUT.mkdir(exist_ok=True)
constraints=dict(width=dict(ideal=1920),height=dict(ideal=1080),resizeMode=dict(ideal='none'),facingMode='user')
source=ROOT/'apps/vehicle-app/src/app/skin/page.tsx'
text=source.read_text('utf8')
assert "width:{ideal:1920},height:{ideal:1080},resizeMode:{ideal:'none'},facingMode:'user'" in text
assert 'canvas.width = video.videoWidth' in text and 'canvas.height = video.videoHeight' in text
receipt=dict(requested=constraints,sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),cameraPixelsSaved=False,hostedCalls=0,phone=dict(status='NO_CONNECTED_DEVICE_OR_BROWSER_ACCESS',actualTrackVerified=False),vehicle=dict(status='NO_CONNECTED_DEVICE_OR_BROWSER_ACCESS',actualTrackVerified=False))
try:
    with HeavyJobLease('CDC-physical-camera-track-metadata',peak_mib=240,minimum_available_mib=680,include_children=True,memory_metric='private') as lease:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chrome',headless=True,args=['--disable-gpu'])
            try:
                context=browser.new_context(permissions=['camera'])
                page=context.new_page();page.set_default_timeout(15000)
                page.route('**/*',lambda route:route.fulfill(body='<html><video autoplay muted></video><canvas></canvas></html>',content_type='text/html') if route.request.url=='http://localhost:18093/track' else route.abort())
                page.goto('http://localhost:18093/track');lease.check()
                receipt['pc']=page.evaluate("""async constraints=>{
                    let stream;
                    try {
                        stream=await navigator.mediaDevices.getUserMedia({video:constraints});
                        const video=document.querySelector('video');video.srcObject=stream;await video.play();
                        await Promise.race([new Promise(r=>video.requestVideoFrameCallback(r)),new Promise((_,r)=>setTimeout(()=>r(Error('VIDEO_FRAME_TIMEOUT')),10000))]);
                        const track=stream.getVideoTracks()[0],settings=track.getSettings(),caps=track.getCapabilities();
                        delete settings.deviceId;delete settings.groupId;delete caps.deviceId;delete caps.groupId;
                        const canvas=document.querySelector('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;
                        // Dimension contract only: no getImageData, PNG, frame upload or personal-photo persistence.
                        return {status:'ACTUAL_PHYSICAL_TRACK',label:track.label,settings,capabilities:caps,videoWidth:video.videoWidth,videoHeight:video.videoHeight,snapshotSize:[canvas.width,canvas.height],orientation:video.videoWidth>=video.videoHeight?'landscape':'portrait',snapshotMatchesTrack:settings.width===canvas.width&&settings.height===canvas.height};
                    } catch(e) {return {status:'PHYSICAL_TRACK_UNAVAILABLE',errorName:e.name,errorMessage:e.message};}
                    finally {stream?.getTracks().forEach(track=>track.stop());}
                }""",constraints)
                lease.check()
                receipt['orientationContract']=page.evaluate("""()=>[[1920,1080],[1080,1920]].map(([w,h])=>{const c=document.querySelector('canvas');c.width=w;c.height=h;return {sourceSize:[w,h],snapshotSize:[c.width,c.height],sameNativeDimensions:c.width===w&&c.height===h,physicalDeviceTest:false};})""")
            finally:browser.close()
        receipt['resource']=lease.receipt()
except HeavyJobUnavailable as error:
    receipt['resourceBlocked']=str(error)
finally:
    (OUT/'physical-camera-track-scope.json').write_text(json.dumps(receipt,indent=2),'utf8')
print(json.dumps(receipt),flush=True)
