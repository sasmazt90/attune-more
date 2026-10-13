"""One frozen component trial: proposal ceiling, local scope and real product payloads."""
import base64,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from component_flake_gate import OUT,ROOT,proposal,field,masks,components
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
cv2.setNumThreads(1)
model=json.loads((OUT/'component-gate-model.json').read_text('utf8'));annotations=json.loads((OUT/'object-labels.json').read_text('utf8'))
def measure(signal,mask,scale):
 active=(signal>.04)&mask;count,_,stats,_=cv2.connectedComponentsWithStats(active.astype('uint8'));sizes=stats[1:,4]
 return dict(activeSourcePixels=float(active.sum()/scale**2),reviewedSourcePixels=float(mask.sum()/scale**2),activeOpticalAreaPercent=float(active.sum()/max(1,mask.sum())*100),componentCount=count-1,largestSourceComponentPixels=float(sizes.max()/scale**2) if sizes.size else 0.)
rows=[];positive_checks=[];negative_checks=[]
for control in annotations['controls']:
 path=Path(control['sourcePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==control['sourceSHA256'];source=cv2.imread(str(path));gray=cv2.cvtColor(source,cv2.COLOR_BGR2GRAY);known,objects=masks(gray.shape,control)
 scales=[]
 for scale in (1.,.5):
  g=gray if scale==1 else cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
  fields={'v3OpticalFunction':A.compute_dryness_signal(g)[0],'unchangedNativeProposal':proposal(g),'componentGate':field(g,model)}
  k={name:(mask>0 if scale==1 else cv2.resize(mask,(g.shape[1],g.shape[0]),interpolation=cv2.INTER_NEAREST)>0) for name,mask in known.items()}
  object_rows=[]
  for obj in objects:
   mask=obj['mask']>0 if scale==1 else cv2.resize(obj['mask'],(g.shape[1],g.shape[0]),interpolation=cv2.INTER_NEAREST)>0
   stats={name:measure(signal,mask,scale) for name,signal in fields.items()}
   for s in stats.values():s['objectHit']=s['activeSourcePixels']>=3 and s['activeOpticalAreaPercent']>=10
   object_rows.append(dict(objectIndex=obj['index'],label=obj['label'],fields=stats))
   if scale==1 and obj['label']=='visible-material':positive_checks.append(dict(controlIndex=control['controlIndex'],split=control['split'],kind=control['kind'],objectIndex=obj['index'],v3Hit=stats['v3OpticalFunction']['objectHit'],proposalHit=stats['unchangedNativeProposal']['objectHit'],candidateHit=stats['componentGate']['objectHit']))
  negative={name:measure(s,k['reviewed-non-flake'],scale) for name,s in fields.items()}
  if scale==1 and k['reviewed-non-flake'].any():negative_checks.append(dict(controlIndex=control['controlIndex'],split=control['split'],fields=negative))
  scales.append(dict(sourceResolutionFactor=scale,materialObjects=object_rows,reviewedNegative=negative,unknownOutsideObjects=True))
  if scale==1:
   x,y,w,h=control['roi'];tiles=[]
   for name,s in fields.items():
    rgb=source[y:y+h,x:x+w,::-1].copy();active=s[y:y+h,x:x+w]>.04;rgb[active]=(.35*rgb[active]+.65*np.array([255,0,0])).astype('uint8');im=Image.fromarray(rgb).resize((320,320));tile=Image.new('RGB',(320,348),'#111');tile.paste(im,(0,28));ImageDraw.Draw(tile).text((3,3),f'C{control["controlIndex"]} {name}',fill='cyan');tiles.append(tile)
   sheet=Image.new('RGB',(960,348),'#111')
   for i,tile in enumerate(tiles):sheet.paste(tile,(320*i,0))
   sheet.save(OUT/f'control-{control["controlIndex"]:02d}-before-after.png')
 rows.append(dict(controlIndex=control['controlIndex'],sourceSHA256=control['sourceSHA256'],kind=control['kind'],split=control['split'],resolutionComparisons=scales))
v=[r for r in positive_checks if r['split']=='validation'];n=[r for r in negative_checks if r['split']=='validation']
positive_preserved=all(not r['v3Hit'] or r['candidateHit'] for r in v) and all(not r['proposalHit'] or r['candidateHit'] for r in v)
before=sum(r['fields']['unchangedNativeProposal']['activeSourcePixels'] for r in n);after=sum(r['fields']['componentGate']['activeSourcePixels'] for r in n);negative_reduction=(before-after)/before if before else None
no_negative_growth=all(r['fields']['componentGate']['activeSourcePixels']<=r['fields']['v3OpticalFunction']['activeSourcePixels'] for r in n)
# Application comparison uses the exact saved real browser payloads, never a
# fabricated response, in an isolated Python process. Only dry photometry changes.
product=[]
payloads=[ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json']
payloads.extend(sorted((OUT/'product').glob('*/*-automatic-payload.json')))
def scalars(result):
 groups=[*result['measurements'].items(),('overview',result.get('general',{}).get('measurements',[]))]
 return {region+':'+v['id']:dict(value=v['value'],reason=v['limitationCode'],normalizationVersion=v['normalizationVersion']) for region,values in groups for v in values}
for path in payloads:
 payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];baseline=A.analyze_skin(payload);bgr,_=A.decode_photo(payload['photo']);native=field(cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY),model)
 h,w=bgr.shape[:2];face=abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*w;scale=min(1,320/max(face,1));points=np.array([[p['x'],p['y']] for mesh in payload['meshes'].values() for p in mesh['points']]);pad=max(20,face*.1);x0=max(0,int(points[:,0].min()-pad));y0=max(0,int(points[:,1].min()-pad));x1=min(w,int(points[:,0].max()+pad+1));y1=min(h,int(points[:,1].max()+pad+1));native=native[y0:y1,x0:x1];original=A.compute_dryness_signal;norm=A.NORMALIZATION['dry']
 def candidate(g,*args,**kwargs):
  result=list(original(g,*args,**kwargs));s=cv2.resize(native,(g.shape[1],g.shape[0]),interpolation=cv2.INTER_AREA);result[0]=s;result[1]=s;return tuple(result)
 A.compute_dryness_signal=candidate;A.NORMALIZATION['dry']='isolated-native-component-gate-v1'
 try:staging=A.analyze_skin(payload)
 finally:A.compute_dryness_signal=original;A.NORMALIZATION['dry']=norm
 before_values=scalars(baseline);after_values=scalars(staging);preserved={key:before_values[key]==after_values[key] for key in before_values if not key.endswith(':dry')};assert all(preserved.values())
 areas_same=all(v['evaluatedArea']==next(a for a in baseline['measurements'][region] if a['id']=='dry')['evaluatedArea'] for region,values in staging['measurements'].items() for v in values if v['id']=='dry');assert areas_same
 key=path.parent.name if path.parent.name!='attempt-2' else '24031977';folder=OUT/'isolated-product-comparison'/key;folder.mkdir(parents=True,exist_ok=True)
 (folder/'baseline.json').write_text(json.dumps(baseline,ensure_ascii=False),'utf8');(folder/'candidate.json').write_text(json.dumps(staging,ensure_ascii=False),'utf8')
 map_counts={}
 for name,result in [('baseline',baseline),('candidate',staging)]:
  for map_key,layer in result['maps'].items():
   if not map_key.endswith(':dry'):continue
   image=cv2.imdecode(np.frombuffer(base64.b64decode(layer['dataUrl'].split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED);support=cv2.imdecode(np.frombuffer(base64.b64decode(layer['validMaskUrl'].split(',')[1]),np.uint8),cv2.IMREAD_GRAYSCALE)>0;active=image[:,:,3]>0;assert not (active&~support).any();map_counts[name+':'+map_key]=dict(activeMapGridCells=int(active.sum()),knownMapGridCells=int(support.sum()),x=layer['x'],y=layer['y'],step=layer['step'],outsideValidMask=int((active&~support).sum()),photoMatches=layer['photoId']==payload['photoId'])
 product.append(dict(sourcePayload=str(path.relative_to(ROOT)),photoId=payload['photoId'],baseline=before_values,candidate=after_values,unchangedOtherMethods=preserved,sameRegionalDenominators=areas_same,maps=map_counts,productionActivated=False))
accepted=positive_preserved and negative_reduction is not None and negative_reduction>=.25 and no_negative_growth
receipt=dict(protocolSHA256=hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest(),modelSHA256=hashlib.sha256((OUT/'component-gate-model.json').read_bytes()).hexdigest(),rows=rows,objects=positive_checks,negativeSupport=negative_checks,validation=dict(materialObjectCount=len(v),v3HitObjects=sum(r['v3Hit'] for r in v),proposalHitObjects=sum(r['proposalHit'] for r in v),candidateHitObjects=sum(r['candidateHit'] for r in v),positivePreserved=positive_preserved,negativeAreaReduction=negative_reduction,noIndividualNegativeGrowthAboveV3=no_negative_growth,predeclaredLocalChecksPassed=accepted),allMaterialObjects=dict(count=len(positive_checks),v3Hits=sum(r['v3Hit'] for r in positive_checks),proposalHits=sum(r['proposalHit'] for r in positive_checks),candidateHits=sum(r['candidateHit'] for r in positive_checks)),productComparisons=product,productionActivated=False,pixelDice=None,pixelPrecision=None,clinicalSeverity=False,decision='No production promotion: missing-proposal ceiling and only one positive labeled validation component cannot establish reliable material localization; revised support requires independent positive evidence even if some local checks pass.')
(OUT/'component-evaluation-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(validation=receipt['validation'],allMaterialObjects=receipt['allMaterialObjects'],productCases=len(product),productionActivated=False)))
