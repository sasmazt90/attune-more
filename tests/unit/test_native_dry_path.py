"""Native source-area plumbing and exclusion regressions; no accuracy claims."""
import base64,sys
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'))
import native_flake_support as F
import native_dry_path as N
import appearance_analysis as A
from test_local_appearance_health import skin_input

def decode(url):return cv2.imdecode(np.frombuffer(base64.b64decode(url.split(',')[1]),np.uint8),cv2.IMREAD_UNCHANGED)

def test_overlapping_native_tiles_preserve_grid_deduplicate_and_clip(monkeypatch):
    image=np.zeros((1400,1700,3),np.uint8);image[500:515,510:530]=255;before=image.copy();eligible=np.ones(image.shape[:2],bool);eligible[:,520:]=False;sizes=[]
    def proposal(tile,*args,**kwargs):
        sizes.append(tile.shape[:2]);return (tile[:,:,0]>0).astype(np.float32)*.5
    monkeypatch.setattr(F,'proposal_tile',proposal)
    field,metadata=F.native_field(image,1.25,eligible)
    expected=(image[:,:,0]>0)&eligible
    assert np.array_equal(field>0,expected) and np.array_equal(image,before)
    assert int((field>0).sum())==150 and float(field.sum())==75
    assert metadata['tiles']>1 and metadata['peakTilePixels']<=612**2
    assert max(max(s) for s in sizes)<=612 and not metadata['analysisResize']

def test_display_max_pool_retains_tiny_material_without_changing_score():
    field=np.zeros((1027,901),np.float32);known=np.ones_like(field,bool);field[515,333]=.4
    count=int((field>0).sum());pooled,valid,step=F.pool_for_display(field,known,256)
    assert step==5 and pooled[515//step,333//step]==.4 and (pooled>0).sum()==1
    assert (field>0).sum()==count and valid.all()

def test_native_anatomical_score_map_and_overview_share_unique_source(monkeypatch):
    image=np.full((800,1000,3),140,np.uint8);payload=skin_input(image);original=A.analyze_skin(payload);source_before=image.copy()
    # A real one-source-pixel proposal intentionally straddles overlapping
    # region ownership. Plumbing must preserve it once, without score flooring.
    def proposal(crop,metric,eligible,check=None):
        field=np.zeros(crop.shape[:2],np.float32);yy,xx=np.where(eligible);field[yy[len(yy)//2],xx[len(xx)//2]]=.5
        return field,dict(analysisResize=False,tileCore=512)
    monkeypatch.setattr(N,'native_field',proposal)
    result=N.analyze_native_dry(payload);assert result['general']['value']>0
    assert result['general']['components']['acceptedMaterialSourcePixels']==1
    values=[]
    for region,row in result['measurements'].items():
        if row['value'] is None:continue
        values.append(row['value']);assert row['value']==pytest.approx(100/row['evaluatedArea']['sourcePixels'])
        layer=result['maps'][region+':dry'];rgba=decode(layer['dataUrl']);valid=decode(layer['validMaskUrl'])>0;active=rgba[:,:,3]>0
        assert active.sum()==1 and not (active&~valid).any() and layer['step']==1
        ys,xs=np.where(active);sx=int(xs[0]+layer['x']);sy=int(ys[0]+layer['y'])
        assert A.closed_surface_mask(image.shape[:2],payload['meshes'][region],1)[sy,sx]
        assert layer['photoId']==payload['photoId'] and layer['nativeScoreSourcePixels']==1
    assert values and all(v<.01 for v in values) # no artificial 1% floor
    assert result['general']['value']==values[0] # union, not sum of six regions
    after=A.analyze_skin(payload)
    assert np.array_equal(image,source_before)
    for key in ['measurements','maps','contours']:assert after[key]==original[key]
    assert after['general']['measurements']==original['general']['measurements']
    assert result['nativeMetadata']['normalProductEnabled'] is False

@pytest.mark.parametrize('case',['quality','exposure','detail'])
def test_unmeasurable_native_quality_never_becomes_healthy_zero(case,monkeypatch):
    image=np.full((800,1000,3),255 if case=='exposure' else 140,np.uint8)
    if case=='detail':image=cv2.resize(image,(160,128))
    payload=skin_input(image)
    if case=='quality':payload['qualityValid']=False
    monkeypatch.setattr(N,'native_field',lambda crop,metric,eligible,check=None:(np.zeros(crop.shape[:2],np.float32),{}))
    result=N.analyze_native_dry(payload)
    assert all(r['value'] is None for r in result['measurements'].values()) and not result['maps']

def test_native_proposal_preserves_input_and_has_no_uniform_glare_support():
    image=np.full((128,192,3),180,np.uint8);before=image.copy();field=F.proposal_tile(image,.5)
    assert not field.any() and np.array_equal(image,before)

def test_native_source_hash_rejects_changed_image():
    payload=skin_input(np.full((400,500,3),140,np.uint8));payload['photoId']='0'*64
    with pytest.raises(ValueError,match='SOURCE_HASH_MISMATCH'):N.analyze_native_dry(payload)
