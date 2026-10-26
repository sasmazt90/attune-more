"""Skin findings for the result screen (general.findings), built ONLY from saved, hash-verified models.

What is measured
  Three findings whose decision is a single saved detector score (findings.pt, RF-DETR) compared with a threshold that
  was chosen on training persons only (research/skin-findings/scripts/det_prev.py, rule thr_prev, results/det_prev.md):
    mole     <- findings 'Riskli Ben'    (cheeks)          threshold 0.58
    melasma  <- findings 'Gunes Lekesi'  (cheeks)          threshold 0.54
    rosacea  <- findings 'Rozasea'       (all 5 regions)   threshold 0.69
  Score scale check: the production evidence (regional_skin_v3.model_evidence on the 1024 px face crop) equals the cached
  research features for the same photos (12 photos / 60 regions, max |diff| 0.001 on usable regions; CODEX_HANDOFF.md).
  Capture set: validated as "front + 20° side" -> needs the FRONT photo and both side photos (LEFT, RIGHT). With any
  pose missing these findings are 'unavailable' (REQUIRED_POSES_MISSING), never guessed from fewer photos.

What is NOT measured (status 'unavailable')
  Every other finding: its decision model (DINOv2/LR, geometry/LR, colour/LR, detector-combination LR) was never saved,
  so it cannot run (MODEL_NOT_AVAILABLE). 'spots' did not reach the precision bar (NOT_VALIDATED).
  No severity, area or count is produced: the severity regressors were not saved, the area of a detector box is not a
  validated area, and counts were not point-validated. Missing values stay absent (never zero / never a low score).

Region states
  seen       - region read in at least one photo that shows it and its score >= threshold
  notSeen    - region read and score < threshold
  inconclusive - region never readable (too small / not visible in any photo); causes from the regional map
"""
from __future__ import annotations

VERSION = 'skin-findings-v1-detector'
APP_REGIONS = ('forehead', 'nose', 'rightCheek', 'leftCheek', 'chin')
CHEEKS = ('rightCheek', 'leftCheek')
MIN_REGION_PX = 150          # same as the research features (features2.py: region mask >= 150 px at 400 px face width)
DETECTOR_FINDINGS = {
    'mole': dict(key='findings_Riskli_Ben_max', cls='Riskli Ben', regions=CHEEKS, threshold=0.58, markers=True),
    'melasma': dict(key='findings_Gunes_Lekesi_max', cls='Gunes Lekesi', regions=CHEEKS, threshold=0.54, markers=False),
    'rosacea': dict(key='findings_Rozasea_max', cls='Rozasea', regions=APP_REGIONS, threshold=0.69, markers=False),
}
THRESHOLD_SOURCE = 'research/skin-findings/results/det_prev.md (thr_prev on 260 training persons; findings.pt)'
EVIDENCE_KEYS = tuple(sorted({d['key'] for d in DETECTOR_FINDINGS.values()}))
UNAVAILABLE = {
    'eyeBags': 'MODEL_NOT_AVAILABLE', 'darkCircles': 'MODEL_NOT_AVAILABLE', 'hoodedEyelids': 'MODEL_NOT_AVAILABLE',
    'downturnedCorners': 'MODEL_NOT_AVAILABLE', 'crowsFeet': 'MODEL_NOT_AVAILABLE', 'foreheadLines': 'MODEL_NOT_AVAILABLE',
    'coldSore': 'MODEL_NOT_AVAILABLE', 'acneMarks': 'MODEL_NOT_AVAILABLE', 'acne': 'MODEL_NOT_AVAILABLE',
    'redness': 'MODEL_NOT_AVAILABLE', 'eczema': 'MODEL_NOT_AVAILABLE', 'flaking': 'MODEL_NOT_AVAILABLE',
    'spots': 'NOT_VALIDATED',
}
REQUIRED_POSES = ('FRONT', 'LEFT', 'RIGHT')
APP_OF = {'forehead': 'forehead', 'nose': 'nose', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek', 'chin': 'chin'}
MARKER_MIN_SCORE = 0.35


def _usable(app: str, view: str) -> bool:
    """A cheek is read only from the front or from the side photo that shows it (same rule as the research)."""
    return not ((app == 'rightCheek' and view == 'neg') or (app == 'leftCheek' and view == 'pos'))


def _point_in(poly, x: float, y: float) -> bool:
    inside = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1:
            inside = not inside
    return inside


def evidence_from_detections(ev: dict, dets: dict, cats: dict, polys: dict, sc: float, view: str, pose: str, inv, src_scale: float):
    """Called by regional_skin_v3.analyze_photo. ev: model_evidence() per research region; polys: 1024-crop polygons;
    inv: crop -> source pixel transform of this photo; src_scale: crop px -> source px."""
    import cv2, numpy as np
    out = {}
    for rk, app in APP_OF.items():
        if rk not in polys:
            continue
        area = float(cv2.contourArea((np.asarray(polys[rk], np.float32) * sc).reshape(-1, 1, 2)))
        e = ev.get(rk, {})
        out[app] = dict(areaPx=round(area), usable=_usable(app, view), **{k: round(float(e.get(k) or 0.0), 4) for k in EVIDENCE_KEYS})
    boxes = []
    names = cats.get('findings', {})
    for c, s, (x0, y0, x1, y1) in dets.get('findings', []):
        cname = names.get(c)
        fid = next((f for f, d in DETECTOR_FINDINGS.items() if d['cls'] == cname and d['markers']), None)
        if fid is None or s < MARKER_MIN_SCORE:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        reg = next((APP_OF[rk] for rk in APP_OF if rk in polys and _point_in(polys[rk], cx, cy)), None)
        if reg is None or not _usable(reg, view):
            continue
        sx, sy = inv(cx, cy)
        boxes.append(dict(finding=fid, region=reg, pose=pose, x=round(sx, 1), y=round(sy, 1), r=round(max(x1 - x0, y1 - y0) / 2 * src_scale, 1), score=round(float(s), 4)))
    return out, boxes


def _unavailable_list(extra_reason: str | None = None) -> list:
    rows = [dict(id=f, reason=r) for f, r in UNAVAILABLE.items()]
    if extra_reason:
        rows += [dict(id=f, reason=extra_reason) for f in DETECTOR_FINDINGS]
    return rows


def findings_from_maps(maps: dict) -> dict:
    """maps: {'FRONT'|'LEFT'|'RIGHT': regional_skin_v3.analyze_photo() output}. Returns general.findings."""
    poses = sorted(p for p, m in maps.items() if isinstance(m, dict) and isinstance(m.get('findingEvidence'), dict))
    base = dict(version=VERSION, poses=poses, thresholdSource=THRESHOLD_SOURCE,
                models={k: v for k, v in ((maps.get('FRONT') or {}).get('models') or {}).items() if k == 'findings.pt'})
    missing = [p for p in REQUIRED_POSES if p not in poses]
    if missing:
        return dict(base, status='unavailable', reason='REQUIRED_POSES_MISSING', missingPoses=missing, findings=[],
                    unavailable=_unavailable_list('REQUIRED_POSES_MISSING'))
    findings = []
    for fid, d in DETECTOR_FINDINGS.items():
        for app in d['regions']:
            reads = [(p, maps[p]['findingEvidence'].get(app)) for p in poses]
            reads = [(p, e) for p, e in reads if e and e.get('usable') and e.get('areaPx', 0) >= MIN_REGION_PX]
            if not reads:
                causes = sorted({c for p in poses for c in ((maps[p].get('regions') or {}).get(app, {}).get('causes') or [])}) or ['ANGLE']
                findings.append(dict(id=fid, region=app, status='inconclusive', causes=causes))
                continue
            best_pose, best = max(reads, key=lambda pe: pe[1][d['key']])
            score = float(best[d['key']])
            row = dict(id=fid, region=app, status='seen' if score >= d['threshold'] else 'notSeen', pose=best_pose,
                       readFrom=[p for p, _ in reads])
            if row['status'] == 'seen' and d['markers']:
                row['markers'] = [dict(x=b['x'], y=b['y'], r=b['r'], pose=b['pose'])
                                  for p in poses for b in (maps[p].get('findingBoxes') or [])
                                  if b['finding'] == fid and b['region'] == app and b['score'] >= d['threshold']]
            findings.append(row)
    return dict(base, status='measured', findings=findings, unavailable=_unavailable_list())
