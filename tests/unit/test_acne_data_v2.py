"""Focused contracts for the acne v2 data preparation (synthetic inputs only)."""
import sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research'), str(ROOT / 'services/core-api')]
import prepare_acne_data_v2 as prep


def ann(i, cls, box): return dict(id=i, cls=cls, box=box)


def test_only_non_conflicting_original_pimple_boxes_are_positive():
    anns = [ann(1, 'Pimple', [10, 10, 20, 20]), ann(2, 'Post acne', [11, 11, 21, 21]),  # same lesion, two classes
            ann(3, 'Pimple', [50, 50, 60, 60]), ann(4, 'Mole', [80, 80, 90, 90]), ann(5, 'Post acne', [100, 100, 400, 400])]
    pos, conf, other = prep.classify_annotations(anns)
    assert [p['id'] for p in pos] == [3] and [c['id'] for c in conf] == [1] and conf[0]['conflictWith'] == [dict(id=2, cls='Post acne')]
    assert {o['id'] for o in other} == {2, 4, 5}                 # never positives, never clean skin
    pos2, conf2, _ = prep.classify_annotations([ann(6, 'Pimple', [150, 150, 160, 160]), ann(5, 'Post acne', [100, 100, 400, 400])])
    assert [p['id'] for p in pos2] == [6] and not conf2         # a huge region box does not erase a Pimple
    assert prep.classify_annotations([ann(7, 'Mole', [0, 0, 5, 5])])[0] == []


def test_tile_targets_keep_cut_and_outside_boxes():
    rect = [100, 100, 484, 484]
    boxes = [dict(id=1, box=[110, 120, 130, 140]), dict(id=2, box=[470, 200, 500, 220]), dict(id=3, box=[600, 600, 610, 610])]
    kept, protected = prep.tile_targets(rect, boxes)
    assert kept == [dict(id=1, tile=[10, 20, 30, 40])] and [p['id'] for p in protected] == [2]  # cut lesion is UNKNOWN, never negative
    assert prep.tile_to_source(kept[0]['tile'], rect) == [110, 120, 130, 140]


def test_tile_tensor_is_the_product_input_and_round_trips():
    rng = np.random.default_rng(0); bgr = rng.integers(0, 255, (500, 700, 3), dtype=np.uint8)
    rect = [500, 300, 700, 500]  # right/bottom edge tile: smaller than 384, padded with 114
    x = prep.tile_tensor(bgr, rect)
    assert x.shape == (3, 384, 384) and x.dtype == np.float32 and x.max() <= 255
    assert np.array_equal(x[:, :200, :200].transpose(1, 2, 0), bgr[300:500, 500:700]) and (x[:, 200:, :] == 114).all()
    assert np.array_equal(x[0, :200, :200], bgr[300:500, 500:700, 0].astype(np.float32))  # channel 0 stays B (no RGB swap)


def test_tile_grid_equals_current_product_tiling():
    from acne_takeover_support import tile_rectangles
    bgr = np.zeros((1280, 1280, 3), np.uint8); crop = dict(x=137, y=41, width=901, height=1003)
    ours = prep.tile_rects_for_crop(crop, bgr.shape[:2])
    ref = tile_rectangles(bgr, None, (crop['x'], crop['y'], crop['x'] + crop['width'], crop['y'] + crop['height']))
    assert ours == ref and all(r[2] - r[0] <= 384 and r[3] - r[1] <= 384 for r in ours)
    with pytest.raises(prep.PrepError): prep.tile_rects_for_crop(dict(x=0, y=0, width=4000, height=4000), (4000, 4000))


def test_grouping_helpers_are_conservative():
    assert prep.family_of('train/433_jpg.rf.abc.jpg') == '433' and prep.family_of('valid/x-y_png.rf.1.jpg') == 'x-y'
    g = (np.arange(64 * 64).reshape(64, 64) % 251).astype(np.uint8)
    assert prep.hamming(prep.dhash(g[:, ::-1]), prep.dhash(g, flip=True)) == 0  # mirrored copy is caught
    uf = prep.UnionFind(); uf.union('a', 'fam:1'); uf.union('b', 'fam:1'); assert uf.find('a') == uf.find('b')
    assert prep.size_band([0, 0, 7.5, 3]) == 'micro' and prep.size_band([0, 0, 12, 5]) == 'small' and prep.size_band([0, 0, 16, 2]) == 'medium'
    assert prep.xywh_to_xyxy([1, 2, 3, 4]) == [1., 2., 4., 6.]
