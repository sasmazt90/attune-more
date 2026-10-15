"""Focused synthetic contracts, not evidence of human detection accuracy."""
import importlib.util,sys
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from acne_lab_dog import detect,candidate_result,match_boxes,CONFIG

def source():
 image=np.full((240,240,3),(120,150,180),np.uint8);yy,xx=np.mgrid[:240,:240];bump=np.exp(-((xx-120)**2+(yy-120)**2)/(2*3**2));image[:,:,2]=np.clip(image[:,:,2]+bump*65,0,255).astype(np.uint8)
 roi=np.zeros((240,240),bool);roi[20:220,20:220]=True
 return image,roi

def test_compact_color_support_is_deterministic_and_first_scan_independent():
 image,roi=source();a,mask,d=detect(image,roi,200);b,other,_=detect(image,roi,200)
 assert d['valid'] and a and np.array_equal(mask,other)
 first,map_=candidate_result(a,roi.shape);second,_=candidate_result(b,roi.shape)
 assert first==second and first['candidateCount']==len(first['candidates']) and map_.sum()==mask.sum()
 assert not (map_&~roi).any()

def test_empty_roi_is_unmeasurable_not_healthy_zero():
 image,roi=source();roi[:]=False;objects,mask,d=detect(image,roi,200)
 assert not objects and not mask.any() and d==dict(valid=False,reason='INSUFFICIENT_VISIBLE_ROI')

def test_uniform_roi_mad_zero_has_fixed_floor_no_spurious_candidate():
 image,roi=source();image[:]=(120,150,180);objects,mask,d=detect(image,roi,200)
 assert d['mad']==0 and d['threshold']==CONFIG['minimumAResponse'] and not objects and not mask.any()

def test_hair_glare_and_boundary_support_are_not_rescued():
 image,roi=source();image[30:200,70:72]=0;image[150:170,150:170]=255;roi[28:202,66:76]=False;roi[145:175,145:175]=False
 objects,mask,_=detect(image,roi,200)
 assert not mask[28:202,66:76].any() and not mask[145:175,145:175].any()
 # Identical real color center placed at the ROI edge cannot own complete support.
 edge=np.zeros_like(roi);edge[120:220,20:220]=True
 objects,mask,_=detect(image,edge,200);assert not mask[118:124,115:125].any()

def test_wrong_dtype_does_not_change_lab_channel_scale_silently():
 image,roi=source()
 with pytest.raises(ValueError,match='UINT8'):detect(image.astype('float32'),roi,200)
 with pytest.raises(ValueError,match='GEOMETRY'):detect(image,roi,0)

def test_origin_scale_and_unique_source_matching():
 obj=dict(x=4,y=6,width=2,height=2,areaPixels=4,pixels=np.array([[4,6],[5,6],[4,7],[5,7]]))
 result,mask=candidate_result([obj],(20,20),(10,30),.5);b=result['candidates'][0]
 assert [b[k] for k in ['x','y','width','height','areaPixels']]==[18,42,4,4,16]
 assert result['candidateCount']==1 and mask.sum()==4
 assert len(match_boxes([[0,0,10,10]],[[0,0,10,10],[0,0,10,10]]))==1

def test_detector_has_no_torch_network_or_personal_baseline_dependency():
 path=ROOT/'scripts/skin-research/acne_lab_dog.py';text=path.read_text('utf8')
 tree=__import__('ast').parse(text);imports=[v.names[0].name for v in tree.body if isinstance(v,__import__('ast').Import)]
 assert imports==['cv2','numpy']
 assert list(__import__('inspect').signature(detect).parameters)==['bgr','eligible','face_width']