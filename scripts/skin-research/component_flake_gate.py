"""One isolated native component experiment; never a clinical severity model."""
import argparse,hashlib,json,time
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from flake_local_classifier import proposal
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-component-followup-20261013'
cv2.setNumThreads(1)
FEATURES=['logArea','elongation','fill','circularity','solidity','ringContrast','gradientDirectionCoherence','darkAdjacentFraction']
def components(gray):
 raw=proposal(gray);active=raw>.04;n,labels,stats,centroids=cv2.connectedComponentsWithStats(active.astype('uint8'))
 dark=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35;dark=cv2.dilate(dark.astype('uint8'),np.ones((7,7),np.uint8))>0
 g=gray.astype('float32')/255;dx=cv2.Sobel(g,cv2.CV_32F,1,0,3);dy=cv2.Sobel(g,cv2.CV_32F,0,1,3);rows=[]
 for i in range(1,n):
  x,y,w,h,area=stats[i]
  if area<3:continue
  x0=max(0,x-5);y0=max(0,y-5);x1=min(gray.shape[1],x+w+5);y1=min(gray.shape[0],y+h+5)
  mask=labels[y0:y1,x0:x1]==i;all_candidates=active[y0:y1,x0:x1]
  ring=(cv2.dilate(mask.astype('uint8'),np.ones((7,7),np.uint8))>0)&~all_candidates
  if ring.sum()<5:continue
  reference=float(np.median(g[y0:y1,x0:x1][ring]));contrast=float(g[y0:y1,x0:x1][mask].mean()-reference)
  contours,_=cv2.findContours(mask.astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);contour=max(contours,key=cv2.contourArea)
  perimeter=float(cv2.arcLength(contour,True));contour_area=float(cv2.contourArea(contour));hull_area=float(cv2.contourArea(cv2.convexHull(contour)))
  gx=dx[y0:y1,x0:x1][mask];gy=dy[y0:y1,x0:x1][mask];a=float(np.mean(gx*gx));b=float(np.mean(gy*gy));c=float(np.mean(gx*gy));coherence=float(np.sqrt((a-b)**2+4*c*c)/max(a+b,1e-8))
  f=[float(np.log1p(area)),float(max(w,h)/max(1,min(w,h))),float(area/(w*h)),float(4*np.pi*area/max(perimeter**2,1)),float(contour_area/max(hull_area,1)),contrast,coherence,float(dark[y0:y1,x0:x1][mask].mean())]
  rows.append(dict(nativeComponentId=i,rect=[int(x),int(y),int(w),int(h)],sourcePixels=int(area),centroid=centroids[i].tolist(),features=f))
 return raw,labels,rows
def masks(shape,control):
 result={v:np.zeros(shape,np.uint8) for v in ('visible-material','reviewed-non-flake','unknown')};x,y,_,_=control['roi'];objects=[]
 for i,obj in enumerate(control['objects']):
  mask=np.zeros(shape,np.uint8);poly=np.array([[a+x,b+y] for a,b in obj['polygon']],np.int32);cv2.fillPoly(mask,[poly],1);result[obj['label']]|=mask
  objects.append(dict(index=i,label=obj['label'],mask=mask))
 return result,objects
def prepare():
 labels_file=OUT/'object-labels.json';c=json.loads(labels_file.read_text('utf8'));assert not c['fitExecuted'];rows=[];tiles=[];ceiling=[]
 for control in c['controls']:
  bgr=cv2.imread(control['sourcePath']);gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);raw,ids,comp=components(gray);known,objects=masks(gray.shape,control);x,y,w,h=control['roi']
  for obj in objects:
   if obj['label']=='visible-material':
    count=int(((raw>.04)&(obj['mask']>0)).sum());size=int(obj['mask'].sum());ceiling.append(dict(controlIndex=control['controlIndex'],objectIndex=obj['index'],sourceSHA256=control['sourceSHA256'],split=control['split'],kind=control['kind'],reviewedMaterialPixels=size,proposalPixelsInside=count,proposalObjectHit=count>=3 and count/size>=.1))
  for row in comp:
   cx,cy=row['centroid']
   if not(x<=cx<x+w and y<=cy<y+h):continue
   a,b,ww,hh=row['rect'];mask=ids[b:b+hh,a:a+ww]==row['nativeComponentId'];area=row['sourcePixels']
   overlap={key:float((mask&(m[b:b+hh,a:a+ww]>0)).sum()/area) for key,m in known.items()}
   label=1 if overlap['visible-material']>=.5 else 0 if overlap['reviewed-non-flake']>=.5 else None
   if overlap['unknown']>0:label=None
   if label is None:continue
   entry={**row,'controlIndex':control['controlIndex'],'sourceSHA256':control['sourceSHA256'],'sourcePath':control['sourcePath'],'group':control['group'],'split':control['split'],'kind':control['kind'],'label':label,'overlap':overlap,'reviewed':False,'componentIndex':len(rows)};rows.append(entry)
   a0=max(0,int(cx)-20);b0=max(0,int(cy)-20);patch=bgr[b0:b0+40,a0:a0+40,::-1].copy();local=ids[b0:b0+40,a0:a0+40]==row['nativeComponentId'];patch[local]=(.6*patch[local]+.4*np.array([0,255,255])).astype('uint8');im=Image.fromarray(patch).resize((160,160));tile=Image.new('RGB',(160,188),'#111');tile.paste(im,(0,28));d=ImageDraw.Draw(tile);d.text((2,2),f'{entry["componentIndex"]} C{entry["controlIndex"]} L{label} {entry["split"]}',fill='white');d.text((2,15),f'{area}px {cx:.1f},{cy:.1f}',fill='cyan');tiles.append(tile)
 for start in range(0,len(tiles),32):
  sheet=Image.new('RGB',(4*160,8*188),'#111')
  for j,tile in enumerate(tiles[start:start+32]):sheet.paste(tile,(j%4*160,j//4*188))
  sheet.save(OUT/f'native-component-review-{start//32}.png')
 file=OUT/'component-features-unreviewed.json';assert not file.exists()
 file.write_text(json.dumps(dict(labelSHA256=hashlib.sha256(labels_file.read_bytes()).hexdigest(),features=FEATURES,rows=rows,proposalCeiling=ceiling,modelFitted=False),indent=2),'utf8');print(json.dumps(dict(labeledProposals=len(rows),pages=(len(rows)+31)//32,positives=sum(r['label']==1 for r in rows),negatives=sum(r['label']==0 for r in rows),proposalHitObjects=sum(r['proposalObjectHit'] for r in ceiling),visibleObjects=len(ceiling))))
def fit():
 file=OUT/'component-features-reviewed.json';data=json.loads(file.read_text('utf8'));assert data['reviewedBeforeFit'] and not data['modelFitted'];rows=[r for r in data['rows'] if r['label'] is not None];train=[r for r in rows if r['split']=='train'];validation=[r for r in rows if r['split']=='validation'];assert not {r['group'] for r in train}&{r['group'] for r in validation}
 X=np.array([r['features'] for r in train]);y=np.array([r['label'] for r in train]);assert set(y)=={0,1};mean=X.mean(0);std=np.maximum(X.std(0),1e-6);X=np.c_[np.ones(len(X)),(X-mean)/std];weights=np.array([len(y)/(2*np.sum(y==v)) for v in y]);beta=np.zeros(X.shape[1]);reg=np.ones(len(beta));reg[0]=0;start=time.monotonic()
 for iteration in range(60):
  p=1/(1+np.exp(-np.clip(X@beta,-40,40)));gradient=X.T@(weights*(p-y))+reg*beta;hessian=(X.T*(weights*p*(1-p)))@X+np.diag(reg+1e-8);delta=np.linalg.solve(hessian,gradient);beta-=delta
  if np.linalg.norm(delta)<1e-7:break
 model=dict(version='isolated-native-component-logistic-v1',accepted=False,features=FEATURES,mean=mean.tolist(),std=std.tolist(),coefficients=beta.tolist(),threshold=.5,regularization=1.,iterations=iteration+1,reviewedFeaturesSHA256=hashlib.sha256(file.read_bytes()).hexdigest(),protocolSHA256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest())
 target=OUT/'component-gate-model.json';assert not target.exists(),'Single fit only';target.write_text(json.dumps(model,indent=2),'utf8')
 matrix=np.zeros((2,2),int);observations=[]
 for row in validation:
  p=predict(row['features'],model);prediction=int(p>=.5);matrix[row['label'],prediction]+=1;observations.append(dict(componentIndex=row['componentIndex'],controlIndex=row['controlIndex'],label=row['label'],prediction=prediction,probability=p,kind=row['kind']))
 receipt=dict(seconds=time.monotonic()-start,trainComponents=len(train),validationComponents=len(validation),unknownComponents=sum(r['label'] is None for r in data['rows']),confusionMatrix=matrix.tolist(),observations=observations,productionActivated=False,modelSHA256=hashlib.sha256(target.read_bytes()).hexdigest());(OUT/'component-fit-receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt))
def predict(values,model):return float(1/(1+np.exp(-np.clip(np.r_[1.,(np.array(values)-model['mean'])/model['std']]@np.array(model['coefficients']),-40,40))))
def field(gray,model):
 raw,labels,rows=components(gray);allowed=np.zeros(int(labels.max())+1,bool)
 for row in rows:
  if predict(row['features'],model)>=model['threshold']:allowed[row['nativeComponentId']]=True
 return raw*allowed[labels]
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','fit']);args=parser.parse_args();prepare() if args.action=='prepare' else fit()
