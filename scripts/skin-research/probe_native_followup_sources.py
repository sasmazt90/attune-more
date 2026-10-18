"""Bounded new source selection: actual MP, quality, pose and snapshot contracts."""
import argparse,base64,hashlib,json,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--selection',type=Path);parser.add_argument('--out',type=Path)
args=parser.parse_args();OUT=args.out or ROOT/'audit-results/dry-sag-native-followup-20261013';OUT.mkdir(parents=True,exist_ok=True)
assert OUT.resolve().is_relative_to((ROOT/'audit-results').resolve())
sources=json.loads((args.selection or OUT/'probe-selection.json').read_text('utf-8-sig'));profile=ROOT/'output/playwright'/OUT.name/'probe-profile'
with sync_playwright() as pw:
 context=pw.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,viewport=dict(width=1400,height=950),args=['--enable-unsafe-swiftshader'])
 context.route('**/__audit/vision_bundle.mjs',lambda r:r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs'),content_type='text/javascript'))
 page=context.new_page();page.goto('http://127.0.0.1:3000/privacy');assert not page.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True).is_checked()
 page.add_script_tag(content=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8'));page.evaluate("async()=>{window.__auditMediaPipe=await import('/__audit/vision_bundle.mjs');return !!await __auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer.getFaceLandmarker()}")
 for row in sources:
  prefix=row['sha256'][:8];data=Path(row['absolutePath']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
  result=page.evaluate('''async(photo)=>{
   const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'),A=R('skinAnalyzer').SkinAnalyzer;
   const im=new Image();im.src=photo;await im.decode();const canvas=document.createElement('canvas');canvas.width=im.naturalWidth;canvas.height=im.naturalHeight;const x=canvas.getContext('2d');x.drawImage(im,0,0);
   const a=A.assessAlignment(x,canvas.width,canvas.height),q=A.checkQuality(x,canvas.width,canvas.height,a.faceDetected,a.box);
   const conditions={yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio,avgLuminance:q.avgLuminance,blurScore:q.blurScore},angles=R('skinMultiAngle').SKIN_ANGLES.filter(p=>R('skinMultiAngle').matchesSkinAngle(a,p));
   let snapshot=null,reason=null,pose='FRONT';
   try{pose=angles[0]||'FRONT';snapshot=R('skinSnapshot').snapshotRawSkinFrame(canvas,a,pose);snapshot.photoId=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',x.getImageData(0,0,canvas.width,canvas.height).data))).map(v=>v.toString(16).padStart(2,'0')).join('');}catch(e){reason=e.message;}
   let capture=null;if(q.isValid&&angles.length)try{capture=await R('skinMultiAngle').captureSkinAngle(x,a,q,pose,{})}catch(e){reason=e.message;}
   const points=a.landmarks||[],mouth=points.length?Math.hypot(points[13].x-points[14].x,points[13].y-points[14].y)/Math.hypot(points[61].x-points[291].x,points[61].y-points[291].y):null;
   return {quality:q,conditions,faceCount:a.faceCount,realMediaPipe:a.isMediaPipeActive,sourceFramed:a.sourceFramed,supportedAngles:angles,poseCaptureCompleted:!!capture,snapshotFailure:reason,mouthOpening:mouth,snapshot};
  }''','data:image/jpeg;base64,'+base64.b64encode(data).decode())
  (OUT/(prefix+'-probe.json')).write_text(json.dumps(result,ensure_ascii=False),'utf8');print(json.dumps({'source':prefix,**{k:v for k,v in result.items() if k not in ('snapshot','quality')}}),flush=True)
 context.close()
