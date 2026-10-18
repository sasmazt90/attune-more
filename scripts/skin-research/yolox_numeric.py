"""Bound decoded dimensions in native tile units before exp(), in train/export.

Unassigned coarse anchors can diverge under partial-label objectness training.
Unbounded exp overflow produces NaN even when their IoU loss is unused. Keep
the positive decoded size in .1..2*tile pixels; never disable gradient checks.
"""
import math,torch

def bounded_regression(output,stride,size=384):
 return torch.cat([output[:,:2],output[:,2:4].clamp(math.log(.1/stride),math.log(2*size/stride))],1)

def install_bounds(net,size=384):
 if getattr(net.head,'native_dimension_bounds',None):return
 net.head.native_dimension_bounds=dict(version='native-exp-dimension-bounds-v1',minimumPixels=.1,maximumPixels=2*size)
 for conv,stride in zip(net.head.reg_preds,net.head.strides):
  conv.register_forward_hook(lambda module,inputs,output,s=stride:bounded_regression(output,s,size))
