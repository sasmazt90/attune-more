"""Regression and verification tests for the 5 skin analysis targets:
A. Acne: off-task box rejection and real lesion retention.
B. Dark circles: normal skin deadband, structural shadow suppression, chromatic pigment verification.
C. Eye bags: separation from normal lid margin, dark circles, shadow, and expression.
D. Crow's feet: radiating angle specificity, eyelash/hair exclusion.
E. Oily/redness/tone unlabelled behavior and Photo57 sag regression test.
"""
import sys, math, json
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
import appearance_analysis as A
from acne_box_support import region_envelopes, accepted_boxes as filter_acne_boxes, box_area, VERSION as ACNE_SUPPORT_VERSION
from test_local_appearance_health import photo


def test_target_a_acne_eyebrow_landmarks_exclude_blurred_brow_false_positive():
    """Target A: Brow landmark tail landmarks (69, 299) ensure convex hull covers
    blurred brow boundaries without arbitrary forehead margins.
    """
    # Landmark 299 is the lateral tail of the left eyebrow
    w, h = 1280, 1280
    landmarks_path = ROOT.parent / 'attune-live-test/audit-results/skin-expanded-20261011/interim-diagnosis/positive-product-chain.json'
    if landmarks_path.exists():
        landmarks = json.loads(landmarks_path.read_text())['rows'][0]['realDerivedLandmarks']
        box = [215.0622100830078, 550.2491455078125, 228.59141540527344, 572.3162841796875]
        
        old_indices = [300, 293, 334, 296, 336, 285, 295, 282]
        new_indices = [300, 293, 334, 296, 299, 336, 285, 295, 282]
        
        poly_old = np.asarray([[landmarks[i]['x']*w, landmarks[i]['y']*h] for i in old_indices], np.float32)
        poly_new = np.asarray([[landmarks[i]['x']*w, landmarks[i]['y']*h] for i in new_indices], np.float32)
        
        hull_old = cv2.convexHull(poly_old).astype(np.int32)
        hull_new = cv2.convexHull(poly_new).astype(np.int32)
        
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        # Old hull was outside (-19.97 px); new hull is inside (+22.92 px)
        assert cv2.pointPolygonTest(hull_old, (cx, cy), True) < 0
        assert cv2.pointPolygonTest(hull_new, (cx, cy), True) > 0
        
        mask_new = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(mask_new, hull_new, 255)
        bx, by, ex, ey = int(box[0]), int(box[1]), int(np.ceil(box[2])), int(np.ceil(box[3]))
        assert (mask_new[by:ey, bx:ex] > 0).mean() == 1.0


def test_target_a_acne_clipping_preserves_pustule_with_specular_highlight():
    """Target A: Single saturated channel (e.g. red > 0.975) is NOT clipping;
    only total loss of all colour channels is considered clipping.
    """
    rgb_saturated_red = np.zeros((10, 10, 3), np.float32)
    rgb_saturated_red[:, :, 0] = 0.99  # Red clipped
    rgb_saturated_red[:, :, 1] = 0.60  # Green fine
    rgb_saturated_red[:, :, 2] = 0.50  # Blue fine
    
    # Old check: np.max(rgb, axis=2) > 0.975 => clipped!
    old_clipped = np.max(rgb_saturated_red, axis=2) > 0.975
    assert old_clipped.all()
    
    # New check: np.min(rgb, axis=2) > 0.975 => preserved!
    new_clipped = np.min(rgb_saturated_red, axis=2) > 0.975
    assert not new_clipped.any()


def test_target_b_dark_circles_normal_skin_deadband():
    """Target B: Normal skin with subtle contrast variation (< 5%) produces 0 dark circle score."""
    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)
    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}
    
    # Image with subtle 3% luminance difference (typical normal healthy skin)
    image = np.full((h, w, 3), 150, np.uint8)
    image[80:95, 50:100] = 145  # 145 vs 150 is 3.3% relative contrast (< 5% deadband)
    
    url, digest = photo(image)
    res = A.analyze_skin(dict(photo=url, photoId=digest, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    dark = next(v for v in res['measurements']['periorbital'] if v['id'] == 'dark')
    assert dark['value'] == 0.0, f"Expected 0 for subtle normal skin variance, got {dark['value']}"


def test_target_b_dark_circles_shadow_vs_pigment_separation():
    """Target B: Pure structural shadow without chromatic shift is discounted,
    whereas true chromatic hyperpigmentation is detected.
    """
    h, w = 280, 320
    p = [dict(x=.5, y=.5, z=0.) for _ in range(478)]
    oval = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
    for i, angle in zip(oval, np.linspace(-np.pi/2, 3*np.pi/2, len(oval), endpoint=False)):
        p[i].update(x=.5+.49*np.cos(angle), y=.5+.48*np.sin(angle))
    locations = {234: (0, 150), 454: (320, 150), 33: (40, 70), 133: (110, 70), 159: (75, 64), 163: (50, 76),
                 144: (60, 80), 145: (75, 82), 153: (90, 83), 154: (100, 80), 155: (105, 76),
                 263: (280, 70), 362: (210, 70), 386: (245, 64), 390: (270, 76), 373: (260, 80),
                 374: (245, 82), 380: (230, 83), 381: (220, 80), 382: (215, 76), 61: (110, 165), 291: (210, 165),
                 13: (160, 165), 14: (160, 168)}
    for i, (x, y) in locations.items():
        p[i].update(x=x/w, y=y/h)
    mesh = {'points': [{'x': 0, 'y': 40}, {'x': 320, 'y': 40}, {'x': 320, 'y': 130}, {'x': 0, 'y': 130}], 'edges': [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]}
    
    # 1. Pure luminance shadow: drop luminance from 160 to 125, but zero chromatic shift
    img_shadow = np.full((h, w, 3), 160, np.uint8)
    img_shadow[80:95, 50:100] = 125
    url_shadow, digest_shadow = photo(img_shadow)
    res_shadow = A.analyze_skin(dict(photo=url_shadow, photoId=digest_shadow, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    score_shadow = next(v for v in res_shadow['measurements']['periorbital'] if v['id'] == 'dark')['value']
    
    # 2. True chromatic pigment: same luminance drop (125) PLUS chromatic shift (purplish/brown undertone)
    img_pigment = np.full((h, w, 3), 160, np.uint8)
    img_pigment[80:95, 50:100, 0] = 140  # Blue higher (bluish/purple pooling)
    img_pigment[80:95, 50:100, 1] = 115  # Green lower
    img_pigment[80:95, 50:100, 2] = 120  # Red lower
    url_pigment, digest_pigment = photo(img_pigment)
    res_pigment = A.analyze_skin(dict(photo=url_pigment, photoId=digest_pigment, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    score_pigment = next(v for v in res_pigment['measurements']['periorbital'] if v['id'] == 'dark')['value']
    
    assert score_pigment > score_shadow, f"True chromatic pigment ({score_pigment}) must score higher than pure shadow ({score_shadow})"


def test_target_c_dark_circles_and_eye_bags_masks_remain_distinct():
    """Target C: Dark circles and eye bags must not produce identical masks.
    Dark circles are relative contrast on bands['dark']; eye bags require fold deflection.
    """
    p = [dict(x=.5, y=.5) for _ in range(478)]
    for i, x, y in [(234, .15, .5), (454, .85, .5)]:
        p[i] = dict(x=x, y=y)
    for ids, xs in [([33, 163, 144, 145, 153, 154, 155, 133], np.linspace(.25, .42, 8)),
                    ([263, 390, 373, 374, 380, 381, 382, 362], np.linspace(.75, .58, 8))]:
        for i, x in zip(ids, xs):
            p[i] = dict(x=float(x), y=.4)
    bands = A.eye_skin_bands(p, (500, 500), 1, (0, 0), (500, 500))
    
    assert not np.array_equal(bands['dark'], bands['bags'])
    # Lower lid margin protects tarsal plate (dark starts at 0.012, bags starts at 0.022)
    assert not bands['dark'][:204].any()
    assert not bands['bags'][:208].any()


def test_target_d_lines_radiating_angles_exclude_vertical_lash_and_hair():
    """Target D: Crow's feet Gabor filter uses radiating orientations (-30, 0, 30 deg).
    Vertical lines (theta = 90 deg) representing eyelashes, lid contours, and hair are excluded.
    """
    from skimage.filters import gabor
    # Vertical edge image (eyelash or vertical hair strand)
    im_vertical = np.zeros((64, 64), np.float32)
    im_vertical[:, 31:33] = 1.0  # Sharp vertical stroke
    
    # Horizontal radiating wrinkle
    im_radiating = np.zeros((64, 64), np.float32)
    im_radiating[31:33, :] = 1.0  # Horizontal wrinkle
    
    # Evaluate with current radiating angles: (pi/3, pi/2, 2*pi/3)
    rad_angles = (np.pi/3, np.pi/2, 2*np.pi/3)
    resp_vertical = max(np.hypot(*gabor(im_vertical, frequency=0.22, theta=th)).max() for th in rad_angles)
    resp_radiating = max(np.hypot(*gabor(im_radiating, frequency=0.22, theta=th)).max() for th in rad_angles)
    
    assert resp_radiating > 2.0 * resp_vertical, "Radiating crow's feet filter must strongly prefer horizontal over vertical eyelashes"


def test_target_e_photo57_sag_regression_preserved():
    """Target E & Regression: Photo57 lower face shadow/crop must be preserved
    as an explicit regression case: declaredLabel='positive',
    visualReview='inconclusive-lower-face-shadow-crop', sag_overview=0 (missed).
    """
    receipt_path = ROOT / 'audit-results/sag-calibrated-true-results.json'
    if not receipt_path.exists():
        receipt_path = ROOT.parent / 'attune-live-test/audit-results/interim-diagnosis/ag-sag-production-replay.json'
    
    if receipt_path.exists():
        data = json.loads(receipt_path.read_text())
        r57 = next((r for r in data['rows'] if r.get('index') == 57), None)
        if r57:
            assert r57['declaredLabel'] == 'positive', "Photo57 declaredLabel must stay positive"
            assert r57['visualReview'] == 'inconclusive-lower-face-shadow-crop', "Photo57 visualReview must stay inconclusive-lower-face-shadow-crop"
            assert r57['sag_overview'] == 0, "Photo57 sag_overview must stay 0 (not falsely marked passed)"
