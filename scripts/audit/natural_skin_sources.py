"""New current-backend measurements of existing rights-recorded natural sources.
Original source RGB, actual face model and exact production snapshot/ROI code.
No natural-photo labels are manufactured from the resulting scores.
"""
import base64,json,subprocess,hashlib,time,os
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/natural-skin';OUT.mkdir(parents=True,exist_ok=True)
names=['skinAnalyzer','skinMesh','skinSnapshot','cameraStability']
compiler="const fs=require('fs'),ts=require('typescript');let out={};for(const n of "+json.dumps(names)+"){out[n]=ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+n+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;}process.stdout.write(JSON.stringify(out));"
modules=json.loads(subprocess.check_output(['node','-e',compiler],cwd=ROOT,text=True,encoding='utf8'))
for n,s in modules.items():
 s=s.replace("from '@mediapipe/tasks-vision'","from './vision_bundle.mjs'")
 for dep in names:s=s.replace("'./"+dep+"'","'./"+dep+".js'")
 modules[n]=s
manifest=json.loads((ROOT/'audit-results/skin-capabilities-20261008/scin/fullface-manifest.json').read_text())
files=[ROOT/'audit-fixtures/high-detail-native-crop.png',ROOT/'audit-fixtures/digital-detail-native-crop.png',*sorted((ROOT/'audit-results/followup-closure-20261010/sellers-frames').glob('*.png'))[::20]]
files += [ROOT/r['image_path'] for r in manifest][:80]
if os.environ.get('ATTUNE_NATURAL_EXTRA')=='1':
 OUT=ROOT/'audit-results/all-health-20261010/natural-extra-measured';OUT.mkdir(parents=True,exist_ok=True)
 files=[ROOT/r['path'] for r in json.loads((ROOT/'audit-results/all-health-20261010/natural-extra/rights.json').read_text()) if 'path' in r]
if os.environ.get('ATTUNE_NATURAL_EXTRA')=='confounders':
 OUT=ROOT/'audit-results/all-health-20261010/natural-confounders-measured';OUT.mkdir(parents=True,exist_ok=True)
 files=[ROOT/r['path'] for r in json.loads((ROOT/'audit-results/all-health-20261010/natural-confounders/rights.json').read_text()) if 'path' in r]
if os.environ.get('ATTUNE_NATURAL_MANIFEST'):
 manifest=(ROOT/os.environ['ATTUNE_NATURAL_MANIFEST']).resolve()
 OUT=(ROOT/os.environ['ATTUNE_NATURAL_OUTPUT']).resolve()
 assert manifest.is_relative_to(ROOT/'audit-results') and OUT.is_relative_to(ROOT/'audit-results')
 OUT.mkdir(parents=True,exist_ok=True)
 files=[ROOT/r['path'] for r in json.loads(manifest.read_text()) if 'path' in r]
rows=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chrome',headless=True);p=b.new_page()
 def route(r):
  name=r.request.url.rsplit('/',1)[-1]
  if name=='index':r.fulfill(body='<html><canvas></canvas></html>',content_type='text/html')
  elif name in [n+'.js' for n in names]:r.fulfill(body=modules[name[:-3]],content_type='text/javascript')
  elif name=='face.task':r.fulfill(path=str(ROOT/'audit-results/skin-capabilities-20261008/scin/face_landmarker.task'),content_type='application/octet-stream')
  elif name=='vision_bundle.mjs':r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision'/name),content_type='text/javascript')
  elif name.startswith('vision_wasm'):r.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/wasm'/name),content_type='application/wasm' if name.endswith('.wasm') else 'text/javascript')
  else:r.continue_()
 p.route('**/audit/natural/**',route);p.goto('http://127.0.0.1:3000/audit/natural/index')
 p.evaluate("""async()=>{const V=await import('./vision_bundle.mjs');window.model=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('/audit/natural/wasm'),{baseOptions:{modelAssetPath:'/audit/natural/face.task'},runningMode:'IMAGE',numFaces:2,outputFacialTransformationMatrixes:true});window.S=(await import('./skinAnalyzer.js')).SkinAnalyzer;S.landmarkerInstance=model;window.snapshot=(await import('./skinSnapshot.js')).snapshotRawSkinFrame;}""")
 for index,file in enumerate(files):
  if not file.exists():continue
  data='data:image/'+('png' if file.suffix.lower()=='.png' else 'jpeg')+';base64,'+base64.b64encode(file.read_bytes()).decode()
  row=dict(index=index,source=str(file.relative_to(ROOT)),sourceSHA256=hashlib.sha256(file.read_bytes()).hexdigest(),natural=True,physicalUserAcceptance=False)
  try:
   payload=p.evaluate("""async(data)=>{const im=new Image();im.src=data;await im.decode();const c=document.querySelector('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(im,0,0);const a=S.assessAlignment(ctx,c.width,c.height),q=S.checkQuality(ctx,c.width,c.height,a.faceDetected,a.box);if(!a.landmarks||a.faceCount!==1)return {failure:'NO_SINGLE_FACE',quality:q};const s=await snapshot(c,a,'FRONT');return {processingConsent:true,photo:s.dataUrl,photoId:s.photoId,pose:'FRONT',meshes:s.meshes,exclusions:s.exclusions,landmarks:a.landmarks,qualityValid:q.isValid,conditions:{yaw:a.yaw,pitch:a.pitch,roll:a.roll,scaleRatio:a.scaleRatio,avgLuminance:q.avgLuminance,blurScore:q.blurScore},quality:q};}""",data)
   if 'failure' in payload:row.update(payload)
   else:
    # snapshotRawSkinFrame preserves the photo; the production adapter hashes
    # its actual RGBA pixels before the request, using this identical digest.
    import io
    decoded=Image.open(io.BytesIO(base64.b64decode(payload['photo'].split(',')[1]))).convert('RGBA')
    payload['photoId']=hashlib.sha256(decoded.tobytes()).hexdigest()
    response=p.request.post('http://127.0.0.1:8000/api/local-health/skin',data=payload,timeout=90000);assert response.ok,(response.status,response.text()[:1000])
    result=response.json();row.update(quality=payload['quality'],conditions=payload['conditions'],photoId=result['photoId'],measurements=result['measurements'])
    (OUT/f'{index}-payload-private.json').write_text(json.dumps(payload),'utf8');(OUT/f'{index}-result-private.json').write_text(json.dumps(result),'utf8')
  except Exception as error:row['failure']=str(error)[:800]
  rows.append(row);(OUT/'measurements-private.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps(dict(index=index,face='measurements' in row,failure=row.get('failure'))),flush=True)
 b.close()
usable=[r for r in rows if 'measurements' in r];tiles=[]
for r in usable:
 im=Image.open(ROOT/r['source']).convert('RGB');im.thumbnail((240,230));tile=Image.new('RGB',(260,280),(20,24,33));tile.paste(im,((260-im.width)//2,0));d=ImageDraw.Draw(tile);d.text((8,235),str(r['index'])+' natural source',(235,240,255));d.text((8,250),'quality '+str(r['quality']['isValid']),(235,240,255));tiles.append(tile)
for batch in range(0,len(tiles),12):
 group=tiles[batch:batch+12];montage=Image.new('RGB',(1040,280*((len(group)+3)//4)),(20,24,33))
 for i,tile in enumerate(group):montage.paste(tile,((i%4)*260,(i//4)*280))
 montage.save(OUT/f'natural-review-{batch//12}.png')
print(json.dumps(dict(total=len(rows),actualFaceSources=len(usable),qualityValid=sum(r['quality']['isValid'] for r in usable),scope='current source/model/backend; independent visual labels remain separate')))
