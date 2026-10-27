"""Saved detector-feature finding classifiers (models/<bundle>/findings-v2/{acne,redness}.json, version
skin-findings-v2-det-*), re-fitted with the exact research recipes by export_det.py:
  * acne    = research/skin-findings/scripts/lesion_eval.py (TASK=Sivilce), method "Dedektör (öğrenilmiş birleşim)"
  * redness = research/skin-findings/scripts/redness_prev.py, method "Dedektör"
Inputs per photo and research region (forehead, nose, cheek_imgL, cheek_imgR, chin):
  * RF-DETR evidence from regional_skin_v3.model_evidence (findings_*, acnes_*, skinmap_* keys), unchanged;
  * c_red, cv_red, cv_redp90 from color_features() below (research features2.py / features.py definitions; production
    bare_skin_features' cv_red uses a bare-skin face reference and its c_red also dilates lesion boxes, so neither is
    the research value; bare_skin_features' c_red is only a fallback when color_features got no masks);
  * ita from regional_skin_v3.ita_angle, rounded to 0.1 as the research cache.
Inference is numpy only: StandardScaler + LogisticRegression per fold, probability averaged / combined exactly as in
the research scripts (see decide()/person_score()). Region mapping: cheek_imgL -> rightCheek, cheek_imgR -> leftCheek;
a cheek is scored only from FRONT or from the side pose that shows it (LEFT = view 'pos' hides leftCheek, RIGHT = view
'neg' hides rightCheek)."""
from __future__ import annotations
import glob, hashlib, json, math, os, threading
import numpy as np

APP = {'forehead': 'forehead', 'nose': 'nose', 'chin': 'chin', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek'}
FACE = ['forehead', 'nose', 'cheek_imgL', 'cheek_imgR', 'chin']
VIEW_OF_POSE = {'FRONT': 'front', 'LEFT': 'pos', 'RIGHT': 'neg'}
VERSION_PREFIX = 'skin-findings-v2-det'
_lock = threading.Lock(); _specs: dict = {}


def specs(model_dir: str) -> dict:
    """{finding_id: spec} of the det-family JSONs in <model_dir>/findings-v2 (other families are ignored)."""
    with _lock:
        if model_dir not in _specs:
            out = {}
            for p in sorted(glob.glob(os.path.join(model_dir, 'findings-v2', '*.json'))):
                if os.path.basename(p) == 'REPORT.json':
                    continue
                s = json.load(open(p, encoding='utf-8'))
                if str(s.get('version', '')).startswith(VERSION_PREFIX):
                    for f in s['model']['folds']:
                        f['_mean'] = np.asarray(f['mean'], float); f['_scale'] = np.asarray(f['scale'], float); f['_coef'] = np.asarray(f['coef'], float)
                    out[s['id']] = s
            _specs[model_dir] = out
        return _specs[model_dir]


def manifest(model_dir: str) -> dict:
    """{'findings-v2/<id>.json': sha256} of the det-family model files."""
    out = {}
    for p in sorted(glob.glob(os.path.join(model_dir, 'findings-v2', '*.json'))):
        try:
            s = json.load(open(p, encoding='utf-8'))
        except Exception:
            continue
        if str(s.get('version', '')).startswith(VERSION_PREFIX):
            out['findings-v2/' + os.path.basename(p)] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return out


LESION_FINDINGS = {'Akne', 'Siyah Nokta', 'Beyaz Nokta', 'Gunes Lekesi', 'Riskli Ben', 'Ucuk'}


def color_features(rgb: np.ndarray, polys: dict, face_w: float, wrinkle: np.ndarray | None = None, hair: np.ndarray | None = None,
                   dets: dict | None = None, cats: dict | None = None) -> dict:
    """Research redness colour features per research region: {region: {'cv_red', 'cv_redp90'[, 'c_red']} | None}.
    rgb / polys / face_w: the 1024-px face crop, its region polygons and face width exactly as analyze_photo has them.
    cv_red / cv_redp90 (research features.py): 400-px face scale; face reference = median a* over the union of the 5
    regions (no bare-skin cleaning). Production bare_skin_features' cv_red uses a bare-skin reference: NOT this feature.
    c_red (research features2.py), only when wrinkle (wrinkle-model mask, 1024 crop), hair (regional_skin_v3.hair_mask
    only, WITHOUT the lesion mask) and dets/cats (RF-DETR detections in crop pixels) are given: mean a* of the bare skin
    of the region minus the median a* of the bare face; wrinkle and beard masks are resized (nearest) and dilated 5x5,
    lesion boxes (acnes all classes + findings lesion classes, score >= 0.35, area <= 25 % of the crop) are removed
    undilated at the 400-px scale. This differs from bare_skin_features' c_red only in that production dilates the
    lesion boxes too; the research definition is reproduced here."""
    import cv2
    sc = 400 / max(face_w, 1); h, w = rgb.shape[:2]; size = (max(1, round(w * sc)), max(1, round(h * sc)))
    im = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC)
    A = cv2.cvtColor(im, cv2.COLOR_RGB2LAB).astype(np.float32)[..., 1] - 128
    masks = {}
    for k in FACE:
        m = np.zeros(A.shape, np.uint8); cv2.fillPoly(m, [(np.asarray(polys[k]) * sc).astype(np.int32)], 1); masks[k] = m > 0
    fm = np.zeros(A.shape, bool)
    for m in masks.values():
        fm |= m
    if fm.sum() < 500:
        return {k: None for k in FACE}
    Am = np.median(A[fm]); out = {}
    for k, m in masks.items():
        if m.sum() < 150:
            out[k] = None; continue
        out[k] = {'cv_red': float(A[m].mean() - Am), 'cv_redp90': float(np.percentile(A[m], 90) - Am)}
    if wrinkle is None or hair is None or dets is None or cats is None:
        return out
    k5 = np.ones((5, 5), np.uint8)
    wr = cv2.dilate(cv2.resize(np.asarray(wrinkle).astype(np.uint8), size, interpolation=cv2.INTER_NEAREST), k5) > 0
    br = cv2.dilate(cv2.resize(np.asarray(hair).astype(np.uint8), size, interpolation=cv2.INTER_NEAREST), k5) > 0
    for mn in ('acnes', 'findings'):
        for c, s, (x0, y0, x1, y1) in dets.get(mn, []):
            if s < 0.35 or (x1 - x0) * (y1 - y0) > 0.25 * w * h:
                continue
            if mn == 'findings' and (cats.get(mn) or {}).get(c) not in LESION_FINDINGS:
                continue
            br[max(0, int(y0 * sc)):int(y1 * sc) + 1, max(0, int(x0 * sc)):int(x1 * sc) + 1] = True
    clean = fm & ~wr & ~br; ref = clean if clean.sum() > 300 else fm; Amc = np.median(A[ref])
    for k, m in masks.items():
        if out[k] is None:
            continue
        cl = m & ~wr & ~br
        out[k]['c_red'] = float(A[cl].mean() - Amc) if cl.sum() >= 80 else None
    return out


_lm_lock = threading.Lock(); _lm = {}


def default_task_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.environ.get('ATTUNE_FACE_LANDMARKER_TASK', os.path.join(here, '..', '..', 'apps', 'vehicle-app', 'public', 'mediapipe', 'models', 'face_landmarker.task'))


def crop_landmarks(crop_bgr: np.ndarray, task_path: str | None = None):
    """MediaPipe FaceLandmarker (python tasks API, num_faces=1) on the 1024-px face crop itself: the research landmark
    recipe of k5_items.py (polygons/features) and redness_feats.py (light correction). Returns the normalised landmark
    list (objects with .x .y .z) or None when mediapipe / the .task file is unavailable or no face is found."""
    try:
        import cv2, mediapipe as mp
        from mediapipe.tasks.python import vision, BaseOptions
    except Exception:
        return None
    task_path = task_path or default_task_path()
    if not os.path.exists(task_path):
        return None
    with _lm_lock:
        if task_path not in _lm:
            _lm[task_path] = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=task_path), num_faces=1))
        r = _lm[task_path].detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)))
    return r.face_landmarks[0] if r.face_landmarks else None


def crop_regions(crop_bgr: np.ndarray, task_path: str | None = None, lms=None):
    """Research region polygons from crop landmarks: rounded to 0.1 px; face width = round(x-range of all landmarks, 0.1).
    Returns (polys, face_w) or None."""
    lms = lms if lms is not None else crop_landmarks(crop_bgr, task_path)
    if lms is None:
        return None
    h, w = crop_bgr.shape[:2]; P = np.array([[q.x * w, q.y * h] for q in lms])
    import regional_skin_v3 as R
    return {k: P[v].round(1) for k, v in R.REG.items()}, round(float(P[:, 0].max() - P[:, 0].min()), 1)


# ---- light-corrected redness (verbatim port of research/skin-findings/scripts/light.py + redness_feats.py) ----
def _normals_map(P3, shape):
    from scipy.spatial import Delaunay
    from scipy.interpolate import LinearNDInterpolator
    tri = Delaunay(P3[:, :2]); F = tri.simplices
    v0, v1, v2 = P3[F[:, 0]], P3[F[:, 1]], P3[F[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0); fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-9
    fn[fn[:, 2] < 0] *= -1
    vn = np.zeros_like(P3)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-9
    H, W = shape; ys, xs = np.mgrid[0:H, 0:W]
    N = LinearNDInterpolator(P3[:, :2], vn)(np.stack([xs.ravel(), ys.ravel()], 1)).reshape(H, W, 3)
    valid = np.isfinite(N[..., 0]); N[~valid] = 0
    N /= np.linalg.norm(N, axis=-1, keepdims=True) + 1e-9
    return N, valid


def _robust_fit(A, y, iters=8, c=1.5):
    w = np.ones(len(y))
    for _ in range(iters):
        sw = np.sqrt(w); k, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
        r = y - A @ k; s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-6
        u = np.abs(r) / (c * s); w = np.where(u <= 1, 1.0, 1.0 / u)
    return k


def _light_analyze(img_bgr, lms, scale_to=400):
    import cv2, regional_skin_v3 as R
    h, w = img_bgr.shape[:2]
    P = np.array([[q.x * w, q.y * h, q.z * w] for q in lms[:468]])
    fw = P[:, 0].max() - P[:, 0].min(); sc = scale_to / fw
    x0, y0 = P[:, 0].min() - 0.15 * fw, P[:, 1].min() - 0.15 * fw
    P[:, 0] -= x0; P[:, 1] -= y0; P *= sc
    W = int(P[:, 0].max() + 0.15 * scale_to); H = int(P[:, 1].max() + 0.15 * scale_to)
    M = np.float32([[sc, 0, -x0 * sc], [0, sc, -y0 * sc]])
    im = cv2.warpAffine(img_bgr, M, (W, H), flags=cv2.INTER_AREA).astype(np.float32) / 255
    lin = np.where(im <= 0.04045, im / 12.92, ((im + 0.055) / 1.055) ** 2.4)
    N, nvalid = _normals_map(P, (H, W))
    skin = np.zeros((H, W), np.uint8)
    for v in R.REG.values():
        cv2.fillPoly(skin, [P[v, :2].astype(np.int32)], 1)
    skin = (skin > 0) & nvalid
    im2 = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, 1), 1 / 2.4) - 0.055)
    usable = skin & (im2.max(-1) < 0.97) & (lin.mean(-1) > 0.01)
    A1 = np.concatenate([np.ones((H, W, 1)), N], -1); A = A1[usable]; S = np.zeros_like(lin)
    for ch in range(3):
        S[..., ch] = A1 @ _robust_fit(A, lin[..., ch][usable])
    S = np.clip(S, 1e-3, None); corr = np.clip(lin / S * np.median(S[usable], 0), 0, 1)
    return corr, usable, P


def light_redness(crop_bgr: np.ndarray, lms) -> dict:
    """redness_feats.py per research region: [median a*, p90 a*, median a* - am, frac(a* > am+4), frac(a* > am+8),
    median b*] on the light-corrected image (am = median a* over usable skin), or None (region < 50 usable px).
    lms: crop_landmarks() of this crop. {} if the light fit fails (research: item skipped)."""
    import cv2, regional_skin_v3 as R
    try:
        corr, u, P = _light_analyze(crop_bgr, lms)
        srgb = np.where(corr <= 0.0031308, corr * 12.92, 1.055 * np.power(np.clip(corr, 0, 1), 1 / 2.4) - 0.055)
        # light.lab(R['corr'][..., ::-1]): corr is BGR-ordered; [..., ::-1] -> RGB, then lab() flips back to BGR for OpenCV
        lab = cv2.cvtColor((np.clip(srgb[..., ::-1], 0, 1) * 255).astype(np.uint8)[..., ::-1], cv2.COLOR_BGR2LAB).astype(np.float32)
    except Exception:
        return {}
    a = lab[..., 1] - 128; b = lab[..., 2] - 128; am = float(np.median(a[u])); out = {}
    H, W = u.shape
    for k, v in R.REG.items():
        m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [P[v, :2].astype(np.int32)], 1); m = (m > 0) & u
        if m.sum() < 50:
            out[k] = None; continue
        av = a[m]; hit = av > am + 4
        # [0..5] research fields (parity-checked); [6..8] appearance-v1 inputs: usable px, affected px, mean a*-am of affected
        out[k] = [float(np.median(av)), float(np.percentile(av, 90)), float(np.median(av) - am), float(hit.mean()), float((av > am + 8).mean()), float(np.median(b[m])),
                  int(m.sum()), int(hit.sum()), float((av[hit] - am).mean()) if hit.any() else 0.0]
    return out


def photo_inputs(crop_bgr: np.ndarray, polys: dict, face_w: float, dets: dict, cats: dict, wrinkle: np.ndarray, task_path: str | None = None):
    """(ev, extra, source) for photo_scores / photo_result from what analyze_photo already has (1024 crop, its polygons /
    face width, RF-DETR detections, wrinkle mask). Region polygons: re-detected on the crop
    (research recipe) when mediapipe is available (source 'crop-landmarks'); otherwise the caller's polygons (source
    'client-landmarks', a measured deviation, and no light-corrected redness measures). extra also carries
    'lightRedness' (light_redness)."""
    import cv2, regional_skin_v3 as R
    lms = crop_landmarks(crop_bgr, task_path); rp = crop_regions(crop_bgr, lms=lms) if lms is not None else None; source = 'crop-landmarks'
    if rp is None:
        rp = (polys, face_w); source = 'client-landmarks'
    pl, fw = rp; sc = 400 / max(fw, 1); H, W = crop_bgr.shape[:2]
    ev = R.model_evidence(dets, cats, pl, (max(1, round(H * sc)), max(1, round(W * sc))), sc)
    hair = R.hair_mask(crop_bgr, pl, fw); rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    bare, _ = R.bare_skin_features(rgb, pl, fw, wrinkle, hair | R.lesion_mask(dets, cats, (H, W)))
    extra = dict(bare=bare, color=color_features(rgb, pl, fw, wrinkle, hair, dets, cats), ita=R.ita_angle(rgb, pl),
                 lightRedness=light_redness(crop_bgr, lms) if lms is not None else {})
    return ev, extra, source


MEASURE_POSE = {'forehead': 'FRONT', 'nose': 'FRONT', 'chin': 'FRONT', 'rightCheek': 'LEFT', 'leftCheek': 'RIGHT'}


def redness_measures(extra: dict, view: str) -> dict:
    """Per photo: {app_region: {'areaPct': 100 * frac(a* > am + 4), 'toneDiff': median a* - am}} from
    extra['lightRedness'] (redness_feats.py fields [3] and [2]); regions not visible in this view are left out.
    Display rule (decide()): forehead/nose/chin from FRONT, rightCheek from LEFT, leftCheek from RIGHT."""
    out = {}
    for rk, v in (extra.get('lightRedness') or {}).items():
        if v is None or not _usable(rk, view):
            continue
        out[APP[rk]] = {'areaPct': round(100 * v[3], 2), 'toneDiff': round(v[2], 2)}
        if len(v) >= 9:   # appearance-v1 (skin_appearance): real pixel mask, never a box
            import skin_appearance as SA
            app = SA.region(v[6], v[7], v[8])
            if app:
                out[APP[rk]]['appearance'] = app
    return out


def photo_result(ev: dict, extra: dict, view: str, model_dir: str) -> dict:
    """Everything the fusion needs from ONE photo (JSON-serialisable): per-fold scores + redness measures."""
    return dict(scores=photo_scores(ev, extra, view, model_dir, folds=True), redness=redness_measures(extra, view))


def _value(name: str, rk: str, ev: dict, extra: dict):
    if name == 'ita':
        v = extra.get('ita')
        return None if v is None else round(float(v), 1)
    if name == 'c_red':
        col = (extra.get('color') or {}).get(rk) or {}
        if 'c_red' in col:   # research definition (color_features with masks), preferred
            return col['c_red']
        return ((extra.get('bare') or {}).get(rk) or {}).get('c_red')
    if name in ('cv_red', 'cv_redp90'):
        return ((extra.get('color') or {}).get(rk) or {}).get(name)
    return (ev.get(rk) or {}).get(name)


def _usable(rk: str, view: str) -> bool:
    return not ((view == 'pos' and rk == 'cheek_imgR') or (view == 'neg' and rk == 'cheek_imgL'))


def photo_scores(ev: dict, extra: dict, view: str, model_dir: str, folds: bool = False) -> dict:
    """ONE photo -> {finding_id: {app_region: probability}} (probability = mean over the fold models).
    ev: regional_skin_v3.model_evidence(...) result, keyed by research region.
    extra: {'bare': bare_skin_features(...)[0], 'color': color_features(rgb, polys, face_w, wrinkle, hair, dets, cats),
            'ita': ita_angle(rgb, polys)}  (bare is used for region visibility: None = region < 150 px).
    view: 'front' | 'pos' (pose LEFT) | 'neg' (pose RIGHT).
    folds=True returns the per-fold probabilities {finding_id: {app_region: [p_fold, ...]}} instead; decide() needs
    these to apply the research person rule exactly (mean over folds of the per-fold max over regions)."""
    out = {}
    bare = extra.get('bare') or {}; color = extra.get('color') or {}
    for fid, sp in specs(model_dir).items():
        names = sp['features']; regions = sp['regions']; res = {}
        for rk in regions:
            if rk not in ev or bare.get(rk) is None or not _usable(rk, view):
                continue   # research rows exist only for regions >= 150 px (bare_skin_features not None) visible in the pose
            if any(n in ('cv_red', 'cv_redp90') for n in names) and 'color' in extra and color.get(rk) is None:
                continue
            x = []
            for n in names:
                if n.startswith('region_onehot_'):
                    x.append(1.0 if n == 'region_onehot_' + rk else 0.0)
                else:
                    v = _value(n, rk, ev, extra); x.append(float(v or 0))
            x = np.asarray(x, float); ps = []
            for f in sp['model']['folds']:
                z = float(f['_coef'] @ ((x - f['_mean']) / f['_scale']) + f['intercept'])
                ps.append(1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z)))
            res[APP[rk]] = ps if folds else float(np.mean(ps))
        out[fid] = res
    return out


def _scores_only(scores_by_pose: dict) -> dict:
    return {p: (v.get('scores') if isinstance(v, dict) and 'scores' in v else v) for p, v in scores_by_pose.items()}


def _region_fold_scores(scores_by_pose: dict, fid: str) -> dict:
    """{app_region: (per-fold region score array, {pose: fold-mean prob})}; region score = mean over the poses that score it."""
    acc = {}
    for pose, sc in _scores_only(scores_by_pose).items():
        for app, v in ((sc or {}).get(fid) or {}).items():
            acc.setdefault(app, {})[pose] = np.atleast_1d(np.asarray(v, float))
    out = {}
    for app, by in acc.items():
        out[app] = (np.mean(list(by.values()), 0), {p: float(np.mean(v)) for p, v in by.items()})
    return out


def person_score(scores_by_pose: dict, spec: dict) -> float | None:
    """Research person score: mean over folds of (max over regions of the region's mean over poses).
    scores_by_pose: {pose: {region: probs}} for this finding, or {pose: {finding_id: {region: probs}}}."""
    fid = spec['id']
    sbp = {p: (v if fid in (v or {}) else {fid: v}) for p, v in _scores_only(scores_by_pose).items()}
    reg = _region_fold_scores(sbp, fid)
    if not reg:
        return None
    return float(np.mean(np.max(np.stack([r for r, _ in reg.values()]), 0)))


def decide(scores_by_pose: dict, spec) -> list:
    """scores_by_pose: {'FRONT'|'LEFT'|'RIGHT': photo_result(...)} (or photo_scores(..., folds=True); fold-mean floats are
    accepted but then the person score is the max of the fold-mean, a close approximation for the 5-fold acne ensemble).
    spec: a spec dict, a list of spec dicts, or the model_dir. Returns one entry per finding and scored region:
    {id, region, status 'seen'|'notSeen', pose (pose with the highest probability for that region), probability,
    personScore, threshold} plus, for redness when photo_result values are given, areaPct / toneDiff measured from ONE
    photo per region (MEASURE_POSE: FRONT for forehead/nose/chin, LEFT for rightCheek, RIGHT for leftCheek; 'measurePose').
    Acne lesion counts are not produced here (skin_findings_v1 counts lesions).
    Person rule (research): seen <=> person_score >= threshold; then every region with region probability >= threshold
    is 'seen', or, if none reaches it, the highest-probability region."""
    if isinstance(spec, str):
        spec = list(specs(spec).values())
    elif isinstance(spec, dict):
        spec = [spec]
    out = []
    for sp in spec:
        fid = sp['id']; thr = float(sp['threshold'])
        reg = _region_fold_scores(scores_by_pose, fid)
        if not reg:
            continue
        ps = float(np.mean(np.max(np.stack([r for r, _ in reg.values()]), 0)))
        rp = {app: float(np.mean(r)) for app, (r, _) in reg.items()}
        seen = set()
        if ps >= thr:
            seen = {a for a, v in rp.items() if v >= thr} or {max(rp, key=rp.get)}
        for app in sorted(rp, key=lambda a: -rp[a]):
            byp = reg[app][1]
            e = dict(id=fid, region=app, status='seen' if app in seen else 'notSeen', pose=max(byp, key=byp.get),
                     probability=round(rp[app], 4), personScore=round(ps, 4), threshold=round(thr, 4))
            mp_ = MEASURE_POSE[app]; res = scores_by_pose.get(mp_)
            if isinstance(res, dict) and 'scores' in res:
                if fid == 'redness' and app in (res.get('redness') or {}):
                    e.update(res['redness'][app], measurePose=mp_)
            out.append(e)
    return out
