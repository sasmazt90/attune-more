"""Two independently reviewed native side photos; never a fabricated three-angle scan."""
import argparse,base64,hashlib,json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
parser=argparse.ArgumentParser();parser.add_argument('--selection',type=Path);parser.add_argument('--out',type=Path);parser.add_argument('--indices',type=int,nargs='+',default=[111,225]);args=parser.parse_args()
OUT=args.out or OUT;assert OUT.resolve().is_relative_to((ROOT/'audit-results').resolve());OUT.mkdir(parents=True,exist_ok=True)
sources=json.loads((args.selection or OUT/'contour-selection.json').read_text('utf8'))
with sync_playwright() as pw:
 c=pw.chromium.launch_persistent_context(str(ROOT/'output/playwright'/OUT.name/'side-runtime-profile'),channel='chrome',headless=False,args=['--enable-unsafe-swiftshader'])
 c.route('**/__audit/vision_bundle.mjs',lambda r:r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/vision_bundle.mjs'),content_type='text/javascript'))
 p=c.new_page();p.goto('http://127.0.0.1:3000/privacy')
 assert not p.get_by_label('Cilt tipi için yüz fotoğrafımın Roboflow tarafından işlenmesine izin ver',exact=True).is_checked()
 p.add_script_tag(content=(ROOT/'.runtime/periorbital-v5-browser-support/utilities.js').read_text('utf8'))
 p.evaluate("async()=>{window.__auditMediaPipe=await import('/__audit/vision_bundle.mjs');return !!await __auditRequire('apps/vehicle-app/src/utils/skinAnalyzer.ts').SkinAnalyzer.getFaceLandmarker()}")
 results=[]
 for index in args.indices:
  row=sources[index];data=Path(row['absolutePath']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
  result=p.evaluate('''async(photo)=>{
   const R=n=>__auditRequire('apps/vehicle-app/src/utils/'+n+'.ts'),A=R('skinAnalyzer').SkinAnalyzer;
   const im=new Image();im.src=photo;await im.decode();const canvas=document.createElement('canvas');canvas.width=im.naturalWidth;canvas.height=im.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(im,0,0);
   const a=A.assessAlignment(ctx,canvas.width,canvas.height),q=A.checkQuality(ctx,canvas.width,canvas.height,a.faceDetected,a.box);
   const angles=R('skinMultiAngle').SKIN_ANGLES.filter(p=>R('skinMultiAngle').matchesSkinAngle(a,p));if(!q.isValid||angles.length!==1||angles[0]==='FRONT')throw Error('No real supported side pose');
   const pose=angles[0],capture=await R('skinMultiAngle').captureSkinAngle(ctx,a,q,pose,{}),snapshot=R('skinSnapshot').snapshotRawSkinFrame(canvas,a,pose);snapshot.photoId=capture.frameToken;
   const conditions={yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio,avgLuminance:q.avgLuminance,blurScore:q.blurScore};
   const response=await R('appearanceMeasurements').analyzeAppearance(snapshot,q.isValid,conditions,[],()=>true);
   return {realMediaPipe:a.isMediaPipeActive,pose,conditions,quality:q,visibleRegions:Object.keys(capture.regions),snapshotRegions:Object.keys(snapshot.meshes),response};
  }''','data:image/jpeg;base64,'+base64.b64encode(data).decode())
  region='leftCheek' if result['pose']=='RIGHT' else 'rightCheek'
  assert result['realMediaPipe'] and result['visibleRegions']==result['snapshotRegions']==list(result['response']['measurements'])==[region]
  runtime=result['response']['modelRuntime']['degrees'];assert runtime['sessionLoaded'] and not runtime['usedInResponse'] and runtime['status']=='not-used'
  folder=OUT/'side-product';folder.mkdir(exist_ok=True)
  file=folder/(row['sha256'][:8]+'-side-api.json');file.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
  sag=next(v for v in result['response']['measurements'][region] if v['id']=='sag')
  results.append(dict(sourceSHA256=row['sha256'],pose=result['pose'],conditions=result['conditions'],qualityValid=result['quality']['isValid'],realMediaPipe=result['realMediaPipe'],region=region,value=sag['value'],reason=sag['reason'],onlyVisibleRegionMeasured=list(result['response']['measurements'])==[region],modelRuntime=runtime,fullThreeAngleHistoryProven=False))
 c.close()
(OUT/'side-runtime-receipt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8');print(json.dumps(results))
