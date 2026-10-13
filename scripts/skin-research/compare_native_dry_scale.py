"""Unchanged partial labels; native/half/source-span-320 optical diagnostics."""
import argparse,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-dry-scale-20261013';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
from native_flake_support import proposal_tile,native_field,PARAMETERS,VERSION
from component_flake_gate import masks
from trial_region_flake_proposal import region_proposal,measure
cv2.setNumThreads(1)
label_file=ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json';labels=json.loads(label_file.read_text('utf8'))
parser=argparse.ArgumentParser();parser.add_argument('--variant',default='grow-v1');args=parser.parse_args()
protocol=OUT/(args.variant+'-parameters.json')
assert not protocol.exists(),'Freeze one multiscale configuration before comparison'
protocol.write_text(json.dumps(dict(version=VERSION,parameters=PARAMETERS,labelsSHA256=hashlib.sha256(label_file.read_bytes()).hexdigest(),classifierFit=False),indent=2),'utf8')
rows=[]
for row in labels['controls']:
 source=cv2.imread(row['sourcePath']);assert hashlib.sha256(Path(row['sourcePath']).read_bytes()).hexdigest()==row['sourceSHA256']
 x,y,w,h=row['roi'];reference_span=min(source.shape[:2]);basis='image-short-edge optical reference; no full-face geometry'
 probes=list((ROOT/'audit-results').glob('*20261013/'+row['sourceSHA256'][:8]+'-probe.json'))
 for path in probes:
  snapshot=json.loads(path.read_text('utf8')).get('snapshot')
  if snapshot and snapshot.get('landmarks'):
   reference_span=abs(snapshot['landmarks'][454]['x']-snapshot['landmarks'][234]['x'])*source.shape[1];basis='cached actual browser face span';break
 base_metric=reference_span/640;pad=max(64,int(np.ceil(40*base_metric)))
 a=max(0,x-pad);b=max(0,y-pad);c=min(source.shape[1],x+w+pad);d=min(source.shape[0],y+h+pad)
 source_crop=source[b:d,a:c];known,objects=masks(source.shape[:2],row);scales=[]
 factors=list(dict.fromkeys([1.,.5,min(1.,320/reference_span)]))
 for factor in factors:
  image=source_crop if factor==1 else cv2.resize(source_crop,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA)
  field,stages,details=proposal_tile(image,base_metric*factor,True,pixel_density=factor);old,_=region_proposal(image)
  fields={'previousSingleMSER':old['poreSeparated'],'multiscaleNative':field,**{'stage:'+k:v for k,v in stages.items()}}
  records=[]
  for obj in objects:
   m=obj['mask'][b:d,a:c]>0
   if factor!=1:m=cv2.resize(m.astype(np.uint8),(image.shape[1],image.shape[0]),interpolation=cv2.INTER_NEAREST)>0
   records.append(dict(index=obj['index'],label=obj['label'],sourcePolygon=row['objects'][obj['index']]['polygon'],fields={k:measure(v,m,factor) for k,v in fields.items()}))
  negative=known['reviewed-non-flake'][b:d,a:c]>0
  if factor!=1:negative=cv2.resize(negative.astype(np.uint8),(image.shape[1],image.shape[0]),interpolation=cv2.INTER_NEAREST)>0
  scales.append(dict(factor=factor,coordinateMetric=base_metric*factor,objects=records,reviewedNegative={k:measure(v,negative,factor) for k,v in fields.items()},candidateComponents=len(details)))
  if factor==1:
   tiles=[]
   for name in ['previousSingleMSER','multiscaleNative','stage:pore-separated']:
    dx=x-a;dy=y-b;tile=source_crop[dy:dy+h,dx:dx+w].copy();active=fields[name][dy:dy+h,dx:dx+w]>.04;tile[active]=(.4*tile[active]+.6*np.array([0,0,255])).astype(np.uint8);tile=cv2.resize(tile,(320,320));cv2.putText(tile,name,(3,18),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,0),1);tiles.append(tile)
   cv2.imwrite(str(OUT/f'{args.variant}-C{row["controlIndex"]:02d}-native-multiscale.png'),np.hstack(tiles))
 rows.append(dict(controlIndex=row['controlIndex'],sourceSHA256=row['sourceSHA256'],group=row['group'],split=row['split'],kind=row['kind'],sourceShape=[source.shape[1],source.shape[0]],referenceSpan=reference_span,metricBasis=basis,cropOrigin=[a,b],scales=scales))
summary=[]
for split in ['train','validation']:
 for kind in ['pul','raw','old']:
  relevant=[r for r in rows if r['split']==split and r['kind']==kind]
  if not relevant:continue
  for scale_index in [0,1]:
   groups=[r['scales'][scale_index] for r in relevant];obj=[o for g in groups for o in g['objects'] if o['label']=='visible-material']
   summary.append(dict(split=split,kind=kind,factor=groups[0]['factor'],objects=len(obj),oldHits=sum(o['fields']['previousSingleMSER']['objectHit'] for o in obj),newHits=sum(o['fields']['multiscaleNative']['objectHit'] for o in obj),oldNegativePixels=sum(g['reviewedNegative']['previousSingleMSER']['activeSourcePixels'] for g in groups),newNegativePixels=sum(g['reviewedNegative']['multiscaleNative']['activeSourcePixels'] for g in groups)))
(OUT/(args.variant+'-comparison.json')).write_text(json.dumps(dict(rows=rows,summary=summary,labelsSHA256=hashlib.sha256(label_file.read_bytes()).hexdigest(),independentFinalTest=False,classifierFitted=False,normalProductEnabled=False),indent=2),'utf8')
print(json.dumps(summary))
