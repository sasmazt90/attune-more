"""Small shared ResNet18 U-Net with independent sigmoid targets (no softmax)."""
import torch
import json
from torch import nn
from torchvision.models import resnet18
from safetensors.torch import load_file
from prepare_focused_data import OUT as OLD
from selected_sources import TARGETS
from prepare_focused_data import sha

class Block(nn.Sequential):
 def __init__(self,a,b):
  super().__init__(nn.Conv2d(a,b,3,padding=1),nn.GroupNorm(8,b),nn.ReLU(),nn.Conv2d(b,b,3,padding=1),nn.GroupNorm(8,b),nn.ReLU())

class SkinUNet(nn.Module):
 def __init__(self):
  super().__init__();self.encoder=resnet18(weights=None)
  path=OLD/'pretrained/resnet18-f37072fd.pth.safetensors';rights=json.loads((OLD/'pretrained/rights.json').read_text());record=next(r for r in rights if r['file']=='resnet18-f37072fd.pth');assert sha(path)==record['safeSHA256']
  self.encoder.load_state_dict(load_file(str(path)))
  self.d4=Block(512+256,128);self.d3=Block(128+128,64);self.d2=Block(64+64,32);self.d1=Block(32+64,16);self.head=nn.Conv2d(16,len(TARGETS),1)
 def forward(self,x):
  e=self.encoder;a=e.relu(e.bn1(e.conv1(x)));b=e.layer1(e.maxpool(a));c=e.layer2(b);d=e.layer3(c);f=e.layer4(d)
  up=lambda u,v:nn.functional.interpolate(u,size=v.shape[-2:],mode='bilinear',align_corners=False)
  z=self.d4(torch.cat([up(f,d),d],1));z=self.d3(torch.cat([up(z,c),c],1));z=self.d2(torch.cat([up(z,b),b],1));z=self.d1(torch.cat([up(z,a),a],1));return nn.functional.interpolate(self.head(z),size=x.shape[-2:],mode='bilinear',align_corners=False)

def masked_loss(logits,truth,support,balanced=False,target_weights=None,image_balanced=False):
 """Unobserved channel/pixel has exactly zero contribution and gradient."""
 if not bool(support.any()):return logits.sum()*0
 bce=nn.functional.binary_cross_entropy_with_logits(logits,truth,reduction='none');den=support.sum().clamp_min(1)
 if image_balanced:
  values=[];weights=[]
  for j in range(logits.shape[1]):
   images=[]
   for i in range(logits.shape[0]):
    known=support[i,j]>0;positive=known&(truth[i,j]>0);negative=known&~positive
    if not bool(known.any()):continue
    parts=[bce[i,j][m].mean() for m in (positive,negative) if bool(m.any())]
    value=torch.stack(parts).mean()
    if bool(positive.any()):
     p=logits[i,j].sigmoid();y=truth[i,j];s=support[i,j]
     value=value+1-(2*(p*y*s).sum()+1)/((p*s).sum()+(y*s).sum()+1)
    images.append(value)
   if images:
    weight=1. if target_weights is None else float(target_weights[j]);values.append(torch.stack(images).mean()*weight);weights.append(weight)
  return torch.stack(values).sum()/sum(weights)
 if balanced:
  # Equal target contribution, then equal reviewed positive/negative
  # contribution within each target. Area is not a target's loss weight.
  values=[];weights=[]
  for j in range(logits.shape[1]):
   known=support[:,j]>0;positive=known&(truth[:,j]>0);negative=known&~positive
   if not bool(known.any()):continue
   parts=[bce[:,j][m].mean() for m in (positive,negative) if bool(m.any())]
   value=torch.stack(parts).mean()
   if bool(positive.any()):
    p=logits[:,j].sigmoid();y=truth[:,j];s=support[:,j]
    value=value+1-(2*(p*y*s).sum()+1)/((p*s).sum()+(y*s).sum()+1)
   weight=1. if target_weights is None else float(target_weights[j]);values.append(value*weight);weights.append(weight)
  return torch.stack(values).sum()/sum(weights)
 p=logits.sigmoid();valid=support.sum((0,2,3))>0
 dice=1-(2*(p*truth*support).sum((0,2,3))+1)/((p*support).sum((0,2,3))+(truth*support).sum((0,2,3))+1)
 return (bce*support).sum()/den+dice[valid].mean()
