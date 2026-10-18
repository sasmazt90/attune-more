"""Source-aligned loss layers and independent chin target/corridor evidence."""
import hashlib,importlib.util,inspect,json,sys
from pathlib import Path
import cv2,numpy as np
cv2.setNumThreads(1)
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_periorbital_and_acne_comparative as audit
import appearance_analysis as working
OUT=ROOT/'audit-results/dry-sag-native-followup-20261013';BASE=ROOT/'.runtime/dry-sag-native-baseline-20261013'
saved={n:sys.modules[n] for n in ('instant_appearance','skin_general')}
modules={}
for n in ['instant_appearance','skin_general','appearance_analysis']:
 alias=n if n!='appearance_analysis' else 'traced_baseline';spec=importlib.util.spec_from_file_location(alias,BASE/(n+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[alias]=m;spec.loader.exec_module(m);modules[n]=m
sys.modules.update(saved);A=modules['appearance_analysis'];I=modules['instant_appearance'];records=[]
for prefix in ['c31892d1','515cc548','d3e8bb60']:
 f=ROOT/'audit-results/dry-sag-product-20261013'/(prefix+'-payload.json');p=json.loads(f.read_text('utf8'));layers=[];profiles=[];original=A.eligible_flake_components;curve=I.curve_profile
 def collect(signal,eligible):
  result=original(signal,eligible);frame=inspect.currentframe().f_back
  if frame.f_code.co_name=='analyze_skin':
   loc=frame.f_locals;layers.append(dict(signal=signal.copy(),eligible=eligible.copy(),accepted=result.copy(),locals={k:loc[k] for k in ['gray8','image','origin','scale','exclusion','hair','luma_clipping','surface_masks','texture_visible','dry_union','dark_ringing']}))
  return result
 def profile(*args,**kw):
  q=curve(*args,**kw);loc=inspect.currentframe().f_back.f_locals
  if q is not None and loc['region'] in ('chin','rightCheek','leftCheek'):profiles.append(dict(region=loc['region'],side=loc['side'],q=q,eligible=loc['eligible'].copy(),guide=args[2].copy(),origin=loc['origin'],scale=loc['scale']))
  return q
 A.eligible_flake_components=collect;I.curve_profile=profile
 try:result=A.analyze_skin(p)
 finally:A.eligible_flake_components=original;I.curve_profile=curve
 bgr=A.decode_photo(p['photo'])[0];receipt=dict(source=prefix,payloadSHA256=hashlib.sha256(f.read_bytes()).hexdigest(),sourcePhotoId=p['photoId'],profiles=[])
 if layers:
  z=layers[0];loc=z['locals'];gray8=loc['gray8'];g=gray8.astype('float32')/255;high=g-cv2.GaussianBlur(g,(0,0),1.2);broad=cv2.GaussianBlur(g,(0,0),.7)-cv2.GaussianBlur(g,(0,0),2.3);dog=np.clip((high-.025)/.10,0,1)*np.clip((broad-.018)/.10,0,1);_,raw,contrast,lbp,dark,_=A.compute_dryness_signal(gray8)
  before=A.compute_dryness_signal(gray8)[0];x0,y0=loc['origin'];scale=loc['scale'];h,w=loc['image'].shape[:2];nativegray=cv2.cvtColor(bgr[y0:min(bgr.shape[0],y0+int(round(h/scale))),x0:min(bgr.shape[1],x0+int(round(w/scale)))],cv2.COLOR_BGR2GRAY)
  native=A.compute_dryness_signal(nativegray)
  stages=[('DoG contrast',dog>.04),('after LBP',(dog*(lbp<8))>.04),('after local contrast',raw>.04),('after dark ring',(raw>.04)&~dark),('component before anatomy',before>.04),('after source visibility',(before>.04)&loc['texture_visible']),('after actual anatomy',z['accepted']>.04)]
  panels=[];counts=[]
  for title,mask in stages:
   image=loc['image'].copy();image[mask]=(image[mask]*.3+np.asarray([0,255,255])*.7).astype('uint8');cv2.imwrite(str(OUT/(prefix+'-'+title.replace(' ','-')+'.png')),image)
   image=cv2.resize(image,(360,410));image=cv2.copyMakeBorder(image,26,0,0,0,cv2.BORDER_CONSTANT);cv2.putText(image,title,(5,18),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1);panels.append(image);counts.append(dict(stage=title,analysisPixels=int(mask.sum())))
  while len(panels)%3:panels.append(panels[-1]*0)
  cv2.imwrite(str(OUT/(prefix+'-loss-stages.jpg')),np.concatenate([np.concatenate(panels[i:i+3],axis=1) for i in range(0,len(panels),3)]))
  receipt.update(origin=loc['origin'],scale=scale,nativeCropShape=nativegray.shape,analysisCropShape=gray8.shape,nativeAfterLBPContrastPixels=int((native[1]>.04).sum()),stages=counts,encodedActiveSourcePixels=int((audit.project_map_alpha(result['maps'].get('overview:dry'),bgr.shape)>0).sum()))
 for profile in profiles:
  q=profile['q'];scale=profile['scale'];origin=np.asarray(profile['origin']);image=bgr.copy();guide=np.rint(profile['guide']/scale+origin).astype('int32');cv2.polylines(image,[guide],False,(255,120,0),2)
  layer=A.map_result(profile['eligible'].astype('float32'),profile['eligible'],profile['region'],'sag',p['photoId'],p['pose'],bgr.shape,scale,'index',1.,tuple(origin));support=audit.project_map_alpha(layer,bgr.shape)>0;image[support]=(image[support]*.8+np.asarray([0,180,0])*.2).astype('uint8')
  for xy,observed,supported in zip(q['tracked'],q['observedSamples'],q['support']):
   xy=np.rint(xy/scale+origin).astype('int32');cv2.circle(image,tuple(xy),2,(0,255,255) if observed and supported else (0,0,255),-1)
  cv2.imwrite(str(OUT/(prefix+'-'+profile['region']+'-'+profile['side']+'-baseline-target.png')),image)
  receipt['profiles'].append(dict(region=profile['region'],side=profile['side'],observedCenters=int(q['observedSamples'].sum()),positiveObservedCenters=int((q['support']&q['observedSamples']).sum()),coverage=q['coverage'],continuity=q['continuity'],trackingResidual=q['trackingResidual']))
 records.append(receipt);print(json.dumps(receipt),flush=True)
(OUT/'source-loss-and-target-receipt.json').write_text(json.dumps(records,indent=2),'utf8')
