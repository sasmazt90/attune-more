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

VERSION = 'skin-findings-v2'
APP_REGIONS = ('forehead', 'nose', 'rightCheek', 'leftCheek', 'chin')
CHEEKS = ('rightCheek', 'leftCheek')
MIN_REGION_PX = 150          # same as the research features (features2.py: region mask >= 150 px at 400 px face width)
DETECTOR_FINDINGS = {
    'mole': dict(key='findings_Riskli_Ben_max', cls='Riskli Ben', regions=CHEEKS, threshold=0.58, markers=True),
    'melasma': dict(key='findings_Gunes_Lekesi_max', cls='Gunes Lekesi', regions=CHEEKS, threshold=0.54, markers=False),
    'rosacea': dict(key='findings_Rozasea_max', cls='Rozasea', regions=APP_REGIONS, threshold=0.69, markers=False),
}
THRESHOLD_SOURCE = 'research/skin-findings/results/det_prev.md (thr_prev on 260 training persons; findings.pt)'
EVIDENCE_KEYS = tuple(sorted({d['key'] for d in DETECTOR_FINDINGS.values()} |
                             {'findings_Riskli_Ben_n35', 'findings_Ucuk_n35', 'findings_Gunes_Lekesi_cov20', 'c_flake'}))
# Displayed values (every seen finding shows a number; none of these counts/areas is validated against ground truth):
#  counts  = boxes the detector marks (score >= 0.35, the research n35 rule), from ONE photo per region so a lesion is
#            never counted twice: forehead/nose/chin from FRONT, each cheek from the side photo that faces the camera;
#  melasma = share of the cheek covered by Gunes Lekesi boxes >= 0.2 (research cov20), on the photo that decided;
#  flaking = rank of the bare-skin flake texture (c_flake) among flaking-positive regions of the training characters.
COUNT_POSE = {'forehead': 'FRONT', 'nose': 'FRONT', 'chin': 'FRONT', 'rightCheek': 'LEFT', 'leftCheek': 'RIGHT'}
BOX_CLASSES = {'Riskli Ben': 'mole', 'Ucuk': 'coldSore'}
# acne lesions counted (research n35 classes of the acne features) and their displayed type
ACNE_CLASSES = {('findings', 'Akne'): 'unspecified', ('findings', 'Siyah Nokta'): 'blackhead', ('findings', 'Beyaz Nokta'): 'whitehead',
                ('acnes', 'blackhead'): 'blackhead', ('acnes', 'whitehead'): 'whitehead', ('acnes', 'papule'): 'papule',
                ('acnes', 'pustule'): 'pustule'}
LIP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
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


def evidence_from_detections(ev: dict, dets: dict, cats: dict, polys: dict, sc: float, view: str, pose: str, inv, src_scale: float, Pc=None):
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
    lip = None
    if Pc is not None and len(Pc) > max(LIP):
        L = np.asarray(Pc)[LIP]; fw = float(np.asarray(Pc)[:, 0].max() - np.asarray(Pc)[:, 0].min()); pad = 0.04 * fw   # research lip crop
        lip = (L[:, 0].min() - pad, L[:, 1].min() - pad, L[:, 0].max() + pad, L[:, 1].max() + pad)
    for c, s, (x0, y0, x1, y1) in dets.get('findings', []):
        fid = BOX_CLASSES.get(names.get(c))
        if fid is None or s < MARKER_MIN_SCORE:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if fid == 'coldSore':
            if lip is None or not (lip[0] <= cx <= lip[2] and lip[1] <= cy <= lip[3]):
                continue
            reg = 'chin'
        else:
            reg = next((APP_OF[rk] for rk in APP_OF if rk in polys and _point_in(polys[rk], cx, cy)), None)
        if reg is None or not _usable(reg, view):
            continue
        sx, sy = inv(cx, cy)
        boxes.append(dict(finding=fid, region=reg, pose=pose, x=round(sx, 1), y=round(sy, 1), r=round(max(x1 - x0, y1 - y0) / 2 * src_scale, 1), score=round(float(s), 4)))
    # acne lesions: boxes >= 0.35 of the acne-type classes of both detectors, one lesion per location (a box whose centre
    # lies in an already kept higher-score box is the same lesion; a typed class names the lesion over the generic 'Akne')
    cand = []
    for mn in ('findings', 'acnes'):
        cmap = cats.get(mn, {})
        for c, s, (x0, y0, x1, y1) in dets.get(mn, []):
            sub = ACNE_CLASSES.get((mn, cmap.get(c)))
            if sub is None or s < MARKER_MIN_SCORE or (x1 - x0) * (y1 - y0) > 0.8 * 1024 * 1024:
                continue
            cand.append([float(s), sub, (x0, y0, x1, y1)])
    kept = []
    for s, sub, bx in sorted(cand, key=lambda t: -t[0]):
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        same = next((q for q in kept if q[2][0] <= cx <= q[2][2] and q[2][1] <= cy <= q[2][3]), None)
        if same is not None:
            if same[1] == 'unspecified' and sub != 'unspecified':
                same[1] = sub
            continue
        kept.append([s, sub, bx])
    for s, sub, (x0, y0, x1, y1) in kept:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        reg = next((APP_OF[rk] for rk in APP_OF if rk in polys and _point_in(polys[rk], cx, cy)), None)
        if reg is None or not _usable(reg, view):
            continue
        sx, sy = inv(cx, cy)
        boxes.append(dict(finding='acne', region=reg, pose=pose, type=sub, x=round(sx, 1), y=round(sy, 1),
                          r=round(max(x1 - x0, y1 - y0) / 2 * src_scale, 1), score=round(float(s), 4)))
    return out, boxes


def _unavailable_list(extra_reason: str | None = None) -> list:
    rows = [dict(id=f, reason=r) for f, r in UNAVAILABLE.items()]
    if extra_reason:
        rows += [dict(id=f, reason=extra_reason) for f in DETECTOR_FINDINGS]
    return rows


def _model_dir() -> str:
    import regional_skin_v3 as R
    return R.MODEL_DIR


def _det_specs() -> dict:
    try:
        import skin_findings_det as SFD
        return SFD.specs(_model_dir())
    except Exception:  # noqa: BLE001
        return {}


def _det_rows(det: dict, maps: dict, poses: list) -> tuple[list, dict]:
    """acne + redness rows (research decision rule in skin_findings_det.decide) and the light-corrected redness
    measures per region ({region: {areaPct, toneDiff}}), which rosacea and eczema also display."""
    import skin_findings_det as SFD
    per = {p: maps[p].get('findingDet') for p in poses if isinstance(maps[p].get('findingDet'), dict)}
    rows, measures = [], {}
    if len(per) == len(poses):
        for r in SFD.decide(per, list(det.values())):
            row = dict(id=r['id'], region=r['region'], status=r['status'], pose=r['pose'], readFrom=sorted(per))
            if r['id'] == 'redness' and r.get('areaPct') is not None:
                measures[r['region']] = dict(areaPct=round(float(r['areaPct']), 1), toneDiff=round(float(r['toneDiff']), 1))
                if row['status'] == 'seen':
                    row.update(measures[r['region']])
            rows.append(row)
    have = {(r['id'], r['region']) for r in rows}
    for fid, sp in det.items():
        for reg in sorted(set((sp.get('regionOf') or {}).values()) or APP_REGIONS):
            if (fid, reg) not in have:
                rows.append(dict(id=fid, region=reg, status='inconclusive', causes=['ANGLE']))
    return rows, measures


def _eye_specs() -> dict:
    try:
        import skin_findings_eye as SEYE
        return SEYE.specs(_model_dir())
    except Exception:  # noqa: BLE001
        return {}


def _eye_rows(fid: str, spec: dict, maps: dict) -> list:
    """Eye-area classifiers decide on the FRONT photo (research recipe); absent score -> inconclusive, never notSeen."""
    import skin_findings_eye as SEYE
    p = (maps.get('FRONT', {}).get('eyeScores') or {}).get(fid)
    if p is None:
        return [dict(id=fid, region='periorbital', status='inconclusive', causes=['ANGLE'])]
    row = dict(id=fid, region='periorbital', status=SEYE.decide(float(p), spec), pose='FRONT', readFrom=['FRONT'])
    v = (maps.get('FRONT', {}).get('eyeMeasures') or {}).get(fid)
    if row['status'] == 'seen' and v is not None:
        row['severity'] = v
    return [row]


def _saved_specs() -> dict:
    """Saved finding classifiers present in the model bundle (findings-v2/*.json). Missing bundle -> {}."""
    try:
        import skin_findings_dino as SD
        return SD.specs(_model_dir())
    except Exception:  # noqa: BLE001 - absent bundle keeps the findings 'unavailable'
        return {}


def _unavailable(extra_reason: str | None, available: set) -> list:
    rows = [dict(id=f, reason=r) for f, r in UNAVAILABLE.items() if f not in available]
    if extra_reason:
        rows += [dict(id=f, reason=extra_reason) for f in (*DETECTOR_FINDINGS, *sorted(available))]
    return rows


def _dino_rows(fid: str, spec: dict, maps: dict, poses: list) -> list:
    """Rows of one saved DINOv2-crop finding: region scores from the per-photo crop probabilities (research decision rule)."""
    thr = float(spec['threshold']); fa4 = spec.get('recipe') == 'fa4'
    vals = {}   # crop -> [(pose, prob)]
    for p in poses:
        for c, v in ((maps[p].get('findingScores') or {}).get(fid) or {}).items():
            vals.setdefault(c, []).append((p, float(v)))
    by_region = {}
    for c, pv in vals.items():
        reg = spec['regionOf'][c]
        score = max(v for _, v in pv) if fa4 else sum(v for _, v in pv) / len(pv)
        best_pose = max(pv, key=lambda t: t[1])[0]
        cur = by_region.get(reg)
        if cur is None or score > cur[0]:
            by_region[reg] = (score, best_pose, sorted({p for p, _ in pv}))
    regions = sorted(set(spec['regionOf'].values()))
    rows = []
    person = max((v for pv in vals.values() for _, v in pv), default=None)
    for reg in regions:
        if reg not in by_region:
            rows.append(dict(id=fid, region=reg, status='inconclusive', causes=['ANGLE'])); continue
        score, pose, read = by_region[reg]
        rows.append(dict(id=fid, region=reg, status='seen' if score >= thr else 'notSeen', pose=pose, readFrom=read))
    # person-level decision (max over crops and poses) is the validated one; if it fires but no region reached the
    # threshold on its own aggregate, the region holding the maximum is the one shown
    if person is not None and person >= thr and not any(r['status'] == 'seen' for r in rows):
        top = max(by_region, key=lambda r: by_region[r][0])
        for r in rows:
            if r['region'] == top:
                r['status'] = 'seen'
    return rows


def _attach_count(row: dict, maps: dict, poses: list, fallback_pose: str | None = None) -> None:
    """count + markers of a seen box-type finding from ONE photo (no double counting across photos): the photo that
    faces the region (COUNT_POSE); if it marks nothing there, the photo that decided the finding; then any photo."""
    def boxes(p):
        return [b for b in (maps.get(p, {}).get('findingBoxes') or []) if b['finding'] == row['id'] and b['region'] == row['region']]
    order = [COUNT_POSE.get(row['region'])] + [fallback_pose] + list(poses)
    pose = next((p for p in order if p in poses and boxes(p)), None)
    marks = boxes(pose) if pose else []
    row['markers'] = [dict(x=b['x'], y=b['y'], r=b['r'], pose=b['pose'], **({'type': b['type']} if 'type' in b else {})) for b in marks]
    row['count'] = len(marks)
    if row['id'] == 'acne':
        types = {}
        for b in marks:
            types[b.get('type', 'unspecified')] = types.get(b.get('type', 'unspecified'), 0) + 1
        row['subtypes'] = {k: types.get(k, 0) for k in ('blackhead', 'whitehead', 'papule', 'pustule', 'unspecified')}
    if not marks:   # the decision says it is there, the detector marked no single lesion: at least one
        row['count'] = 1; row['countAtLeast'] = True
        if row['id'] == 'acne':
            row['subtypes'] = dict(blackhead=0, whitehead=0, papule=0, pustule=0, unspecified=1)


def _measures_ref(name: str):
    try:
        import json, os
        path = os.path.join(_model_dir(), 'findings-v2', 'measures', f'{name}.json')
        return json.load(open(path)) if os.path.exists(path) else None
    except Exception:  # noqa: BLE001
        return None


def _attach_measures(findings: list, maps: dict, poses: list) -> None:
    """Values for seen findings without a rated severity model (see the comment at EVIDENCE_KEYS)."""
    import bisect
    flake = _measures_ref('flaking')
    for f in findings:
        if f['status'] != 'seen':
            continue
        if f['id'] == 'coldSore':
            _attach_count(f, maps, poses)
        elif f['id'] == 'flaking' and flake and 'severity' not in f:
            e = (maps.get('FRONT', {}).get('findingEvidence') or {}).get(f['region']) or {}
            if e.get('c_flake') is not None:
                ref = flake['reference']; v = float(e['c_flake'])
                lo, hi = bisect.bisect_left(ref, v), bisect.bisect_right(ref, v)
                f['severity'] = round(100.0 * (lo + 0.5 * (hi - lo)) / len(ref), 1)


def _attach_severity(findings: list, maps: dict, poses: list) -> None:
    """Belirginlik (0-100) on the seen rows of findings that have a saved severity model and every expected photo row."""
    try:
        import skin_findings_severity as SV
        md = _model_dir()
    except Exception:  # noqa: BLE001
        return
    for fid in {f['id'] for f in findings if f['status'] == 'seen'}:
        terms = {}
        for p in poses:
            terms.update((maps[p].get('severityTerms') or {}).get(fid) or {})
        v = SV.from_terms(fid, terms, md)
        if v is None:
            continue
        for f in findings:
            if f['id'] == fid and f['status'] == 'seen':
                f['severity'] = round(v, 1)


def findings_from_maps(maps: dict) -> dict:
    """maps: {'FRONT'|'LEFT'|'RIGHT': regional_skin_v3.analyze_photo() output}. Returns general.findings."""
    poses = sorted(p for p, m in maps.items() if isinstance(m, dict) and isinstance(m.get('findingEvidence'), dict))
    specs = _saved_specs(); eye = _eye_specs(); det = _det_specs()
    available = {f for f in (*specs, *eye, *det) if f in UNAVAILABLE}
    front_models = (maps.get('FRONT') or {}).get('models') or {}
    base = dict(version=VERSION, poses=poses, thresholdSource=THRESHOLD_SOURCE,
                models={k: v for k, v in front_models.items() if k == 'findings.pt' or k.startswith('findings-v2')})
    missing = [p for p in REQUIRED_POSES if p not in poses]
    if missing:
        return dict(base, status='unavailable', reason='REQUIRED_POSES_MISSING', missingPoses=missing, findings=[],
                    unavailable=_unavailable('REQUIRED_POSES_MISSING', available))
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
                _attach_count(row, maps, poses, fallback_pose=best_pose)
            if row['status'] == 'seen' and fid == 'melasma':
                row['areaPct'] = round(100 * float(best.get('findings_Gunes_Lekesi_cov20') or 0.0), 1)
            findings.append(row)
    for fid in sorted(available - set(det)):
        findings += _dino_rows(fid, specs[fid], maps, poses) if fid in specs else _eye_rows(fid, eye[fid], maps)
    measures = {}
    if det:
        rows, measures = _det_rows(det, maps, poses); findings += rows
    for f in findings:   # rosacea and eczema show the light-corrected red area of their region
        if f['status'] == 'seen' and f['id'] in ('rosacea', 'eczema') and f['region'] in measures and 'areaPct' not in f:
            f.update(measures[f['region']])
        if f['status'] == 'seen' and f['id'] == 'acne':
            _attach_count(f, maps, poses, fallback_pose=f.get('pose'))
    _attach_severity(findings, maps, poses)
    _attach_measures(findings, maps, poses)
    return dict(base, status='measured', findings=findings, unavailable=_unavailable(None, available))
