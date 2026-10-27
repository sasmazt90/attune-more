"""Validation-only four-corner tiling experiment; no product activation.

Map crop detections back to the original frame before class-aware NMS and
compare with unchanged full-frame truth. Never clip truth to crop boundaries.
"""
import math
from evaluate_detector_snapshot import CLASSES, finite, iou


def corner_tiles(width, height, fraction=.6):
    if (not isinstance(width, int) or not isinstance(height, int) or
        width <= 0 or height <= 0 or not finite(fraction) or not .5 <= fraction <= 1):
        raise ValueError('INVALID_TILE_SHAPE')
    w, h = math.ceil(width * fraction), math.ceil(height * fraction)
    return list(dict.fromkeys((x, y, w, h) for y in (0, height-h) for x in (0, width-w)))


def map_predictions(predictions, tile):
    x, y, w, h = tile
    result = []
    for p in predictions:
        if (p.get('class') not in CLASSES or not all(finite(p.get(k)) for k in
            ('x', 'y', 'width', 'height', 'confidence')) or p['width'] <= 0 or
            p['height'] <= 0 or not 0 <= p['confidence'] <= 1):
            raise ValueError('INVALID_TILE_PREDICTION')
        # Server reports pixel coordinates in the submitted crop, with no client resize.
        row = dict(p, x=p['x'] + x, y=p['y'] + y)
        row['bbox'] = [row['x']-p['width']/2, row['y']-p['height']/2, p['width'], p['height']]
        result.append(row)
    return result


def suppress_duplicates(predictions, overlap=.5):
    if not finite(overlap) or not 0 < overlap <= 1:
        raise ValueError('INVALID_NMS_OVERLAP')
    kept = []
    for p in sorted(predictions, key=lambda p: -p['confidence']):
        if not any(p['class'] == q['class'] and iou(p['bbox'], q['bbox']) >= overlap for q in kept):
            kept.append(p)
    return kept
