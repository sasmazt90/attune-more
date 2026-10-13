"""One fixed, label-free stable bright-region proposal; no classifier fitting."""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
import cv2,numpy as np
from skimage.feature import local_binary_pattern
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/dry-sag-proposal-tracking-20261013';OUT.mkdir(parents=True,exist_ok=True)
OLD=ROOT/'audit-results/dry-sag-component-followup-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
from component_flake_gate import masks
cv2.setNumThreads(1)
PARAMETERS=dict(delta=5,minArea=4,maxArea=1500,maxVariation=.25,minDiversity=.2,maxElongation=8.,minFill=.15,
                minRingLumaDifference=3.,minBoundaryEdgeFraction=.35,minBoundaryEdge=4/255,
                smallPoreMaxArea=20,maxSmallPoreDarkAdjacency=.25,contrastSpan=32.)

def region_proposal(bgr):
 """No annotation, ROI label, person ID or source name is an inference input."""
 gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY);lab=cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB);luma=lab[:,:,0]
 p=PARAMETERS
 regions,_=cv2.MSER_create(p['delta'],p['minArea'],p['maxArea'],p['maxVariation'],p['minDiversity']).detectRegions(255-luma)
 dark=cv2.dilate((cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35).astype('uint8'),np.ones((7,7),np.uint8))>0
 g=gray.astype('float32')/255;gradient=np.hypot(cv2.Sobel(g,cv2.CV_32F,1,0,3),cv2.Sobel(g,cv2.CV_32F,0,1,3))
 stages={k:np.zeros(gray.shape,np.float32) for k in ['stableRegions','geometry','ringContrast','boundaryEdges','poreSeparated']};details=[]
 for points in regions:
  x,y,w,h=cv2.boundingRect(points);area=len(points)
  stages['stableRegions'][points[:,1],points[:,0]]=1
  if max(w,h)/max(1,min(w,h))>p['maxElongation'] or area/(w*h)<p['minFill']:continue
  stages['geometry'][points[:,1],points[:,0]]=1
  a=max(0,x-4);b=max(0,y-4);c=min(gray.shape[1],x+w+4);d=min(gray.shape[0],y+h+4)
  mask=np.zeros((d-b,c-a),np.uint8);mask[points[:,1]-b,points[:,0]-a]=1
  ring=(cv2.dilate(mask,np.ones((7,7),np.uint8))>0)&~(mask>0)
  if ring.sum()<8:continue
  # The actual candidate pixels are excluded from every background statistic.
  reference=float(np.median(luma[b:d,a:c][ring]));contrast=float(np.median(luma[points[:,1],points[:,0]])-reference)
  if contrast<=p['minRingLumaDifference']:continue
  intensity=float(np.clip((contrast-p['minRingLumaDifference'])/p['contrastSpan'],0,1));stages['ringContrast'][points[:,1],points[:,0]]=np.maximum(stages['ringContrast'][points[:,1],points[:,0]],intensity)
  border=(mask>0)&~(cv2.erode(mask,np.ones((3,3),np.uint8))>0)
  edge_fraction=float((gradient[b:d,a:c][border]>p['minBoundaryEdge']).mean())
  if edge_fraction<p['minBoundaryEdgeFraction']:continue
  stages['boundaryEdges'][points[:,1],points[:,0]]=np.maximum(stages['boundaryEdges'][points[:,1],points[:,0]],intensity)
  dark_fraction=float(dark[points[:,1],points[:,0]].mean())
  if area<=p['smallPoreMaxArea'] and dark_fraction>p['maxSmallPoreDarkAdjacency']:continue
  stages['poreSeparated'][points[:,1],points[:,0]]=np.maximum(stages['poreSeparated'][points[:,1],points[:,0]],intensity)
  if intensity>.04:
   details.append(dict(rect=[x,y,w,h],area=area,ringLuma=reference,contrast=contrast,edgeFraction=edge_fraction,darkAdjacentFraction=dark_fraction))
 return stages,details

def old_stages(gray):
 g=gray.astype('float32')/255;bg=cv2.medianBlur(gray,11).astype('float32')/255
 mad=cv2.medianBlur(np.rint(np.abs(g-bg)*255).astype('uint8'),11).astype('float32')/255
 base=np.clip((g-bg-.025)/.10,0,1);lbp=local_binary_pattern(gray,8,1,'uniform')
 high=g-cv2.GaussianBlur(g,(0,0),1.2);broad=cv2.GaussianBlur(g,(0,0),.7)-cv2.GaussianBlur(g,(0,0),2.3)
 dog=np.clip((high-.025)/.10,0,1)*np.clip((broad-.018)/.10,0,1)
 lc=np.sqrt(np.maximum(0,cv2.GaussianBlur(g*g,(0,0),2)-cv2.GaussianBlur(g,(0,0),2)**2))
 filtered=dog*(lbp<8);filtered_contrast=filtered*((lc>.015)&(lc<.14))
 dark=cv2.dilate((cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((7,7),np.uint8))>35).astype('uint8'),np.ones((7,7),np.uint8))>0
 return dict(oldMedianPeaks=base,oldAfterLBP=base*(lbp<8),oldAfterMAD=base*(lbp<8)*(g-bg>np.maximum(.025,3*1.4826*mad)),
             productionDoG=dog,productionAfterLBP=filtered,productionAfterContrast=filtered_contrast,
             productionAfterDarkRinging=filtered_contrast*(~dark),productionAfterCompactness=A.eligible_flake_components(filtered_contrast,~dark))

def measure(field,mask,scale):
 active=(field>.04)&mask
 n,_,stats,_=cv2.connectedComponentsWithStats(active.astype('uint8'));sizes=stats[1:,4]
 return dict(activeSourcePixels=float(active.sum()/scale**2),reviewedSourcePixels=float(mask.sum()/scale**2),
             activeOpticalAreaPercent=float(100*active.sum()/max(1,mask.sum())),components=n-1,
             largestSourceComponent=float(sizes.max()/scale**2) if sizes.size else 0.,
             objectHit=bool(active.sum()/scale**2>=3 and active.sum()/max(1,mask.sum())>=.1))

def main():
 labels=json.loads((OLD/'object-labels.json').read_text('utf8'))
 protocol=dict(frozenUTC=datetime.now(timezone.utc).isoformat(),baselineSHA='5a40a1276c9eccc6bd099d42775dcd7eb4e3e604',
   labelsSHA256=hashlib.sha256((OLD/'object-labels.json').read_bytes()).hexdigest(),parameters=PARAMETERS,
   changedVariable='MSER connected bright regions with non-self ring contrast and measured boundary edges; no new gate/classifier',
   acceptance=dict(materialHits='At least 8/21 native material objects and 3/8 familiar validation objects; never independent final test',
    negative='Each reviewed-negative area <= max(2*production-v3 local support fraction, production-v3 + 0.25 percentage points); no meaningful new product score above 0.5 index points',
    domain='Do not lose baseline proposal object hits in either processed or natural-origin controls',
    objectHit='>=3 native pixels AND >=10% within partial visible-material polygon; not Dice/precision'),
   outsideLabels='unknown',annotationAsInferenceInput=False,classifierFitAllowedOnlyAfterProposalAcceptance=True)
 target=OUT/'region-proposal-protocol.json'
 if target.exists():
  frozen=json.loads(target.read_text('utf8'))
  assert {k:v for k,v in frozen.items() if k!='frozenUTC'}=={k:v for k,v in protocol.items() if k!='frozenUTC'},'No parameter search'
  try: json.loads((OUT/'region-proposal-receipt.json').read_text('utf8'))
  except (FileNotFoundError,json.JSONDecodeError):pass
  else:raise AssertionError('Completed trial already exists')
 else:target.write_text(json.dumps(protocol,indent=2),'utf8')
 rows=[]
 for control in labels['controls']:
  path=Path(control['sourcePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==control['sourceSHA256'];bgr=cv2.imread(str(path));known,objects=masks(bgr.shape[:2],control)
  scales=[]
  for scale in [1.,.5]:
   image=bgr if scale==1 else cv2.resize(bgr,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
   gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY);new,details=region_proposal(image);stages={**old_stages(gray),**{'new:'+k:v for k,v in new.items()}}
   object_rows=[]
   for obj in objects:
    mask=obj['mask']>0 if scale==1 else cv2.resize(obj['mask'],(gray.shape[1],gray.shape[0]),interpolation=cv2.INTER_NEAREST)>0
    object_rows.append(dict(index=obj['index'],label=obj['label'],sourceObjectPixels=int(obj['mask'].sum()),
      sizeClass='small' if obj['mask'].sum()<=150 else 'wide',stages={k:measure(v,mask,scale) for k,v in stages.items()}))
   neg=known['reviewed-non-flake']>0 if scale==1 else cv2.resize(known['reviewed-non-flake'],(gray.shape[1],gray.shape[0]),interpolation=cv2.INTER_NEAREST)>0
   scales.append(dict(scale=scale,objects=object_rows,negative={k:measure(v,neg,scale) for k,v in stages.items()},candidateRegionCount=len(details),candidateRegions=details))
   if scale==1:
    x,y,w,h=control['roi'];tiles=[]
    for name in ['oldAfterMAD','productionAfterCompactness','new:poreSeparated']:
     tile=image[y:y+h,x:x+w].copy();active=stages[name][y:y+h,x:x+w]>.04;tile[active]=(.35*tile[active]+.65*np.array([0,0,255])).astype('uint8');tile=cv2.resize(tile,(320,320));cv2.putText(tile,name,(2,18),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,0),1);tiles.append(tile)
    cv2.imwrite(str(OUT/f'C{control["controlIndex"]:02d}-region-proposal.png'),np.hstack(tiles))
  rows.append(dict(controlIndex=control['controlIndex'],sourceSHA256=control['sourceSHA256'],group=control['group'],split=control['split'],kind=control['kind'],resolutions=scales))
 native=[(r,o) for r in rows for o in r['resolutions'][0]['objects'] if o['label']=='visible-material'];val=[(r,o) for r,o in native if r['split']=='validation']
 hits=sum(o['stages']['new:poreSeparated']['objectHit'] for _,o in native);valhits=sum(o['stages']['new:poreSeparated']['objectHit'] for _,o in val)
 negative_checks=[]
 for r in rows:
  n=r['resolutions'][0]['negative'];before=n['productionAfterCompactness']['activeOpticalAreaPercent'];after=n['new:poreSeparated']['activeOpticalAreaPercent']
  if n['new:poreSeparated']['reviewedSourcePixels']:
   negative_checks.append(dict(controlIndex=r['controlIndex'],beforePercent=before,afterPercent=after,accepted=after<=max(before*2,before+.25)))
 domain_preserved=all(not o['stages']['oldAfterMAD']['objectHit'] or o['stages']['new:poreSeparated']['objectHit'] for _,o in native)
 accepted=hits>=8 and valhits>=3 and all(r['accepted'] for r in negative_checks) and domain_preserved
 receipt=dict(protocolSHA256=hashlib.sha256(target.read_bytes()).hexdigest(),rows=rows,nativeMaterialHits=hits,nativeMaterialCount=len(native),familiarValidationHits=valhits,familiarValidationCount=len(val),negativeChecks=negative_checks,oldProposalHitsPreserved=domain_preserved,proposalAcceptancePassed=accepted,classifierFitted=False,productionActivated=False)
 (OUT/'region-proposal-receipt.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps({k:v for k,v in receipt.items() if k!='rows'}))
if __name__=='__main__':main()
