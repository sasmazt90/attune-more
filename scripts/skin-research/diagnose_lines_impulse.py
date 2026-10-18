"""Source pixels and Gabor responses responsible for the fixed noise regression.

Pinned delivered baseline and a bounded lines-only photometric comparison. Local
licensed development data; source photos and request bodies remain ignored.
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
OUT=ROOT/'audit-results/lines-impulse-20261012'
payload=json.loads((ROOT/'audit-results/bag-label-followup-20261012/5bd42346-v2-payload.json').read_text('utf8'))
def load(name,file):
 spec=importlib.util.spec_from_file_location(name,file);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
mods={name:load('noise_'+name,ROOT/'.runtime/lines-impulse-20261012'/file) for name,file in [('before','baseline.py'),('native-only','native-only.py'),('after','candidate.py')]}
native=mods['before'].decode_photo(payload['photo'])[0];_,impulses=mods['before'].isolated_impulse_sampling(native)
gray8=cv2.cvtColor(native,cv2.COLOR_BGR2GRAY);median=cv2.medianBlur(gray8,3)
known_source=json.loads((ROOT/'audit-results/periorbital-v5-integration-20261012/sources.json').read_text('utf8'))['sources'][-1]
ledger=json.loads((ROOT/'audit-results/skin-expanded-20261011/scope-v4-mask-data.json').read_text('utf8'))['rows']
scope=[v for v in ledger if v.get('sha256')==known_source['sha256'] and v.get('target')=='lines']
known=audit.known_roi({'scopeLedgerRows':scope},native.shape,['acne','oil','dry','redness','tone','lines','dark','bags'])
rows=[];panels=[]
for name,mod in mods.items():
 responses=[];field=[];original=mod.gabor;map_fn=mod.map_result
 def gabor(gray,frequency,theta):
  real,imaginary=original(gray,frequency=frequency,theta=theta)
  responses.append((frequency,theta,np.hypot(real,imaginary)));return real,imaginary
 def map_capture(values,mask,region,criterion,*args,**kw):
  if region=='periorbital' and criterion=='lines':field.append((values.copy(),mask.copy(),args,kw))
  return map_fn(values,mask,region,criterion,*args,**kw)
 mod.gabor=gabor;mod.map_result=map_capture
 try:r=mod.analyze_skin(payload)
 finally:mod.gabor=original;mod.map_result=map_fn
 vals,mask,args,kw=field[0];scale=args[3];origin=args[6] if len(args)>6 else kw.get('origin',(0,0))
 radial=[v for i,v in enumerate(responses) if i%6<3];orthogonal=[v for i,v in enumerate(responses) if i%6>=3]
 rad=np.stack([v[2] for v in radial]);ortho=np.stack([v[2] for v in orthogonal]);rmax=rad.max(axis=0);omax=ortho.max(axis=0)
 ratio=rmax/np.maximum(omax,.005);gate=np.clip((ratio-1.22)/.35,0,1)
 active=(np.rint(np.clip(vals,0,1)*mask*100)>0)
 pixels=[];iy,ix=np.where(impulses);noise_xy=np.column_stack([ix,iy])
 for y,x in zip(*np.where(active)):
  sx,sy=np.rint(np.asarray([x,y])/scale+origin).astype(int)
  index=int(rad[:,y,x].argmax());frequency,theta,_=radial[index]
  nearest=int(np.argmin(np.linalg.norm(noise_xy-[sx,sy],axis=1)));nx,ny=noise_xy[nearest];distance=float(np.linalg.norm([nx-sx,ny-sy]))
  pixels.append(dict(analysisXY=[int(x),int(y)],sourceXY=[int(sx),int(sy)],insideReviewedNegative=bool(known[sy,sx]),radialMagnitude=float(rmax[y,x]),orthogonalMagnitude=float(omax[y,x]),directionRatio=float(ratio[y,x]),directionGate=float(gate[y,x]),strongestFrequency=float(frequency),strongestTheta=float(theta),acceptedField=float(vals[y,x]),nearestImpulseXY=[int(nx),int(ny)],distanceToImpulseSourcePixels=distance,impulseGray=int(gray8[ny,nx]),impulseMedian=int(median[ny,nx])))
 map_active=audit.project_map_alpha(r['maps']['periorbital:lines'],native.shape)>0
 row=dict(stage=name,value=next(v for v in r['measurements']['periorbital'] if v['id']=='lines')['value'],activeGridPixels=int(active.sum()),activeSourcePixels=int(map_active.sum()),activeKnownNegativeSourcePixels=int((map_active&known).sum()),rawAcceptedGridPixels=int(((vals>0)&mask).sum()),pixels=pixels)
 rows.append(row)
 for title,image_mask,color in [(name+' active source map',map_active,(0,255,255)),(name+' radial Gabor / known area',known,(160,60,0))]:
  im=native.copy();im[image_mask]=(im[image_mask]*.4+np.asarray(color)*.6).astype('uint8');im[impulses]=(255,0,255)
  if 'Gabor' in title:
   for v in pixels:cv2.circle(im,tuple(v['sourceXY']),1,(0,255,255),-1)
  crop=im[120:280,230:500];crop=cv2.resize(crop,(810,480));crop=cv2.copyMakeBorder(crop,35,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(crop,title,(8,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1);panels.append(crop)
cv2.imwrite(str(OUT/'5bd42346-source-gabor-responses.png'),np.concatenate([np.concatenate(panels[i:i+2],axis=1) for i in range(0,len(panels),2)],axis=0))
receipt=dict(sourceSHA256=known_source['sha256'],transformedNoiseRegressionOnly=True,nativeImpulsePixels=int(impulses.sum()),inputSHA256=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),stages=rows,filter='Existing native 3x3 median residual >0.35, connected components <=2 pixels; Gabor photometric input only. Support/masks/relative brightness use original image.')
(OUT/'noise-filter-response.json').write_text(json.dumps(receipt,indent=2),'utf8')
print(json.dumps([{k:v for k,v in row.items() if k!='pixels'} for row in rows]))
