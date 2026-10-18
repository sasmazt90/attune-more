"""Offline pigment-contrast hypothesis; no score inversion or pixel labels."""
import cv2,numpy as np

def tone_field(image,valid):
 lab=cv2.cvtColor(image.astype(np.float32)/255,cv2.COLOR_BGR2LAB);empty=np.zeros(valid.shape,np.float32)
 if valid.sum()<100:return empty,dict(reason='INSUFFICIENT_VISIBLE_SUPPORT')
 yy,xx=np.indices(valid.shape,dtype=np.float32);x=(xx-valid.shape[1]/2)/max(valid.shape[1],1);y=(yy-valid.shape[0]/2)/max(valid.shape[0],1)
 design=np.stack([np.ones_like(x),x,y,x*x,x*y,y*y],-1);a=design[valid];values=lab[:,:,0][valid]
 # Fixed deterministic source subsampling, no annotations/model predictions.
 stride=max(1,len(values)//5000);a=a[::stride];values=values[::stride];weights=np.ones(len(values))
 for _ in range(4):
  root=np.sqrt(weights);coef=np.linalg.lstsq(a*root[:,None],values*root,rcond=None)[0];residual=values-a@coef;scale=max(2.,float(np.median(np.abs(residual-np.median(residual)))*1.4826));weights=np.minimum(1.,2.5*scale/np.maximum(np.abs(residual),.001))
 reference=np.einsum('ijk,k->ij',design,coef);dark=np.maximum(0,reference-lab[:,:,0]-3.)
 center=np.median(lab[:,:,1:3][valid],axis=0);chroma=np.linalg.norm(lab[:,:,1:3]-center,axis=2)
 # Fixed CIELAB units; broad illumination is detrended rather than labelled
 # pigmentation. This cannot resolve every shadow/cosmetic from one photo.
 field=np.clip(np.hypot(chroma,dark),0,100).astype(np.float32)*valid
 return field,dict(version='offline-lab-pigment-detrended-v1',colorSpace='CIELAB',luminanceDeadband=3.,reference='robust observed quadratic illumination',pixelSeverityTruth=False,annotationLookup=False,coefficients=coef.tolist())
