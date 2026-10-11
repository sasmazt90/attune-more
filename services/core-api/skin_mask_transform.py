"""Shared source-coordinate RGB/letterbox transform; display zoom is absent."""
import cv2,numpy as np
MEAN=np.array([.485,.456,.406],np.float32)[:,None,None]
STD=np.array([.229,.224,.225],np.float32)[:,None,None]

def mask_input(bgr,rect,size=256):
 a,b,c,d=map(int,rect);h0,w0=bgr.shape[:2]
 if not 0<=a<c<=w0 or not 0<=b<d<=h0:raise ValueError('INVALID_SOURCE_ROI')
 rgb=bgr[b:d,a:c,::-1];h,w=rgb.shape[:2];s=min(size/w,size/h);nw,nh=round(w*s),round(h*s);ox=(size-nw)//2;oy=(size-nh)//2
 canvas=np.zeros((size,size,3),np.uint8);canvas[oy:oy+nh,ox:ox+nw]=cv2.resize(rgb,(nw,nh),interpolation=cv2.INTER_AREA)
 x=((canvas.transpose(2,0,1).astype(np.float32)/255-MEAN)/STD)[None].copy()
 return x,dict(sourceRect=[a,b,c,d],resizeScaleXY=[nw/w,nh/h],padding=[ox,oy],size=[nw,nh],sourcePixels=[w,h],inputSize=size,sourceWidth=w0,sourceHeight=h0,RGB=True,coordinateSpace='source-pixels')

def restore_mask(values,transform):
 """Remove actual integer padding before mapping each channel into original ROI."""
 a,b,c,d=transform['sourceRect'];ox,oy=transform['padding'];nw,nh=transform['size']
 value=np.asarray(values,np.float32)
 if value.ndim!=3 or value.shape[-2:]!=(transform['inputSize'],transform['inputSize']) or not np.isfinite(value).all():raise ValueError('INVALID_MASK_OUTPUT')
 return np.stack([cv2.resize(v[oy:oy+nh,ox:ox+nw],(c-a,d-b),interpolation=cv2.INTER_LINEAR) for v in value])
