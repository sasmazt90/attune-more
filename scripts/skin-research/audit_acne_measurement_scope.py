"""Post-hoc per-target loss and measurement-scope audit over FROZEN classical A/B outputs.

Diagnostic only. This is NOT a detector, a new candidate run, a fit, a threshold
search or a product decision; production acne stays accepted:false, file:null.

* The frozen A/B candidate lists in the classical comparison are authoritative.
  Stage 8/9 attribution replays only the frozen preprocessing/response fields
  with the frozen code and is used ONLY when the replay reproduces the frozen
  candidate list exactly (otherwise that photo/method is REPLAY_UNVERIFIED).
* Source boxes are boxes, not pixel masks. Box/mask area intersections are
  support geometry, never lesion-pixel visibility or Dice.
* Rejected or invalid inputs stay NOT_MEASURED/UNKNOWN; never a healthy zero.
* input-root is opened read-only; every output goes under output-root, which
  may not live inside input-root.
"""
import argparse, hashlib, json, math, os, sys, time
from pathlib import Path

import numpy as np

VERSION = 'acne-measurement-scope-audit-v1'
FROZEN_COMMIT = '5f11c111e3f6547e6420ddf37db477190d232f10'
FROZEN_MANIFEST_SHA256 = '719218a1c818ee637d442c06c8ef9318fa2da18ec550ed9d9e3b7fe16f2da55d'
A_FUNCTION_SHA256 = 'c6f8907466539fdcbe79f5f62c986d59d36692d8fd2c2a768bf6cec70086827e'
TAKEOVER = 'audit-results/acne-takeover-20261015'
COMPARISON = 'audit-results/acne-classical-comparison-20261015'
REGIONS = ('forehead', 'rightCheek', 'leftCheek', 'nose', 'chin')
GATE_ORDER = ('NO_FACE', 'QUALITY', 'POSE', 'SNAPSHOT_FRAME', 'EYEWEAR')
# Explicit, pre-registered order for the sequential first-loss attribution.
MASK_STAGES = ('PHOTO_INPUT_CROP', 'ANATOMICAL_REGION', 'AUTO_EXCLUSION', 'ANATOMICAL_EXCLUSION',
               'HAIR', 'GLARE_EXPOSURE', 'GRAY_THRESHOLD')
STAGES = ('PRODUCT_GATE',) + MASK_STAGES + ('CANDIDATE_GENERATION', 'COMPONENT_FILTERS')
OUTCOMES = STAGES + ('LOCALIZATION_IOU_BELOW_050', 'IOU_050_HIT', 'REPLAY_UNVERIFIED', 'UNKNOWN')
CODE_FILES = ('scripts/skin-research/audit_acne_measurement_scope.py',
              'scripts/skin-research/evaluate_acne_classical.py',
              'scripts/skin-research/prepare_acne_classical_comparison.py',
              'scripts/skin-research/acne_lab_dog.py',
              'scripts/skin-research/heavy_job_lease.py',
              'scripts/skin-research/compute_owner_observer.py',
              'services/core-api/appearance_analysis.py',
              'services/core-api/skin_models.py',
              'services/core-api/skin_scan_baseline/blemishes.py',
              'services/core-api/skin_scan_baseline/oiliness.py')
INPUT_FILES = (TAKEOVER + '/browser-preflight.json',
               TAKEOVER + '/inputs/original-reviewed-detector-data.json',
               TAKEOVER + '/inputs/annotation-scope-manifest.json',
               TAKEOVER + '/evaluation-step0/summary.json',
               COMPARISON + '/preregistered-manifest.json',
               COMPARISON + '/A/results.json',
               COMPARISON + '/B/results.json',
               COMPARISON + '/negative-visibility-adjudication.json')


class AuditError(RuntimeError):
    pass


# ----------------------------------------------------------------- identities
def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def normalized_text_sha(path):
    """Line-ending independent identity (a Windows CRLF checkout and an LF
    worktree of the same Git blob must agree)."""
    return sha_bytes(Path(path).read_bytes().replace(b'\r\n', b'\n'))


def read_json(path):
    return json.loads(Path(path).read_text('utf8'))


def check_roots(input_root, output_root):
    i, o = Path(input_root).resolve(), Path(output_root).resolve()
    if o == i or i in o.parents:
        raise AuditError('OUTPUT_ROOT_INSIDE_INPUT_ROOT')
    if not (i / TAKEOVER).is_dir() or not (i / COMPARISON).is_dir():
        raise AuditError('INPUT_ROOT_MISSING_FROZEN_RESULTS')
    return i, o


def map_path(path, path_maps):
    """Frozen manifests hold Windows absolute paths; map them read-only."""
    text = str(path)
    for prefix, local in path_maps:
        if text.lower().startswith(prefix.lower()):
            rest = text[len(prefix):].replace('\\', '/').lstrip('/')
            return Path(local) / rest
    return Path(text)


# ------------------------------------------------------------ coordinates
def source_to_analysis(x, y, origin, scale):
    return (x - origin[0]) * scale, (y - origin[1]) * scale


def analysis_to_source(u, v, origin, scale):
    return u / scale + origin[0], v / scale + origin[1]


def analysis_to_source_matrix(origin, scale):
    """Exactly the frozen evaluate_acne_classical warp (dst->src inverse map
    with WARP default: OpenCV inverts this forward analysis->source matrix)."""
    return np.array([[1 / scale, 0, origin[0]], [0, 1 / scale, origin[1]]], np.float32)


def to_native(mask, origin, scale, shape):
    import cv2
    return cv2.warpAffine(np.asarray(mask).astype(np.uint8), analysis_to_source_matrix(origin, scale),
                          (shape[1], shape[0]), flags=cv2.INTER_NEAREST) > 0


def box_center(box):
    """Frozen measure() convention: int() of the float box centre."""
    return int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2)


def box_window(box, shape):
    """Frozen measure() pixel window: [int(y), ceil(ey)) x [int(x), ceil(ex))."""
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(shape[1], int(math.ceil(box[2]))), min(shape[0], int(math.ceil(box[3])))
    return (y0, y1, x0, x1) if x1 > x0 and y1 > y0 else None


def center_value(mask, box):
    """True/False when the centre is on the source canvas, None (UNKNOWN) otherwise."""
    cx, cy = box_center(box)
    if not (0 <= cy < mask.shape[0] and 0 <= cx < mask.shape[1]):
        return None
    return bool(mask[cy, cx])


def window_fraction(mask, box):
    w = box_window(box, mask.shape)
    if w is None:
        return None
    patch = mask[w[0]:w[1], w[2]:w[3]]
    return float(patch.mean())


def box_area(box):
    return max(0., box[2] - box[0]) * max(0., box[3] - box[1])


def iou(a, b):
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.


# ------------------------------------------------------------- attribution
def gate_attribution(pre, ev):
    """Photo-level product gate. Independent flags (True=rejects, False=passes,
    None=not evaluated) and one explicit first-loss reason."""
    q = pre.get('quality') or {}
    al = pre.get('alignment') or {}
    flags = dict(NO_FACE=q.get('status') == 'NO_FACE' or al.get('faceDetected') is False,
                 QUALITY=None if q.get('isValid') is None else not q['isValid'],
                 POSE=None if pre.get('poseEligible') is None else not pre['poseEligible'],
                 SNAPSHOT_FRAME=pre.get('snapshotError') is not None)
    eye = [v.get('status') for v in (ev.get('eyewearFrontend'), ev.get('eyewearBackend')) if v]
    flags['EYEWEAR'] = None if not eye else any(s != 'CLEAR' for s in eye)
    passed = bool(ev.get('fullStaticProductPass'))
    first = next((k for k in GATE_ORDER if flags[k]), None)
    if not passed and first is None:
        first = 'UNATTRIBUTED_PRODUCT_REJECTION'
    if passed and first is not None:
        raise AuditError('GATE_FLAGS_CONTRADICT_PASS:' + pre['sha256'][:8])
    return dict(passed=passed, firstLoss=first, independent=flags,
                qualityStatus=q.get('status'), eyewearStatuses=eye, snapshotError=pre.get('snapshotError'))


def attribute_masks(stage_masks, box):
    """stage_masks: ordered [(stage, pass_mask)]. Returns independent and
    sequential (cumulative) centre/area attribution. Each target receives
    exactly one centre first-loss; overlapping reasons stay as flags."""
    if not stage_masks:
        raise AuditError('NO_STAGE_MASKS')
    shape = stage_masks[0][1].shape
    cumulative = np.ones(shape, bool)
    independent, sequential = {}, []
    first_center, full_area_loss = None, None
    center_known = center_value(cumulative, box) is not None
    for stage, mask in stage_masks:
        c = center_value(mask, box)
        independent[stage] = dict(centerRejected=None if c is None else not c,
                                  boxFractionPassing=window_fraction(mask, box))
        cumulative = cumulative & mask
        cc = center_value(cumulative, box)
        frac = window_fraction(cumulative, box)
        sequential.append(dict(stage=stage, centerPasses=cc, boxFractionRemaining=frac))
        if cc is False and first_center is None:
            first_center = stage
        if frac is not None and frac == 0 and full_area_loss is None:
            full_area_loss = stage
    return dict(centerOnCanvas=center_known,
                centerFirstLoss=first_center if center_known else 'UNKNOWN',
                areaFullLossStage=full_area_loss,
                centerEligible=(first_center is None) if center_known else None,
                boxFractionEligible=window_fraction(cumulative, box),
                independent=independent, sequential=sequential), cumulative


def center_hits(truth, pred):
    """Frozen secondary metric reproduced verbatim: target order, first unused
    candidate whose centre is inside the box; one candidate, one target."""
    used, hits = set(), []
    for ti, (x, y, ex, ey) in enumerate(truth):
        for pi, (bx, by, bex, bey) in enumerate(pred):
            if pi not in used and x <= (bx + bex) / 2 <= ex and y <= (by + bey) / 2 <= ey:
                used.add(pi); hits.append([ti, pi]); break
    return hits


def greedy_one_to_one(truth, pred, accept):
    """Greedy by IoU, each target and candidate at most once. `accept(iou)`
    decides eligibility; used for the frozen >=.50 rule and the loose >0 rule."""
    cand = [(iou(a, b), i, j) for i, a in enumerate(truth) for j, b in enumerate(pred)]
    cand = [c for c in cand if accept(c[0])]
    ut, up, pairs = set(), set(), []
    for score, i, j in sorted(cand, key=lambda v: (-v[0], v[1], v[2])):
        if i not in ut and j not in up:
            ut.add(i); up.add(j); pairs.append([i, j, score])
    return pairs


def max_reachable_iou(target_w, target_h, area_range, aspect_range, steps=241):
    """Upper bound of IoU between a target box and ANY axis-aligned box whose
    area lies in area_range and width/height in aspect_range (concentric
    placement is optimal). Pure geometry bound, not a fit."""
    if target_w <= 0 or target_h <= 0 or area_range[1] <= 0:
        return None
    lo, hi = max(area_range[0], 1e-9), area_range[1]
    if lo > hi:
        return None
    best = 0.
    for area in np.geomspace(lo, hi, steps):
        for aspect in np.geomspace(aspect_range[0], aspect_range[1], steps):
            w = math.sqrt(area * aspect); h = area / w
            inter = min(w, target_w) * min(h, target_h)
            best = max(best, inter / (target_w * target_h + area - inter))
    return float(best)


def size_bound_iou(a, b):
    """Area-ratio bound: IoU(a,b) <= min(area)/max(area)."""
    x, y = box_area(a), box_area(b)
    return min(x, y) / max(x, y) if max(x, y) > 0 else None


def scale_band(box):
    side = max(box[2] - box[0], box[3] - box[1])
    return 'micro' if side < 8 else 'small' if side < 16 else 'medium'


def classify(gate, masks, replay_ok, raw_in_box, accepted_overlap, best_iou):
    """One primary (centre-based) outcome per target/method; first loss wins."""
    if not gate['passed']:
        return 'PRODUCT_GATE'
    if masks is None or masks['centerFirstLoss'] == 'UNKNOWN':
        return 'UNKNOWN'
    if masks['centerFirstLoss'] is not None:
        return masks['centerFirstLoss']
    if best_iou is not None and best_iou >= .5:
        return 'IOU_050_HIT'
    if accepted_overlap:
        return 'LOCALIZATION_IOU_BELOW_050'
    if not replay_ok:
        return 'REPLAY_UNVERIFIED'
    if not raw_in_box:
        return 'CANDIDATE_GENERATION'
    return 'COMPONENT_FILTERS'


def classify_area(gate, masks, replay_ok, raw_in_box, accepted_overlap, best_iou):
    """Secondary outcome: a mask stage loses a target only when NO box area
    remains eligible; otherwise later stages are judged on the remaining area."""
    if not gate['passed']:
        return 'PRODUCT_GATE'
    if masks is None or masks['boxFractionEligible'] is None:
        return 'UNKNOWN'
    if masks['areaFullLossStage'] is not None:
        return masks['areaFullLossStage']
    if best_iou is not None and best_iou >= .5:
        return 'IOU_050_HIT'
    if accepted_overlap:
        return 'LOCALIZATION_IOU_BELOW_050'
    if not replay_ok:
        return 'REPLAY_UNVERIFIED'
    return 'CANDIDATE_GENERATION' if not raw_in_box else 'COMPONENT_FILTERS'


def tally(rows, key):
    counts = {k: 0 for k in OUTCOMES}
    for r in rows:
        counts[r[key]] = counts.get(r[key], 0) + 1
    if sum(counts.values()) != len(rows):
        raise AuditError('DOUBLE_COUNT')
    return {k: v for k, v in counts.items() if v}


# ------------------------------------------------------------ frozen replays
def replay_a(ctx, eligible):
    """Frozen A, reason-annotated. Mirrors appearance_analysis.acne_candidates
    and evaluate_acne_classical.run(A) ownership; verified against both."""
    import cv2
    from skin_scan_baseline.blemishes import blemish_map
    from appearance_analysis import acne_candidates
    baseline = blemish_map(ctx['image'], {k: (v * 255).astype(np.uint8) for k, v in ctx['masks'].items()})
    red, gray, sat, high, lc, overall = (ctx[k] for k in ('red', 'gray', 'saturation', 'high', 'local_contrast', 'overall'))
    red_center = red - cv2.GaussianBlur(red, (0, 0), 4)
    scale2 = red - cv2.GaussianBlur(red, (0, 0), 2)
    detected = (red_center > .055) & (scale2 > .028) & (lc > .008) & (baseline > .02) & overall
    n, labels, stats, _ = cv2.connectedComponentsWithStats(detected.astype(np.uint8))
    support = cv2.erode(overall.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    regions = {k: v for k, v in ctx['masks'].items() if k in REGIONS}
    comps, stage1 = [], []
    for label in range(1, n):
        x, y, w, h, count = map(int, stats[label]); blob = labels == label; reason = None
        if not 5 <= count <= 180: reason = 'SIZE'
        elif not .45 <= w / max(h, 1) <= 2.2 or count / max(w * h, 1) < .38: reason = 'SHAPE'
        elif not support[blob].all(): reason = 'SUPPORT_EROSION'
        elif np.mean(gray[blob]) < .20: reason = 'GRAY'
        elif np.mean(sat[blob]) < .12: reason = 'SATURATION'
        elif np.mean(high[blob] > 0) < .08: reason = 'HIGH_FREQUENCY'
        if reason is None:
            stage1.append((x, y, w, h, count))
            owners = [k for k in REGIONS if k in regions and regions[k][blob].mean() >= .65]
            if not owners or not eligible[blob].all(): reason = 'SHARED_SCOPE_OR_OWNERSHIP'
        comps.append(dict(label=label, box=[x, y, w, h], count=count, reason=reason or 'ACCEPTED', owner=None))
    frozen, _ = acne_candidates(red, gray, sat, high, lc, baseline, overall)
    if [tuple(v[:5]) for v in frozen] != stage1:
        raise AuditError('A_REPLAY_DIVERGES_FROM_PRODUCTION_FUNCTION')
    return dict(raw=detected, labels=labels, components=comps, space='analysis')


def replay_b(image, native_eligible, crop, face_pixels, native_regions):
    """Frozen B, reason-annotated. Mirrors acne_lab_dog.detect + run(B)."""
    import cv2
    from acne_lab_dog import CONFIG, detect
    x, y, w, h = (crop[k] for k in ('x', 'y', 'width', 'height'))
    bgr, el = image[y:y + h, x:x + w], native_eligible[y:y + h, x:x + w]
    objects, _, diag = detect(bgr, el, face_pixels)
    if not diag['valid']:
        return dict(valid=False, reason=diag['reason'])
    lab = cv2.cvtColor(bgr.astype(np.float32) / 255., cv2.COLOR_BGR2LAB); a = lab[:, :, 1]
    local = a - cv2.GaussianBlur(a, (0, 0), max(.6, face_pixels * CONFIG['localSurroundFaceFraction']))
    response = np.zeros(a.shape, np.float32)
    for s in [max(.6, face_pixels * v) for v in CONFIG['sigmaFaceFractions']]:
        np.maximum(response, cv2.GaussianBlur(a, (0, 0), s) - cv2.GaussianBlur(a, (0, 0), s * CONFIG['surroundRatio']), out=response)
    values = response[el]; med = float(np.median(values)); mad = float(np.median(np.abs(values - med)))
    thr = max(CONFIG['minimumAResponse'], med + CONFIG['madK'] * CONFIG['madScale'] * mad)
    if thr != diag['threshold']:
        raise AuditError('B_THRESHOLD_REPLAY_DIVERGES')
    radius = max(1, int(round(face_pixels * CONFIG['borderFaceFraction'])))
    interior = cv2.erode(el.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))) > 0
    binary = (response > thr) & (local > CONFIG['minimumLocalA']) & el
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary.astype(np.uint8))
    f2 = face_pixels ** 2; comps, kept = [], []
    for i in range(1, n):
        bx, by, bw, bh, count = map(int, stats[i]); patch = labels[by:by + bh, bx:bx + bw] == i; reason = None
        if not max(3, f2 * CONFIG['minAreaFaceSquared']) <= count <= f2 * CONFIG['maxAreaFaceSquared']: reason = 'SIZE'
        elif not CONFIG['aspect'][0] <= bw / max(bh, 1) <= CONFIG['aspect'][1] or count / (bw * bh) < CONFIG['minFill']: reason = 'SHAPE'
        elif not interior[by:by + bh, bx:bx + bw][patch].all(): reason = 'BOUNDARY_OR_EXCLUSION'
        elif float(lab[by:by + bh, bx:bx + bw, 0][patch].mean()) < CONFIG['minimumL']: reason = 'DARK'
        if reason is None:
            kept.append((bx, by, bw, bh, count))
            pix = np.column_stack(np.where(labels == i))[:, ::-1] + [x, y]
            owners = [k for k in REGIONS if k in native_regions and native_regions[k][pix[:, 1], pix[:, 0]].mean() >= .65]
            if not owners: reason = 'OWNERSHIP'
        comps.append(dict(label=i, box=[bx + x, by + y, bw, bh], count=count, reason=reason or 'ACCEPTED'))
    if [(o['x'], o['y'], o['width'], o['height'], o['areaPixels']) for o in objects] != kept:
        raise AuditError('B_REPLAY_DIVERGES_FROM_FROZEN_DETECT')
    raw = np.zeros(native_eligible.shape, bool); raw[y:y + h, x:x + w] = binary
    full_labels = np.zeros(native_eligible.shape, np.int32); full_labels[y:y + h, x:x + w] = labels
    return dict(valid=True, raw=raw, labels=full_labels, components=comps, space='native',
                response=response, local=local, threshold=thr)


def b_crop_counterfactual(image, native_eligible, crop, face_pixels):
    """A/B crop asymmetry: B's response field filtered on the full source vs the
    frozen photo_input crop, compared INSIDE the crop on the same eligible
    sample. Pixel flips only; no components or candidates are formed."""
    import cv2
    from acne_lab_dog import CONFIG
    x, y, w, h = (crop[k] for k in ('x', 'y', 'width', 'height'))

    def field(bgr):
        lab = cv2.cvtColor(bgr.astype(np.float32) / 255., cv2.COLOR_BGR2LAB); a = lab[:, :, 1]
        local = a - cv2.GaussianBlur(a, (0, 0), max(.6, face_pixels * CONFIG['localSurroundFaceFraction']))
        resp = np.zeros(a.shape, np.float32)
        for s in [max(.6, face_pixels * v) for v in CONFIG['sigmaFaceFractions']]:
            np.maximum(resp, cv2.GaussianBlur(a, (0, 0), s) - cv2.GaussianBlur(a, (0, 0), s * CONFIG['surroundRatio']), out=resp)
        return resp, local

    el = native_eligible[y:y + h, x:x + w]
    out = {}
    for name, (resp, local) in (('crop', field(image[y:y + h, x:x + w])),
                                ('full', tuple(v[y:y + h, x:x + w] for v in field(image)))):
        values = resp[el]; med = float(np.median(values)); mad = float(np.median(np.abs(values - med)))
        thr = max(CONFIG['minimumAResponse'], med + CONFIG['madK'] * CONFIG['madScale'] * mad)
        out[name] = dict(binary=(resp > thr) & (local > CONFIG['minimumLocalA']) & el, threshold=thr)
    flips = out['crop']['binary'] ^ out['full']['binary']
    native_flips = np.zeros(native_eligible.shape, bool); native_flips[y:y + h, x:x + w] = flips
    return dict(thresholdCrop=out['crop']['threshold'], thresholdFull=out['full']['threshold'],
                rawPixelsCrop=int(out['crop']['binary'].sum()), rawPixelsFull=int(out['full']['binary'].sum()),
                flippedPixels=int(flips.sum()), eligiblePixels=int(el.sum())), native_flips


# --------------------------------------------------------------- stage masks
def stage_masks_for(ctx, payload_exclusions, crop, shape):
    """Recompose the frozen shared eligible support from named parts, in
    analysis space, then map each to native source pixels with the frozen warp."""
    import cv2
    gshape = ctx['gray'].shape; scale = ctx['scale']; x0, y0 = ctx['origin']
    masks = ctx['masks']
    region5 = np.logical_or.reduce([masks[k] for k in REGIONS if k in masks])
    allmesh = np.logical_or.reduce(list(masks.values()))
    face = ctx['face_support'] > 0
    rects = np.zeros(gshape, np.uint8)
    for b in payload_exclusions:
        x = int((b['x'] - x0) * scale); y = int((b['y'] - y0) * scale); w = int(b['w'] * scale); h = int(b['h'] * scale)
        cv2.rectangle(rects, (max(0, x), max(0, y)), (max(0, x + w), max(0, y + h)), 255, -1)
    edge = np.zeros(gshape, np.uint8); e = max(2, int(round(4 * scale)))
    edge[:e, :] = 255; edge[-e:, :] = 255; edge[:, :e] = 255; edge[:, -e:] = 255
    points, width, height = ctx['points'], ctx['width'], ctx['bgr'].shape[0]
    holes = np.zeros(gshape, np.uint8)
    for idx in ctx['holes']:
        poly = np.asarray([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in idx], np.int32)
        cv2.fillPoly(holes, [poly], 255)
    margin = ctx['margin']
    ocular = cv2.dilate(ctx['ocular'], cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margin * 2 + 1, margin * 2 + 1)))
    brow = np.zeros(gshape, np.uint8)
    for idx in ctx['holes'][4:]:
        poly = np.asarray([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in idx], np.float32)
        cv2.fillConvexPoly(brow, cv2.convexHull(poly).astype(np.int32), 255)
    if not np.array_equal((rects | edge | holes) > 0, ctx['exclusion'] > 0):
        raise AuditError('EXCLUSION_DECOMPOSITION_MISMATCH')
    if not np.array_equal((ctx['exclusion'] | ocular | brow) > 0, ctx['acne_exclusion'] > 0):
        raise AuditError('ACNE_EXCLUSION_DECOMPOSITION_MISMATCH')
    parts = dict(region5=region5, allMeshUnion=allmesh, faceOval=face, autoRectangles=rects > 0, frameEdge=edge > 0,
                 landmarkHoles=holes > 0, ocularMargin=ocular > 0, browHull=brow > 0, hair=ctx['hair'],
                 valueClipping=ctx['clipping'], allChannelClipping=ctx['acne_clipping'], grayAtOrBelow012=~(ctx['gray'] > .12))
    native = {k: to_native(v, ctx['origin'], scale, shape) for k, v in parts.items()}
    canvas = to_native(np.ones(gshape, bool), ctx['origin'], scale, shape)
    crop_mask = np.zeros(shape, bool); crop_mask[crop['y']:crop['y'] + crop['height'], crop['x']:crop['x'] + crop['width']] = True
    stages = [('PHOTO_INPUT_CROP', crop_mask),
              ('ANATOMICAL_REGION', canvas & native['region5'] & native['allMeshUnion'] & native['faceOval']),
              ('AUTO_EXCLUSION', ~(native['autoRectangles'] | native['frameEdge'])),
              ('ANATOMICAL_EXCLUSION', ~(native['landmarkHoles'] | native['ocularMargin'] | native['browHull'])),
              ('HAIR', ~native['hair']),
              ('GLARE_EXPOSURE', ~(native['valueClipping'] | native['allChannelClipping'])),
              ('GRAY_THRESHOLD', canvas & ~native['grayAtOrBelow012'])]
    return stages, native, canvas


# ------------------------------------------------------------------- inputs
def load_frozen(input_root):
    i = Path(input_root)
    pre = {r['sha256']: r for r in read_json(i / TAKEOVER / 'browser-preflight.json')['rows']}
    orig = {r['sha256']: r for r in read_json(i / TAKEOVER / 'inputs/original-reviewed-detector-data.json')['rows']}
    scope = {r['sha256']: r for r in read_json(i / TAKEOVER / 'inputs/annotation-scope-manifest.json')['images']}
    ev = {r['sha256']: r for r in read_json(i / TAKEOVER / 'evaluation-step0/summary.json')['rows']}
    man = read_json(i / COMPARISON / 'preregistered-manifest.json')
    res = {m: {r['sha256']: r for r in read_json(i / COMPARISON / m / 'results.json')['rows']} for m in 'AB'}
    return pre, orig, scope, ev, man, res


def targets_for(sha, cohort, orig, scope):
    """Fixed source targets exactly as the frozen comparison selected them."""
    if cohort == 'scope-B-development':
        anns = [v for v in scope[sha]['annotations'] if v['scopeCategory'] == 'IN_SCOPE_VISIBLE_REGION']
        return [dict(box=list(map(float, v['box'])), annotationIndex=v.get('annotationIndex')) for v in anns]
    return [dict(box=list(map(float, v['box'])), annotationIndex=k) for k, v in enumerate(orig[sha].get('annotations', []))]


def build_manifest(code_root, input_root, path_maps):
    code_root, input_root = Path(code_root), Path(input_root)
    pre, orig, scope, ev, man, res = load_frozen(input_root)
    if sha_file(input_root / COMPARISON / 'preregistered-manifest.json') != FROZEN_MANIFEST_SHA256:
        raise AuditError('FROZEN_MANIFEST_CHANGED')
    photos, targets = [], []
    for row in man['rows']:
        s = row['sha256']; t = targets_for(s, row['cohort'], orig, scope)
        snap = input_root / TAKEOVER / 'product-inputs' / s / 'snapshot.png'
        photos.append(dict(sha256=s, cohort=row['cohort'], staticProductPass=row['staticProductPass'],
                           snapshotSHA256=row['snapshotSHA256'], sourceFileSHA256=row['sourceFileSHA256'],
                           sourcePathMapped=str(map_path(row['sourcePath'], path_maps)), targetCount=len(t),
                           frozenResultSHA256={m: sha_file(input_root / COMPARISON / m / (s + '.json')) for m in 'AB'
                                               if (input_root / COMPARISON / m / (s + '.json')).exists()},
                           snapshotPresent=snap.exists()))
        for k, v in enumerate(t):
            targets.append(dict(targetId=f'{s[:8]}#{k}', sha256=s, index=k, cohort=row['cohort'], box=v['box'],
                                annotationIndex=v['annotationIndex'], scaleBand=scale_band(v['box'])))
    def count(f): return sum(1 for t in targets if f(t))
    measured = {p['sha256'] for p in photos if p['staticProductPass']}
    return dict(
        version=VERSION, kind='post-hoc diagnostic re-evaluation of frozen outputs; NOT a product acceptance input',
        productDecisionChanged=False, productionAcne=dict(accepted=False, file=None),
        frozenCommit=FROZEN_COMMIT, frozenManifestSHA256=FROZEN_MANIFEST_SHA256, aFunctionSHA256=A_FUNCTION_SHA256,
        code={p: dict(normalizedSHA256=normalized_text_sha(code_root / p)) for p in CODE_FILES},
        inputs={p: dict(sha256=sha_file(input_root / p)) for p in INPUT_FILES},
        photos=photos, targets=targets,
        expectedCounts=dict(scopeBTargets=count(lambda t: t['cohort'] == 'scope-B-development'),
                            controlTargets=count(lambda t: t['cohort'] == 'heldout-train'),
                            controlTargetsInPassedPhotos=count(lambda t: t['cohort'] == 'heldout-train' and t['sha256'] in measured),
                            controlTargetsInRejectedPhotos=count(lambda t: t['cohort'] == 'heldout-train' and t['sha256'] not in measured),
                            photosMeasured=len(measured)),
        measurements=dict(
            primaryRetained='frozen greedy one-to-one source-box IoU>=.50 (reproduced, must equal frozen pairs)',
            secondaryRetained='frozen one-to-one candidate-centre-in-box (reproduced, must equal frozen centerHits)',
            continuous='best IoU per target; candidate/target area ratio; area-ratio IoU bound; method-geometry reachable max IoU',
            looseDiagnosticOnly='greedy one-to-one IoU>0 overlap; parameter-free; NOT success, NOT acceptance',
            tolerances='none chosen; no post-result threshold or tolerance',
            boxVsMask='box/mask intersection is support geometry, not lesion-pixel visibility or Dice'),
        maskAttribution=dict(
            order=list(STAGES),
            maskStageDefinitions=dict(
                PHOTO_INPUT_CROP='skin_models.photo_input crop rectangle (native source pixels)',
                ANATOMICAL_REGION='union(forehead,rightCheek,leftCheek,nose,chin triangle masks) AND all-mesh union AND face oval, on analysis canvas',
                AUTO_EXCLUSION='snapshot exclusion rectangles + analysis frame-edge band',
                ANATOMICAL_EXCLUSION='landmark holes (eyes, lips, nostrils, brows) + ocular margin + brow convex hull',
                HAIR='appearance_analysis.elongated_dark_mask', GLARE_EXPOSURE='HSV V>.975 OR min(RGB)>.975',
                GRAY_THRESHOLD='analysis gray<=.12'),
            primary='sequential first loss of the box centre pixel (frozen visibility convention)',
            secondary='sequential stage at which no box pixel remains eligible; later stages on remaining area',
            independent='per-stage centre rejection flag and box pass fraction; overlapping, not additive',
            noCausalRule='no automatic causal decision rule (e.g. "half eliminated => mask is the problem")'),
        replay=dict(scope='frozen preprocessing/response only for stage 8/9 attribution; frozen candidates authoritative',
                    verification='replay must reproduce production acne_candidates / frozen detect AND the frozen JSON candidate list and eligible PNG; else REPLAY_UNVERIFIED',
                    cropCounterfactual='B response field full-source vs crop, pixel flips inside crop only; no components/candidates'),
        visualReview='source overlays for every measured target; non-blind post-hoc Claude engineering review; UNKNOWN unless the structure is visible',
        computeBudget=dict(process='single, streaming one photo at a time', photosDecoded=len(measured),
                           lease='HeavyJobLease peak 700 MiB private, minimum available 1200 MiB (contract values; not lowered)',
                           wallClockLimitSeconds=900, newDownloads=0, weightsLoaded=0),
        labelLimits=['positive-photo outside-box is not negative', '401 pseudo-positives unused', 'Mole/Pimple conflicts untouched',
                     'hair/beard/ambiguous border never clean negative', 'boxes are not pixel masks', 'no red/pale/white subtype inference',
                     'Scope B and 28 controls are exposed development data, not an independent final test',
                     'publisher licence declaration is not individual consent'])


def verify_manifest(manifest, code_root, input_root):
    for p, v in manifest['code'].items():
        if normalized_text_sha(Path(code_root) / p) != v['normalizedSHA256']:
            raise AuditError('CODE_IDENTITY_CHANGED:' + p)
    for p, v in manifest['inputs'].items():
        if sha_file(Path(input_root) / p) != v['sha256']:
            raise AuditError('INPUT_IDENTITY_CHANGED:' + p)
    if manifest['frozenManifestSHA256'] != FROZEN_MANIFEST_SHA256 or manifest['version'] != VERSION:
        raise AuditError('FROZEN_IDENTITY_CHANGED')


# ---------------------------------------------------------------- the audit
def production_payload(photo_bytes, entry):
    import cv2
    image = cv2.imdecode(np.frombuffer(photo_bytes, np.uint8), cv2.IMREAD_COLOR)
    import base64
    snap, a = entry['snapshot'], entry['alignment']
    pixel_id = sha_bytes(cv2.cvtColor(image, cv2.COLOR_BGR2RGBA).tobytes())
    payload = dict(photo='data:image/png;base64,' + base64.b64encode(photo_bytes).decode(), photoId=pixel_id,
                   landmarks=a['landmarks'], meshes=snap['meshes'], exclusions=snap['exclusions'],
                   qualityValid=entry['quality']['isValid'], conditions={k: a[k] for k in ['yaw', 'pitch', 'roll', 'scaleRatio']})
    return image, payload


def audit_photo(s, input_root, entry, targets, frozen, lease=None):
    """All measured-photo work. Returns per-target rows, crop diagnostics and
    overlay material; frozen candidate JSON is never rewritten."""
    import cv2
    from evaluate_acne_classical import production_context
    from skin_models import photo_input
    snap = Path(input_root) / TAKEOVER / 'product-inputs' / s / 'snapshot.png'
    photo = snap.read_bytes()
    image, payload = production_payload(photo, entry)
    if image.shape[1] != entry['snapshot']['width'] or image.shape[0] != entry['snapshot']['height']:
        raise AuditError('SNAPSHOT_SIZE_MISMATCH')
    ctx = production_context(payload)
    shape = image.shape[:2]; origin, scale = ctx['origin'], ctx['scale']
    _, crop = photo_input(image, entry['alignment']['landmarks'])
    regions = {k: v for k, v in ctx['masks'].items() if k in REGIONS}
    eligible = ctx['overall'] & ctx['acne_skin'] & np.logical_or.reduce(list(regions.values()))
    stages, native, canvas = stage_masks_for(ctx, entry['snapshot']['exclusions'], crop, shape)
    final = np.logical_and.reduce([m for _, m in stages])
    frozen_eligible = to_native(eligible, origin, scale, shape)
    frozen_eligible[:crop['y'], :] = False; frozen_eligible[crop['y'] + crop['height']:, :] = False
    frozen_eligible[:, :crop['x']] = False; frozen_eligible[:, crop['x'] + crop['width']:] = False
    if not np.array_equal(final, frozen_eligible):
        raise AuditError('STAGE_RECOMPOSITION_MISMATCH:' + s[:8])
    png_check = {}
    for m in 'AB':
        p = Path(input_root) / COMPARISON / m / (s + '-eligible.png')
        if p.exists():
            saved = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) > 0
            png_check[m] = bool(np.array_equal(saved, final))
    if lease: lease.check()
    native_regions = {k: to_native(v, origin, scale, shape) for k, v in regions.items()}
    replays, verified = {}, {}
    try:
        ra = replay_a(ctx, eligible)
        from acne_lab_dog import candidate_result
        objs = []
        for c in ra['components']:
            if c['reason'] != 'ACCEPTED': continue
            blob = ra['labels'] == c['label']; x, y, w, h = c['box']
            owners = [k for k in REGIONS if k in regions and regions[k][blob].mean() >= .65]
            objs.append(dict(x=x, y=y, width=w, height=h, areaPixels=c['count'], region=owners[0], pixels=np.column_stack(np.where(blob))[:, ::-1]))
        rebuilt, _ = candidate_result(objs, eligible.shape, origin, scale)
        verified['A'] = json.loads(json.dumps(rebuilt['candidates'])) == frozen['A']['candidates']
        ra['rawNative'] = to_native(ra['raw'], origin, scale, shape)
        ra['labelsNative'] = cv2.warpAffine(ra['labels'].astype(np.float32), analysis_to_source_matrix(origin, scale), (shape[1], shape[0]), flags=cv2.INTER_NEAREST).astype(np.int32)
        replays['A'] = ra
    except AuditError as e:
        verified['A'] = False; replays['A'] = dict(error=str(e))
    if lease: lease.check()
    try:
        rb = replay_b(image, final, crop, ctx['face_pixels'], native_regions)
        if rb['valid']:
            from acne_lab_dog import candidate_result
            objs = []
            for c in rb['components']:
                if c['reason'] != 'ACCEPTED': continue
                blob = rb['labels'] == c['label']; pix = np.column_stack(np.where(blob))[:, ::-1]
                owners = [k for k in REGIONS if k in native_regions and native_regions[k][pix[:, 1], pix[:, 0]].mean() >= .65]
                x, y, w, h = c['box']
                ob = dict(x=x, y=y, width=w, height=h, areaPixels=c['count'], region=owners[0], pixels=pix)
                objs.append(ob)
            rebuilt, _ = candidate_result(objs, shape)
            strip = lambda rows: [{k: v for k, v in r.items() if k in ('x', 'y', 'width', 'height', 'areaPixels', 'region')} for r in rows]
            verified['B'] = strip(json.loads(json.dumps(rebuilt['candidates']))) == strip(frozen['B']['candidates'])
            rb['rawNative'] = rb['raw']; rb['labelsNative'] = rb['labels']
        else:
            verified['B'] = False
        replays['B'] = rb
    except AuditError as e:
        verified['B'] = False; replays['B'] = dict(error=str(e))
    if lease: lease.check()
    crop_diag, flips = b_crop_counterfactual(image, final, crop, ctx['face_pixels'])
    # A crop asymmetry: A's components were scoped by the analysis-space support
    # without the photo_input crop; measure the actual effect on frozen output.
    a_out = []
    for i, c in enumerate(frozen['A']['candidates']):
        b = [c['x'], c['y'], c['x'] + c['width'], c['y'] + c['height']]
        inside = crop['x'] <= b[0] and crop['y'] <= b[1] and b[2] <= crop['x'] + crop['width'] and b[3] <= crop['y'] + crop['height']
        a_out.append(dict(candidate=i, fullyInsideCrop=bool(inside)))
    a_elig_native = to_native(eligible, origin, scale, shape)
    crop_mask = stages[0][1]
    crop_diag.update(aCandidatesTotal=len(a_out), aCandidatesFullyInsideCrop=sum(v['fullyInsideCrop'] for v in a_out),
                     aEligibleNativePixels=int(a_elig_native.sum()), aEligibleNativePixelsOutsideCrop=int((a_elig_native & ~crop_mask).sum()))
    if lease: lease.check()

    face_pixels = ctx['face_pixels']
    geometry = dict(A=dict(areaRange=[5 / scale ** 2, 180 / .38 / scale ** 2], aspect=[.45, 2.2]),
                    B=dict(areaRange=[max(3, face_pixels ** 2 * 2.5e-5), face_pixels ** 2 * .002 / .38], aspect=[.45, 2.2]))
    truth = [t['box'] for t in targets]
    rows = []
    preds = {m: [[c['x'], c['y'], c['x'] + c['width'], c['y'] + c['height']] for c in frozen[m]['candidates']] for m in 'AB'}
    repro = {}
    from acne_lab_dog import match_boxes
    for m in 'AB':
        repro[m] = dict(iou050PairsFrozen=frozen[m]['metrics']['pairs'], iou050PairsReproduced=match_boxes(truth, preds[m]),
                        centerHitsFrozen=frozen[m]['metrics']['centerHits'], centerHitsReproduced=center_hits(truth, preds[m]),
                        looseOverlapPairs=greedy_one_to_one(truth, preds[m], lambda v: v > 0))
        repro[m]['iou050Equal'] = [p[:2] for p in repro[m]['iou050PairsFrozen']] == [p[:2] for p in repro[m]['iou050PairsReproduced']]
        repro[m]['centerEqual'] = repro[m]['centerHitsFrozen'] == repro[m]['centerHitsReproduced']
    for k, t in enumerate(targets):
        box = t['box']
        masks, cumulative = attribute_masks(stages, box)
        tw, th = box[2] - box[0], box[3] - box[1]
        row = dict(targetId=t['targetId'], sha256=s, cohort=t['cohort'], index=k, annotationIndex=t['annotationIndex'],
                   sourceBox=box, sourceCenter=list(box_center(box)), sourceResolution=[shape[1], shape[0]],
                   analysisResolution=[ctx['gray'].shape[1], ctx['gray'].shape[0]], origin=list(origin), scale=scale,
                   analysisBox=[*source_to_analysis(box[0], box[1], origin, scale), *source_to_analysis(box[2], box[3], origin, scale)],
                   photoInputCrop=crop, scaleBand=t['scaleBand'], targetArea=box_area(box),
                   masks=masks, partsCenter={k2: center_value(v, box) for k2, v in native.items()},
                   partsBoxFraction={k2: window_fraction(v, box) for k2, v in native.items()}, methods={})
        w = box_window(box, shape)
        for m in 'AB':
            rp = replays[m]; ok = bool(verified.get(m)) and 'rawNative' in rp
            raw_any = raw_elig = None; comps = []
            if ok and w is not None:
                rawp = rp['rawNative'][w[0]:w[1], w[2]:w[3]]
                raw_any = bool(rawp.any()); raw_elig = bool((rawp & cumulative[w[0]:w[1], w[2]:w[3]]).any())
                labels = set(np.unique(rp['labelsNative'][w[0]:w[1], w[2]:w[3]])) - {0}
                comps = [dict(label=c['label'], reason=c['reason'], count=c['count']) for c in rp['components'] if c['label'] in labels]
            ious = [(iou(box, p), j) for j, p in enumerate(preds[m])]
            overl = [(v, j) for v, j in ious if v > 0]
            best = max(ious) if ious else (None, None)
            centers_in = [j for j, p in enumerate(preds[m]) if box[0] <= (p[0] + p[2]) / 2 <= box[2] and box[1] <= (p[1] + p[3]) / 2 <= box[3]]
            g = geometry[m]
            mr = dict(replayVerified=ok, rawResponseInBox=raw_any, rawResponseInEligibleBox=raw_elig,
                      rawComponentsTouchingBox=comps,
                      frozenCandidatesOverlapping=[dict(candidate=j, iou=v, areaRatio=box_area(preds[m][j]) / max(box_area(box), 1e-9),
                                                        areaRatioIoUBound=size_bound_iou(box, preds[m][j])) for v, j in overl],
                      frozenCandidateCentersInsideBox=centers_in, bestIoU=best[0], bestIoUCandidate=best[1] if best[0] else None,
                      reachableMaxIoUGivenMethodGeometry=max_reachable_iou(tw, th, g['areaRange'], g['aspect']),
                      methodCandidateBoxAreaRangeNative=g['areaRange'])
            gate = dict(passed=True)
            mr['primaryOutcome'] = classify(gate, masks, ok, raw_elig if raw_elig is not None else raw_any, bool(overl), best[0])
            mr['areaOutcome'] = classify_area(gate, masks, ok, raw_elig if raw_elig is not None else raw_any, bool(overl), best[0])
            row['methods'][m] = mr
        rows.append(row)
    overlay = dict(image=image, stages=stages, crop=crop, preds=preds, flips=flips)
    return dict(rows=rows, reproduction=repro, cropDiagnostics=crop_diag, replayVerified=verified, eligiblePNGEqual=png_check,
                faceSourcePixels=face_pixels, sourceTransform=dict(origin=list(origin), scale=scale),
                replayComponentReasons={m: (sorted({c['reason'] for c in replays[m].get('components', [])})) for m in 'AB'},
                frozenCandidateCounts={m: len(preds[m]) for m in 'AB'}), overlay


# ---------------------------------------------------------------- overlays
STAGE_COLORS = {'PHOTO_INPUT_CROP': (90, 90, 90), 'ANATOMICAL_REGION': (40, 40, 40), 'AUTO_EXCLUSION': (0, 0, 220),
                'ANATOMICAL_EXCLUSION': (0, 140, 255), 'HAIR': (220, 0, 220), 'GLARE_EXPOSURE': (0, 230, 230), 'GRAY_THRESHOLD': (200, 60, 0)}


def first_loss_map(stages):
    shape = stages[0][1].shape; out = np.full(shape, -1, np.int8); alive = np.ones(shape, bool)
    for k, (_, m) in enumerate(stages):
        lost = alive & ~m; out[lost] = k; alive &= m
    return out


def render_overlays(s, overlay, rows, out_dir):
    import cv2
    img, stages = overlay['image'], overlay['stages']; fl = first_loss_map(stages)
    tint = img.copy()
    for k, (name, _) in enumerate(stages):
        tint[fl == k] = (tint[fl == k] * .45 + np.array(STAGE_COLORS[name]) * .55).astype(np.uint8)
    out_dir.mkdir(parents=True, exist_ok=True); tiles = []
    for r in rows:
        b = r['sourceBox']; side = max(b[2] - b[0], b[3] - b[1]); half = max(32., 3 * side)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        x0, y0 = int(max(0, cx - half)), int(max(0, cy - half)); x1, y1 = int(min(img.shape[1], cx + half)), int(min(img.shape[0], cy + half))
        f = 256 / max(1, max(x1 - x0, y1 - y0))
        size = (max(1, min(256, int(round((x1 - x0) * f)))), max(1, min(256, int(round((y1 - y0) * f)))))
        panels = []
        for base, draw in ((img, False), (tint, True)):
            p = cv2.resize(base[y0:y1, x0:x1], size, interpolation=cv2.INTER_NEAREST)
            P = lambda x, y: (int(round((x - x0) * f)), int(round((y - y0) * f)))
            cv2.rectangle(p, P(b[0], b[1]), P(b[2], b[3]), (0, 255, 0), 1)
            if draw:
                for m, col in (('A', (0, 120, 255)), ('B', (255, 255, 0))):
                    for c in overlay['preds'][m]:
                        if c[2] >= x0 and c[0] <= x1 and c[3] >= y0 and c[1] <= y1:
                            cv2.rectangle(p, P(c[0], c[1]), P(c[2], c[3]), col, 1)
            panels.append(cv2.copyMakeBorder(p, 0, 256 - p.shape[0], 0, 256 - p.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)))
        tile = np.hstack([panels[0], np.full((256, 4, 3), 255, np.uint8), panels[1]])
        label = f"{r['targetId']} c:{r['masks']['centerFirstLoss'] or 'ELIGIBLE'} A:{r['methods']['A']['primaryOutcome']} B:{r['methods']['B']['primaryOutcome']}"
        tile = cv2.copyMakeBorder(tile, 22, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(tile, label, (3, 15), cv2.FONT_HERSHEY_SIMPLEX, .38, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.imwrite(str(out_dir / f"{r['targetId'].replace('#', '-t')}.png"), tile); tiles.append(tile)
    if tiles:
        cols = 3; rws = [np.hstack(tiles[i:i + cols] + [np.full_like(tiles[0], 255)] * (cols - len(tiles[i:i + cols]))) for i in range(0, len(tiles), cols)]
        cv2.imwrite(str(out_dir / f'{s[:8]}-targets-sheet.png'), np.vstack(rws))
    over = tint.copy()
    for r in rows:
        b = r['sourceBox']; cv2.rectangle(over, (int(b[0]) - 3, int(b[1]) - 3), (int(math.ceil(b[2])) + 3, int(math.ceil(b[3])) + 3), (0, 255, 0), 2)
        cv2.putText(over, str(r['index']), (int(b[2]) + 4, int(b[1])), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 0), 2)
    c = overlay['crop']; cv2.rectangle(over, (c['x'], c['y']), (c['x'] + c['width'] - 1, c['y'] + c['height'] - 1), (255, 255, 255), 2)
    f = min(1., 1100 / max(over.shape[:2]))
    cv2.imwrite(str(out_dir / f'{s[:8]}-overview.png'), cv2.resize(over, None, fx=f, fy=f, interpolation=cv2.INTER_AREA))


# --------------------------------------------------------------------- main
def summarize(target_rows):
    def group(rows):
        out = dict(targets=len(rows), centerFirstLoss=tally([dict(k=r['primary']) for r in rows], 'k') if rows else {})
        return out
    res = {}
    cohorts = dict(scopeB=lambda r: r['cohort'] == 'scope-B-development',
                   controlsMeasured=lambda r: r['cohort'] == 'heldout-train' and r['gatePassed'],
                   controlsGateRejected=lambda r: r['cohort'] == 'heldout-train' and not r['gatePassed'])
    for name, f in cohorts.items():
        sub = [r for r in target_rows if f(r)]
        res[name] = dict(targets=len(sub))
        for m in 'AB':
            res[name][m] = dict(primary=tally([dict(k=r['outcome'][m]['primary']) for r in sub], 'k'),
                                area=tally([dict(k=r['outcome'][m]['area']) for r in sub], 'k'),
                                byScale={b: tally([dict(k=r['outcome'][m]['primary']) for r in sub if r['scaleBand'] == b], 'k') for b in ('micro', 'small', 'medium')})
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('phase', choices=['manifest', 'run'])
    ap.add_argument('--input-root', required=True, help='CD checkout (read-only)')
    ap.add_argument('--output-root', required=True, help='new results folder outside input-root')
    ap.add_argument('--code-root', default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument('--manifest', required=True, help='pre-registered audit manifest path')
    ap.add_argument('--path-map', action='append', default=[], help='WINDOWS_PREFIX=LOCAL_PREFIX (read-only source mapping)')
    args = ap.parse_args(argv)
    input_root, output_root = check_roots(args.input_root, args.output_root)
    code_root = Path(args.code_root).resolve(); manifest_path = Path(args.manifest)
    maps = [tuple(v.split('=', 1)) for v in args.path_map]
    sys.path[:0] = [str(code_root / 'scripts/skin-research'), str(code_root / 'services/core-api')]
    if args.phase == 'manifest':
        if manifest_path.exists():
            raise AuditError('AUDIT_MANIFEST_ALREADY_FROZEN')
        m = build_manifest(code_root, input_root, maps)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(m, indent=1, ensure_ascii=False) + '\n', 'utf8')
        print(json.dumps(dict(manifest=str(manifest_path), sha256=sha_file(manifest_path), targets=len(m['targets']), expected=m['expectedCounts'])))
        return
    manifest = read_json(manifest_path); verify_manifest(manifest, code_root, input_root)
    output_root.mkdir(parents=True, exist_ok=True)
    if (output_root / 'audit-results.json').exists():
        raise AuditError('COMPLETED_AUDIT_NOT_REPEATED')
    pre, orig, scope, ev, man, res = load_frozen(input_root)
    from heavy_job_lease import HeavyJobLease
    import cv2
    started = time.monotonic()
    with HeavyJobLease('CLAUDE-acne-measurement-audit', peak_mib=700, minimum_available_mib=1200, memory_metric='private') as lease:
        cv2.setNumThreads(2)
        photos, target_rows, details = [], [], []
        by_photo = {}
        for t in manifest['targets']:
            by_photo.setdefault(t['sha256'], []).append(t)
        for p in manifest['photos']:
            lease.check(); s = p['sha256']
            if time.monotonic() - started > manifest['computeBudget']['wallClockLimitSeconds']:
                raise AuditError('COMPUTE_BUDGET_EXCEEDED')
            gate = gate_attribution(pre[s], ev[s])
            if gate['passed'] != p['staticProductPass']:
                raise AuditError('GATE_DISAGREES_WITH_FROZEN:' + s[:8])
            targets = by_photo.get(s, [])
            src = map_path(man_row['sourcePath'], maps) if (man_row := next(r for r in man['rows'] if r['sha256'] == s)) else None
            src_ok = sha_file(src) == p['sourceFileSHA256'] if src and src.exists() else None
            entry = dict(sha256=s, cohort=p['cohort'], gate=gate, targetCount=len(targets), sourceFileSHA256Verified=src_ok)
            if not gate['passed']:
                for t in targets:
                    target_rows.append(dict(targetId=t['targetId'], sha256=s, cohort=t['cohort'], scaleBand=t['scaleBand'], sourceBox=t['box'],
                                            gatePassed=False, gateFirstLoss=gate['firstLoss'], downstream='NOT_MEASURED',
                                            outcome={m: dict(primary='PRODUCT_GATE', area='PRODUCT_GATE') for m in 'AB'}))
                photos.append(entry); continue
            snap = input_root / TAKEOVER / 'product-inputs' / s / 'snapshot.png'
            if sha_file(snap) != p['snapshotSHA256']:
                raise AuditError('SNAPSHOT_IDENTITY_CHANGED:' + s[:8])
            frozen = {m: res[m][s] for m in 'AB'}
            result, overlay = audit_photo(s, input_root, pre[s], targets, frozen, lease)
            render_overlays(s, overlay, result['rows'], output_root / 'overlays')
            del overlay
            entry.update({k: v for k, v in result.items() if k != 'rows'})
            photos.append(entry); details.extend(result['rows'])
            for r in result['rows']:
                target_rows.append(dict(targetId=r['targetId'], sha256=s, cohort=r['cohort'], scaleBand=r['scaleBand'], sourceBox=r['sourceBox'],
                                        gatePassed=True, gateFirstLoss=None, centerFirstLoss=r['masks']['centerFirstLoss'],
                                        areaFullLossStage=r['masks']['areaFullLossStage'], boxFractionEligible=r['masks']['boxFractionEligible'],
                                        outcome={m: dict(primary=r['methods'][m]['primaryOutcome'], area=r['methods'][m]['areaOutcome']) for m in 'AB'}))
            print(json.dumps(dict(sha=s[:8], targets=len(targets), verified=result['replayVerified'], png=result['eligiblePNGEqual'])), flush=True)
        receipt = lease.receipt()
    receipt['scopeNote'] = ('lease files are the shared TOGG coordination files; process/RAM census ran inside the '
                            'desktop Linux VM that executed this audit and cannot see Windows-host processes')
    report = dict(version=VERSION, manifestSHA256=sha_file(manifest_path), kind=manifest['kind'],
                  productDecisionChanged=False, productionAcne=manifest['productionAcne'],
                  summary=summarize(target_rows), photos=photos, targets=target_rows, targetDetails=details,
                  resource=receipt, elapsedSeconds=time.monotonic() - started,
                  environment=dict(python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__,
                                   skimage=__import__('skimage').__version__),
                  torchImported='torch' in sys.modules, onnxruntimeImported='onnxruntime' in sys.modules)
    (output_root / 'audit-results.json').write_text(json.dumps(report, indent=1, allow_nan=False) + '\n', 'utf8')
    print(json.dumps(dict(results=str(output_root / 'audit-results.json'), elapsed=report['elapsedSeconds'])))


if __name__ == '__main__':
    main()
