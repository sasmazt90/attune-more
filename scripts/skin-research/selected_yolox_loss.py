"""Mask unknown YOLOX objectness cells while preserving all assigned positives."""
import torch
from torch import nn

class KnownObjectnessBCE(nn.Module):
 def __init__(self):super().__init__();self.known=None
 def forward(self,logits,truth):
  values=nn.functional.binary_cross_entropy_with_logits(logits,truth,reduction='none')
  if self.known is not None and logits.shape==self.known.shape:
   values=values*((truth>0)|self.known).to(values.dtype)
  return values

def known_cells(source_roi,tile_rect,fully_reviewed,strides=(8,16,32),size=384):
 import numpy as np
 a,b,c,d=tile_rect;values=[]
 for stride in strides:
  side=size//stride;xx,yy=np.meshgrid((np.arange(side)+.5)*stride+a,(np.arange(side)+.5)*stride+b);x=xx.astype(int);y=yy.astype(int)
  inside=(x<c)&(y<d)&(x>=0)&(y>=0)&(x<source_roi.shape[1])&(y<source_roi.shape[0]);safe_x=np.clip(x,0,source_roi.shape[1]-1);safe_y=np.clip(y,0,source_roi.shape[0]-1)
  values.append((inside&source_roi[safe_y,safe_x].astype(bool)&bool(fully_reviewed)).ravel())
 return torch.from_numpy(np.concatenate(values)[:,None])
