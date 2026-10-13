"""Material feature identity/split and observed contour support contracts."""
import sys
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import material_component_features as M
import contour_appearance as C

def test_square_crops_preserve_rgb_contract_and_do_not_invent_pixels():
    image=np.zeros((100,140,3),np.uint8);image[:]=(10,80,200);before=image.copy();row=dict(rect=[50,30,10,8])
    crops,boxes=M.component_crops(image,row,1.)
    for crop,box in zip(crops,boxes):
        center=crop[:,112,112];assert np.allclose(center,(np.array([200,80,10])/255-M.MEAN[0,0])/M.STD[0,0],atol=1e-6)
        assert crop.shape==(3,224,224) and box['sourcePixelsNotAdded']
    assert boxes[1]['width']>boxes[0]['width'] and np.array_equal(image,before)

def test_feature_ring_excludes_candidate_pixels_and_geometry_scales():
    image=np.full((96,96,3),100,np.uint8);image[30:40,30:40]=160;field=np.zeros((96,96),np.float32);field[30:40,30:40]=.5
    ids,rows=M.describe(image,field,1.)
    assert len(rows)==1 and rows[0]['geometry'][5]==pytest.approx(60/255,abs=1e-6)
    big=cv2.resize(image,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST);f=cv2.resize(field,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST);_,b=M.describe(big,f,2.)
    assert b[0]['geometry'][0]==pytest.approx(rows[0]['geometry'][0])
    assert b[0]['geometry'][5]==pytest.approx(rows[0]['geometry'][5],abs=1e-6)

def test_train_only_scaler_is_exact_and_no_validation_enters_fit():
    X=np.array([[1,2],[2,4],[3,7],[4,9]],float);model=M.fit_classifier(X,[0,0,1,1],['a','a','b','b'])
    assert np.array_equal(model['mean'],X.mean(0)) and model['trainGroups']==['a','b']
    before=list(model['mean']);M.predict(np.array([[999,-999]]),model);assert model['mean']==before

def test_contour_local_fit_excludes_center_and_never_bridges_holes():
    x=np.arange(96);track=np.c_[x,50+.001*x*x];normal=np.tile([0.,1.],(96,1));seen=np.ones(96,bool)
    ordinary=C.contour_prominence(track,seen,normal,320)
    assert not ordinary['accepted'].any()
    changed=track.copy();changed[45:52,1]+=5
    prominent=C.contour_prominence(changed,seen,normal,320)
    assert prominent['excursion'][48]==pytest.approx(5/320)
    seen[44:52]=False;changed[44:52]=np.nan
    fragmented=C.contour_prominence(changed,seen,normal,320)
    assert not fragmented['accepted'][44:52].any() and np.isnan(fragmented['excursion'][44:52]).all()

def synthetic_boundary(bulge=False,factor=1.):
    yy,xx=np.mgrid[:160,:240];line=75+.0003*(xx-120)**2
    if bulge:line+=9*np.exp(-((xx-120)/12)**2)
    image=np.empty((160,240,3),np.uint8);image[:]=(45,50,55);image[yy<line]=(80,120,165)
    image=cv2.resize(image,None,fx=factor,fy=factor,interpolation=cv2.INTER_NEAREST);guide=np.array([[35,77],[120,75],[205,77]],float)*factor
    return image,guide,np.ones(image.shape[:2],bool)

def test_real_boundary_support_is_not_a_landmark_curve_or_a_fold():
    image,guide,eligible=synthetic_boundary();normal=C.trace_boundary(image,guide,eligible,320,np.array([120,0]));assert normal['reason'] is None and normal['value']==0
    no_edge=C.trace_boundary(np.full_like(image,140),guide,eligible,320,np.array([120,0]));assert no_edge['reason']=='IMAGE_BOUNDARY_NOT_TRACKABLE' and np.isnan(no_edge['tracked']).all()
    image,guide,eligible=synthetic_boundary(True);positive=C.trace_boundary(image,guide,eligible,320,np.array([120,0]));assert positive['accepted'].any() and positive['value']>0
    pts=positive['tracked'][positive['accepted']];assert ((pts[:,0]>90)&(pts[:,0]<150)).all()

def test_contour_support_location_survives_source_scaling():
    traces=[]
    for factor in [1.,2.]:
        im,guide,mask=synthetic_boundary(True,factor);r=C.trace_boundary(im,guide,mask,320*factor,np.array([120,0])*factor);assert r['reason'] is None
        traces.append(r['tracked'][r['accepted']]/factor)
    assert abs(len(traces[0])-len(traces[1]))<=5
    assert np.linalg.norm(np.mean(traces[0],0)-np.mean(traces[1],0))<4

def test_skin_to_neck_shadow_is_not_external_contour_evidence():
    image,guide,eligible=synthetic_boundary(True);inside=np.array([80,120,165]);outside=(inside*.35).astype(np.uint8);old=(image[:,:,0]==45);image[old]=outside
    q=C.trace_boundary(image,guide,eligible,320,np.array([120,0]))
    assert q['rawBrightnessEdgeRows']>50 and q['exteriorConfirmedRows']==0
    assert q['value'] is None and q['reason']=='IMAGE_BOUNDARY_NOT_TRACKABLE'

def test_controlled_half_crop_keeps_original_source_context_extent():
    image=np.full((128,128,3),120,np.uint8);row={'rect':[50,50,6,6]}
    _,native=M.component_crops(image,row,1.,1.)
    half=cv2.resize(image,None,fx=.5,fy=.5);_,scaled=M.component_crops(half,{'rect':[25,25,3,3]},.5,.5)
    assert native[0]['width']==2*scaled[0]['width'] and native[1]['width']==2*scaled[1]['width']

def test_contour_roll_normalization_keeps_true_source_support_location():
    image,guide,mask=synthetic_boundary(True);original=C.trace_boundary(image,guide,mask,320,np.array([120,0]))
    transform=cv2.getRotationMatrix2D((120,80),10,1);rotated=cv2.warpAffine(image,transform,(240,160),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    project=lambda xy:np.c_[xy,np.ones(len(xy))]@transform.T
    q=C.trace_boundary(rotated,project(guide),mask,320,project(np.array([[120,0]]))[0]);assert q['reason'] is None and q['accepted'].any()
    inverse=cv2.invertAffineTransform(transform);points=np.c_[q['tracked'][q['accepted']],np.ones(int(q['accepted'].sum()))]@inverse.T
    expected=original['tracked'][original['accepted']]
    assert np.linalg.norm(points.mean(0)-expected.mean(0))<4

def test_material_confidence_changes_cannot_change_accepted_pixel_score():
    class FakeFrozenEncoder:
        def extract(self,crops,batch):
            assert batch==4
            return np.zeros((len(crops),1280),np.float32)
    image=np.full((80,100,3),120,np.uint8);image[30:40,40:50]=160;field=np.zeros((80,100),np.float32);field[30:40,40:50]=.3;before=field.copy()
    head=dict(mean=np.zeros(2572).tolist(),std=np.ones(2572).tolist(),coefficients=np.zeros(2572).tolist(),intercept=2.,threshold=.5)
    a,_=M.filter_material_support(image,field,1.,FakeFrozenEncoder(),head);head['intercept']=12.;b,_=M.filter_material_support(image,field,1.,FakeFrozenEncoder(),head)
    assert np.array_equal(a,b) and np.array_equal(a,before) and np.array_equal(field,before)

def test_encoder_refuses_unverified_or_skin_type_weights(tmp_path):
    file=tmp_path/'wrong.safetensors';file.write_bytes(b'not original ImageNet')
    with pytest.raises(AssertionError,match='ImageNet encoder identity'):M.FrozenMaterialEncoder(file)
