"""Meaningful boundaries: invalid geometry, unknown losses, unavailable zero."""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
sys.path.insert(0,str(ROOT/'services/core-api'))
from selected_sources import geometry,MAP
from skin_measurement_contract import attach_measurement_receipt

def test_boxes_rectangles_and_invalid_polygons_never_become_pixel_truth():
 box=geometry({'label':'Acne','bbox':[1,2,4,5]},20,20)
 rect=geometry({'label':'Wrinkles','bbox':[1,1,8,8],'segmentation':[[1,1,9,1,9,9,1,9]]},20,20)
 bad=geometry({'label':'Wrinkles','bbox':[1,1,8,8],'segmentation':[[1,1,30,1,2,4]]},20,20)
 assert box['validBox'] and not box['validMask']
 assert rect['kind']=='rectangle-polygon' and not rect['validMask']
 assert not bad['validMask'] and bad['kind']=='invalid-polygon'
 assert MAP['smart'].get('Post acne') is None and MAP['skin5'].get('melasma') is None

def test_real_coco_rle_and_rectangle_annotations_remain_distinct():
 import pytest
 M=pytest.importorskip('pycocotools.mask')
 mask=np.zeros((20,30),np.uint8);mask[3:8,4:9]=1;rle=M.encode(np.asfortranarray(mask));rle['counts']=rle['counts'].decode('ascii')
 r=geometry({'label':'Oily','bbox':[4,3,5,5],'segmentation':rle},30,20)
 assert r['kind']=='rle' and r['validMask'] and r['segmentation']['counts']==rle['counts']

def test_unknown_mask_pixels_have_no_gradient_and_targets_overlap():
 import torch
 from selected_mask_model import masked_loss
 logits=torch.randn(1,7,12,12,requires_grad=True);truth=torch.zeros_like(logits);support=torch.zeros_like(logits)
 truth[:,0,2:5,2:5]=1;truth[:,1,2:5,2:5]=1;support[:,:2,1:8,1:8]=1
 masked_loss(logits,truth,support).backward()
 assert torch.count_nonzero(logits.grad[support==0])==0
 assert torch.count_nonzero(logits.grad[:,0])>0 and torch.count_nonzero(logits.grad[:,1])>0
 empty=torch.randn(1,7,12,12,requires_grad=True);v=masked_loss(empty,torch.zeros_like(empty),torch.zeros_like(empty));v.backward()
 assert v.item()==0 and torch.count_nonzero(empty.grad)==0

def test_different_calibrations_do_not_share_a_history_line():
 import subprocess
 script="""
 require('./tests/unit/ts_loader.js');const assert=require('assert/strict');const {canCompareIndicator}=require('./apps/vehicle-app/src/utils/skinIndicators.ts');
 const a={id:'oil',method:'appearance-cv-6',unit:'%',appearance:{normalizationVersion:'area-v1',calibrationVersion:'calibration-v1'},measurement:{scope:'regional',region:'nose',methodVersion:'appearance-cv-6',modelHash:null,unit:'percent-visible-area',validation:'appearance-proxy'}};
 const b=structuredClone(a);assert(canCompareIndicator(a,b));b.appearance.calibrationVersion='calibration-v2';assert(!canCompareIndicator(a,b));delete b.appearance.calibrationVersion;assert(!canCompareIndicator(a,b));
 """
 r=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,timeout=30)
 assert r.returncode==0,r.stderr

def test_measured_zero_and_unavailable_are_different_and_coverage_is_explicit():
 good=attach_measurement_receipt(dict(quality='valid',value=0.,normalizationVersion='area-v1',evaluatedArea=dict(sourcePixels=40,anatomicalSourcePixels=100)))
 bad=attach_measurement_receipt(dict(quality='insufficient',value=None,limitationCode='OCCLUDED'))
 assert good['status']=='measured' and good['coverage']==.4 and good['calibrationVersion']=='area-v1'
 assert bad['status']=='unavailable' and bad['reason']=='OCCLUDED' and bad['coverage'] is None

def test_letterbox_padding_is_removed_in_source_coordinates():
 from skin_mask_transform import mask_input,restore_mask
 bgr=np.full((180,300,3),[12,80,190],np.uint8);x,t=mask_input(bgr,[25,30,275,130]);assert x.shape==(1,3,256,256) and t['sourceRect']==[25,30,275,130]
 values=np.zeros((7,256,256),np.float32);ox,oy=t['padding'];nw,nh=t['size'];values[:,oy:oy+nh,ox:ox+nw]=.75
 restored=restore_mask(values,t);assert restored.shape==(7,100,250) and np.allclose(restored,.75)

def test_yolox_unknown_objectness_has_zero_gradient_and_positive_stays_supervised():
 import torch
 from selected_yolox_loss import KnownObjectnessBCE,known_cells
 loss=KnownObjectnessBCE();loss.known=torch.tensor([[False],[True],[False]])
 logits=torch.zeros(3,1,requires_grad=True);truth=torch.tensor([[0.],[0.],[1.]])
 loss(logits,truth).sum().backward();assert logits.grad[0]==0 and logits.grad[1]>0 and logits.grad[2]<0
 roi=np.ones((300,300),np.uint8);cells=known_cells(roi,[0,0,300,300],False);assert not cells.any()
 assert known_cells(roi,[0,0,300,300],True).sum()<3024,'padding is unknown'
