"""Observed anatomical non-skin is loss-unknown, never new healthy truth."""
import sys
import cv2,numpy as np
from expanded_sources import ROOT
sys.path.insert(0,str(ROOT/'services/core-api'))
from appearance_analysis import elongated_dark_mask

def anatomical_skin_scope(row,image):
 h,w=image.shape[:2];points=np.array([[p['x']*w,p['y']*h] for p in row['landmarks']],np.float32);scope=np.zeros((h,w),np.uint8)
 oval=[10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
 cv2.fillPoly(scope,[np.rint(points[oval]).astype(np.int32)],1)
 for indices in [[33,160,158,133,153,144],[263,387,385,362,380,373],[61,40,37,0,267,270,291,321,314,17,84,91],[98,97,2,326,327,294],[70,63,105,66,107,55,65,52],[300,293,334,296,336,285,295,282]]:cv2.fillPoly(scope,[np.rint(points[indices]).astype(np.int32)],0)
 return scope

def known_skin_scope(row,image):
 scope=anatomical_skin_scope(row,image)
 scope[elongated_dark_mask(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY))]=0
 return scope
