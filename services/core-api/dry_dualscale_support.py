"""Staging-only accepted support union. No detector, head, labels or scale choice.

Coordinates are image-edge coordinates: source pixel (x,y) has center
(x+.5,y+.5). A sampled pixel owns [j/f,(j+1)/f) from its integer source
origin. Copy its value only to original pixel centers in that cell; do not
interpolate, dilate, clamp missing edge cells or sum overlapping support.
"""
from dataclasses import dataclass
import numpy as np

VERSION='native-half-accepted-source-max-v1-staging'
COORDINATES='source-center-owned-sampled-cells-v1'
OPTICAL_CUTOFF=.04

@dataclass
class SupportUnion:
    native:np.ndarray
    combined:np.ndarray
    metadata:dict

def project_sampled_cells(field,source_shape,origin,factor,visible_source):
    """Original-grid cell ownership; outside sampled extent stays zero."""
    field=np.asarray(field)
    if field.ndim!=2 or not np.isfinite(field).all() or (field<0).any():raise ValueError('INVALID_ACCEPTED_FIELD')
    if len(source_shape)!=2 or any(type(v) is not int or v<=0 for v in source_shape):raise ValueError('INVALID_SOURCE_SHAPE')
    if len(origin)!=2 or any(type(v) is not int for v in origin):raise ValueError('INTEGER_SOURCE_ORIGIN_REQUIRED')
    if factor not in (1.,.5):raise ValueError('ONLY_FIXED_NATIVE_HALF_SUPPORTED')
    visible=np.asarray(visible_source)
    if visible.shape!=tuple(source_shape) or visible.dtype!=np.bool_:raise ValueError('ORIGINAL_VISIBLE_MASK_REQUIRED')
    h,w=source_shape;ox,oy=origin
    xs=np.floor(((np.arange(w,dtype=np.float64)+.5)-ox)*factor).astype(np.int64)
    ys=np.floor(((np.arange(h,dtype=np.float64)+.5)-oy)*factor).astype(np.int64)
    xx=np.flatnonzero((xs>=0)&(xs<field.shape[1]));yy=np.flatnonzero((ys>=0)&(ys<field.shape[0]))
    result=np.zeros(source_shape,np.float32)
    if len(xx) and len(yy):result[np.ix_(yy,xx)]=field[np.ix_(ys[yy],xs[xx])]
    result[~visible]=0
    return result

def merge_accepted_supports(native_field,half_field,*,source_shape,native_origin,half_origin,visible_source):
    """The SAME fixed rule for replay or a future anatomical runtime adapter.

    visible_source must come from the original source, never an enlarged
    prediction denominator. Optical replay supplies only its recorded optical
    domain; it must not claim that domain is a product anatomical mask.
    """
    if np.asarray(visible_source).shape!=tuple(source_shape) or np.asarray(visible_source).dtype!=np.bool_:raise ValueError('ORIGINAL_VISIBLE_MASK_REQUIRED')
    native=project_sampled_cells(native_field,source_shape,native_origin,1.,np.ones(source_shape,bool))
    if ((native>OPTICAL_CUTOFF)&~visible_source).any():raise ValueError('NATIVE_SUPPORT_OUTSIDE_VISIBLE_MASK')
    native[~visible_source]=0
    half=project_sampled_cells(half_field,source_shape,half_origin,.5,visible_source)
    combined=np.maximum(native,half)
    active=native>OPTICAL_CUTOFF;merged=combined>OPTICAL_CUTOFF
    return SupportUnion(native,combined,dict(version=VERSION,coordinates=COORDINATES,scales=[1.,.5],aggregation='max/OR',nativeAcceptedSourcePixels=int(active.sum()),combinedAcceptedSourcePixels=int(merged.sum()),addedAcceptedSourcePixels=int((merged&~active).sum()),nativeLostSourcePixels=int((active&~merged).sum()),visibleSourcePixels=int(visible_source.sum()),overlapCountedOnce=True,interpolation=False,dilation=False,labelsAsInput=False))
