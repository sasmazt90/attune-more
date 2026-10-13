"""Computed before/after receipts and normal-product preservation, not admission."""
import base64,hashlib,json,sys,time,subprocess,urllib.request,re
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';PREV=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
cv2.setNumThreads(1)
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def active(result):
    support=np.zeros((result['sourceHeight'],result['sourceWidth']),bool)
    for layer in result['maps'].values():
        rgba=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED);ys,xs=np.where(rgba[:,:,3]>0);support[ys+int(layer['y']),xs+int(layer['x'])]=True
    return support
def summarize(receipt):
    summary=[]
    for factor in [1.,.5]:
        for domain in ['all','natural','processed']:
            rows=[r for r in receipt['rows'] if r['factor']==factor and (domain=='all' or (r['kind']=='raw')==(domain=='natural'))];objects=[o for r in rows for o in r['objects'] if o['label']=='visible-material']
            summary.append(dict(factor=factor,domain=domain,objects=len(objects),hits=sum(o['fields']['encoder']['objectHit'] for o in objects),negativeSourcePixels=sum(r['negative']['encoder']['activeSourcePixels'] for r in rows),proposalHits=sum(o['fields']['proposal']['objectHit'] for o in objects)))
    return summary
baseline=read(PREV/'material-encoder-scale-corrected.json');trial=read(PREV/'material-encoder-balanced-comparison.json');protocol=read(OUT/'balanced-trial-protocol.json')
assert sha(PREV/'encoder-material-head.json')==protocol['originalHeadSHA256'] and trial['trainRows']==63 and trial['trainGroups']==15
product=[]
for source in ['9bab7ab2','24031977']:
    old=read(OUT/(source+'-native-result.json'));new=read(OUT/(source+'-balanced-native-result.json'));oldfield=active(old);newfield=active(new);targets=[]
    polygons=[[[212,326],[281,326],[281,350],[212,350]]] if source=='9bab7ab2' else [t['polygon'] for t in read(OUT/'source-location-correction.json')['targets']]
    for poly in polygons:
        mask=np.zeros(oldfield.shape,np.uint8);cv2.fillPoly(mask,[np.asarray(poly,np.int32)],1);targets.append(dict(polygon=poly,beforeActivePixels=int((oldfield&(mask>0)).sum()),afterActivePixels=int((newfield&(mask>0)).sum()),scope='reviewed eyewear negative only' if source=='9bab7ab2' else 'partial visible material location; not full-pixel mask'))
    product.append(dict(source=source,targets=targets,regions=[dict(region=k,before=v['value'],after=new['measurements'][k]['value']) for k,v in old['measurements'].items()]))
old_objects={(r['controlIndex'],o['index']):o for r in baseline['rows'] if r['factor']==1 for o in r['objects'] if o['label']=='visible-material'}
trial_objects={(r['controlIndex'],o['index']):o for r in trial['rows'] if r['factor']==1 for o in r['objects'] if o['label']=='visible-material'}
retained=sum(v['fields']['tenPreserved']['objectHit'] and trial_objects[k]['fields']['encoder']['objectHit'] for k,v in old_objects.items())
scope_controls=[dict(control=k[0],object=k[1],baselineEncoderHit=v['fields']['encoder']['objectHit'],trialEncoderHit=trial_objects[k]['fields']['encoder']['objectHit']) for k,v in old_objects.items() if k[0] in [0,9]]
new_stats=summarize(trial);native=next(r for r in new_stats if r['factor']==1 and r['domain']=='all')
admission=dict(accepted=False,reasons=['eyewear remains falsely mapped','both corrected visible cheek material locations still rejected','high-resolution full native encoder exceeds 45 seconds','reviewed native negative support grew from 0 to 30 pixels'],nativeNegativePixels=native['negativeSourcePixels'],originalSixHitsRetained=retained,thresholdSearch=False,secondCNNFit=False)
# A new actual bitmap, current normal router and no hosted consent. Same body
# goes to normal 8000 only for preservation; the research host used 18011.
path=OUT/'new-photo/00312529-payload.json';payload=read(path);expected=A.analyze_skin(payload);start=time.monotonic();request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',json.dumps(payload).encode(),{'Content-Type':'application/json'});actual=json.loads(urllib.request.urlopen(request,timeout=45).read());api_seconds=time.monotonic()-start
same=all(actual[k]==expected[k] for k in ['measurements','maps','contours']);assert same
pins=read(ROOT/'.runtime/skin-proposal-tracking-final-20261013/source-receipt.json');assert all(sha(ROOT/name)==digest for name,digest in pins.items())
unchanged=subprocess.check_output(['git','diff','d190b6c70aff6442366f47a5a4af10077f5ac263','--','services/core-api/appearance_analysis.py','services/core-api/instant_appearance.py','services/core-api/local_health.py','services/core-api/skin_general.py','apps/vehicle-app','packages/shared'],cwd=ROOT)==b'';assert unchanged
with urllib.request.urlopen('http://127.0.0.1:3000/skin',timeout=10) as r:html=r.read().decode()
js_urls=list(dict.fromkeys(re.findall(r'src="(/_next/[^"?]+\.js)',html)));js=[]
for url in js_urls:
    local=ROOT/'apps/vehicle-app/.next'/url.removeprefix('/_next/')
    with urllib.request.urlopen('http://127.0.0.1:3000'+url,timeout=10) as r:download=r.read()
    js.append(dict(url=url,sha256=hashlib.sha256(download).hexdigest(),same=download==local.read_bytes()))
assert js and all(r['same'] for r in js)
contour=read(OUT/'expression-contour-comparison.json');units=read(OUT/'contour-capture-units.json');finite=read(OUT/'finite-source-review.json')
scope_review=dict(authority='engineering source-coordinate optical review; no clinical sag labels',targets=[dict(source='99f82af5',review='marked structure is inside the visible silhouette, near the lateral cheek fold; zero target overlap is a scope mismatch, not validated contour detection failure or success'),dict(source='fc3a6b13',review='marked lateral outline is not verified local outward prominence; only 5 observed target centers, insufficient visible-side support'),dict(source='05619d0a',review='right-side contour observed but no localized excess beyond neighbor uncertainty; covered left side remains unmeasurable')],bandExpanded=False,ageAsTruth=False,neckFoldAsChinTruth=False,neutralPositiveDemonstrated=False)
files=[p for p in OUT.glob('*.json') if p.name!='final-evidence.json']+[PREV/'encoder-material-balanced-head.json',PREV/'material-encoder-balanced-comparison.json']
evidence=dict(baselineSHA='d190b6c70aff6442366f47a5a4af10077f5ac263',BUILD_ID=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),productionChanged=False,
    profile=read(OUT/'profile.json'),onnx=read(OUT/'encoder-parity.json'),firstNewPhoto=read(OUT/'new-photo-request.json'),apiBudget=read(OUT/'api-budget.json'),runtimeLimit='normal frontend remains 45s AbortController; cooperative stop verified only in isolated research host, no native production selector',
    before=summarize(baseline),after=new_stats,trainScope=dict(rows=63,groups=15,newValidationRowsInTrain=0,unknownAsNegative=False),opticalC0C9=scope_controls,product=product,locationCorrection=read(OUT/'source-location-correction.json'),dryAdmission=admission,
    expressionUnits=units,expressionTrial=contour,contourScope=scope_review,finiteReview=dict(inspected=finite['inspected'],usableNeutralContourPositive=finite['usableNeutralContourPositive'],sources=[dict(sha256=r['sha256'],group=r['group'],reason=r['reviewReason']) for r in finite['rows']],remainingNotReviewed=True),
    preservation=dict(normalSourcePathsUnchanged=unchanged,normalAPIExact=same,normalAPISeconds=api_seconds,normalAPIPhotoId=actual['photoId'],pinnedFrontendBuildSources=len(pins),servedJavaScript=js,userHistoryRewritten=False,AGTouched=False,normalDry='v3',normalChin='v9',normalCheek='v7',newBuild=False),
    artifacts=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in files])
(OUT/'final-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),'utf8');(ROOT/'docs/material-runtime-evidence-20261013.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps(dict(before=evidence['before'],after=evidence['after'],product=product,admission=admission,normalAPISeconds=api_seconds,servedChunks=len(js))),flush=True)
