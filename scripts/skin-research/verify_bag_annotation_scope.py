"""Source eyebag annotation vs lower-fold measurement: different target scopes.

No invented ontology or full-ROI Dice. The source only labels a partial polygon;
the unannotated remainder is unknown. Visual evidence stays local/ignored.
"""
import hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as A,instant_appearance as IA
OUT=ROOT/'audit-results/lines-bags-followup-20261012';prefix='20031f35'
source=json.loads((OUT/(prefix+'-source.json')).read_text('utf8'))
assert hashlib.sha256(Path(source['absolutePath']).read_bytes()).hexdigest()==source['sha256']
p=json.loads((ROOT/'audit-results/bag-label-followup-20261012'/(prefix+'-v2-payload.json')).read_text('utf8'))
calls=[];profiles=[];proxy=A.instant_proxy;curve=IA.curve_profile
def capture(*args,**kwargs):
 if args[3]=='periorbital':calls.append(args)
 return proxy(*args,**kwargs)
def profile(*args,**kwargs):
 q=curve(*args,**kwargs)
 if kwargs.get('center_support') is not None:profiles.append(q)
 return q
A.instant_proxy=capture;IA.curve_profile=profile
try:r=A.analyze_skin(p)
finally:A.instant_proxy=proxy;IA.curve_profile=curve
gray,target,points,_,_,scale,origin,shape,*_=calls[0]
bgr=A.decode_photo(p['photo'])[0];truth=np.zeros(shape[:2],np.uint8)
annotations=[x for x in source['annotations'] if x['label']=='eyebag']
assert annotations and all(x['kind']=='polygon' for x in annotations)
for ann in annotations:
 for seg in ann['segmentation']:cv2.fillPoly(truth,[np.rint(np.asarray(seg).reshape(-1,2)).astype('int32')],1)
band=A.eye_skin_bands(points,gray.shape,scale,origin,shape)['bags']
mesh=A.bag_support_mask(gray.shape,p['meshes']['periorbital'],scale,origin)
x0,y0=origin
def native(mask):
 z=np.zeros(shape[:2],np.uint8);w=round(mask.shape[1]/scale);h=round(mask.shape[0]/scale)
 z[y0:min(shape[0],y0+h),x0:min(shape[1],x0+w)]=cv2.resize(mask.astype('uint8'),(w,h),interpolation=cv2.INTER_NEAREST)[:min(h,shape[0]-y0),:min(w,shape[1]-x0)];return z>0
nband=native(band);nmesh=native(mesh);eligible=native(target)
active=audit.project_map_alpha(r['maps'].get('periorbital:bags'),shape)>0
centers=[]
for q in profiles:
 for xy,supported,fold,edge in zip(q['tracked'],q['support'],q['values'],q['edgeValues']):
  if supported and q['continuity']>=.20 and edge>0:
   center=np.asarray(xy)/scale+origin;centers.append(center.tolist())
panels=[]
for title,mask,color in [('SOURCE partial eyebag polygon',truth>0,(255,70,30)),('V5 band yellow / selected cells green',nband,(0,240,240)),('MEASURED lower folds / source annotation',active,(0,255,0))]:
 image=bgr.copy();image[mask]=(image[mask]*.45+np.asarray(color)*.55).astype('uint8')
 if title.startswith('V5'):cv2.drawContours(image,cv2.findContours(nmesh.astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],-1,(0,255,0),1)
 if title.startswith('MEASURED'):
  cv2.drawContours(image,cv2.findContours(truth,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0],-1,(255,70,30),1)
  for xy in centers:cv2.circle(image,tuple(np.rint(xy).astype(int)),1,(0,255,255),-1)
 tile=image[270:385,100:560];tile=cv2.resize(tile,(920,230));tile=cv2.copyMakeBorder(tile,35,0,0,0,cv2.BORDER_CONSTANT,value=(20,20,20));cv2.putText(tile,title,(10,24),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1);panels.append(tile)
cv2.imwrite(str(OUT/'20031f35-target-scope.png'),np.concatenate(panels))
receipt=dict(sourceSHA256=source['sha256'],sourceClass='eyebag',sourceDataset=source['source'],sourceLabelType='partial polygon',sourceAnnotations=annotations,authoritativeWholeBagOntologyAvailable=False,sourcePixels=int(truth.sum()),sourcePixelsInsideBand=int(((truth>0)&nband).sum()),sourcePixelsOutsideBand=int(((truth>0)&~nband).sum()),sourcePixelsInsideSelectedCells=int(((truth>0)&nmesh).sum()),sourcePixelsInsideEligibleSupport=int(((truth>0)&eligible).sum()),activeSourcePixels=int(active.sum()),activeWithinAnnotatedSourcePixels=int((active&(truth>0)).sum()),measuredFoldCentersSource=centers,origin=list(origin),scale=scale,decision='target-scope mismatch: visible source polygon hugs upper lower-lid/bag margin; fixed v5 target tracks supported lower folds. No evidence of a coordinate transform error. Partial bag polygon overlap is not full bag detection accuracy.',sourceAnnotationOutsideIsUnknown=True,bandExpandedToFitAnnotation=False,formula=A.NORMALIZATION['bags'],samplingVersion=next(v for v in r['measurements']['periorbital'] if v['id']=='bags')['components']['samplingSupportVersion'])
(OUT/'bag-target-scope.json').write_text(json.dumps(receipt,indent=2),'utf8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('sourceAnnotations','measuredFoldCentersSource')}))
