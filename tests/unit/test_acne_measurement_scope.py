"""Focused synthetic contracts for the post-hoc acne measurement/scope audit.
Synthetic inputs are not evidence of human or detector performance."""
import ast, hashlib, json, sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research'), str(ROOT / 'services/core-api')]
import audit_acne_measurement_scope as audit


def full(shape=(40, 40)):
    return np.ones(shape, bool)


def stages_with(**overrides):
    shape = (40, 40)
    return [(name, overrides.get(name, full(shape))) for name in audit.MASK_STAGES]


# 1. source/analysis/origin/scale transforms ------------------------------------
def test_source_analysis_roundtrip_and_frozen_warp_matrix():
    origin, scale = (30, 20), .5
    u, v = audit.source_to_analysis(50, 44, origin, scale)
    assert (u, v) == (10, 12) and audit.analysis_to_source(u, v, origin, scale) == (50, 44)
    # identical to evaluate_acne_classical.run(): [[1/s,0,ox],[0,1/s,oy]]
    assert np.array_equal(audit.analysis_to_source_matrix(origin, scale),
                          np.array([[1 / scale, 0, origin[0]], [0, 1 / scale, origin[1]]], np.float32))
    analysis = np.zeros((30, 30), bool); analysis[12, 10] = True
    native = audit.to_native(analysis, origin, scale, (100, 100))
    ys, xs = np.where(native)
    assert native[44, 50] and native.sum() == 4  # one analysis pixel = 1/scale^2 source pixels
    assert len(set(xs)) == 2 and len(set(ys)) == 2 and np.ptp(xs) == 1 and np.ptp(ys) == 1


# 2. crop-outside and boundary targets ----------------------------------------
def test_crop_outside_boundary_and_off_canvas_targets():
    crop = np.zeros((40, 40), bool); crop[:, 10:20] = True  # x=10,width=10 -> columns 10..19
    st = stages_with(PHOTO_INPUT_CROP=crop)
    inside_edge, _ = audit.attribute_masks(st, [18, 5, 20, 7])   # centre x=19: last crop column
    outside_edge, _ = audit.attribute_masks(st, [19, 5, 21, 7])  # centre x=20: first column outside
    assert inside_edge['centerFirstLoss'] is None and inside_edge['centerEligible']
    assert outside_edge['centerFirstLoss'] == 'PHOTO_INPUT_CROP' and outside_edge['boxFractionEligible'] == .5
    off, _ = audit.attribute_masks(st, [45, 45, 49, 49])
    assert off['centerFirstLoss'] == 'UNKNOWN' and off['centerEligible'] is None and off['boxFractionEligible'] is None


# 3. several rejection reasons, one non-duplicated first loss -------------------
def test_overlapping_reasons_keep_flags_but_count_target_once():
    hair = full(); glare = full(); hair[10, 10] = False; glare[10, 10] = False
    masks, _ = audit.attribute_masks(stages_with(HAIR=hair, GLARE_EXPOSURE=glare), [8, 8, 12.9, 12.9])
    assert masks['independent']['HAIR']['centerRejected'] and masks['independent']['GLARE_EXPOSURE']['centerRejected']
    assert masks['centerFirstLoss'] == 'HAIR'
    gate = dict(passed=True)
    outcome = audit.classify(gate, masks, True, False, False, None)
    counts = audit.tally([dict(k=outcome), dict(k='IOU_050_HIT')], 'k')
    assert counts == {'HAIR': 1, 'IOU_050_HIT': 1} and sum(counts.values()) == 2
    with pytest.raises(KeyError):
        audit.tally([dict(k='HAIR')], 'missing')  # malformed rows never silently vanish


# 4. centre outside, box partly inside -----------------------------------------
def test_center_lost_but_box_partly_eligible_is_reported_separately():
    excl = full(); excl[:, 10:] = False  # columns >= 10 excluded
    masks, _ = audit.attribute_masks(stages_with(AUTO_EXCLUSION=excl), [6, 6, 14, 10])  # centre x=10
    assert masks['centerFirstLoss'] == 'AUTO_EXCLUSION' and masks['areaFullLossStage'] is None
    assert masks['boxFractionEligible'] == .5
    gate = dict(passed=True)
    assert audit.classify(gate, masks, True, True, False, None) == 'AUTO_EXCLUSION'
    assert audit.classify_area(gate, masks, True, True, False, None) == 'COMPONENT_FILTERS'
    gone = full(); gone[:] = False
    lost, _ = audit.attribute_masks(stages_with(HAIR=gone), [6, 6, 14, 10])
    assert lost['areaFullLossStage'] == 'HAIR' and audit.classify_area(gate, lost, True, False, False, None) == 'HAIR'


# 5. small kernel inside a large target: IoU bound ------------------------------
def test_small_kernel_large_box_iou_bound():
    target = [0, 0, 11.5, 19.5]; kernel = [3, 7, 8, 12]  # 5x5 candidate fully inside the target box
    expected = 25 / (11.5 * 19.5)
    assert audit.iou(target, kernel) == pytest.approx(expected)
    assert audit.size_bound_iou(target, kernel) == pytest.approx(expected) and expected < .5
    tight = audit.max_reachable_iou(11.5, 19.5, (25, 25), (.45, 2.2))
    assert tight == pytest.approx(expected, rel=1e-3) and tight < .5
    assert audit.max_reachable_iou(11.5, 19.5, (10, 1000), (.45, 2.2)) > .99
    assert audit.max_reachable_iou(0, 5, (1, 2), (.45, 2.2)) is None
    assert audit.scale_band(target) == 'medium' and audit.scale_band([0, 0, 7.9, 3]) == 'micro'


# 6. one-to-one matching -------------------------------------------------------
def test_one_candidate_never_satisfies_two_targets():
    truth = [[0, 0, 10, 10], [4, 4, 14, 14]]; pred = [[5, 5, 9, 9]]  # centre (7,7) inside both
    assert audit.center_hits(truth, pred) == [[0, 0]]
    loose = audit.greedy_one_to_one(truth, pred, lambda v: v > 0)
    assert len(loose) == 1 and loose[0][1] == 0
    assert audit.greedy_one_to_one(truth, pred, lambda v: v >= .5) == []
    from acne_lab_dog import match_boxes
    assert match_boxes(truth, pred) == audit.greedy_one_to_one(truth, pred, lambda v: v >= .5)


# 7. invalid / UNKNOWN never becomes a healthy zero --------------------------
def test_invalid_and_rejected_inputs_stay_unmeasured():
    rejected = audit.gate_attribution(
        dict(sha256='x' * 64, quality=dict(status='BLURRY', isValid=False), alignment=dict(faceDetected=True), poseEligible=False, snapshotError=None),
        dict(fullStaticProductPass=False, eyewearFrontend=None, eyewearBackend=None))
    assert rejected['firstLoss'] == 'QUALITY' and rejected['independent']['POSE'] and rejected['independent']['EYEWEAR'] is None
    assert audit.classify(rejected, None, False, None, False, None) == 'PRODUCT_GATE'
    off, _ = audit.attribute_masks(stages_with(), [80, 80, 90, 90])
    assert audit.classify(dict(passed=True), off, True, None, False, None) == 'UNKNOWN'
    assert audit.classify_area(dict(passed=True), off, True, None, False, None) == 'UNKNOWN'
    ok, _ = audit.attribute_masks(stages_with(), [8, 8, 12, 12])
    assert audit.classify(dict(passed=True), ok, False, None, False, None) == 'REPLAY_UNVERIFIED'
    rows = [dict(targetId='a#0', cohort='heldout-train', gatePassed=False, scaleBand='small',
                 outcome={m: dict(primary='PRODUCT_GATE', area='PRODUCT_GATE') for m in 'AB'})]
    summary = audit.summarize(rows)
    assert summary['controlsGateRejected']['A']['primary'] == {'PRODUCT_GATE': 1}
    assert 'IOU_050_HIT' not in summary['controlsGateRejected']['A']['primary'] and summary['controlsMeasured']['targets'] == 0
    with pytest.raises(audit.AuditError):
        audit.gate_attribution(dict(sha256='y' * 64, quality=dict(status='OPTIMAL', isValid=True), alignment={}, poseEligible=False, snapshotError=None),
                               dict(fullStaticProductPass=True))


def test_frozen_b_replay_reasons_reproduce_frozen_detect():
    import cv2
    from acne_lab_dog import detect
    image = np.full((240, 240, 3), (120, 150, 180), np.uint8); yy, xx = np.mgrid[:240, :240]
    image[:, :, 2] = np.clip(image[:, :, 2] + np.exp(-((xx - 120) ** 2 + (yy - 120) ** 2) / 18) * 65, 0, 255).astype(np.uint8)
    roi = np.zeros((240, 240), bool); roi[20:220, 20:220] = True
    crop = dict(x=0, y=0, width=240, height=240)
    rb = audit.replay_b(image, roi, crop, 200., dict(forehead=roi))
    objects, _, _ = detect(image, roi, 200.)
    assert rb['valid'] and sum(c['reason'] == 'ACCEPTED' for c in rb['components']) == len(objects) > 0
    empty = audit.replay_b(image, np.zeros_like(roi), crop, 200., dict(forehead=roi))
    assert empty == dict(valid=False, reason='INSUFFICIENT_VISIBLE_ROI')


# 8. frozen method/config/input identities --------------------------------------
def test_frozen_method_identities_are_pinned():
    lab = ROOT / 'scripts/skin-research/acne_lab_dog.py'
    assert audit.normalized_text_sha(lab) == '5bc824456badcd329b78951f2274e8ddd7f3bf09e34c7cf5183c454239c235e9'
    source = (ROOT / 'services/core-api/appearance_analysis.py').read_text('utf8'); tree = ast.parse(source)
    node = next(v for v in tree.body if isinstance(v, ast.FunctionDef) and v.name == 'acne_candidates')
    assert hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest() == audit.A_FUNCTION_SHA256
    from acne_lab_dog import VERSION, CONFIG
    assert VERSION == 'acne-lab-dog-mad-native-v1' and CONFIG['madK'] == 3.5 and CONFIG['sigmaFaceFractions'] == [.0035, .006, .010]
    assert audit.FROZEN_COMMIT == '5f11c111e3f6547e6420ddf37db477190d232f10'


def test_identity_drift_and_root_overlap_fail_closed(tmp_path):
    code, inp = tmp_path / 'code', tmp_path / 'in'
    for p in audit.CODE_FILES:
        (code / p).parent.mkdir(parents=True, exist_ok=True); (code / p).write_bytes(b'x = 1\r\n')
    for p in audit.INPUT_FILES:
        (inp / p).parent.mkdir(parents=True, exist_ok=True); (inp / p).write_text('{}', 'utf8')
    manifest = dict(version=audit.VERSION, frozenManifestSHA256=audit.FROZEN_MANIFEST_SHA256,
                    code={p: dict(normalizedSHA256=audit.normalized_text_sha(code / p)) for p in audit.CODE_FILES},
                    inputs={p: dict(sha256=audit.sha_file(inp / p)) for p in audit.INPUT_FILES})
    audit.verify_manifest(manifest, code, inp)
    (code / audit.CODE_FILES[3]).write_bytes(b'x = 1\n')  # CRLF->LF only: same normalized identity
    audit.verify_manifest(manifest, code, inp)
    (code / audit.CODE_FILES[3]).write_bytes(b'x = 2\n')
    with pytest.raises(audit.AuditError, match='CODE_IDENTITY_CHANGED'):
        audit.verify_manifest(manifest, code, inp)
    (code / audit.CODE_FILES[3]).write_bytes(b'x = 1\n'); (inp / audit.INPUT_FILES[0]).write_text('{"a":1}', 'utf8')
    with pytest.raises(audit.AuditError, match='INPUT_IDENTITY_CHANGED'):
        audit.verify_manifest(manifest, code, inp)
    with pytest.raises(audit.AuditError, match='OUTPUT_ROOT_INSIDE_INPUT_ROOT'):
        audit.check_roots(inp, inp / 'audit-results' / 'x')
    assert audit.map_path('C:\\A B\\x\\y.jpg', [('C:\\A B', '/mnt/t')]) == Path('/mnt/t/x/y.jpg')


def test_unevaluated_stage_flag_is_unknown_not_rejected_and_region_split():
    canvas = full(); canvas[:, 20:] = False  # analysis canvas ends at column 20
    gray = canvas.copy()                      # outside canvas the gray stage cannot pass
    st = [(n, m, canvas) if n == 'GRAY_THRESHOLD' else (n, m) for n, m in stages_with(GRAY_THRESHOLD=gray)]
    masks, _ = audit.attribute_masks(st, [28, 8, 32, 12])
    assert masks['independent']['GRAY_THRESHOLD']['centerRejected'] is None
    assert masks['independent']['GRAY_THRESHOLD']['boxFractionPassing'] is None
    assert masks['centerFirstLoss'] == 'GRAY_THRESHOLD'  # sequential support loss is still recorded once
    assert audit.region_category(True, True, False, 'FRONT') == 'PRESENTATION_MESH_CELL_GAP'
    assert audit.region_category(False, False, False, 'RIGHT') == 'OUTSIDE_EXPORTED_REGIONS_SIDE_POSE'
    assert audit.region_category(True, False, False, 'FRONT') == 'OUTSIDE_EXPORTED_REGION_ENVELOPES'
    assert audit.region_category(None, None, None, 'FRONT') == 'UNKNOWN'
