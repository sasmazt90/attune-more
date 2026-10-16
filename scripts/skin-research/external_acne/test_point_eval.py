import json, random
from pathlib import Path
import numpy as np, pytest
import point_eval as P


def ev(T, boxes, roi=None, kind='positive-photo'):
    it = dict(sha256='a' * 64, kind=kind, positive=T)
    masks = {}
    if roi is not None: it['roiMask'] = 'r.png'; masks['r.png'] = roi
    rows = [dict(sha='a' * 64, final=[b + [.9] for b in boxes], sec=.1)]
    return P.evaluate(rows, [it], Path('.'), lambda f: masks[f.name])


def test_one_point_cannot_hit_two_targets():
    S, pt, *_ = ev([[0, 0, 20, 20], [5, 5, 25, 25]], [[8, 8, 16, 16]])      # centre (12,12) inside both
    assert S['point'] == 1 and sum(t['pointHit'] for t in pt) == 1


def test_two_points_on_one_target_count_once():
    S, *_ = ev([[0, 0, 20, 20]], [[2, 2, 8, 8], [10, 10, 18, 18]])
    assert S['point'] == 1 and S['duplicates'] == 1 and S['unknown'] == 0


def test_point_outside_label_box_does_not_match():
    S, *_ = ev([[0, 0, 10, 10]], [[8, 8, 20, 20]])                           # centre (14,14) outside, IoU low too
    assert S['point'] == 0 and S['unknown'] == 1


def test_max_cardinality_beats_nearest_greedy():
    # point A is nearest to target 0 but is also the only point inside target 1; maximum cardinality must use both points
    T = [[0, 0, 30, 30], [20, 20, 40, 40]]; boxes = [[23, 23, 27, 27], [4, 4, 8, 8]]   # A centre (25,25) in both; B centre (6,6) only in 0
    S, pt, *_ = ev(T, boxes)
    assert S['point'] == 2


def test_unknown_point_not_counted_as_false():
    roi = np.zeros((50, 50), bool); roi[30:50, 30:50] = True
    S, _, roi_pp, *_ = ev([[0, 0, 10, 10]], [[12, 12, 16, 16], [38, 38, 42, 42]], roi)
    assert S['roiFP'] == 1 and S['unknown'] == 1 and roi_pp[0]['falsePoints'] == 1


def test_iou_matcher_matches_earlier_harness():
    import eval_external as E
    rnd = random.Random(0)
    for _ in range(50):
        T = [[x, y, x + rnd.uniform(4, 30), y + rnd.uniform(4, 30)] for x, y in [(rnd.uniform(0, 200), rnd.uniform(0, 200)) for _ in range(6)]]
        F = [[t[0] + rnd.uniform(-5, 5), t[1] + rnd.uniform(-5, 5), t[2] + rnd.uniform(-5, 5), t[3] + rnd.uniform(-5, 5)] for t in T] + [[50, 50, 70, 70]]
        for thr in (.5, .3): assert len(P.o2o_iou(T, F, thr)) == len(E.o2o(T, F, thr))


def test_crop_and_tile_outputs_stay_in_source_coordinates(monkeypatch, tmp_path):
    import cv2, eval_external as E
    img = np.zeros((600, 800, 3), np.uint8); cv2.imwrite(str(tmp_path / 'x.png'), img)
    man = [dict(sha256='b' * 64, kind='positive-photo', set='dev', file='x.png', positive=[], rects=[[100, 50, 484, 338], [400, 300, 784, 588]])]
    monkeypatch.setattr(E, 'P', tmp_path); monkeypatch.setattr(E, 'man', man)
    monkeypatch.setattr(E, 'YOLO', lambda f: None)
    monkeypatch.setattr(E, 'predict', lambda model, im, imgsz, keep, conf=.25, agnostic=False: [[10., 20., 30., 40., .9]])
    crop = E.run('dewiin-anyacne', 'crop')[0]['final']; tiles = E.run('dewiin-anyacne', 'tiles')[0]['final']
    assert crop == [[110., 70., 130., 90., .9]]                                     # crop origin = (min x, min y) of rects
    assert sorted(b[:4] for b in tiles) == [[110., 70., 130., 90.], [410., 320., 430., 340.]]
