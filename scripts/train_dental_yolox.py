"""Real official YOLOX-s training, group/duplicate splits, safe NPZ + ONNX.

No pretrained weights. Validation chooses threshold/checkpoint. The held-out
test is evaluated once after freezing both. No unlabeled healthy negatives.
Source/public-dataset artifacts stay in ignored audit-results, never Git.
"""
import argparse,base64,hashlib,json,random,re,sys,time
from pathlib import Path
from collections import defaultdict
import cv2,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit-results/combined-health-20261008/dental-training'
DATA=ROOT/'audit-results/combined-health-20261008/dental'
REV='6ddff4824372906469a7fae2dc3206c7aa4bbaee'
SRC=ROOT/f'audit-results/combined-health-20261008/yolox/extracted/YOLOX-{REV}'
sys.path.insert(0,str(SRC))
from yolox.models import YOLOX,YOLOPAFPN,YOLOXHead
from yolox.utils import postprocess


class Groups:
 def __init__(self,n):self.parent=list(range(n))
 def root(self,n):
  while n!=self.parent[n]:self.parent[n]=self.parent[self.parent[n]];n=self.parent[n]
  return n
 def join(self,a,b):
  a,b=self.root(a),self.root(b)
  if a!=b:self.parent[b]=a


def partition_rows(rows):
 # Retain all shared source case identifiers, regardless of separator/view.
 # A timestamp-only capture family is not a verified patient identifier.
 groups=Groups(len(rows));stems={};buckets=defaultdict(list)
 for i,item in enumerate(rows):
  name=Path(item['path']).stem
  case=re.match(r'anonymous_(\d+)[_-](\d+)[_-](\d+)[_-]\d+',name)
  capture=re.match(r'anonymous[-_](\d{13})(?:_|$)',name)
  stem='case:'+':'.join(case.groups()) if case else ('capture:'+capture.group(1) if capture else None)
  item['caseStem']=stem
  if stem:
   if stem in stems:groups.join(i,stems[stem])
   else:stems[stem]=i
  possible=set()
  for band in range(5):possible.update(buckets[(band,(item['phash']>>(band*13))&8191)])
  for j in possible:
   if (item['phash']^rows[j]['phash']).bit_count()<=4:groups.join(i,j)
  for band in range(5):buckets[(band,(item['phash']>>(band*13))&8191)].append(i)
 components=defaultdict(list)
 for i in range(len(rows)):components[groups.root(i)].append(i)
 partitions={'train':[],'validation':[],'test':[]}
 for indices in components.values():
  signature=min(rows[i]['sha256'] for i in indices)
  u=int(hashlib.sha256(('dental-split-v2:'+signature).encode()).hexdigest()[:8],16)/2**32
  split='train' if u<.70 else 'validation' if u<.85 else 'test'
  for i in indices:rows[i]['group']=signature;rows[i]['split']=split;partitions[split].append(rows[i])
 assert len({r['sha256'] for r in rows})==len(rows)
 for stem in stems:
  assert len({r['split'] for r in rows if r['caseStem']==stem})==1
 return partitions,components


def inventory():
 # Index all formats' image directories, but read COCO annotations only.
 images=defaultdict(list)
 for path in DATA.rglob('*'):
  if path.suffix.lower() in ('.jpg','.jpeg','.png') and '.part' not in str(path):images[path.name.lower()].append(path)
 records={};class_names=None;annotation_files=[];skipped_empty=0;invalid_images={}
 annotation_sources=list(DATA.glob('**/MS_coco/*.json'))+list(DATA.glob('**/coco/*.json'))
 covered=set()
 for file in annotation_sources:
  try:value=json.loads(file.read_text('utf8'))
  except (ValueError,UnicodeError):continue
  if not isinstance(value,dict) or not all(k in value for k in ('images','annotations','categories')):continue
  categories=sorted(value['categories'],key=lambda c:c['id']);names=sorted(c['name'] for c in categories)
  if class_names is None:class_names=names
  if names!=class_names:raise ValueError('INCONSISTENT_CATEGORY_MEANING')
  class_ids={c['id']:class_names.index(c['name']) for c in categories};anns=defaultdict(list)
  for a in value['annotations']:anns[a['image_id']].append(a)
  annotation_files.append({'path':str(file.relative_to(DATA)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'categories':categories})
  for meta in value['images']:
   covered.add(Path(meta['file_name']).stem)
   candidates=images[Path(meta['file_name']).name.lower()]
   if not candidates:raise ValueError('ANNOTATED_IMAGE_MISSING')
   candidates.sort(key=lambda p:len(str(p)))
   path=candidates[0];raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
   if not anns[meta['id']]:skipped_empty+=1;continue
   im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
   if im is None:raise ValueError('INVALID_DATA_IMAGE')
   h,w=im.shape[:2]
   if (w,h)!=(meta['width'],meta['height']):raise ValueError('COCO_DIMENSION_MISMATCH')
   boxes=[];invalid=False
   for a in anns[meta['id']]:
    x,y,bw,bh=map(float,a['bbox'])
    if not np.isfinite([x,y,bw,bh]).all() or bw<=0 or bh<=0 or x<0 or y<0 or x+bw>w or y+bh>h:
     invalid=True;break
    boxes.append([class_ids[a['category_id']],x,y,bw,bh])
   if invalid:
    invalid_images[digest]={'reason':'INVALID_SOURCE_COCO_COORDINATE','width':w,'height':h,'annotationFile':str(file.relative_to(DATA))};records.pop(digest,None);continue
   if digest in invalid_images:continue
   if digest in records:
    existing=records[digest];existing['aliases'].append(str(path.relative_to(DATA)))
    # Repackaged labels must agree geometrically; never silently change truth.
    old=np.array(sorted(existing['boxes']));new=np.array(sorted(boxes))
    if old.shape!=new.shape or not np.allclose(old,new,atol=1.):raise ValueError('DUPLICATE_ANNOTATION_DISAGREEMENT')
    continue
   gray=cv2.resize(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32)
   dct=cv2.dct(gray)[:8,:8];bits=(dct>np.median(dct.ravel()[1:])).ravel();phash=sum(int(v)<<i for i,v in enumerate(bits))
   # File names may expose an anonymous case stem; timestamp-only names do not
   # establish a person ID. Report this uncertainty, not patient independence.
   case_match=re.match(r'(anonymous_\d+-\d+-\d+-\d+)',path.stem);stem=case_match.group(1) if case_match else None
   records[digest]=dict(path=str(path),sha256=digest,width=w,height=h,boxes=boxes,phash=phash,caseStem=stem,aliases=[str(path.relative_to(DATA))])
  print('annotation inventory',file.name,'unique labelled images',len(records),flush=True)
 # The original LabelMe release has 18 photos absent from the COCO package.
 # Read only these source rectangles. Empty labels are not healthy negatives.
 for file in DATA.glob('Dataset/Dataset/Annotations/Labelme/**/*.json'):
  if file.stem in covered:continue
  value=json.loads(file.read_text('utf8'));boxes=[]
  if not value['shapes']:skipped_empty+=1;continue
  candidates=images[Path(value['imagePath']).name.lower()] or images[(file.stem+'.jpg').lower()]
  if candidates:path=sorted(candidates,key=lambda p:len(str(p)))[0]
  else:
   # Original LabelMe embeds its source photo; retain those exact bytes.
   raw=base64.b64decode(value['imageData'],validate=True);path=OUT/'original-labelme-photos'/(file.stem+'.jpg');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
  raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();im=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR);h,w=im.shape[:2]
  valid=(w,h)==(value['imageWidth'],value['imageHeight'])
  for shape in value['shapes']:
   if shape['shape_type']!='rectangle' or shape['label'] not in class_names:raise ValueError('UNSUPPORTED_SOURCE_LABELME_MEANING')
   pts=np.asarray(shape['points'],dtype=float);x,y=pts.min(axis=0);x1,y1=pts.max(axis=0)
   valid=valid and np.isfinite(pts).all() and 0<=x<x1<=w and 0<=y<y1<=h
   boxes.append([class_names.index(shape['label']),float(x),float(y),float(x1-x),float(y1-y)])
  if not valid:invalid_images[digest]={'reason':'INVALID_SOURCE_LABELME_COORDINATE_OR_DIMENSION'};continue
  gray=cv2.resize(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32);dct=cv2.dct(gray)[:8,:8];bits=(dct>np.median(dct.ravel()[1:])).ravel();phash=sum(int(v)<<i for i,v in enumerate(bits))
  records[digest]=dict(path=str(path),sha256=digest,width=w,height=h,boxes=boxes,phash=phash,caseStem=None,aliases=[str(file.relative_to(DATA))])
  annotation_files.append({'path':str(file.relative_to(DATA)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'categories':class_names,'format':'original LabelMe rectangle'})
 rows=list(records.values());partitions,components=partition_rows(rows)
 for split in partitions:
  if not partitions[split]:raise ValueError('EMPTY_GROUP_SPLIT')
 manifest=dict(classes=class_names,classMeaning='raw dataset D/d dental-decay codes; subtype mapping not assumed; category IDs mapped by raw name in each file',annotationFiles=annotation_files,uniqueLabeledImages=len(rows),groups=len(components),patientIndependent=False,groupLimitation='case identifiers with both separators + shared capture timestamp families + exact/perceptual duplicate groups; patient identity is not verified',excludedEmptyAnnotationOccurrences=skipped_empty,excludedInvalidSourceImages=invalid_images,partitions={k:len(v) for k,v in partitions.items()},rows=rows)
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'dataset-split.json').write_text(json.dumps(manifest,indent=2),'utf8')
 # Human-reviewable exact COCO boxes on public source photos, no new labels.
 for i,item in enumerate(sorted(rows,key=lambda r:r['sha256'])[:12]):
  im=cv2.imread(item['path'])
  for cls,x,y,w,h in item['boxes']:cv2.rectangle(im,(int(x),int(y)),(int(x+w),int(y+h)),(255,255,0),2)
  cv2.imwrite(str(OUT/f'coordinate-check-{i}.jpg'),im)
 return partitions,class_names,manifest


def image_tensor(item,size):
 im=cv2.imread(item['path']);ratio=min(size/im.shape[0],size/im.shape[1]);resized=cv2.resize(im,(int(im.shape[1]*ratio),int(im.shape[0]*ratio)))
 canvas=np.full((size,size,3),114,np.uint8);canvas[:resized.shape[0],:resized.shape[1]]=resized
 return torch.from_numpy(canvas.transpose(2,0,1).copy()).float(),ratio


def batch(items,size):
 tensors=[];labels=torch.zeros((len(items),max(1,max(len(i['boxes']) for i in items)),5))
 for n,item in enumerate(items):
  tensor,ratio=image_tensor(item,size);tensors.append(tensor)
  for j,(cls,x,y,w,h) in enumerate(item['boxes']):labels[n,j]=torch.tensor([cls,(x+w/2)*ratio,(y+h/2)*ratio,w*ratio,h*ratio])
 return torch.stack(tensors),labels


def predict(model,items,size,nclasses):
 model.eval();predictions=[]
 with torch.no_grad():
  for i,item in enumerate(items):
   x,ratio=image_tensor(item,size);output=model(x[None]);detection=postprocess(output,nclasses,.001,.45,class_agnostic=False)[0]
   predictions.append([] if detection is None else (detection.cpu().numpy()*np.array([1/ratio]*4+[1,1,1])).tolist())
   if i and i%100==0:print('evaluation images',i,flush=True)
 return predictions


def iou(a,b):
 x0,y0=max(a[0],b[0]),max(a[1],b[1]);x1,y1=min(a[2],b[2]),min(a[3],b[3]);inter=max(0,x1-x0)*max(0,y1-y0)
 return inter/max((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter,1e-8)


def metrics(items,predictions,threshold,nclasses,overlap=.5):
 counts=[];aps=[]
 for cls in range(nclasses):
  truth={i:[[x,y,x+w,y+h] for c,x,y,w,h in item['boxes'] if c==cls] for i,item in enumerate(items)};total=sum(len(v) for v in truth.values())
  ranked=sorted([(float(p[4]*p[5]),i,p[:4]) for i,ps in enumerate(predictions) for p in ps if int(p[6])==cls],reverse=True,key=lambda v:v[0]);matched=defaultdict(set);tp=[];fp=[]
  for score,i,box in ranked:
   options=[(iou(box,t),j) for j,t in enumerate(truth[i]) if j not in matched[i]];best=max(options,default=(0,-1))
   positive=best[0]>=overlap
   if positive:matched[i].add(best[1])
   tp.append(int(positive));fp.append(int(not positive))
  ct=np.cumsum(tp);cf=np.cumsum(fp);recall=ct/max(total,1);precision=ct/np.maximum(ct+cf,1)
  ap=float(np.mean([precision[recall>=r].max(initial=0) for r in np.linspace(0,1,101)])) if total else None
  selected=[j for j,v in enumerate(ranked) if v[0]>=threshold];t=sum(tp[j] for j in selected);f=sum(fp[j] for j in selected);p=t/max(t+f,1);r=t/max(total,1)
  counts.append(dict(classIndex=cls,truePositive=t,falsePositive=f,falseNegative=total-t,precision=p,recall=r,F1=2*p*r/max(p+r,1e-8),AP=ap));aps.append(ap)
 return dict(classes=counts,macroF1=float(np.mean([c['F1'] for c in counts])),mAP=float(np.mean([a for a in aps if a is not None])),threshold=threshold,IoU=overlap)


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--epochs',type=int,default=20);parser.add_argument('--batch',type=int,default=8);parser.add_argument('--size',type=int,default=320);parser.add_argument('--inventory-only',action='store_true');parser.add_argument('--verified-inventory',action='store_true');parser.add_argument('--regroup-inventory',action='store_true');parser.add_argument('--threads',type=int,default=2);args=parser.parse_args()
 random.seed(8102026);np.random.seed(8102026);torch.manual_seed(8102026);torch.set_num_threads(args.threads);cv2.setNumThreads(1)
 manifest=json.loads((ROOT/'audit-results/combined-health-20261008/source-manifest.json').read_text('utf8'))
 assert manifest['yoloxRevision']==REV and manifest['datasetLicense']=='CC BY 4.0' and not manifest['pretrainedWeightsDownloaded']
 if args.verified_inventory:
  data_manifest=json.loads((OUT/'dataset-split.json').read_text('utf8'));classes=data_manifest['classes'];partitions={s:[r for r in data_manifest['rows'] if r['split']==s] for s in ('train','validation','test')}
  if args.regroup_inventory:
   previous=OUT/'dataset-split-superseded-v1.json'
   if not previous.exists():previous.write_text(json.dumps(data_manifest,indent=2),'utf8')
   partitions,components=partition_rows(data_manifest['rows']);data_manifest.update(groups=len(components),splitVersion='case-capture-v2',partitions={k:len(v) for k,v in partitions.items()},groupLimitation='both separator case IDs, capture families and duplicates; person identity remains unverified')
   (OUT/'dataset-split.json').write_text(json.dumps(data_manifest,indent=2),'utf8')
  for row in data_manifest['rows']:
   if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('VERIFIED_INVENTORY_SOURCE_CHANGED')
 else:partitions,classes,data_manifest=inventory()
 if args.inventory_only:print(json.dumps({k:v for k,v in data_manifest.items() if k not in ('rows','annotationFiles','excludedInvalidSourceImages')}));return
 model=YOLOX(YOLOPAFPN(depth=.33,width=.50),YOLOXHead(len(classes),width=.50))
 model.head.initialize_biases(.01)
 optimizer=torch.optim.SGD(model.parameters(),lr=.01,momentum=.9,weight_decay=.0005,nesterov=True)
 best=-1.;history=[];selected_threshold=.1;started=time.monotonic()
 # Actual full-data training; no imported/unlicensed startup weights.
 for epoch in range(args.epochs):
  model.train();items=list(partitions['train']);random.shuffle(items);losses=[]
  optimizer.param_groups[0]['lr']=.01*(.2+.8*(1+np.cos(np.pi*epoch/args.epochs))/2)*min(1,(epoch+1)/3)
  for offset in range(0,len(items),args.batch):
   batch_items=items[offset:offset+args.batch]
   if len(batch_items)<2:continue
   x,labels=batch(batch_items,args.size);optimizer.zero_grad(set_to_none=True);output=model(x,labels);loss=output['total_loss']
   if not torch.isfinite(loss):raise RuntimeError('NON_FINITE_TRAINING_LOSS')
   loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),10);optimizer.step();losses.append(float(loss.detach()))
   if offset%(args.batch*25)==0:print(json.dumps(dict(epoch=epoch+1,images=offset,trainImages=len(items),loss=losses[-1],elapsedSeconds=time.monotonic()-started)),flush=True)
  # Validation fixed subset is allowed for model selection, never held-out test.
  val=partitions['validation'];predictions=predict(model,val,args.size,len(classes));choices=[metrics(val,predictions,t,len(classes)) for t in (.005,.01,.025,.05,.10,.20,.35,.5)]
  chosen=max(choices,key=lambda m:(m['macroF1'],m['threshold']));score=chosen['macroF1'];history.append(dict(epoch=epoch+1,trainLoss=float(np.mean(losses)),validation=chosen))
  np.savez_compressed(OUT/'latest-weights.npz',**{k:v.detach().cpu().numpy() for k,v in model.state_dict().items()})
  if score>best:
   best=score;selected_threshold=chosen['threshold'];np.savez_compressed(OUT/'best-weights.npz',**{k:v.detach().cpu().numpy() for k,v in model.state_dict().items()})
  (OUT/'training-history.json').write_text(json.dumps(history,indent=2),'utf8');print('validation',json.dumps(history[-1]),flush=True)
 archive=np.load(OUT/'best-weights.npz',allow_pickle=False);model.load_state_dict({k:torch.from_numpy(archive[k]) for k in archive.files});model.eval()
 test=partitions['test'];predictions=predict(model,test,args.size,len(classes));evaluation=metrics(test,predictions,selected_threshold,len(classes));evaluation['mAP50']=evaluation.pop('mAP');evaluation['mAP50_95']=float(np.mean([metrics(test,predictions,selected_threshold,len(classes),overlap)['mAP'] for overlap in np.arange(.5,.96,.05)]));evaluation.update(images=len(test),patientIndependent=False,negatives='unannotated images excluded; no healthy-specificity claim')
 # Group bootstrap confidence intervals on the untouched held-out set.
 rng=np.random.default_rng(8102026);group_indices=defaultdict(list)
 for i,item in enumerate(test):group_indices[item['group']].append(i)
 groups=list(group_indices);boot=[]
 # Match once per image; bootstrap groups by summing their same frozen counts.
 group_counts=[]
 for group in groups:
  total=np.zeros((len(classes),3),dtype=np.int64)
  for i in group_indices[group]:
   m=metrics([test[i]],[predictions[i]],selected_threshold,len(classes))
   total+=np.array([[c['truePositive'],c['falsePositive'],c['falseNegative']] for c in m['classes']])
  group_counts.append(total)
 group_counts=np.asarray(group_counts)
 for _ in range(200):
  counts=group_counts[rng.integers(0,len(groups),len(groups))].sum(axis=0)
  f1=2*counts[:,0]/np.maximum(2*counts[:,0]+counts[:,1]+counts[:,2],1)
  boot.append(float(f1.mean()))
 evaluation['groupBootstrapF1_95CI']=np.quantile(boot,[.025,.975]).tolist()
 destination=ROOT/'services/core-api/models';destination.mkdir(exist_ok=True)
 path=destination/'dental-yolox-s.onnx';example=image_tensor(test[0],args.size)[0][None]
 torch.onnx.export(model,example,str(path),input_names=['images'],output_names=['detections'],opset_version=17,dynamo=False)
 import onnx,onnxruntime as ort
 onnx.checker.check_model(str(path));session=ort.InferenceSession(str(path),providers=['CPUExecutionProvider']);errors=[]
 for item in test[:10]:
  x=image_tensor(item,args.size)[0][None]
  with torch.no_grad():expected=model(x).numpy()
  actual=session.run(None,{'images':x.numpy()})[0];difference=float(np.max(np.abs(actual-expected)));errors.append(difference)
  if not np.allclose(actual,expected,rtol=.002,atol=.005):raise RuntimeError('ONNX_EQUIVALENCE_FAILED')
 result=dict(modelVersion='yolox-s-dental-from-scratch-v1',modelHash=hashlib.sha256(path.read_bytes()).hexdigest(),inputSize=args.size,confidenceThreshold=selected_threshold,classes=classes,codeRevision=REV,codeLicense='Apache-2.0',startupWeights='none; random initialization',weightsLicense='project-created; training data CC-BY-4.0',dataset=manifest,evaluation=evaluation,onnxMaxAbsoluteErrors=errors,epochs=args.epochs,trainingSeconds=time.monotonic()-started,clinicalValidation=False,batchSize=args.batch,torchCPUThreads=args.threads,splitVersion=data_manifest.get('splitVersion','case-capture-v2'))
 (destination/'dental-yolox-s.json').write_text(json.dumps(result,indent=2),'utf8');(OUT/'heldout-predictions.json').write_text(json.dumps(predictions),'utf8');print('DELIVERABLE',json.dumps(result),flush=True)
if __name__=='__main__':main()
