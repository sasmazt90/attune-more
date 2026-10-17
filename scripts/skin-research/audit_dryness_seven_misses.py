"""Read frozen optical records; no photo decoding, encoder/session, fitting or new proposal.
Reproduce only the existing head's arithmetic on its SHA-bound stored features.
"""
import os
for name in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[name]='1'
import ast,builtins,hashlib,json,math,sys,time
from pathlib import Path
from datetime import datetime,timezone
import psutil
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT.parent/'attune-live-test';DATA=SOURCE/'audit-results';OUT=ROOT.parent/'cdc-progress/skin-dryness-closeout-20261017'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(65536),b''):h.update(block)
 return h.hexdigest()
process=psutil.Process();peak=0.
def budget():
 global peak
 peak=max(peak,process.memory_info().rss/2**20)
 if peak>250 or psutil.virtual_memory().available<650*2**20:raise RuntimeError('OFFLINE_AUDIT_MEMORY_RESERVE')
original_import=builtins.__import__;blocked=[]
def guarded_import(name,*args,**kw):
 if name.split('.')[0] in ('torch','torchvision','onnxruntime','transformers','sklearn'):
  blocked.append(name);raise AssertionError('No heavy model/session allowed in offline record audit')
 return original_import(name,*args,**kw)
builtins.__import__=guarded_import
import numpy as np,cv2
from PIL import Image
sys.path.insert(0,str(ROOT/'services/core-api'));import material_component_features as M
cv2.setNumThreads(1);budget();start=time.monotonic()
base=ROOT/'services/core-api/models/dryness-calibrated-v3';config=read(base/'config.json');head=read(base/'head.json')
assets=[]
for key in ['head','encoder','parity']:
 p=base/config[key];assert sha(p)==config[key+'SHA256'];assets.append(dict(kind=key,path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
weights=DATA/'focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors'
assert sha(weights)==config['sourceEncoderSHA256']==M.ENCODER_SHA
assets.append(dict(kind='sourceEncoder',path=str(weights),bytes=weights.stat().st_size,sha256=sha(weights)))
assert config['threshold']==head['threshold']==.5 and head['trainRows']==64
controls=read(DATA/'dry-sag-component-followup-20261013/object-labels.json')['controls']
review=read(DATA/'native-material-contour-20261013/added-components-reviewed.json')['rows'];sources=read(DATA/'native-material-contour-20261013/added-train-source-selection.json')
scale=read(DATA/'native-dry-scale-20261013/independent-v3-comparison.json')['rows'];optical=read(DATA/'native-camera-scope-20261013/single-crop-comparison.json')['rows']
old=read(DATA/'native-material-contour-20261013/material-encoder-balanced-comparison.json');pinned=read(DATA/'dryness-integration-v2-20261014/reviewed-head-replay.json')
assert assets[0]['sha256']==pinned['headSHA256']
records=[];cases=[];case_receipts=[]
def collect(meta,metric,density):
 budget();path=DATA/f'native-camera-scope-20261013/conditioned-case-{len(cases):02d}.npz'
 with np.load(path) as f:
  ids=f['ids'];cids=f['componentIds'];geometry=f['X'][:,-12:].copy()
 _,_,stats,_=cv2.connectedComponentsWithStats((ids>0).astype(np.uint8),8);indices=[]
 for j,cid in enumerate(cids):
  row=dict(componentId=int(cid),rect=stats[cid,:4].astype(int).tolist(),geometry=geometry[j].tolist());indices.append(len(records));records.append(dict(**meta,**row,cropBoxes=M.component_crop_boxes(row,metric,density)))
 cases.append(dict(**meta,path=path,indices=indices,metric=metric,density=density));case_receipts.append(dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size))
for si,source in enumerate(sources):
 picked=[r for r in review if r['sourceIndex']==si and r['label'] is not None]
 if picked:collect(dict(scope='added',sourceSHA256=source['sha256'],factor=1.,sourceIndex=si),picked[0]['coordinateScale'],1.)
for c in controls:
 for factor in [1.,.5]:collect(dict(scope='preserved',sourceSHA256=c['sourceSHA256'],factor=factor,controlIndex=c['controlIndex']),scale[c['controlIndex']]['referenceSpan']/640*factor,factor)
signature=hashlib.sha256(json.dumps([(r['sourceSHA256'],r['factor'],r['rect'],r['cropBoxes']) for r in records],sort_keys=True).encode()).hexdigest()
assert signature==pinned['cachedFeatureRowIdentitySHA256'] and old['cacheFile'].startswith(signature[:16])
cache=DATA/'native-material-contour-20261013'/old['cacheFile']
with np.load(cache) as f:features=f['features'].copy()
assert features.shape==(len(records),2560)
X=np.c_[features,np.array([r['geometry'] for r in records])];probabilities=M.predict(X,head);budget()
def measure(field,mask,factor):
 active=(field>.04)&mask;n,_,stats,_=cv2.connectedComponentsWithStats(active.astype(np.uint8));sizes=stats[1:,4]
 return dict(activeSourcePixels=float(active.sum()/factor**2),reviewedSourcePixels=float(mask.sum()/factor**2),activeOpticalAreaPercent=float(100*active.sum()/max(1,mask.sum())),components=n-1,largestSourceComponent=float(sizes.max()/factor**2) if sizes.size else 0.,objectHit=bool(active.sum()/factor**2>=3 and active.sum()/max(1,mask.sum())>=.1))
all_objects=[];negatives=[];source_receipts={};misses=[]
for case in cases:
 if case['scope']!='preserved':continue
 budget();ci=case['controlIndex'];factor=case['factor'];control=controls[ci];meta=next(r for r in optical if r['control']==ci and r['factor']==factor);origin=meta['origin'];cw,ch=meta['cropShape']
 path=Path(control['sourcePath'])
 if ci not in source_receipts:
  assert sha(path)==control['sourceSHA256']
  with Image.open(path) as image:size=list(image.size)
  # compare_native_dry_scale.py serializes sourceShape as [width,height],
  # despite the NumPy-style field name. Verify the writer's actual schema.
  assert size==scale[ci]['sourceShape'],('Frozen source dimensions drift',ci,size,scale[ci]['sourceShape'])
  source_receipts[ci]=dict(control=ci,sourceSHA256=control['sourceSHA256'],sourcePath=str(path),sourceSize=size,sourceSizeOrder='width,height; verified against original writer',kind=control['kind'],family=control.get('family'),split=control['split'],group=control['group'],rights=control.get('rights'),metricBasis=scale[ci]['metricBasis'],referenceSpan=scale[ci]['referenceSpan'],roi=control['roi'])
 with np.load(case['path']) as f:ids=f['ids'];field=f['field'].copy();cids=f['componentIds']
 assert origin==scale[ci]['cropOrigin'],('Optical source origin drift',ci,factor)
 assert list(field.shape)==[round(ch*factor),round(cw*factor)]
 sw,sh=source_receipts[ci]['sourceSize'];assert 0<=origin[0]<origin[0]+cw<=sw and 0<=origin[1]<origin[1]+ch<=sh
 allowed=np.zeros(int(ids.max())+1,bool);allowed[cids]=probabilities[case['indices']]>=.5;final=field*allowed[ids]
 bycid={records[i]['componentId']:(records[i],float(probabilities[i])) for i in case['indices']}
 negative=np.zeros((ch,cw),np.uint8)
 prior=next(r for r in pinned['rows'] if r['control']==ci and r['factor']==factor)
 for index,obj in enumerate(control['objects']):
  mask=np.zeros((ch,cw),np.uint8);polygon=[[x+control['roi'][0]-origin[0],y+control['roi'][1]-origin[1]] for x,y in obj['polygon']];cv2.fillPoly(mask,[np.array(polygon,np.int32)],1)
  assert all(0<=x<cw and 0<=y<ch for x,y in polygon),('Reviewed polygon cropped',ci,index,factor)
  if obj['label']=='reviewed-non-flake':negative|=mask
  local=mask>0 if factor==1 else cv2.resize(mask,(field.shape[1],field.shape[0]),interpolation=cv2.INTER_NEAREST)>0
  after=measure(final,local,factor);before=measure(field,local,factor);saved=next(o['measure'] for o in prior['objects'] if o['index']==index)
  assert after==saved,('Pinned stored-head result drift',ci,factor,index)
  row=dict(control=ci,index=index,sourceSHA256=control['sourceSHA256'],split=control['split'],label=obj['label'],factor=factor,proposal=before,finalOptical=after)
  all_objects.append(row)
  if factor==1 and obj['label']=='visible-material' and not after['objectHit']:
   components=[]
   for cid in np.unique(ids[local&(field>.04)]):
    rec,p=bycid.get(int(cid),(None,None));pixels=int(((ids==cid)&local&(field>.04)).sum())
    components.append(dict(componentId=int(cid),proposalPixelsInside=pixels,headProbability=p,accepted=None if p is None else p>=.5,described=rec is not None,rectInOpticalCrop=rec['rect'] if rec else None,sourceRect=[rec['rect'][0]/factor+origin[0],rec['rect'][1]/factor+origin[1],rec['rect'][2]/factor,rec['rect'][3]/factor] if rec else None,cropBoxes=rec['cropBoxes'] if rec else None))
   attribution='proposal-below-frozen-object-hit-criterion' if not before['objectHit'] else 'component-description-no-head-support' if any(c['headProbability'] is None for c in components) else 'fixed-head-rejection-or-insufficient-retained-local-support'
   misses.append(dict(**row,source=source_receipts[ci],sourcePolygon=[[x+control['roi'][0],y+control['roi'][1]] for x,y in obj['polygon']],opticalCropOrigin=origin,opticalCropShape=[cw,ch],sampledShape=[field.shape[1],field.shape[0]],cropToSource='source = opticalCropOrigin + sampled/factor; component crops use the original pinned context/padding contract',components=components,attribution=attribution,productScope='optical ROI only; record explicitly has no full-face geometry. Same-source normal capture/mesh/quality admission and anatomical final map are not established here; NOT declared out of scope solely for missing record',finalMask='stored proposal field times fixed-head component acceptance',productRegionAndOverviewMap='not measured by this optical replay; no fabricated ROI/healthy negative'))
 local=negative>0 if factor==1 else cv2.resize(negative,(field.shape[1],field.shape[0]),interpolation=cv2.INTER_NEAREST)>0
 negative_measure=measure(final,local,factor);assert negative_measure==prior['negative'];negatives.append(dict(control=ci,factor=factor,**negative_measure))
summary=[]
for factor in [1.,.5]:
 rows=[r for r in all_objects if r['factor']==factor and r['label']=='visible-material'];negative=[r for r in negatives if r['factor']==factor]
 summary.append(dict(factor=factor,hits=sum(r['finalOptical']['objectHit'] for r in rows),targets=len(rows),reviewedNegativeSourcePixels=sum(r['activeSourcePixels'] for r in negative),reviewedNegativeAreaSourcePixels=sum(r['reviewedSourcePixels'] for r in negative)))
for row in misses:row['halfSource']=next(r for r in all_objects if r['control']==row['control'] and r['index']==row['index'] and r['factor']==.5)
assert len(misses)==7 and [s['hits'] for s in summary]==[14,13] and not blocked
budget();result=dict(createdUTC=datetime.now(timezone.utc).isoformat(),scope='existing frozen optical development records and cached-feature head arithmetic only; NOT a fresh encoder/native camera evaluation',modelAssets=assets,headThreshold=.5,headLoss=head['lossVersion'],recordRowIdentitySHA256=signature,featureFile=dict(path=str(cache),sha256=sha(cache),bytes=cache.stat().st_size,shape=list(features.shape)),caseFiles=case_receipts,sources=list(source_receipts.values()),summary=summary,sevenMisses=misses,allReviewedObjects=all_objects,reviewedNegativeRecords=negatives,allStoredMeasuresMatched=True,unknownOutsideReviewedPolygons=True,newEncoderInferenceCalls=0,heavyModelSessionImports=blocked,headScoreComputation='existing standardized linear/logistic head applied once to pinned stored features; no fit/threshold change',newPhotometricProposalCalls=0,sourcePhotosDecoded=0,resource=dict(pid=process.pid,processStarted=process.create_time(),executable=process.exe(),cwd=process.cwd(),commandSHA256=hashlib.sha256(json.dumps(process.cmdline()).encode()).hexdigest(),peakMeasuredRSSMiB=peak,offlineAuditBudgetMiB=250,minimumSystemReserveMiB=650,heavyModelStartGuardMiB=2500,heavyModelStartAttempted=False,elapsedSeconds=time.monotonic()-start))
OUT.mkdir(exist_ok=True);tmp=OUT/'seven-target-trace.tmp';tmp.write_text(json.dumps(result,indent=2),'utf8');tmp.replace(OUT/'seven-target-trace.json')
print(json.dumps(dict(summary=summary,misses=[dict(control=r['control'],index=r['index'],proposal=r['proposal']['activeSourcePixels'],final=r['finalOptical']['activeSourcePixels'],p=[c['headProbability'] for c in r['components']],attribution=r['attribution']) for r in misses],peakMiB=peak)))
