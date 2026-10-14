"""Image-tracked contour prominence, evaluated separately from fold evidence.

No personal history, age, z/depth or skin-type head is used. A landmark guide
defines a search corridor; only observed image edges can be measured or mapped.
Granular expression gate correctly disambiguates resting full lips from active pucker.
"""

from pathlib import Path
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

VERSION = 'image-contour-neighbor-excursion-exterior-expression-v4-staging'
PARAMETERS = dict(
    samples=96, offsetFaceFraction=0.025, offsetSamples=41, edgeContrast=0.04,
    minimumCoverage=0.55, minimumRun=5, neighborSpan=16, excludedCenterSpan=3,
    minimumFacePixels=180, maxYaw=0.65, maxPitch=0.22, maxMouthOpening=0.10, maxTrackingResidual=2.5,
    inwardReferenceFaceFraction=0.04, exteriorReferenceFaceFraction=0.009375, skinEnvelopeSigma=3.0
)


def expression_reason(payload, opening, corner, lip_width_ratio=None):
    """Static lip shape is not expression truth. Research observations must be
    bound to this bitmap; absent observations retain the established gate.
    These local blendshape coefficients are rejection support, never severity.
    Disambiguates resting full lips from true active pucker using physical lip width.
    """
    observation = payload.get('expressionObservation')
    if observation is None:
        if opening > 0.10:
            return 'EXPRESSION_OPEN_MOUTH'
        if corner < -0.07:
            return 'EXPRESSION_SMILE'
        return None

    if observation.get('photoId') != payload['photoId'] or observation.get('version') != 'local-mediapipe-expression-support-v1':
        raise ValueError('EXPRESSION_PHOTO_MISMATCH')

    names = [
        'mouthSmileLeft', 'mouthSmileRight', 'mouthFrownLeft', 'mouthFrownRight',
        'mouthPucker', 'mouthPressLeft', 'mouthPressRight', 'cheekPuff', 'jawOpen',
        'mouthFunnel'
    ]
    scores = observation.get('scores', {})
    if any(k not in scores or not np.isfinite(scores[k]) or not 0 <= scores[k] <= 1 for k in names):
        raise ValueError('INVALID_EXPRESSION_SUPPORT')

    # 1. Open Mouth
    if opening > 0.10 or scores.get('jawOpen', 0.0) > 0.15:
        return 'EXPRESSION_OPEN_MOUTH'

    # 2. Smile
    if max(scores['mouthSmileLeft'], scores['mouthSmileRight']) > 0.50:
        return 'EXPRESSION_SMILE'

    # 3. Frown
    if max(scores.get('mouthFrownLeft', 0.0), scores.get('mouthFrownRight', 0.0)) > 0.50:
        return 'EXPRESSION_FROWN'

    # 4. Cheek Puff
    if scores.get('cheekPuff', 0.0) > 0.50:
        return 'EXPRESSION_CHEEK_PUFF'

    # 5. Mouth Press
    if max(scores.get('mouthPressLeft', 0.0), scores.get('mouthPressRight', 0.0)) > 0.50:
        return 'EXPRESSION_MOUTH_PRESS'

    # 6. Pucker: Distinguish true active pucker from resting full lips
    pucker_score = scores['mouthPucker']
    if pucker_score > 0.50:
        funnel_score = scores['mouthFunnel']
        # True active pucker significantly narrows the mouth horizontally (lip_width_ratio < 0.35) or exhibits funnel
        is_narrowed = (lip_width_ratio is not None and lip_width_ratio < 0.35) or funnel_score > 0.25
        if is_narrowed:
            return 'EXPRESSION_PUCKER'
        # Resting full lips: normal horizontal mouth width (>=0.35) and closed jaw -> neutral facial morphology

    return None


def exterior_support(image, line, normal, coords, face_width):
    """Reject a skin-to-skin illumination edge masquerading as a silhouette."""
    inward = line[:, None, :] - normal[:, None, :] * (0.04 * face_width)
    exterior = coords + normal[:, None, :] * (0.009375 * face_width)
    inward = inward.astype(np.float32)
    exterior = exterior.astype(np.float32)
    xy = np.concatenate([inward.reshape(-1, 2), exterior.reshape(-1, 2)])
    h, w = image.shape[:2]
    a = max(0, min(w - 1, int(np.floor(xy[:, 0].min())) - 2))
    b = max(0, min(h - 1, int(np.floor(xy[:, 1].min())) - 2))
    c = max(a + 1, min(w, int(np.ceil(xy[:, 0].max())) + 3))
    d = max(b + 1, min(h, int(np.ceil(xy[:, 1].max())) + 3))
    rgb = image[b:d, a:c].astype(np.float32) / 255
    remap = lambda xy: cv2.remap(rgb, xy[:, :, 0] - np.float32(a), xy[:, :, 1] - np.float32(b), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    sampled = remap(inward)[:, 0, :]
    totals = sampled.sum(1)
    good = totals > 0.36
    if good.sum() < 12:
        return np.zeros(coords.shape[:2], bool)
    ref = sampled[good, :2] / totals[good, None]
    median = np.median(ref, axis=0)
    mad = 1.4826 * np.median(np.abs(ref - median), axis=0)
    noise = np.maximum(mad, 2 / 255 / max(float(np.median(totals[good])), 0.36))
    outside = remap(exterior)
    chroma = outside[:, :, :2] / np.maximum(outside.sum(2)[:, :, None], 1e-6)
    distance = np.linalg.norm((chroma - median) / noise, axis=2)
    return distance > PARAMETERS['skinEnvelopeSigma']


def runs(mask):
    d = np.diff(np.r_[False, np.asarray(mask, bool), False].astype(int))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def contour_prominence(track, observed, normal, face_width):
    """Local excess versus independently observed neighboring contour points."""
    track = np.asarray(track, float)
    seen = np.asarray(observed, bool) & np.isfinite(track).all(1)
    normal = np.asarray(normal, float)
    excess = np.full(len(track), np.nan)
    uncertainty = np.full(len(track), np.nan)
    eligible = np.zeros(len(track), bool)
    for a, b in runs(seen):
        for i in range(int(a) + 6, int(b) - 6):
            left = np.arange(max(a, i - 16), i - 3, dtype=int)
            right = np.arange(i + 4, min(b, i + 17), dtype=int)
            if len(left) < 3 or len(right) < 3:
                continue
            idx = np.r_[left, right]
            t = (idx - i) / 16
            design = np.c_[np.ones(len(t)), t, t * t]
            fit = np.linalg.lstsq(design, track[idx], rcond=None)[0]
            baseline = fit[0]
            residual = (track[idx] - design @ fit) @ normal[i]
            mad = 1.4826 * np.median(np.abs(residual - np.median(residual)))
            excess[i] = float((track[i] - baseline) @ normal[i]) / face_width
            uncertainty[i] = max(0.05 / 40, 2 * float(mad) / face_width)
            eligible[i] = True
    raw = eligible & (excess > uncertainty)
    accepted = np.zeros(len(track), bool)
    for a, b in runs(raw):
        if b - a >= PARAMETERS['minimumRun']:
            accepted[a:b] = True
    return dict(excursion=excess, localizationUncertainty=uncertainty, observedNeighborFit=eligible, accepted=accepted)


def trace_boundary(image, guide, eligible, face_width, face_center):
    """Track one actual edge per observed contiguous corridor, never argmax -1."""
    guide = np.asarray(guide, float)
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(guide, axis=0), axis=1))]
    if distance[-1] < face_width * 0.05:
        return None
    t = np.linspace(0, distance[-1], PARAMETERS['samples'])
    line = np.c_[np.interp(t, distance, guide[:, 0]), np.interp(t, distance, guide[:, 1])]
    tangent = np.gradient(line, axis=0)
    normal = np.c_[-tangent[:, 1], tangent[:, 0]]
    normal /= np.maximum(np.linalg.norm(normal, axis=1)[:, None], 1e-6)
    flip = np.sum(normal * (line - face_center), axis=1) < 0
    normal[flip] *= -1
    offsets = np.linspace(-0.025, 0.025, 41) * face_width
    coords = line[:, None, :] + normal[:, None, :] * offsets[None, :, None]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    radius = 0.003125 * face_width
    inner = coords - normal[:, None, :] * radius
    outer = coords + normal[:, None, :] * radius
    remap = lambda raster, xy, mode: cv2.remap(raster, xy[:, :, 0].astype(np.float32), xy[:, :, 1].astype(np.float32), mode, borderMode=cv2.BORDER_CONSTANT)
    inside = remap(gray, inner, cv2.INTER_LINEAR)
    outside = remap(gray, outer, cv2.INTER_LINEAR)
    response = np.abs(inside - outside)
    valid = remap(eligible.astype(np.uint8), coords, cv2.INTER_NEAREST) > 0
    h, w = gray.shape
    valid &= (inner[:, :, 0] >= 0) & (inner[:, :, 0] < w) & (inner[:, :, 1] >= 0) & (inner[:, :, 1] < h) & (outer[:, :, 0] >= 0) & (outer[:, :, 0] < w) & (outer[:, :, 1] >= 0) & (outer[:, :, 1] < h)
    visible = valid.any(1)
    raw_supported = valid & (response > PARAMETERS['edgeContrast'])
    exterior = exterior_support(image, line, normal, coords, face_width)
    supported = raw_supported & exterior
    found = supported.any(1)
    track = np.full((len(line), 2), np.nan)
    strength = np.zeros(len(line))
    indices = np.full(len(line), -1, int)
    for a, b in runs(found):
        if b - a < PARAMETERS['minimumRun']:
            continue
        candidates = [np.flatnonzero(supported[i]) for i in range(a, b)]
        cost = -response[a, candidates[0]]
        backs = []
        for j, i in enumerate(range(a + 1, b)):
            transition = np.abs(offsets[candidates[j]][:, None] - offsets[candidates[j + 1]][None, :]) / (face_width / 320)
            total = cost[:, None] + 0.01 * transition - response[i, candidates[j + 1]][None, :]
            previous = total.argmin(0)
            backs.append(previous)
            cost = total[previous, np.arange(len(previous))]
        current = int(cost.argmin())
        chosen = [int(candidates[-1][current])]
        for j in range(len(backs) - 1, -1, -1):
            current = int(backs[j][current])
            chosen.append(int(candidates[j][current]))
        chosen = chosen[::-1]
        indices[a:b] = chosen
        track[a:b] = coords[np.arange(a, b), chosen]
        strength[a:b] = response[np.arange(a, b), chosen]
    observed = np.isfinite(track).all(1)
    residuals = []
    for a, b in runs(observed):
        displacement = track[a:b] - line[a:b]
        r = np.linalg.norm(displacement - gaussian_filter1d(displacement, 2, axis=0), axis=1) / (face_width / 320)
        residuals.extend(r.tolist())
    residual = float(np.mean(residuals)) if residuals else None
    prominence = contour_prominence(track, observed, normal, face_width)
    accepted = prominence['accepted']
    value = float(100 * accepted.sum() / max(1, visible.sum()))
    reason = 'ANATOMICAL_BOUNDARY_NOT_VISIBLE' if visible.mean() < 0.55 else 'IMAGE_BOUNDARY_NOT_TRACKABLE' if observed.mean() < 0.55 else 'BOUNDARY_TRACKING_UNSTABLE' if residual is not None and residual > 2.5 else 'NEIGHBOR_CONTOUR_NOT_OBSERVED' if prominence['observedNeighborFit'].sum() < 12 else None
    return dict(
        value=None if reason else value, reason=reason, unit='percent-observed-boundary-support', version=VERSION,
        tracked=track, guide=line, normal=normal, edgeStrength=strength, visible=visible, observed=observed, accepted=accepted,
        trackingResidual=residual, rawBrightnessEdgeRows=int(raw_supported.any(1).sum()), exteriorConfirmedRows=int(found.sum()),
        **{k: v for k, v in prominence.items() if k != 'accepted'}, sourceCoordinates=True, confidenceNotSeverity=True
    )


def closed_surface_mask(shape, mesh, scale, origin=(0, 0)):
    """Dry/sag-only closed convex cells, bounded by four actual safe edges."""
    import itertools
    from appearance_analysis import polygon_mask
    mask = polygon_mask(shape, mesh, scale, origin).astype(np.uint8)
    edges = {tuple(sorted(e)) for e in mesh['edges']}
    neighbors = {i: set() for i in range(len(mesh['points']))}
    for a, b in edges:
        neighbors[a].add(b)
        neighbors[b].add(a)
    points = np.asarray([[p['x'], p['y']] for p in mesh['points']], np.float32)
    cells = {}
    for a, b in itertools.combinations(neighbors, 2):
        if (a, b) in edges:
            continue
        for c, d in itertools.combinations(sorted(neighbors[a] & neighbors[b]), 2):
            if tuple(sorted((c, d))) in edges:
                continue
            cell = [a, c, b, d]
            if cv2.isContourConvex(points[cell]):
                cells[tuple(sorted(cell))] = cell
    if len(cells) > 64:
        raise ValueError('INVALID_SURFACE_CELLS')
    for cell in cells.values():
        projected = ((points[cell] - np.asarray(origin)) * scale).astype(np.int32)
        cv2.fillPoly(mask, [projected], 1)
    return mask > 0


def elongated_dark_mask(gray8):
    """Exclude long dark filaments, not every round dark focus as hair."""
    dark = cv2.morphologyEx(gray8, cv2.MORPH_BLACKHAT, np.ones((7, 7), np.uint8)) > 35
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8))
    hair = np.zeros_like(dark)
    for i in range(1, n):
        _, _, w, h, area = stats[i]
        if max(w, h) >= 8 and max(w, h) / max(min(w, h), 1) >= 3:
            hair |= labels == i
    return cv2.dilate(hair.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0


def analyze_contour(payload, check=None):
    """Native photometric branch; source-field and score share accepted centers."""
    from appearance_analysis import decode_photo, map_result
    check = check or (lambda: None)
    check()
    image, digest = decode_photo(payload['photo'])
    assert digest == payload['photoId']
    check()
    h, w = image.shape[:2]
    p = np.asarray([[v['x'] * w, v['y'] * h] for v in payload['landmarks']])
    axis = p[263] - p[33]
    axis /= np.linalg.norm(axis)
    vertical = np.array([-axis[1], axis[0]])
    vertical *= 1 if vertical[1] >= 0 else -1
    face = abs((p[454] - p[234]) @ axis)
    mouth = np.linalg.norm(p[13] - p[14]) / max(1, np.linalg.norm(p[61] - p[291]))
    smile = ((p[61] + p[291] - p[13] - p[14]) / 2) @ vertical / max(1, np.linalg.norm(p[61] - p[291]))
    lip_width_ratio = np.linalg.norm(p[61] - p[291]) / max(1, face)

    conditions = payload['conditions']
    quality_reason = (
        'CAPTURE_QUALITY' if not payload['qualityValid'] else
        'INSUFFICIENT_NATIVE_DETAIL' if face < 180 else
        'HEAD_ANGLE_UNSUPPORTED' if abs(conditions.get('yaw', 99)) > 0.65 or abs(conditions.get('pitch', 99)) > 0.22 else
        expression_reason(payload, mouth, smile, lip_width_ratio)
    )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    g = gray.astype(np.float32) / 255
    metric = max(0.125, face / 320)
    small = cv2.resize(gray, None, fx=min(1, 1 / metric), fy=min(1, 1 / metric), interpolation=cv2.INTER_AREA)
    hair = cv2.resize(elongated_dark_mask(small).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
    excluded = np.zeros((h, w), np.uint8)
    for b in payload['exclusions']:
        cv2.rectangle(excluded, (int(b['x']), int(b['y'])), (int(b['x'] + b['w']), int(b['y'] + b['h'])), 1, -1)

    indices = {'rightCheek': [132, 58, 172], 'leftCheek': [361, 288, 397], 'chin': [149, 176, 148, 152, 377, 400, 378]}
    rows = {}
    maps = {}
    for region, guide in indices.items():
        check()
        if region not in payload['meshes']:
            continue
        anatomy = closed_surface_mask((h, w), payload['meshes'][region], 1)
        corridor = np.zeros((h, w), np.uint8)
        cv2.polylines(corridor, [np.rint(p[guide]).astype(np.int32)], False, 1, max(1, int(np.ceil(0.05 * face))))
        scope = anatomy & (corridor > 0)
        eligible = scope & (excluded == 0) & ~hair & (g > 0.12) & (g < 0.975)
        reason = quality_reason
        if reason is None and scope.any() and (g[scope] > 0.975).mean() > 0.03:
            reason = 'GLARE_OR_EXPOSURE'
        if reason is None and scope.any() and hair[scope].mean() > 0.22:
            reason = 'HAIR_OR_SHARP_LINE_CONFOUNDER'
        if reason is None and eligible.sum() >= 100:
            ys, xs = np.where(eligible)
            design = np.c_[(xs - xs.min()) / max(1, np.ptp(xs)), (ys - ys.min()) / max(1, np.ptp(ys)), np.ones(len(xs))]
            slope = np.linalg.lstsq(design, cv2.GaussianBlur(g, (0, 0), 8 * metric)[eligible], rcond=None)[0]
            if np.linalg.norm(slope[:2]) > 0.55:
                reason = 'HARD_DIRECTIONAL_SHADOW'

        q = None if reason else trace_boundary(image, p[guide], eligible, face, p[1])
        reason = reason or (q['reason'] if q else 'INSUFFICIENT_CONTOUR_SUPPORT')
        value = None if reason else q['value']
        field = np.zeros((h, w), np.float32)
        accepted_centers = set()
        observed_slots = set()
        accepted_slots = set()
        if q:
            observed_slots = {tuple(np.rint(xy).astype(int)) for xy, vis in zip(q['guide'], q['visible']) if vis}
        if q and value is not None:
            for xy, guide_xy, accepted in zip(q['tracked'], q['guide'], q['accepted']):
                if not accepted or not np.isfinite(xy).all():
                    continue
                x, y = np.rint(xy).astype(int)
                if 0 <= x < w and 0 <= y < h and eligible[y, x]:
                    field[y, x] = 1.0
                    accepted_centers.add((x, y))
                    accepted_slots.add(tuple(np.rint(guide_xy).astype(int)))
            value = float(100 * len(accepted_slots) / max(1, len(observed_slots)))
            maps[region] = map_result(field, eligible, region, 'sag', digest, payload['pose'], image.shape, 1.0, 'percent-observed-boundary-support', 1.0)

        row = dict(
            value=value, reason=reason, version=VERSION, unit='percent-observed-boundary-support',
            observedAnatomicalSamples=int(q['visible'].sum()) if q else 0,
            uniqueObservedSlots=len(observed_slots), acceptedBoundarySlots=len(accepted_slots),
            trackedImageSamples=int(q['observed'].sum()) if q else 0,
            acceptedSamples=len(accepted_centers), activeSourcePixels=int((field > 0).sum()),
            quality='valid' if value is not None else 'insufficient'
        )
        if payload.get('expressionObservation'):
            row['expressionSupportVersion'] = 'local-mediapipe-expression-support-v1'
        if region in maps and maps[region]:
            maps[region].update(method='appearance-contour-staging-2', normalizationVersion=row['version'], samplingSupportVersion='image-boundary-observed-neighbor-slots-v2-staging')
        if q:
            row['trace'] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in q.items()}
            row['trace']['tracked'] = [xy.tolist() if np.isfinite(xy).all() else None for xy in q['tracked']]
            row['trace']['version'] = row['version']
            for k in ['excursion', 'localizationUncertainty']:
                row['trace'][k] = [float(v) if np.isfinite(v) else None for v in q[k]]
        rows[region] = row
    check()
    return dict(
        photoId=digest, measurements=rows, maps=maps, normalProductEnabled=False,
        formula='fraction of anatomically visible boundary samples with image-tracked local outward excursion beyond neighbor localization uncertainty; not tissue volume or clinical sag grade'
    )
