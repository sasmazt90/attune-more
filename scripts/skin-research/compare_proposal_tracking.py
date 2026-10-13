"""Finite actual-payload comparison; dry region proposal stays isolated."""
import base64,hashlib,inspect,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-proposal-tracking-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
import appearance_analysis as A
import instant_appearance as I
from trial_region_flake_proposal import region_proposal
cv2.setNumThreads(1)

def scalars(result):
 return {region+':'+v['id']:dict(value=v['value'],quality=v['quality'],reason=v['limitationCode'],normalizationVersion=v['normalizationVersion'],samplingSupportVersion=v['components'].get('samplingSupportVersion')) for region,values in [*result['measurements'].items(),('overview',result.get('general',{}).get('measurements',[]))] for v in values}

def maps(result,criterion):
 output={}
 for key,layer in result['maps'].items():
  if not key.endswith(':'+criterion):continue
  decode=lambda url:cv2.imdecode(np.frombuffer(base64.b64decode(url.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)
  image=decode(layer['dataUrl']);valid=decode(layer['validMaskUrl'])>0;active=image[:,:,3]>0
  assert not (active&~valid).any()
  output[key]=dict(activeMapCells=int(active.sum()),knownMapCells=int(valid.sum()),outsideMask=int((active&~valid).sum()),x=layer['x'],y=layer['y'],step=layer['step'],photoId=layer['photoId'])
 return output

profiles=[];original=I.curve_profile
def capture(*args,**kwargs):
 q=original(*args,**kwargs);caller=inspect.currentframe().f_back
 if q is None or caller.f_locals.get('region')!='chin':return q
 scale=caller.f_locals['scale'];origin=np.asarray(caller.f_locals['origin']);points=q['tracked']/scale+origin
 profiles.append(dict(status=q['trackingStatus'],residual=q['trackingResidual'],segments=q['trackingSegments'],rawFoldSamples=q['rawFoldSamples'],trackedFoldSamples=q['trackedFoldSamples'],observedSamples=q['observedSamples'].tolist(),acceptedFoldSamples=q['support'].tolist(),sourcePoints=[xy.tolist() if np.isfinite(xy).all() else None for xy in points]))
 return q
I.curve_profile=capture;tracking=[]
for old in json.loads((OUT/'tracking-baseline-diagnosis.json').read_text('utf8'))['cases']:
 path=ROOT/old['payloadPath'];payload=json.loads(path.read_text('utf8'));profiles=[];current=A.analyze_skin(payload);baseline=json.loads((OUT/(old['sourcePrefix']+'-baseline-api.json')).read_text('utf8'))
 before=scalars(baseline);after=scalars(current)
 unchanged={k:after[k]==v for k,v in before.items() if k not in ['chin:sag','overview:sag']};assert all(unchanged.values()),[k for k,v in unchanged.items() if not v]
 old_chin=next(v for v in baseline['measurements']['chin'] if v['id']=='sag');new_chin=next(v for v in current['measurements']['chin'] if v['id']=='sag')
 old_roi=old_chin['components'].get('measurementROI');new_roi=new_chin['components'].get('measurementROI')
 geometry_same=old_roi is None and new_roi is None or old_roi is not None and new_roi is not None and old_roi['anatomicalSourcePixels']==new_roi['anatomicalSourcePixels']
 assert geometry_same
 prefix=old['sourcePrefix'];(OUT/(prefix+'-new-api.json')).write_text(json.dumps(current,ensure_ascii=False),'utf8')
 image,_=A.decode_photo(payload['photo'])
 for q in profiles:
  for xy,support in zip(q['sourcePoints'],q['acceptedFoldSamples']):
   if xy is not None:cv2.circle(image,tuple(np.rint(xy).astype(int)),3,(0,255,0) if support else (0,180,255),-1)
 cv2.imwrite(str(OUT/(prefix+'-new-tracking-source.png')),image)
 tracking.append(dict(source=prefix,photoId=payload['photoId'],before=before['chin:sag'],after=after['chin:sag'],overviewBefore=before['overview:sag'],overviewAfter=after['overview:sag'],anatomicalDenominatorUnchanged=geometry_same,oldArea=old_roi,newArea=new_roi,otherMethodsUnchanged=unchanged,profiles=profiles,maps=maps(current,'sag')))
I.curve_profile=original

dry=[]
paths=[ROOT/'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json']
paths+=list((ROOT/'audit-results/dry-sag-component-followup-20261013/product').glob('*/*-automatic-payload.json'))
for path in paths:
 payload=json.loads(path.read_text('utf8'));assert not payload['hostedProcessingConsent'];baseline=A.analyze_skin(payload);bgr,_=A.decode_photo(payload['photo']);native,_=region_proposal(bgr);signal=native['poreSeparated']
 h,w=bgr.shape[:2];face=abs(payload['landmarks'][454]['x']-payload['landmarks'][234]['x'])*w;points=np.asarray([[p['x'],p['y']] for mesh in payload['meshes'].values() for p in mesh['points']],np.float32);pad=max(20,face*.1)
 x=max(0,int(points[:,0].min()-pad));y=max(0,int(points[:,1].min()-pad));right=min(w,int(points[:,0].max()+pad+1));bottom=min(h,int(points[:,1].max()+pad+1));crop=signal[y:bottom,x:right]
 original_dry=A.compute_dryness_signal;original_components=A.eligible_flake_components
 def staged(g,*args,**kwargs):
  result=list(original_dry(g,*args,**kwargs));field=cv2.resize(crop,(g.shape[1],g.shape[0]),interpolation=cv2.INTER_AREA);result[0]=field;result[1]=field;return tuple(result)
 A.compute_dryness_signal=staged
 # Stable regions already passed their geometric/ring/edge/pore gates. Applying
 # the old 80-pixel island cap would again remove connected material interiors.
 A.eligible_flake_components=lambda field,eligible:field*eligible
 try:candidate=A.analyze_skin(payload)
 finally:A.compute_dryness_signal=original_dry;A.eligible_flake_components=original_components
 before=scalars(baseline);after=scalars(candidate);unchanged={k:v==after[k] for k,v in before.items() if not k.endswith(':dry')};assert all(unchanged.values())
 same_area=all(v['evaluatedArea']==next(b for b in baseline['measurements'][region] if b['id']=='dry')['evaluatedArea'] for region,values in candidate['measurements'].items() for v in values if v['id']=='dry');assert same_area
 prefix='24031977' if path.parent.name=='attempt-2' else path.parent.name
 (OUT/(prefix+'-isolated-region-proposal-api.json')).write_text(json.dumps(candidate,ensure_ascii=False),'utf8')
 dry.append(dict(source=prefix,photoId=payload['photoId'],scores={k:dict(before=v['value'],isolatedProposal=after[k]['value']) for k,v in before.items() if k.endswith(':dry')},maps=maps(candidate,'dry'),otherMethodsUnchanged=unchanged,anatomicalAreaUnchanged=same_area,productionActivated=False))
receipt=dict(tracking=tracking,dryProposal=dry,onlyChinProductionChange=True,dryProductionActivated=False,classifierFitted=False,sourceOrLabelsChanged=False)
(OUT/'actual-payload-comparison.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(tracking=[dict(source=r['source'],before=r['before'],after=r['after'],profiles=[{k:q[k] for k in ['status','residual','rawFoldSamples','trackedFoldSamples']} for q in r['profiles']]) for r in tracking],dry=[dict(source=r['source'],overview=r['scores']['overview:dry']) for r in dry])))
