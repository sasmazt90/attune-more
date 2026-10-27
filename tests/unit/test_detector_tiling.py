import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/skin-research'))
from detector_tiling import corner_tiles, map_predictions, suppress_duplicates


def prediction(x=20,y=30,label='Pimple',confidence=.8):
    return dict(x=x,y=y,width=10,height=12,confidence=confidence,**{'class':label})


def test_four_tiles_cover_original_frame_and_overlap():
    tiles=corner_tiles(1280,1280)
    assert tiles == [(0,0,768,768),(512,0,768,768),(0,512,768,768),(512,512,768,768)]
    assert corner_tiles(1,1)==[(0,0,1,1)]


def test_crop_offsets_preserve_original_pixel_geometry():
    p=map_predictions([prediction()],(512,512,768,768))[0]
    assert p['x']==532 and p['y']==542 and p['bbox']==[527,536,10,12]


def test_duplicate_suppression_is_class_aware_and_keeps_best_score():
    ps=map_predictions([prediction(confidence=.3),prediction(confidence=.9),prediction(label='Post acne')],(0,0,768,768))
    kept=suppress_duplicates(ps)
    assert len(kept)==2 and kept[0]['confidence']==.9


def test_crop_seam_detection_is_not_clipped_or_turned_into_truth():
    p=map_predictions([prediction(x=-1)],(512,0,768,768))[0]
    assert p['bbox'][0]==506


@pytest.mark.parametrize('shape',[(0,10,.6),(10,10,.4),(10,10,float('nan'))])
def test_bad_crop_config_rejected(shape):
    with pytest.raises(ValueError):corner_tiles(*shape)


def test_malformed_predictions_rejected():
    with pytest.raises(ValueError):map_predictions([prediction(confidence=float('nan'))],(0,0,768,768))
