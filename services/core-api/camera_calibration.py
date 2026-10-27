"""One-time colour calibration of a vehicle cabin camera (per vehicle model / camera module).

Procedure: print the Attune calibration chart (scripts/camera-calibration/make_chart.py; 4 ArUco markers + 24 colour
patches), hold it in front of the cabin camera under the usual cabin light, take 1+ photos, fit. The fit is a 3x3 colour
correction matrix + offset in linear-light sRGB (least squares over the patches) and is stored in the vehicle camera
profile (`camera_color`, schema attune-camera-profile-v1) together with the camera's YUV matrix/range.

Reference colours: by default the nominal sRGB values of the 24-patch ColorChecker Classic layout (published values).
A home/office print does not reproduce them exactly; for production use a certified chart's values or measure the
printed patches with a spectrophotometer and pass them as `reference` (sRGB 0-255, same order).

Quality gates (engineering choices, not validated against skin outcomes): all 4 markers found, >= 20 usable patches
(no clipping, uniform), fitted mean CIEDE2000 <= 3 and max <= 8, leave-one-out mean <= 4, matrix well conditioned.
A failed gate returns the report without a profile.
"""
import datetime, hashlib, json
import cv2, numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000
from camera_color import SCHEMA, MATRICES, srgb_to_linear, linear_to_srgb, _check_profile

LAYOUT = 'attune-chart-v1'
NAMES = ['dark skin', 'light skin', 'blue sky', 'foliage', 'blue flower', 'bluish green', 'orange', 'purplish blue',
         'moderate red', 'purple', 'yellow green', 'orange yellow', 'blue', 'green', 'red', 'yellow', 'magenta', 'cyan',
         'white 9.5', 'neutral 8', 'neutral 6.5', 'neutral 5', 'neutral 3.5', 'black 2']
NOMINAL = [[115, 82, 68], [194, 150, 130], [98, 122, 157], [87, 108, 67], [133, 128, 177], [103, 189, 170],
           [214, 126, 44], [80, 91, 166], [193, 90, 99], [94, 60, 108], [157, 188, 64], [224, 163, 46],
           [56, 61, 150], [70, 148, 73], [175, 54, 60], [231, 199, 31], [187, 86, 149], [8, 133, 161],
           [243, 243, 242], [200, 200, 200], [160, 160, 160], [122, 122, 121], [85, 85, 85], [52, 52, 52]]
# chart geometry in millimetres (A4 landscape 297 x 210): markers at the corners, 6 x 4 patches between them
W_MM, H_MM, MARK, MARGIN, PATCH, GAP = 297.0, 210.0, 30.0, 12.0, 26.0, 6.0
MARKER_IDS = (10, 11, 12, 13)  # top-left, top-right, bottom-right, bottom-left
DICT = cv2.aruco.DICT_4X4_50
GATES = dict(minPatches=20, meanDeltaE=3.0, maxDeltaE=8.0, looMeanDeltaE=4.0)


def marker_corners_mm():
    x0, y0, x1, y1 = MARGIN, MARGIN, W_MM - MARGIN - MARK, H_MM - MARGIN - MARK
    origins = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return {mid: np.array([[x, y], [x + MARK, y], [x + MARK, y + MARK], [x, y + MARK]], float) for mid, (x, y) in zip(MARKER_IDS, origins)}


def patch_rects_mm():
    gw, gh = 6 * PATCH + 5 * GAP, 4 * PATCH + 3 * GAP
    x0, y0 = (W_MM - gw) / 2, (H_MM - gh) / 2
    return [(x0 + c * (PATCH + GAP), y0 + r * (PATCH + GAP), PATCH, PATCH) for r in range(4) for c in range(6)]


def render_chart(px_per_mm=300 / 25.4, reference=NOMINAL):
    """Chart image (BGR) at the given resolution; default 300 dpi."""
    w, h = int(round(W_MM * px_per_mm)), int(round(H_MM * px_per_mm))
    img = np.full((h, w, 3), 255, np.uint8)
    d = cv2.aruco.getPredefinedDictionary(DICT)
    for mid, c in marker_corners_mm().items():
        side = int(round(MARK * px_per_mm)); x, y = (c[0] * px_per_mm).round().astype(int)
        img[y:y + side, x:x + side] = cv2.cvtColor(cv2.aruco.generateImageMarker(d, mid, side), cv2.COLOR_GRAY2BGR)
    for (x, y, pw, ph), rgb in zip(patch_rects_mm(), reference):
        x0, y0 = int(round(x * px_per_mm)), int(round(y * px_per_mm))
        img[y0:y0 + int(round(ph * px_per_mm)), x0:x0 + int(round(pw * px_per_mm))] = rgb[::-1]
    cv2.putText(img, LAYOUT, (int(60 * px_per_mm), int((H_MM - 5) * px_per_mm)), cv2.FONT_HERSHEY_SIMPLEX, px_per_mm * .35, (90, 90, 90), max(1, int(px_per_mm * .2)))
    return img


def measure_chart(bgr):
    """Median sRGB (0-255) of each patch's central half; rejects clipped or non-uniform patches."""
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT), cv2.aruco.DetectorParameters())
    corners, ids, _ = det.detectMarkers(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    found = {} if ids is None else {int(i): c.reshape(4, 2) for i, c in zip(ids.ravel(), corners)}
    missing = [m for m in MARKER_IDS if m not in found]
    if missing:
        return dict(ok=False, reason='MARKERS_NOT_FOUND', missingMarkers=missing)
    ref = marker_corners_mm()
    src = np.concatenate([ref[m] for m in MARKER_IDS]); dst = np.concatenate([found[m] for m in MARKER_IDS])
    Hm, _ = cv2.findHomography(src, dst)
    reproj = float(np.abs(cv2.perspectiveTransform(src[None], Hm)[0] - dst).max())
    rows = []
    for i, (x, y, pw, ph) in enumerate(patch_rects_mm()):
        quad = cv2.perspectiveTransform(np.array([[[x + pw * .25, y + ph * .25], [x + pw * .75, y + ph * .25], [x + pw * .75, y + ph * .75], [x + pw * .25, y + ph * .75]]]), Hm)[0]
        mask = np.zeros(bgr.shape[:2], np.uint8); cv2.fillConvexPoly(mask, quad.round().astype(np.int32), 1)
        px = bgr[mask.astype(bool)][:, ::-1].astype(float)
        if len(px) < 30:
            rows.append(dict(index=i, name=NAMES[i], usable=False, reason='TOO_SMALL')); continue
        med = np.median(px, 0); spread = float(np.percentile(np.abs(px - med).max(1), 90))
        clipped = float(((px >= 254) | (px <= 1)).any(1).mean())
        usable = clipped < .02 and spread < 25
        rows.append(dict(index=i, name=NAMES[i], rgb=med.round(2).tolist(), pixels=int(len(px)), clipped=round(clipped, 4), spread90=round(spread, 2), usable=usable,
                         reason=None if usable else ('CLIPPED' if clipped >= .02 else 'NOT_UNIFORM')))
    return dict(ok=True, reprojectionErrorPx=round(reproj, 2), patches=rows)


def _lab(srgb255):
    return rgb2lab(np.clip(np.asarray(srgb255, float) / 255, 0, 1)[None])[0]


def _apply(lin, M):
    return lin @ M[:3] + M[3]


def _fit(lin_meas, lin_ref):
    A = np.hstack([lin_meas, np.ones((len(lin_meas), 1))])
    return np.linalg.lstsq(A, lin_ref, rcond=None)[0]   # 4x3


def fit_profile(measurements, profile_id, yuv=None, reference=NOMINAL, reference_kind='nominal-colorchecker-srgb', sources=()):
    """measurements: list of measure_chart() results (one per photo). Returns (profile or None, report)."""
    good = [m for m in measurements if m.get('ok')]
    report = dict(layout=LAYOUT, photos=len(measurements), photosWithChart=len(good), referenceKind=reference_kind, gates=GATES,
                  failures=[m['reason'] for m in measurements if not m.get('ok')])
    if not good:
        return None, {**report, 'status': 'REJECTED', 'reason': 'NO_CHART_FOUND'}
    use = [i for i in range(24) if all(m['patches'][i]['usable'] for m in good)]
    report['usablePatches'] = len(use); report['unusable'] = [NAMES[i] for i in range(24) if i not in use]
    if len(use) < GATES['minPatches']:
        return None, {**report, 'status': 'REJECTED', 'reason': 'TOO_FEW_USABLE_PATCHES'}
    meas = np.mean([[m['patches'][i]['rgb'] for i in use] for m in good], 0)
    ref = np.asarray(reference, float)[use]
    lin_m, lin_r = srgb_to_linear(meas / 255), srgb_to_linear(ref / 255)
    M = _fit(lin_m, lin_r)
    after = linear_to_srgb(_apply(lin_m, M)) * 255
    de_before = deltaE_ciede2000(_lab(meas), _lab(ref)); de_after = deltaE_ciede2000(_lab(after), _lab(ref))
    loo = []
    for k in range(len(use)):
        keep = [j for j in range(len(use)) if j != k]; Mk = _fit(lin_m[keep], lin_r[keep])
        loo.append(float(deltaE_ciede2000(_lab(linear_to_srgb(_apply(lin_m[k:k + 1], Mk)) * 255), _lab(ref[k:k + 1]))[0]))
    fit = dict(deltaE00Before=dict(mean=round(float(de_before.mean()), 2), max=round(float(de_before.max()), 2)),
               deltaE00After=dict(mean=round(float(de_after.mean()), 2), max=round(float(de_after.max()), 2)),
               leaveOneOutMean=round(float(np.mean(loo)), 2), perPatch={NAMES[i]: round(float(d), 2) for i, d in zip(use, de_after)})
    report['fit'] = fit
    ccm, offset = M[:3].T, M[3]
    failed = [g for g, bad in (('meanDeltaE', fit['deltaE00After']['mean'] > GATES['meanDeltaE']), ('maxDeltaE', fit['deltaE00After']['max'] > GATES['maxDeltaE']),
                                ('looMeanDeltaE', fit['leaveOneOutMean'] > GATES['looMeanDeltaE'])) if bad]
    profile = dict(schema=SCHEMA, profileId=profile_id, createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                   yuv=yuv, ccm=np.round(ccm, 6).tolist(), offset=np.round(offset, 6).tolist(),
                   chart=dict(layout=LAYOUT, referenceKind=reference_kind, usablePatches=len(use)), fit=fit, sources=list(sources))
    try:
        _check_profile(profile)
    except ValueError as error:
        failed.append(str(error))
    if failed:
        return None, {**report, 'status': 'REJECTED', 'reason': 'QUALITY_GATES', 'failedGates': failed}
    if yuv is not None and (yuv.get('matrix') not in MATRICES or not isinstance(yuv.get('fullRange'), bool)):
        return None, {**report, 'status': 'REJECTED', 'reason': 'INVALID_YUV'}
    return profile, {**report, 'status': 'ACCEPTED'}


def write_profile(profile, path):
    import os
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(profile, f, indent=1)
    os.replace(tmp, path)
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()
