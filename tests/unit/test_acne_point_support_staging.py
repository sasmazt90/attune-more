"""Focused tests for the offline point support filter (services/core-api/acne_point_support_staging.py)."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/core-api')]
import acne_point_support_staging as P

H = W = 100; ORIGIN = (200., 100.); SCALE = .5          # raster covers source x 200..400, y 100..300


def masks():
    skin = np.zeros((H, W), bool); skin[10:90, 10:90] = True
    env = {'rightCheek': np.zeros((H, W), bool), 'leftCheek': np.zeros((H, W), bool), 'forehead': np.zeros((H, W), bool)}
    env['rightCheek'][10:60, 10:50] = True; env['leftCheek'][10:60, 50:90] = True; env['forehead'][5:20, 10:90] = True
    hair = np.zeros((H, W), bool); hair[70:80, 20:30] = True
    excl = np.zeros((H, W), np.uint8); excl[70:80, 60:70] = 255
    return env, skin, hair, excl


def run(boxes, vis=None, env=None, src=(600, 800)):
    e, s, h, x = masks(); e = env or e
    return P.point_accepted(boxes, e, s, h, x, 'p', SCALE, ORIGIN, visible_regions=vis, landmarks=None, source_shape=src)


def box(px, py, half): return [px - half, py - half, px + half, py + half, .9]


def test_same_centre_different_sizes_same_decision_and_region():
    for px, py in [(260., 160.), (380., 300.5), (150., 160.), (330., 250.), (270., 250.)]:
        outs = [run([box(px, py, s)]) for s in (1., 6., 40., 160.)]
        keys = [([(a['region'], a['reason']) for a in acc], [r['reason'] for r in rej]) for acc, rej in outs]
        assert all(k == keys[0] for k in keys)


def test_point_on_skin_is_accepted_with_unmoved_point():
    acc, rej = run([box(260., 160., 5)])
    assert len(acc) == 1 and acc[0]['point'] == [260., 160.] and acc[0]['region'] == 'rightCheek' and not rej


def test_eye_mouth_hair_and_out_of_scope_are_rejected():
    _, rej = run([box(330., 250., 3), box(250., 250., 3), box(150., 160., 3), box(260., 380., 3)])
    assert [r['reason'] for r in rej] == ['POINT_ON_EXCLUSION', 'POINT_ON_HAIR', 'POINT_OUTSIDE_SCOPE', 'POINT_OUTSIDE_SCOPE']


def test_point_outside_image_is_rejected_not_clamped():
    acc, rej = run([[-10., 150., 4., 160., .9], [790., 590., 820., 610., .9], [float('nan'), 1., 2., 3., .9]])
    assert not acc and [r['reason'] for r in rej] == ['POINT_OUTSIDE_IMAGE', 'POINT_OUTSIDE_IMAGE', 'POINT_NOT_FINITE']


def test_origin_scale_mapping():
    # source (299.9, 160) -> analysis x 49.95 -> pixel 49 (rightCheek); source (300.1, 160) -> 50.05 -> pixel 50 (leftCheek)
    acc, _ = run([box(299.9, 160., 2), box(300.1, 160., 2)])
    assert [a['region'] for a in acc] == ['rightCheek', 'leftCheek']


def test_overlapping_envelopes_assign_deterministically():
    acc, _ = run([box(260., 123., 2), box(260., 150., 2)])     # pixel rows 11 (forehead + rightCheek) and 25 (rightCheek only)
    assert acc[0]['region'] == 'forehead' and 'first of forehead,rightCheek' in acc[0]['reason']
    assert acc[1]['region'] == 'rightCheek' and acc[1]['reason'] == 'POINT_IN_ENVELOPE'


def test_side_angle_scope_is_kept():
    e, *_ = masks(); only = {'rightCheek': e['rightCheek']}
    acc, rej = run([box(260., 160., 3), box(360., 160., 3)], vis=['rightCheek'], env=only)
    # the leftCheek point lies on skin inside the raster but no visible envelope contains it; fallback across the midline is blocked
    assert [a['region'] for a in acc] == ['rightCheek'] and [r['reason'] for r in rej] == ['POINT_UNCERTAIN_REGION']


def test_output_does_not_depend_on_labels():
    # the function has no label / review-mask input; identical inputs give identical outputs
    a = run([box(260., 160., 5), box(330., 250., 3)]); b = run([box(260., 160., 5), box(330., 250., 3)])
    assert a == b and 'labels' not in P.point_accepted.__code__.co_varnames and 'review' not in ' '.join(P.point_accepted.__code__.co_varnames)
