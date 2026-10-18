"""Audit every released SCIN photo without the previous Haar prefilter.
Separate geometry, quality, case labels and expert image annotation. Geometry
candidates never become localized disease targets or certified healthy controls.
Only existing product MediaPipe assets run, all photographs remain on this device.
"""
import argparse,base64,collections,concurrent.futures,csv,hashlib,json,threading,time
from pathlib import Path
import cv2
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'audit-results/skin-capabilities-20261008/scin'
OUT=ROOT/'audit-results/skin-expanded-20261008/scin'
MODEL_SHA='64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
VERSION='scin-no-haar-geometry-v1'
LOCK=threading.Lock()
JS=r'''async(data)=>{const im=new Image();im.src=data;await im.decode();const t=performance.now(),result=window.model.detect(im),p=result.faceLandmarks[0];
if(result.faceLandmarks.length!==1||!p)return {faces:result.faceLandmarks.length,ms:performance.now()-t,full:false,regions:[]};
const inside=i=>p[i].x>.018&&p[i].x<.982&&p[i].y>.018&&p[i].y<.982;
const outline=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109],box={x:Math.min(...outline.map(i=>p[i].x)),y:Math.min(...outline.map(i=>p[i].y)),right:Math.max(...outline.map(i=>p[i].x)),bottom:Math.max(...outline.map(i=>p[i].y))};
const groups={forehead:[10,67,109,338,297,151],rightCheek:[50,101,205,123,116],leftCheek:[280,330,425,352,345],nose:[1,4,6,98,327],chin:[152,175,199,176,400]};
const regions=Object.entries(groups).filter(([name,ids])=>ids.every(inside)&&Math.max(...ids.map(i=>p[i].x))-Math.min(...ids.map(i=>p[i].x))>.018).map(([name])=>name);
const eyeSpan=Math.abs(p[33].x-p[263].x),noseFraction=(p[1].x-p[33].x)/(p[263].x-p[33].x);
const full=outline.every(inside)&&box.right-box.x>.1&&eyeSpan*im.width>=15;
return {faces:1,ms:performance.now()-t,full,regions,box,noseFraction,poseProxy:Math.abs(noseFraction-.5)>.22?'oblique-candidate':'front-candidate'};}'''

def worker(index,jobs):
 out=OUT/('worker-'+str(index)+'.jsonl');cached={}
 if out.exists():
  for line in out.read_text('utf8').splitlines():
   try:
    row=json.loads(line)
    if row['auditVersion']==VERSION:cached[row['sha256']]=row
   except (ValueError,KeyError):pass
 results=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='chrome',headless=True);page=browser.new_page();page.set_default_timeout(15000)
  def local(route):
   if not route.request.url.startswith('http://127.0.0.1:6933/scin/'):route.abort();return
   name=route.request.url.rsplit('/',1)[-1]
   if name=='index':route.fulfill(body='<html></html>',content_type='text/html')
   elif name=='face.task':route.fulfill(path=str(OLD/'face_landmarker.task'),content_type='application/octet-stream')
   elif name=='vision_bundle.mjs':route.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision'/name),content_type='text/javascript')
   elif name in ['vision_wasm_internal.js','vision_wasm_internal.wasm','vision_wasm_nosimd_internal.js','vision_wasm_nosimd_internal.wasm']:route.fulfill(path=str(ROOT/'node_modules/@mediapipe/tasks-vision/wasm'/name),content_type='application/wasm' if name.endswith('.wasm') else 'text/javascript')
   else:route.abort()
  page.route('**/*',local);page.goto('http://127.0.0.1:6933/scin/index')
  load=page.evaluate("""async()=>{const t=performance.now(),V=await import('./vision_bundle.mjs');window.model=await V.FaceLandmarker.createFromOptions(await V.FilesetResolver.forVisionTasks('http://127.0.0.1:6933/scin/wasm'),{baseOptions:{modelAssetPath:'http://127.0.0.1:6933/scin/face.task',delegate:'CPU'},runningMode:'IMAGE',numFaces:2});return performance.now()-t;}""")
  with out.open('a',encoding='utf8') as stream:
   for n,(old,head) in enumerate(jobs):
    raw=(ROOT/old['image_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==old['sha256']
    if old['sha256'] in cached:results.append(cached[old['sha256']]);continue
    image=cv2.imdecode(__import__('numpy').frombuffer(raw,dtype='uint8'),cv2.IMREAD_COLOR);h,w=image.shape[:2];scale=min(1,640/max(h,w));small=cv2.resize(image,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA) if scale<1 else image
    encoded=cv2.imencode('.png',small)[1].tobytes();data='data:image/png;base64,'+base64.b64encode(encoded).decode()
    try:geometry=page.evaluate(JS,data)
    except Exception as error:geometry={'faces':None,'full':False,'regions':[],'error':type(error).__name__}
    quality={'blur':None,'luminance':None,'engineeringUsable':False}
    if geometry.get('box'):
     b=geometry['box'];x=max(0,int(b['x']*w));y=max(0,int(b['y']*h));right=min(w,int(b['right']*w));bottom=min(h,int(b['bottom']*h));roi=image[y:bottom,x:right]
     if roi.size:
      gray=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY);quality={'blur':float(cv2.Laplacian(gray,cv2.CV_32F).var()),'luminance':float(gray.mean())};quality['engineeringUsable']=quality['blur']>=10 and 35<=quality['luminance']<=220
    row={**old,'auditVersion':VERSION,'selfReportedHeadNeck':head,'previousHaar':old['face_box'] is not None,'previousEligible':old['eligible'],'geometry':geometry,'qualityAudit':quality,'sourceUnchanged':True,'analysisMaxDimension':640,'expertImageAnatomyTarget':None,'regionalClinicalLabel':None,'eligibleForProductTraining':False}
    stream.write(json.dumps(row)+'\n');stream.flush();results.append(row)
    if n%200==0:
     with LOCK:print(json.dumps({'worker':index,'processed':n+1,'workerTotal':len(jobs)}),flush=True)
  browser.close()
 return results,load

def summarize(rows):
 def pool(items):return {'images':len(items),'cases':len({r['case_id'] for r in items}),'positiveProxyImages':sum(r['target']==1 for r in items),'positiveProxyCases':len({r['case_id'] for r in items if r['target']==1}),'negativeProxyImages':sum(r['target']==0 for r in items),'unknownLabelImages':sum(r['target'] is None for r in items),'tones':dict(collections.Counter(r['tone'] for r in items)),'shotTypes':dict(collections.Counter(r['shotType'] for r in items))}
 full=[r for r in rows if r['geometry']['full']];partial=[r for r in rows if r['geometry'].get('faces')==1 and not r['geometry']['full'] and r['geometry']['regions']]
 return {'inventory':pool(rows),'previousHaar':pool([r for r in rows if r['previousHaar']]),'allSingleFaceGeometry':pool([r for r in rows if r['geometry'].get('faces')==1]),'framedWholeFace':pool(full),'partialRegionGeometry':pool(partial),'fullQualityCaseLabelProxy':pool([r for r in full if r['qualityAudit']['engineeringUsable'] and r['target'] is not None]),'partialQualityCaseLabelProxy':pool([r for r in partial if r['qualityAudit']['engineeringUsable'] and r['target'] is not None]),'haarMissedSingleGeometry':pool([r for r in rows if not r['previousHaar'] and r['geometry'].get('faces')==1]),'geometryReasons':dict(collections.Counter('whole-face' if r['geometry']['full'] else 'partial-region' if r in partial else 'single-insufficient-geometry' if r['geometry'].get('faces')==1 else 'no-face' if r['geometry'].get('faces')==0 else 'multiple-or-error' for r in rows)),'poseProxy':dict(collections.Counter(r['geometry'].get('poseProxy','unknown') for r in full+partial)),'clinicalUsableFaceCount':None,'regionalExpertLabels':0,'ordinaryProductAdmission':False}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,choices=[1,2,4],default=2);ap.add_argument('--limit',type=int);args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True);cv2.setNumThreads(1)
 assert hashlib.sha256((OLD/'face_landmarker.task').read_bytes()).hexdigest()==MODEL_SHA
 cases={r['case_id']:r for r in csv.DictReader((OLD/'scin_cases.csv').open(encoding='utf8'))};rows=json.loads((OLD/'manifest.json').read_text('utf8'));jobs=[(r,cases[r['case_id']]['body_parts_head_or_neck']=='YES') for r in rows];jobs.sort(key=lambda v:(v[0]['target']!=1,not v[1],v[0]['sha256']));jobs=jobs[:args.limit] if args.limit else jobs
 start=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:result=list(pool.map(lambda i:worker(i,jobs[i::args.workers]),range(args.workers)))
 audited=[r for part,load in result for r in part];report=summarize(audited);report.update(status='COMPLETE' if len(audited)==len(rows) else 'PARTIAL-INVENTORY',modelSHA256=MODEL_SHA,sdkVersion='1.0.1',auditVersion=VERSION,seconds=time.monotonic()-start,workers=args.workers,loadMs=[load for part,load in result],clinicalTruth='case differential only; no image-specific anatomy/lesion target',geometryIsExpertReview=False)
 (OUT/'manifest.json').write_text(json.dumps(audited,indent=2),'utf8');(OUT/'report.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
