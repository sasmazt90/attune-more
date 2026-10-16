"""Focused coordinate checks for the Step0 product-like chain used in the trace (no model weights needed).
1. infer_tiles maps tile-local head boxes to source px by the tile origin and clips them to the tile rect.
2. tile_rectangles covers the product crop with 384 px tiles at 288 px stride: every crop pixel lies >= 48 px inside some tile
   (or at the crop edge).
3. principled_accepted_boxes maps source boxes to the analysis raster with (src - origin) * scale, returns accepted boxes with
   unchanged source coordinates, and rejects boxes outside the raster (OUTSIDE_SOURCE_SUPPORT) or on exclusion.
"""
import sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research'), str(ROOT / 'services/core-api')]


class FakeNet:
    """Returns one decoded head row per tile: cx, cy, w, h (tile px), obj, cls."""
    def __init__(self, rows): self.rows = rows; self.i = 0
    def __call__(self, x):
        import torch
        r = self.rows[self.i]; self.i += 1
        return torch.tensor([[r]], dtype=torch.float32)


def test_infer_tiles_maps_tile_local_boxes_to_source():
    pytest.importorskip('torch'); import acne_takeover_support as ats
    bgr = np.zeros((700, 900, 3), np.uint8)
    rects = [[100, 50, 484, 434], [388, 338, 772, 700]]                 # second tile is cut by the image bottom (362 px tall)
    net = FakeNet([[60., 40., 10., 8., .9, .9], [380., 30., 20., 20., .9, .9]])
    sel, trace = ats.infer_tiles(net, bgr, rects)
    boxes = sorted([[round(v, 3) for v in b[:4]] for b in sel])
    assert boxes == sorted([[155., 86., 165., 94.], [758., 358., 772., 378.]])   # +origin; right edge clipped to the rect (772)


def test_tile_rectangles_cover_crop_with_margin():
    import acne_takeover_support as ats, skin_models
    orig = skin_models.photo_input
    try:
        skin_models.photo_input = lambda bgr, pts: (None, dict(x=37, y=11, width=1000, height=777))
        rects = ats.tile_rectangles(np.zeros((900, 1100, 3), np.uint8), [dict(x=0, y=0)] * 468)
    finally: skin_models.photo_input = orig
    xs, ys = np.meshgrid(np.arange(37, 1037, 7), np.arange(11, 788, 7))
    for x, y in zip(xs.ravel(), ys.ravel()):
        best = max(min(x - a, y - b, c - 1 - x, d - 1 - y) for a, b, c, d in rects if a <= x < c and b <= y < d)
        edge = min(x - 37, y - 11, 1036 - x, 787 - y)
        assert best >= min(48, edge)


def test_staging_filter_mapping_origin_scale():
    import acne_box_support_staging as st
    h = w = 100; origin = (200, 100); scale = .5                        # raster covers source x 200..400, y 100..300
    skin = np.zeros((h, w), bool); skin[20:60, 20:60] = True             # source x 240..320, y 140..220
    env = {'rightCheek': skin.copy()}; hair = np.zeros((h, w), bool); excl = np.zeros((h, w), np.uint8); excl[70:80, 70:80] = 255
    boxes = [[270., 170., 280., 180., .9],                               # on skin -> accepted, coordinates unchanged
             [120., 170., 130., 180., .9],                               # left of the raster -> OUTSIDE_SOURCE_SUPPORT
             [342., 242., 352., 252., .9]]                               # on exclusion (raster 71..76) -> ANATOMICAL_HOLE
    assigned, rejected = st.principled_accepted_boxes(boxes, env, skin, hair, excl, 'p', scale, origin, visible_regions=['rightCheek'],
                                                       landmarks=None, source_shape=(600, 800), bgr=None)
    acc = [b for v in assigned.values() for b in v]
    assert len(acc) == 1 and [acc[0]['x'], acc[0]['y'], acc[0]['x'] + acc[0]['width'], acc[0]['y'] + acc[0]['height']] == boxes[0][:4]
    assert [r['reason'] for r in rejected] == ['OUTSIDE_SOURCE_SUPPORT', 'ANATOMICAL_HOLE']
