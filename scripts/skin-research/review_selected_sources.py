"""Prepare source/target overlays for engineering review, never final-test selection."""
import json, collections, sys
import cv2, numpy as np
from PIL import Image,ImageDraw
from selected_sources import ROOT,OUT,MAP,TARGETS,write,sha,geometry

def annotation_mask(r,target):
 mask=np.zeros((r['height'],r['width']),np.uint8)
 decision=r.get('reviewDecision',{})
 if target in decision.get('maskOverrides',{}):
  for points in decision['maskOverrides'][target]:cv2.fillPoly(mask,[np.rint(np.asarray(points)).astype(np.int32)],1)
  return mask
 if target in decision.get('excludedMaskTargets',[]):return mask
 for a in r['annotations']:
  if MAP.get(r['source'],{}).get(a['label'])!=target or not a['validMask']:continue
  if a['kind']=='polygon':cv2.fillPoly(mask,[np.rint(np.array(v).reshape(-1,2)).astype(np.int32) for v in a['segmentation']],1)
  elif a['kind']=='rle':
   from pycocotools import mask as M
   raw=a['segmentation'];rle=M.frPyObjects(raw,r['height'],r['width']) if isinstance(raw.get('counts'),list) else raw
   mask|=M.decode(rle)
 return mask

def main():
 sys.path.insert(0,str(ROOT/'.runtime/python-packages'))
 import mediapipe as mp
 from mediapipe.tasks.python import BaseOptions
 from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions
 from prepare_focused_data import face_crop
 cv2.setNumThreads(1);manifest=json.loads((OUT/'manifest.json').read_text('utf8'));rows=manifest['rows']
 folder=OUT/'review';folder.mkdir(exist_ok=True)
 supplement='--supplement' in sys.argv or '--pul' in sys.argv
 if (folder/'candidates.json').exists() and not supplement:raise RuntimeError('Preserve review evidence')
 assert not (folder/'decisions.json').exists(),'Review decisions already frozen'
 model=ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
 detector=FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model)),num_faces=2,output_face_blendshapes=True))
 candidates=json.loads((folder/'candidates.json').read_text('utf8'))['rows'] if supplement else []
 if supplement:
  for r in rows:
   if r['source']=='old-eye' and r['oldMetadata']['eligible']:
    anns=[]
    for a in r['oldMetadata']['annotations']:
     if a['classId'] not in [0,1]:continue
     x,y,c,d=a['box'];raw=dict(label='Acne' if a['classId']==0 else 'Eyebags',bbox=[x,y,c-x,d-y],segmentation=[np.asarray(a['polygon']).reshape(-1).tolist()] if a['kind']=='polygon' else [])
     anns.append(geometry(raw,r['width'],r['height']))
    r['annotations']=anns
 # Select examples using source targets and fixed group hash, no prediction.
 for source in (['merve'] if '--pul' in sys.argv else ['clean3','old-eye'] if supplement else ['v11','smart','clean3','dc','wrinkles','skin5','face','care','merve','arnold','csv']):
  quotas=collections.Counter()
  eligible=sorted([r for r in rows if r['source']==source and r['split']!='test' and not r.get('excluded')],key=lambda r:r['sha256'])
  for r in eligible:
   if '--pul' in sys.argv and (not any(a['label']=='pul' and a['validBox'] for a in r['annotations']) or any(v['sha256']==r['sha256'] for v in candidates)):continue
   targets=sorted({MAP.get(source,{}).get(a['label']) for a in r['annotations']} - {None})
   if supplement and source=='clean3':targets=[t for t in targets if t in ['oil','dry']]
   if source in ['merve','csv']:targets=['dry' if source=='merve' else 'auxiliary']
   limit=6 if source=='smart' else 3
   if not targets or all(quotas[(t,r['split'])]>=limit for t in targets):continue
   im=cv2.imread(r['absolutePath']);rgb=cv2.cvtColor(im,cv2.COLOR_BGR2RGB)
   res=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
   if len(res.face_landmarks)!=1:continue
   p=res.face_landmarks[0];crop=face_crop(p,r['width'],r['height']);a,b,c,d=crop
   if c-a<130 or d-b<130:continue
   rr={**r,'reviewIndex':len(candidates),'crop':crop,'landmarks':[dict(x=v.x,y=v.y,z=v.z) for v in p],'blendshapes':{v.category_name:v.score for v in res.face_blendshapes[0]},'reviewTargets':targets}
   candidates.append(rr)
   for t in targets:quotas[(t,r['split'])]+=1
   if len(candidates)%12==0:print('review prepared',source,len(candidates),flush=True)
 detector.close();write('review/candidates.json',dict(manifestSHA256=sha(OUT/'manifest.json'),rows=candidates,predictionsUsed=False,expertReview=False,finalTestOpened=False))
 for start in range(0,len(candidates),12):
  sheet=Image.new('RGB',(1440,4*410),(12,18,30));draw=ImageDraw.Draw(sheet)
  for k,r in enumerate(candidates[start:start+12]):
   im=cv2.imread(r['absolutePath']);a,b,c,d=r['crop'];im=im[b:d,a:c];factor=min(470/im.shape[1],350/im.shape[0]);thumb=cv2.resize(im,None,fx=factor,fy=factor);x=k%3*480;y=k//3*410
   raw=thumb[:,:,::-1].copy();over=raw.copy()
   for j,t in enumerate(TARGETS):
    mask=annotation_mask(r,t)[b:d,a:c];mask=cv2.resize(mask,(thumb.shape[1],thumb.shape[0]),interpolation=cv2.INTER_NEAREST)>0
    color=np.array([(j*53+30)%255,(j*79+70)%255,(j*31+180)%255]);over[mask]=(over[mask]*.75+color*.25).astype('uint8')
   sheet.paste(Image.fromarray(over),(x,y));draw.text((x+4,y+355),f"{r['reviewIndex']} {r['source']} {r['split']} {','.join(r['reviewTargets'])}",fill='white');draw.text((x+4,y+373),r['sha256'][:18],fill='white')
  sheet.save(folder/f'sheet-{start//12:02d}.jpg')
 print('review',len(candidates),'photos',flush=True)

if __name__=='__main__':main()
