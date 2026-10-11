"""Actual tensors, known support and independent channels on source crops."""
import json
import cv2,numpy as np
from PIL import Image,ImageDraw
from selected_sources import OUT,TARGETS,write
from train_selected_local import reviewed,mask_tensor

def main():
 rows=reviewed();chosen=[r for r in rows if r['split']=='train' and r['source']=='v11'][:4]
 canvas=Image.new('RGB',(1536,4*360),(12,18,30));draw=ImageDraw.Draw(canvas);proof=[]
 for i,r in enumerate(chosen):
  x,y,s,t=mask_tensor(r);a,b,c,d=r['crop'];raw=cv2.imread(r['absolutePath'])[b:d,a:c,::-1].copy()
  normalized=x.numpy();tensor=np.clip((normalized*np.asarray([.229,.224,.225])[:,None,None]+np.asarray([.485,.456,.406])[:,None,None])*255,0,255).astype(np.uint8).transpose(1,2,0)
  positive=y.numpy();known=s.numpy();overlay=tensor.copy();unknown=np.logical_not(known.any(axis=0));overlay[unknown]=(overlay[unknown]*.25).astype('uint8')
  for j,target in enumerate(TARGETS):
   mask=positive[j]>0;color=np.asarray([(j*53+30)%255,(j*79+70)%255,(j*31+180)%255]);overlay[mask]=(overlay[mask]*.5+color*.5).astype('uint8')
  for k,im in enumerate([raw,tensor,overlay]):
   factor=min(500/im.shape[1],315/im.shape[0]);thumb=cv2.resize(im,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA);canvas.paste(Image.fromarray(thumb),(k*512,i*360))
   draw.text((k*512+4,i*360+320),['Source crop','Actual RGB letterbox tensor','Actual truth/support; dark = unknown'][k],fill='white')
  draw.text((4,i*360+338),r['sha256'][:20],fill='white');proof.append(dict(sourceSHA256=r['sha256'],inputShape=list(x.shape),targetShape=list(y.shape),knownPixels={target:int(known[j].sum()) for j,target in enumerate(TARGETS)},positivePixels={target:int(positive[j].sum()) for j,target in enumerate(TARGETS)},transform=t,unknownGradientPolicy='excluded',paddingUnknown=True))
 canvas.save(OUT/'mask/actual-tensor-truth.jpg');write('mask/actual-tensor-truth.json',dict(rows=proof,predictorGeneratedTruth=False))
if __name__=='__main__':main()
