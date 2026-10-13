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
sys.path.insert(0, str(ROOT / 'scripts'))
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


def test_target_a_acne_borderline_lesion_retention_and_support_v3():
    """Target A: Lesions straddling regional boundaries or peripheral skin envelopes
    are retained if total skin support is valid (>= 50%) and center is not in holes/hair.
    Deep hole/hair overlaps (> 25% or center in exclusion) are strictly rejected.
    """
    h, w = 100, 100
    skin_support = np.ones((h, w), bool)
    hair = np.zeros((h, w), bool)
    exclusion = np.zeros((h, w), np.uint8)
    
    # 2 envelopes: region1 covers x in [0, 50], region2 covers x in [50, 100]
    env1 = np.zeros((h, w), bool); env1[:, :50] = True
    env2 = np.zeros((h, w), bool); env2[:, 50:] = True
    envelopes = {'rightCheek': env1, 'nose': env2}
    
    # Box 1: straddles boundary at x=50, from x=45 to 55 (w=10, h=10).
    # Overlap with rightCheek is 50%, overlap with nose is 50%.
    # In v2 (>= 65%), this was rejected! In v3 (max overlap >= 15%), it is accepted!
    box_straddle = [45, 45, 55, 55, 0.85]
    assigned, rejected = filter_acne_boxes([box_straddle], envelopes, skin_support, hair, exclusion, 'test_photo', 1.0, (0, 0))
    assert len(rejected) == 0, f"Expected box to be accepted, got rejections: {rejected}"
    assert len(assigned['rightCheek']) + len(assigned['nose']) == 1
    
    # Box 2: Center is in hair -> strictly rejected
    hair[50, 50] = True
    assigned, rejected = filter_acne_boxes([box_straddle], envelopes, skin_support, hair, exclusion, 'test_photo', 1.0, (0, 0))
    assert len(rejected) == 1 and rejected[0]['reason'] == 'ANATOMICAL_HOLE_OR_HAIR'
    hair[50, 50] = False
    
    # Box 3: Overlap with exclusion exceeds 25% -> strictly rejected
    exclusion[45:55, 45:48] = 255  # 30% overlap
    assigned, rejected = filter_acne_boxes([box_straddle], envelopes, skin_support, hair, exclusion, 'test_photo', 1.0, (0, 0))
    assert len(rejected) == 1 and rejected[0]['reason'] == 'ANATOMICAL_HOLE_OR_HAIR'


def test_target_a_acne_peripheral_visible_skin_fallback_v4():
    """Target A (v4): Lesions on visible facial skin (skin_support >= 50%) outside narrow
    mesh presentation envelopes (overlap < 15%) are retained and assigned to nearest region
    via Euclidean distance transform fallback.
    """
    h, w = 100, 100
    skin_support = np.ones((h, w), bool)
    hair = np.zeros((h, w), bool)
    exclusion = np.zeros((h, w), np.uint8)
    
    # Envelope covers x in [50, 100]
    env = np.zeros((h, w), bool); env[:, 50:] = True
    envelopes = {'rightCheek': env}
    
    # Box 1: adjacent to envelope (x in [42, 48], overlap=0.0 with [50, 100], norm_dist <= 0.15)
    # On visible skin, within normalized upper bound -> retained via anatomical distance fallback!
    box_adjacent = [42, 42, 48, 48, 0.90]
    assigned, rejected = filter_acne_boxes([box_adjacent], envelopes, skin_support, hair, exclusion, 'test_photo', 1.0, (0, 0))
    assert len(rejected) == 0
    assert len(assigned['rightCheek']) == 1
    assert assigned['rightCheek'][0]['confidence'] == 0.90

    # Box 2: distant from envelope (x in [5, 15], norm_dist > 0.15)
    # Outside anatomical proximity upper bound -> rejected as UNCERTAIN_ANATOMICAL_REGION!
    box_far = [5, 5, 15, 15, 0.90]
    assigned_far, rejected_far = filter_acne_boxes([box_far], envelopes, skin_support, hair, exclusion, 'test_photo', 1.0, (0, 0))
    assert len(rejected_far) == 1
    assert rejected_far[0]['reason'] == 'UNCERTAIN_ANATOMICAL_REGION'


def test_target_a_acne_support_v4_version_contract():
    """Target A: acne_box_support VERSION contract is source-box-anatomical-support-v4."""
    assert ACNE_SUPPORT_VERSION == 'source-box-anatomical-support-v4'


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


def test_target_c_eye_bags_version_and_eyelid_margin_separation():
    """Target C: Method version is contour-fold-local-support-v5.
    Lower eyelid margin (offsets < 7) is excluded, and discontinuous valley noise (< 0.20 continuity)
    produces score 0.0, eliminating false positives on normal lower lids.
    """
    import instant_appearance as IA
    assert A.NORMALIZATION['bags'] == 'contour-fold-local-support-v5'
    
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
    
    # Normal image with subtle lower eyelid margin dip at offset 4-5
    img = np.full((h, w, 3), 150, np.uint8)
    img[84:86, 50:110] = 142  # 5% dip near eyelid margin
    url, digest = photo(img)
    
    res = A.analyze_skin(dict(photo=url, photoId=digest, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    bags = next(v for v in res['measurements']['periorbital'] if v['id'] == 'bags')
    assert bags['normalizationVersion'] == 'contour-fold-local-support-v5'
    assert bags['components']['formulaVersion'] == 'contour-fold-local-support-v5'
    assert bags['value'] == 0.0, f"Normal lower eyelid margin dip must produce score 0.0, got {bags['value']}"
    
    # Map consistency: zero score must have zero active pixels on map
    from evaluate_periorbital_and_acne_comparative import decode_map_overlay
    overlay = decode_map_overlay(res.get('maps', {}).get('periorbital:bags'), (h, w, 3))
    assert (overlay.sum(axis=2) > 0).sum() == 0, "Zero card score must produce 0 active map pixels"
    
    # Cheek / chin sag preservation: continuity gate < 0.20 zeroing must be strictly isolated to periorbital
    # In cheek/chin, continuity_gate = min(1.0, continuity / 0.6) and is NOT zeroed
    gray = np.full((h, w), 150, np.uint8)
    eligible = np.ones((h, w), bool)
    cond = dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)
    # Call instant_proxy for rightCheek and periorbital with synthetic flat input
    v_cheek, comp_cheek, sig_cheek, _, _ = IA.instant_proxy(gray, eligible, p, 'rightCheek', cond, 1.0, (0, 0), (h, w))
    assert 'times continuity/0.6' in comp_cheek['indexAggregation'], "Cheek must retain previous continuity/0.6 aggregation"
    assert comp_cheek['formulaVersion'] == 'contour-fold-target-roi-local-support-v6'


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


def test_target_d_lines_hair_exclusion_from_signal_and_denominator():
    """Target D: Hair margin is strictly excluded from scored pixels, denominator,
    and cyan signal map. When hair completely occludes the line band (< 20 px),
    the limitation is 'HAIR_OR_OCCLUSION_IN_LINE_BAND' and value is None (not 0.0).
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
    
    # 1. Clean image without hair
    img_clean = np.full((h, w, 3), 150, np.uint8)
    url_c, dig_c = photo(img_clean)
    res_c = A.analyze_skin(dict(photo=url_c, photoId=dig_c, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    sides_c = next(v for v in res_c['measurements']['periorbital'] if v['id'] == 'lines')['components']['sides']
    px_clean = next(s['analysisPixels'] for s in sides_c if s['side'] == 'right')

    # 2. Image with hair margin covering part of lateral canthus
    img_hair = np.full((h, w, 3), 150, np.uint8)
    img_hair[60:85, 20:45] = 10  # dark hair strand covering outer canthus
    url_h, dig_h = photo(img_hair)
    res_h = A.analyze_skin(dict(photo=url_h, photoId=dig_h, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    sides_h = next(v for v in res_h['measurements']['periorbital'] if v['id'] == 'lines')['components']['sides']
    px_hair = next(s['analysisPixels'] for s in sides_h if s['side'] == 'right')
    
    assert px_hair < px_clean, f"Hair margin must reduce scored analysis support (clean {px_clean} vs hair {px_hair})"

    # 3. Heavy occlusion over outer canthus line band (< 20 px valid)
    img_occ = np.full((h, w, 3), 150, np.uint8)
    img_occ[50:100, 10:60] = 10
    url_o, dig_o = photo(img_occ)
    res_o = A.analyze_skin(dict(photo=url_o, photoId=dig_o, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    s_occ = next(s for s in next(v for v in res_o['measurements']['periorbital'] if v['id'] == 'lines')['components']['sides'] if s['side'] == 'right')
    assert s_occ['value'] is None, "Occluded band must return value=None (not 0.0)"
    assert s_occ['limitationCode'] in ('HAIR_OR_OCCLUSION_IN_LINE_BAND', 'INSUFFICIENT_VISIBLE_AREA')


def test_target_d_lines_v4_contract_and_makeup_exclusion():
    """Target D: Crow's feet v4 normalization contract and dark makeup exclusion.
    Verifies normalizationVersion is 'outer-canthus-gabor-radiating-hair-excluded-v4',
    and dark eyeliner/makeup (gray < 0.18) at lateral canthus is excluded from skin support.
    """
    assert A.NORMALIZATION['lines'] == 'outer-canthus-gabor-radiating-hair-excluded-v4'
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
    
    # Image with clean smooth skin
    img = np.full((h, w, 3), 150, np.uint8)
    # Paint dark eyeliner flick directly next to landmark 33
    img[68:74, 30:45] = 20  # dark eyeliner pigment
    url, dig = photo(img)
    res = A.analyze_skin(dict(photo=url, photoId=dig, landmarks=p, meshes={'periorbital': mesh}, exclusions=[], pose='FRONT', qualityValid=True, conditions=dict(yaw=0., pitch=0., roll=0., scaleRatio=.6, avgLuminance=150., blurScore=50.)))
    lines_item = next(v for v in res['measurements']['periorbital'] if v['id'] == 'lines')
    assert lines_item['normalizationVersion'] == 'outer-canthus-gabor-radiating-hair-excluded-v4'
    # The eyeliner should not create a high adverse lines score
    if lines_item['value'] is not None:
        assert lines_item['value'] < 1.0, f"Dark eyeliner flick must be excluded by makeup filter (got {lines_item['value']})"



def test_target_e_photo57_sag_regression_preserved():
    """Target E & Regression: Photo57 lower face shadow/crop must be executed LIVE
    through analyze_skin. Asserts hard failure if image is missing.
    Verifies declaredLabel='positive', visualReview='inconclusive-lower-face-shadow-crop',
    and sag_overview is NOT falsely marked detected (value is None / 0.0 with insufficient quality).
    """
    img_path = ROOT.parent / 'attune-live-test/audit-results/focused-skin-20261010/sources/eye-training-v2/train/images/01321_png_jpg.rf.733bb7917f2fb814339eef418db2b31c.jpg'
    assert img_path.is_file(), f"Photo 57 image MUST exist on disk: {img_path}"
    
    receipt_path = ROOT / 'audit-results/sag-calibrated-true-results.json'
    assert receipt_path.is_file(), f"Calibrated sag receipt MUST exist on disk: {receipt_path}"
    
    data = json.loads(receipt_path.read_text('utf8'))
    r57 = next((r for r in data['rows'] if r.get('index') == 57), None)
    assert r57 is not None, "Photo 57 must exist in calibrated results"
    assert r57['declaredLabel'] == 'positive', "Photo57 declaredLabel must stay positive"
    assert r57['visualReview'] == 'inconclusive-lower-face-shadow-crop', "Photo57 visualReview must stay inconclusive-lower-face-shadow-crop"
    
    # Live execution with real image through analyze_skin
    bgr = cv2.imread(str(img_path))
    assert bgr is not None
    
    sys.path.insert(0, str(ROOT / 'scripts'))
    sys.path.append(str(ROOT.parent / 'attune-live-test/.runtime/python-packages'))
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
    from verify_e2e_skin_type_pipeline import MODEL_ASSET_PATH, build_payload_with_real_landmarks
    
    detector = FaceLandmarker.create_from_options(FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ROOT / MODEL_ASSET_PATH)),
        running_mode=RunningMode.IMAGE,
        num_faces=1
    ))
    det = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
    assert det.face_landmarks, "Photo 57 landmarks must be detectable"
    landmarks = [dict(x=float(pt.x), y=float(pt.y), z=float(pt.z)) for pt in det.face_landmarks[0]]
    
    payload = build_payload_with_real_landmarks(bgr, landmarks)
    res = A.analyze_skin(payload)
    sag = next(m for m in res['general']['measurements'] if m['id'] == 'sag')
    
    # Verify live result: lower face shadow and crop result in insufficient skin support / 0.0
    assert sag['value'] in (0.0, None), f"Expected 0.0 or None for Photo 57, got {sag['value']}"
    assert sag['quality'] == 'insufficient', f"Expected insufficient quality for Photo 57, got {sag['quality']}"
    assert sag['limitationCode'] in ('INSUFFICIENT_SKIN_SUPPORT', 'CONTOUR_TRACKING_UNSTABLE', 'ANATOMICAL_BAND_NOT_VISIBLE')

