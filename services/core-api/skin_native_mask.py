"""Native 256 RGB shared-mask adapter; isolated until per-target acceptance.

Each target uses a pinned FULL encoder/decoder checkpoint and channel. Binary
presence area is an appearance density, never clinical severity/confidence.
"""
import cv2,numpy as np

TARGETS=['acne','oil','redness','tone','lines','dark','bags']
MEAN=np.array([.485,.456,.406],np.float32)[:,None,None]
STD=np.array([.229,.224,.225],np.float32)[:,None,None]
CONTRACT=dict(version='native-rgb-shared-mask-256-v2',tile=256,stride=192,pad=114,
              channelOrder=TARGETS,RGB=True,mean=[.485,.456,.406],std=[.229,.224,.225],
              resize=False,coordinateSpace='source-pixels',overlapMerge='binary OR',threshold=.5)

def rects(crop):
 a,b,c,d=crop;size=256
 xs=sorted(set([*range(a,max(a+1,c-size+1),192),max(a,c-size)]))
 ys=sorted(set([*range(b,max(b+1,d-size+1),192),max(b,d-size)]))
 return [(x,y,min(c,x+size),min(d,y+size)) for x in xs for y in ys]

def tensor(bgr,rect):
 a,b,c,d=rect;rgb=np.full((256,256,3),114,np.uint8);rgb[:d-b,:c-a]=bgr[b:d,a:c,::-1]
 return ((rgb.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD)[None].copy()

def infer_native_mask(bgr,session,metadata,target,crop,visible_support):
 if target not in TARGETS or metadata.get('preprocessing')!=CONTRACT:raise ValueError('NATIVE_MASK_CONTRACT_MISMATCH')
 if metadata.get('channel')!=TARGETS.index(target) or not metadata.get('sha256'):raise ValueError('NATIVE_MASK_FULL_MODEL_CHANNEL_REQUIRED')
 h,w=bgr.shape[:2];a,b,c,d=crop
 if not 0<=a<c<=w or not 0<=b<d<=h or visible_support.shape!=(h,w):raise ValueError('NATIVE_MASK_SOURCE_GEOMETRY')
 tiles=rects(crop)
 if len(tiles)>128:raise ValueError('NATIVE_MASK_TILE_BUDGET')
 mask=np.zeros((h,w),bool)
 for rect in tiles:
  a,b,c,d=rect;logits=session.run(None,{'native_rgb_tile':tensor(bgr,rect)})[0]
  if logits.shape!=(1,7,256,256) or not np.isfinite(logits).all():raise ValueError('NATIVE_MASK_OUTPUT_CONTRACT')
  # threshold .5 sigmoid == logits >= 0; no confidence-to-severity conversion.
  mask[b:d,a:c]|=logits[0,metadata['channel'],:d-b,:c-a]>=0
 evaluated=np.zeros((h,w),bool);a,b,c,d=crop;evaluated[b:d,a:c]=visible_support[b:d,a:c].astype(bool)
 mask&=evaluated
 area=int(evaluated.sum());positive=int(mask.sum())
 return dict(mask=mask,modelSHA256=metadata['sha256'],channel=metadata['channel'],
             coordinateSpace='source-pixels',tileCount=len(tiles),visiblePixels=area,
             predictedPixels=positive,appearanceDensityPercent=positive/area*100 if area else None,
             clinicalSeverity=False,normalizationVersion='visible-predicted-mask-area-v2')
