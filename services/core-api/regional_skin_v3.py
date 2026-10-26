"""Regional skin map v3 (oily / dry / normal / unmeasured + sensitive flag) for the result-photo paint.

Decision inputs per anatomical region (forehead, nose, rightCheek, leftCheek, chin):
  * model evidence (RF-DETR, run locally): skin-map Oily/Redness, findings (Yağlı/Kuru Cilt, Egzama,
    Rozasea, Sedef), acne lesions, regional oily detector;
  * appearance measured ONLY on bare skin: wrinkle lines (wrinkle segmentation) and beard/stubble strokes
    are removed first, so texture of a line or a hair is never read as dryness;
  * all appearance values are standardised within the person's skin-tone group (ITA angle), so shine and
    flake contrast are judged against people of similar tone.
Weights / thresholds come from params.json produced by the offline validation (thresholds chosen on the
fit split by F1, test reported once). The periorbital area is NOT decided here: it did not pass validation.
This module never writes clinical wording; it only returns per-region states for the paint and the type name.
"""
from __future__ import annotations
import json, math, os, threading
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get('ATTUNE_REGIONAL_V3_DIR', os.path.join(HERE, 'models', 'regional-skin-v3'))
VERSION = 'regional-skin-v3'

# MediaPipe FaceMesh indices (unmirrored accepted frame). Image-left cheek == subject's right cheek.
REG = {'forehead': [54,103,67,109,10,338,297,332,284,293,334,296,336,9,107,66,105,63],
       'nose': [168,193,245,188,174,236,198,209,49,48,64,98,97,2,326,327,294,278,279,429,420,456,399,412,465,417],
       'cheek_imgL': [116,117,118,119,100,142,203,206,216,212,214,192,213,147,123],
       'cheek_imgR': [345,346,347,348,329,371,423,426,436,432,434,416,433,376,352],
       'chin': [43,106,182,83,18,313,406,335,273,422,430,394,395,369,396,175,171,140,170,169,210,202]}
APP_ID = {'forehead': 'forehead', 'nose': 'nose', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek', 'chin': 'chin'}
FACE = list(REG)
TZONE = {'forehead', 'nose'}
CV_KEYS = ['c_shine', 'c_p99', 'c_tex', 'c_flake', 'c_matte', 'c_red']

def tone_group(ita: float) -> str:
    return 'light' if ita > 41 else ('medium' if ita > 10 else 'dark')

def region_polys(P: np.ndarray) -> dict:
    return {k: P[v] for k, v in REG.items()}

def ita_angle(rgb: np.ndarray, polys: dict) -> float:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    m = np.zeros(rgb.shape[:2], np.uint8)
    for k in ('forehead', 'cheek_imgL', 'cheek_imgR'):
        cv2.fillPoly(m, [polys[k].astype(np.int32)], 1)
    if m.sum() < 100:
        return 40.0
    L = lab[..., 0][m > 0] * 100 / 255; b = lab[..., 2][m > 0] - 128
    return math.degrees(math.atan2(float(np.median(L)) - 50, max(float(np.median(b)), 1e-3)))

def hair_mask(bgr: np.ndarray, polys: dict, face_w: float) -> np.ndarray:
    """Beard/stubble only: dense dark strokes below the nose base, contrast relative to own skin."""
    L = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    k = max(5, int(face_w / 45) | 1)
    bh = cv2.morphologyEx(L, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    face = np.zeros(L.shape, np.uint8)
    for r in FACE:
        cv2.fillPoly(face, [polys[r].astype(np.int32)], 1)
    upper = np.zeros(L.shape, np.uint8); cv2.fillPoly(upper, [polys['forehead'].astype(np.int32)], 1)
    ref = bh[upper > 0] if upper.sum() > 50 else bh[face > 0]
    Lm = float(np.median(L[face > 0])) if face.any() else 128.0
    t = max(float(np.percentile(ref, 97)) if ref.size else 8.0, 0.10 * Lm, 8.0)
    m = ((bh > t) & (L < Lm * 0.92)).astype(np.uint8)
    ybase = float(polys['nose'][:, 1].max()) - 0.02 * face_w
    m[:int(max(0, ybase)), :] = 0
    dens = cv2.blur(m.astype(np.float32), (k * 3 + 1, k * 3 + 1))
    return ((m > 0) & (dens > 0.12) & (face > 0)).astype(np.uint8)

def model_evidence(dets: dict, cats: dict, polys: dict, shape, sc: float) -> dict:
    """Per region: max confidence of overlapping boxes, coverage at 0.2/0.3/0.45, count of centred boxes >= .35.
    dets[model] = [(class_id, score, [x0,y0,x1,y1]) in source pixels]; cats[model] = {class_id: name}."""
    H, W = shape
    out = {}
    masks = {}
    for k, poly in polys.items():
        m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [(poly * sc).astype(np.int32)], 1); masks[k] = m > 0
    for k, m in masks.items():
        f = {}
        for mn, cmap in cats.items():
            for cname in set(cmap.values()):
                cov = np.zeros((H, W), np.float32); cnt = 0
                for c, s, (x0, y0, x1, y1) in dets.get(mn, []):
                    if cmap.get(c) != cname:
                        continue
                    X0, Y0, X1, Y1 = [int(round(v * sc)) for v in (x0, y0, x1, y1)]
                    if (x1 - x0) * (y1 - y0) > 0.8 * (W / sc) * (H / sc):
                        continue  # full-frame artefact
                    sub = cov[max(0, Y0):Y1, max(0, X0):X1]; np.maximum(sub, s, out=sub)
                    cx, cy = int((X0 + X1) / 2), int((Y0 + Y1) / 2)
                    if 0 <= cy < H and 0 <= cx < W and m[cy, cx] and s >= 0.35:
                        cnt += 1
                v = cov[m]; key = f'{mn}_{cname}'.replace(' ', '_')
                f[key + '_max'] = float(v.max()) if v.size else 0.0
                for t in (0.2, 0.3, 0.45):
                    f[f'{key}_cov{int(t * 100)}'] = float((v >= t).mean()) if v.size else 0.0
                f[key + '_n35'] = cnt
        out[k] = f
    return out

def bare_skin_features(rgb: np.ndarray, polys: dict, face_w: float, wrinkle: np.ndarray, beard: np.ndarray) -> tuple[dict, float]:
    """Appearance on bare skin only, relative to the person's own bare-skin statistics (scale: face width 400 px)."""
    sc = 400 / max(face_w, 1); h, w = rgb.shape[:2]; size = (max(1, round(w * sc)), max(1, round(h * sc)))
    im = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC)
    wr = cv2.dilate(cv2.resize(wrinkle.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST), np.ones((5, 5), np.uint8)) > 0
    br = cv2.dilate(cv2.resize(beard.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST), np.ones((5, 5), np.uint8)) > 0
    lab = cv2.cvtColor(im, cv2.COLOR_RGB2LAB).astype(np.float32); L = lab[..., 0] * 100 / 255; A = lab[..., 1] - 128; B = lab[..., 2] - 128; C = np.hypot(A, B)
    hp = L - cv2.GaussianBlur(L, (0, 0), 3); th = cv2.morphologyEx(L, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    masks = {}
    for k, poly in polys.items():
        m = np.zeros(L.shape, np.uint8); cv2.fillPoly(m, [(poly * sc).astype(np.int32)], 1); masks[k] = m > 0
    face = np.zeros(L.shape, bool)
    for k in FACE:
        face |= masks[k]
    clean_face = face & ~wr & ~br; ref = clean_face if clean_face.sum() > 300 else face
    Lm, Ls = float(np.median(L[ref])), float(np.std(L[ref])) + 1e-6
    Am, Cm, hps = float(np.median(A[ref])), float(np.median(C[ref])), float(np.std(hp[ref])) + 1e-6
    out = {}
    for k, m in masks.items():
        if m.sum() < 150:
            out[k] = None; continue
        cl = m & ~wr & ~br; f = {'frac_clean': float(cl.sum() / m.sum()), 'frac_beard': float((m & br).sum() / m.sum()), 'frac_wrinkle': float((m & wr).sum() / m.sum())}
        # legacy whole-region CV (kept for parity with the validated feature set)
        l0 = L[m]; spec0 = (l0 > Lm + 1.6 * Ls) & (C[m] < Cm)
        f.update(cv_shine=float(spec0.mean()), cv_p99=float((np.percentile(l0, 99) - Lm) / Ls), cv_red=float(A[m].mean() - Am))
        if cl.sum() >= 80:
            l = L[cl]
            f['c_shine'] = float(((l > Lm + 1.6 * Ls) & (C[cl] < Cm)).mean())
            f['c_p99'] = float((np.percentile(l, 99) - Lm) / Ls)
            f['c_tex'] = float(np.std(hp[cl]) / hps)
            f['c_flake'] = float(((th[cl] > max(4.0, 0.08 * Lm)) & (C[cl] < Cm)).mean())
            f['c_red'] = float(A[cl].mean() - Am)
            f['c_matte'] = float(1.0 - min(1.0, (np.percentile(l, 95) - np.median(l)) / max(Ls, 1e-6) / 3))
        else:
            for kk in CV_KEYS:
                f[kk] = None
        out[k] = f
    return out, Lm

class Decider:
    """Applies the validated tone-aware logistic models (params.json)."""
    def __init__(self, params: dict):
        self.p = params
    def _z(self, f, k, tone):
        v = f.get(k)
        if v is None:
            return 0.0
        m, s = self.p['stats'][tone][k]
        return float(np.clip((v - m) / s, -4, 6))
    def vector(self, task, f, region, tone):
        b = lambda k: 0.0 if f.get(k) is None else float(f[k])
        acne = sum(b(f'acnes_{c}_n35') for c in ('papule', 'pustule', 'nodule', 'blackhead', 'whitehead'))
        z = lambda k: self._z(f, k, tone); cw = b('frac_clean')
        if task == 'oily':
            return [b('skinmap_Oily_max'), b('regional_oily_max'), b('findings_Yagli_Cilt_max'), z('c_shine'), z('c_p99'), min(acne, 4) / 4 * min(1, max(0, z('c_shine') + 1))]
        if task == 'dry':
            ecz = b('findings_Egzema_max') * (0.5 if region in TZONE else 1.0)
            return [b('findings_Kuru_Cilt_max'), ecz, z('c_flake') * cw, z('c_tex') * cw, z('c_matte') * cw, -z('c_shine')]
        infl = b('acnes_papule_n35') + b('acnes_pustule_n35') + b('acnes_nodule_n35')
        return [b('skinmap_Redness_max'), b('findings_Rozasea_max'), b('findings_Egzema_max'), b('findings_Sedef_ve_Dokuntu_max'), z('c_red'), min(infl, 4) / 4]
    def prob(self, task, x):
        m = self.p['models'][task]; s = float(np.dot(m['coef'], x) + m['intercept']); return 1 / (1 + math.exp(-s))
    def region(self, f, region, tone):
        if f is None:
            return dict(state='unmeasured', sensitive=False, reason='INSUFFICIENT_VISIBLE_AREA')
        po = self.prob('oily', self.vector('oily', f, region, tone)); pd = self.prob('dry', self.vector('dry', f, region, tone)); ps = self.prob('sens', self.vector('sens', f, region, tone))
        T = self.p['thresholds']
        bare_ok = (f.get('frac_clean') or 0) >= self.p.get('minCleanFraction', 0.3)
        if po >= T['oily'][tone]:
            state, reason = 'oily', None
        elif not bare_ok:
            state, reason = 'unmeasured', 'BEARD_OR_LINES_COVER_REGION'   # too little bare skin to call dry/normal
        elif pd >= T['dry'][tone]:
            state, reason = 'dry', None
        else:
            state, reason = 'normal', None
        sensitive = ps >= T['sens'][tone]
        # Dark skin (ITA < 10): redness is less visible, so the fused model under-calls sensitivity
        # (SCIN smartphone photos, Fitzpatrick V-VI: recall 0.32 at the shared threshold). A direct
        # evidence rule at a lower bar raises recall to 0.47 with ~9% false alarms on dark-skin negatives.
        dark_thr = self.p.get('sensDarkEvidenceThreshold')
        if tone == 'dark' and dark_thr is not None:
            ev = max(float(f.get(k) or 0) for k in ('skinmap_Redness_max', 'findings_Rozasea_max', 'findings_Egzema_max', 'findings_Sedef_ve_Dokuntu_max'))
            sensitive = sensitive or ev >= dark_thr
        return dict(state=state, sensitive=bool(sensitive), reason=reason, scores=dict(oily=round(po, 3), dry=round(pd, 3), sensitive=round(ps, 3)))

def skin_type_from_regions(regions: dict) -> dict:
    """Naming rule (product owner): oily somewhere (esp. T-zone) + dry/normal elsewhere -> combination; all oily -> oily;
    no oily and any dry -> dry (dry+normal mix is dry); all normal -> normal; + sensitive flag if any region is sensitive."""
    states = [r['state'] for r in regions.values() if r['state'] != 'unmeasured']
    sensitive = any(r.get('sensitive') for r in regions.values() if r['state'] != 'unmeasured')
    if len(states) < 3 or not any(regions.get(k, {}).get('state') not in (None, 'unmeasured') for k in ('forehead', 'nose')):
        return dict(value=None, quality='insufficient', sensitive=False, limitationCode='REGIONAL_V3_INSUFFICIENT_REGIONS')
    if 'oily' in states and any(s in ('dry', 'normal') for s in states):
        v = 'combination'
    elif all(s == 'oily' for s in states):
        v = 'oily'
    elif 'dry' in states:
        v = 'dry'
    else:
        v = 'normal'
    return dict(value=v, quality='valid', sensitive=sensitive, limitationCode=None)

LESION_FINDINGS = {'Akne', 'Siyah Nokta', 'Beyaz Nokta', 'Gunes Lekesi', 'Riskli Ben', 'Ucuk'}

def lesion_mask(dets: dict, cats: dict, shape) -> np.ndarray:
    """Acne lesions, comedones, spots and moles are not flakes: their boxes are removed from bare skin (as in validation)."""
    H, W = shape; m = np.zeros((H, W), np.uint8)
    for mn in ('acnes', 'findings'):
        for c, s, (x0, y0, x1, y1) in dets.get(mn, []):
            if s < 0.35 or (x1 - x0) * (y1 - y0) > 0.25 * W * H:
                continue
            if mn == 'findings' and cats.get(mn, {}).get(c) not in LESION_FINDINGS:
                continue
            m[max(0, int(y0)):int(y1) + 1, max(0, int(x0)):int(x1) + 1] = 1
    return m

VIEW_OF_POSE = {'FRONT': 'front', 'LEFT': 'pos', 'RIGHT': 'neg'}   # LEFT pose shows the subject's right cheek
K_REGIONS = ['forehead', 'nose', 'chin', 'rightCheek', 'leftCheek']

def usable(app_region: str, view: str) -> bool:
    """A cheek is read only from the front or from the side pose that shows it (same rule as training)."""
    return not ((app_region == 'rightCheek' and view == 'neg') or (app_region == 'leftCheek' and view == 'pos'))

class KClassifier:
    """In-domain regional classifier (k_classifier.json): DINOv2-small region embedding + evidence/appearance scalars.
    Paints a colour only above its validated threshold; otherwise the region stays 'unmeasured' (Ölçüm notu)."""
    def __init__(self, spec: dict, dino_dir: str):
        import torch
        from transformers import AutoImageProcessor, AutoModel
        self.spec = spec; self.torch = torch
        src = dino_dir if os.path.isdir(dino_dir) else 'facebook/dinov2-small'
        self.proc = AutoImageProcessor.from_pretrained(src, local_files_only=True)
        self.dm = AutoModel.from_pretrained(src, local_files_only=True).eval()
    def embed(self, crops: list) -> np.ndarray:
        from PIL import Image
        with self.torch.no_grad():
            o = self.dm(**self.proc(images=[Image.fromarray(c) for c in crops], return_tensors='pt')).last_hidden_state
            return self.torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy()
    def _lin(self, block, x):
        z = (x - np.asarray(block['mean'])) / np.asarray(block['scale'])
        return np.asarray(block['coef']) @ z + np.asarray(block['intercept'])
    def probs(self, emb: np.ndarray, f: dict, app_region: str) -> tuple[dict, float]:
        sc = np.array([float(f.get(k)) if f.get(k) is not None else 0.0 for k in self.spec['features']['scalars']])
        x = np.concatenate([emb, sc, np.eye(5)[K_REGIONS.index(app_region)]])
        s = self._lin(self.spec['type'], x); e = np.exp(s - s.max()); p = e / e.sum()
        ps = 1 / (1 + math.exp(-float(self._lin(self.spec['sensitive'], x))))
        return {c: float(v) for c, v in zip(self.spec['classes'], p)}, ps

def region_crops(rgb: np.ndarray, polys: dict, face_w: float) -> dict:
    """Masked bbox crop of each region on the 400-px-face image, 224x224 (validation recipe)."""
    sc = 400 / max(face_w, 1); h, w = rgb.shape[:2]; size = (max(1, round(w * sc)), max(1, round(h * sc)))
    im = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC); out = {}
    for k, poly in polys.items():
        m = np.zeros(im.shape[:2], np.uint8); cv2.fillPoly(m, [(poly * sc).astype(np.int32)], 1); m = m > 0
        if m.sum() < 150:
            continue
        ys, xs = np.where(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        cr = im[y0:y1, x0:x1].copy(); cr[~m[y0:y1, x0:x1]] = 0
        out[k] = cv2.resize(cr, (224, 224), interpolation=cv2.INTER_AREA)
    return out

def with_cover(causes: list, decision: dict) -> list:
    """Beard/lines covering the region is its own cause. If nothing measurable explains the result, both capture causes
    are offered as the possible ones (the dialog wording says 'possible reason(s)')."""
    c = list(dict.fromkeys(causes + (['COVER'] if decision.get('reason') == 'BEARD_OR_LINES_COVER_REGION' else [])))
    return c or ['LIGHTING', 'ANGLE']

def capture_causes(rgb: np.ndarray, polys: dict, P: np.ndarray, pose: str) -> dict:
    """Per region, which capture problems are actually measurable in this photo (shown to the user only for regions
    that end up inconclusive):
      LIGHTING - region much darker/brighter than the face, clipped highlights, or a strong left/right light imbalance;
      ANGLE    - the head is turned for a front photo, or the region is clearly foreshortened against its counterpart."""
    L = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32) * 100 / 255
    masks = {}
    for k, poly in polys.items():
        m = np.zeros(L.shape, np.uint8); cv2.fillPoly(m, [poly.astype(np.int32)], 1); masks[k] = m > 0
    face = np.zeros(L.shape, bool)
    for k in FACE:
        face |= masks[k]
    if face.sum() < 500:
        return {APP_ID[k]: ['ANGLE'] for k in FACE}
    fm = float(np.median(L[face]))
    eye_mid = (P[133] + P[362]) / 2; inner = float(np.linalg.norm(P[133] - P[362])) or 1.0
    turn = float((P[1][0] - eye_mid[0]) / (0.8 * inner))          # ~0 when facing the camera
    area = {k: float(masks[k].sum()) for k in FACE}
    lr = abs(float(np.median(L[masks['cheek_imgL']])) - float(np.median(L[masks['cheek_imgR']]))) if masks['cheek_imgL'].any() and masks['cheek_imgR'].any() else 0.0
    out = {}
    for k in FACE:
        c = []; m = masks[k]
        if m.sum() >= 150:
            l = L[m]; d = float(np.median(l)) - fm
            if abs(d) > 15 or float((l > 96).mean()) > 0.03 or (pose == 'FRONT' and lr > 14 and k.startswith('cheek')):
                c.append('LIGHTING')
        if pose == 'FRONT' and abs(turn) > 0.25:
            c.append('ANGLE')
        elif k.startswith('cheek'):
            other = 'cheek_imgR' if k == 'cheek_imgL' else 'cheek_imgL'
            if pose == 'FRONT' and area[k] < 0.6 * max(area[other], 1):
                c.append('ANGLE')
        if m.sum() < 150 and 'ANGLE' not in c:
            c.append('ANGLE')
        out[APP_ID[k]] = c
    return out

def decide_from_probs(probs: dict, ps: float, f: dict, tone: str, thr: dict, params: dict, view_count: int = 1) -> dict:
    best = max(probs, key=probs.get)
    bare_ok = (f.get('frac_clean') or 0) >= params.get('minCleanFraction', 0.3)
    if probs[best] >= thr[best] and (best == 'oily' or bare_ok):
        state, reason = best, None
    else:
        state, reason = 'unmeasured', ('BEARD_OR_LINES_COVER_REGION' if not bare_ok and best != 'oily' else 'LOW_CONFIDENCE')
    sensitive = ps >= thr['sensitive']
    dark_thr = params.get('sensDarkEvidenceThreshold')
    if tone == 'dark' and dark_thr is not None:
        ev = max(float(f.get(k) or 0) for k in ('skinmap_Redness_max', 'findings_Rozasea_max', 'findings_Egzema_max', 'findings_Sedef_ve_Dokuntu_max'))
        sensitive = sensitive or ev >= dark_thr
    return dict(state=state, sensitive=bool(sensitive) and state != 'unmeasured', reason=reason,
                scores={**{k: round(v, 3) for k, v in probs.items()}, 'sensitive': round(ps, 3)}, views=view_count)

_lock = threading.Lock(); _runtime = None

def load_runtime():
    """Lazily loads params + RF-DETR models (torch). Raises FileNotFoundError when the bundle is absent."""
    global _runtime
    with _lock:
        if _runtime is None:
            params = json.load(open(os.path.join(MODEL_DIR, 'params.json')))
            import rfdetr
            models = {name: (getattr(rfdetr, spec['arch'])(pretrain_weights=os.path.join(MODEL_DIR, spec['weights'])), spec) for name, spec in params['detectors'].items()}
            kpath = os.path.join(MODEL_DIR, 'k_classifier.json')
            kc = KClassifier(json.load(open(kpath)), os.environ.get('ATTUNE_DINOV2_DIR', os.path.join(MODEL_DIR, 'dinov2-small'))) if os.path.exists(kpath) else None
            _runtime = dict(params=params, models=models, decider=Decider(params), k=kc)
        return _runtime

def analyze_photo(bgr: np.ndarray, landmarks_norm: list, check=lambda: None, pose: str = 'FRONT') -> dict:
    """bgr: source photo; landmarks_norm: 468/478 MediaPipe points normalised to the source frame."""
    from PIL import Image
    rt = load_runtime(); params = rt['params']
    h, w = bgr.shape[:2]; P = np.array([[p['x'] * w, p['y'] * h] for p in landmarks_norm[:468]], np.float64)
    # same square face crop (1.35x, 1024 px) as the validation set
    x0, y0 = P.min(0); x1, y1 = P.max(0); bw, bh = x1 - x0, y1 - y0; s = max(bw, bh) * 1.35
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 0.08 * bh; X0, Y0, S = int(round(cx - s / 2)), int(round(cy - s / 2)), int(round(s))
    pad = cv2.copyMakeBorder(bgr, S, S, S, S, cv2.BORDER_REPLICATE); crop = pad[Y0 + S:Y0 + 2 * S, X0 + S:X0 + 2 * S]
    k = 1024 / S; crop = cv2.resize(crop, (1024, 1024), interpolation=cv2.INTER_AREA); Pc = (P - [X0, Y0]) * k
    polys = region_polys(Pc); face_w = float(Pc[:, 0].max() - Pc[:, 0].min()); rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb); dets = {}; wrinkle = np.zeros((1024, 1024), np.uint8)
    for name, (model, spec) in rt['models'].items():
        check()
        if spec.get('role') == 'wrinkle-mask':
            d = model.predict(pil, threshold=spec['threshold'])
            if d.mask is not None:
                for mm in d.mask:
                    wrinkle |= mm.astype(np.uint8)
            continue
        d = model.predict(pil, threshold=0.05)
        dets[name] = [(int(c), float(sc), [float(v) for v in b]) for b, sc, c in zip(d.xyxy.tolist(), d.confidence, d.class_id)]
    check()
    cats = {n: {int(k): v for k, v in spec['classes'].items()} for n, (m, spec) in rt['models'].items() if spec.get('role') != 'wrinkle-mask'}
    sc = 400 / max(face_w, 1)
    ev = model_evidence(dets, cats, polys, (max(1, round(1024 * sc)), max(1, round(1024 * sc))), sc)
    beard = hair_mask(crop, polys, face_w) | lesion_mask(dets, cats, (1024, 1024))
    bare, _ = bare_skin_features(rgb, polys, face_w, wrinkle, beard)
    ita = ita_angle(rgb, polys); tone = tone_group(ita)
    view = VIEW_OF_POSE.get(pose, 'front'); regions = {}; raw = {}
    causes = capture_causes(rgb, polys, Pc, pose)
    kc = rt.get('k')
    if kc is not None:
        check(); crops = region_crops(rgb, polys, face_w); keys = [rk for rk in FACE if rk in crops and bare.get(rk) is not None]
        emb = dict(zip(keys, kc.embed([crops[k] for k in keys]))) if keys else {}
    for rk in FACE:
        app = APP_ID[rk]; f = None if bare.get(rk) is None else {**ev[rk], **bare[rk], 'ita': ita}
        if kc is None:
            regions[app] = rt['decider'].region(f, rk, tone); continue
        if f is None or rk not in emb or not usable(app, view):
            regions[app] = dict(state='unmeasured', sensitive=False, reason='INSUFFICIENT_VISIBLE_AREA' if f is None else 'NOT_VISIBLE_IN_THIS_POSE', causes=['ANGLE']); continue
        probs, ps = kc.probs(emb[rk], f, app)
        raw[app] = dict(probs=probs, sensitive=ps, frac_clean=f.get('frac_clean'), causes=causes.get(app, []), evidence={k: f.get(k) for k in ('skinmap_Redness_max', 'findings_Rozasea_max', 'findings_Egzema_max', 'findings_Sedef_ve_Dokuntu_max')})
        d = decide_from_probs(probs, ps, f, tone, kc.spec['thresholds']['single'], params)
        regions[app] = {**d, 'sourcePose': pose, **({'causes': with_cover(causes.get(app, []), d)} if d['state'] == 'unmeasured' else {})}
    # Detector evidence for the findings layer (skin_findings_v1): same per-region values the research features used,
    # whether the region is large enough to be read (>= 150 px at the 400 px face scale, as in validation) and visible in
    # this pose, plus the boxes of box-type findings mapped back to source pixels of THIS photo.
    import skin_findings_v1 as SF
    ev_all = {rk: {**ev.get(rk, {}), **(bare.get(rk) or {})} for rk in ev}
    finding_evidence, finding_boxes = SF.evidence_from_detections(ev_all, dets, cats, polys, sc, view, pose, inv=lambda x, y: ((x / k) + X0, (y / k) + Y0), src_scale=1 / k, Pc=Pc)
    # Saved DINOv2-crop finding classifiers (skin_findings_dino): probability per landmark crop of this photo
    import skin_findings_dino as SD
    finding_scores, severity_terms = SD.photo_outputs(bgr, landmarks_norm, view, kc, MODEL_DIR, check)
    # Saved eye-area classifiers (skin_findings_eye; front photo only): probability per finding + geometry value
    import skin_findings_eye as SEYE
    check(); eye_scores = SEYE.photo_scores(bgr, landmarks_norm, view, kc, MODEL_DIR) if kc is not None else {}
    eye_measures = {}
    if eye_scores.get('downturnedCorners') is not None:
        v = SEYE.downturned_percentile(bgr, landmarks_norm, MODEL_DIR, view)
        if v is not None:
            eye_measures['downturnedCorners'] = round(float(v), 1)
    return dict(version=VERSION, paramsVersion=params.get('version'), classifierVersion=(kc.spec['version'] if kc else None), pose=pose,
                tone=dict(ita=round(ita, 1), group=tone), regions=regions, raw=raw, skinType=skin_type_from_regions(regions),
                findingEvidence=finding_evidence, findingBoxes=finding_boxes, findingScores=finding_scores, severityTerms=severity_terms, eyeScores={k: round(float(v), 5) for k, v in eye_scores.items()}, eyeMeasures=eye_measures, models=model_manifest())

def model_manifest() -> dict:
    """File names + SHA-256 of the loaded bundle (cached), so every result names the exact weights that produced it."""
    global _manifest
    if _manifest is None:
        import hashlib
        out = {}
        for name in ('params.json', 'k_classifier.json', 'skinmap.pt', 'findings.pt', 'acnes.pt', 'regional.pt', 'wrinkles.pt'):
            path = os.path.join(MODEL_DIR, name)
            if os.path.exists(path):
                h = hashlib.sha256()
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(1 << 20), b''):
                        h.update(chunk)
                out[name] = h.hexdigest()
        import skin_findings_dino as SD, skin_findings_eye as SEYE
        out.update(SD.manifest(MODEL_DIR)); out.update(SEYE.manifest(MODEL_DIR))
        _manifest = out
    return _manifest

_manifest = None

def fuse_maps(maps: dict) -> dict | None:
    """maps: {'FRONT': map, 'LEFT': map, 'RIGHT': map} from analyze_photo. Averages the classifier probabilities of each
    region over the poses that show it and applies the validated 3-angle thresholds."""
    rt = load_runtime(); kc = rt.get('k'); params = rt['params']
    front = maps.get('FRONT')
    if kc is None or not front:
        return front
    tone = front['tone']['group']; thr = kc.spec['thresholds']['multi']; regions = {}
    for app in K_REGIONS:
        src = [(pose, m['raw'][app]) for pose, m in maps.items() if m and app in (m.get('raw') or {})]
        if not src:
            regions[app] = front['regions'].get(app) or dict(state='unmeasured', sensitive=False, reason='INSUFFICIENT_VISIBLE_AREA'); continue
        probs = {c: float(np.mean([r['probs'][c] for _, r in src])) for c in kc.spec['classes']}
        ps = float(np.mean([r['sensitive'] for _, r in src]))
        f = {'frac_clean': max(r['frac_clean'] or 0 for _, r in src), **{k: max(float(r['evidence'].get(k) or 0) for _, r in src) for k in src[0][1]['evidence']}}
        side = [p for p, _ in src if p != 'FRONT']
        d = decide_from_probs(probs, ps, f, tone, thr, params, len(src))
        cz = sorted({c for _, r in src for c in (r.get('causes') or [])})
        regions[app] = {**d, 'sourcePose': side[0] if app in ('rightCheek', 'leftCheek') and side else 'FRONT', **({'causes': with_cover(cz, d)} if d['state'] == 'unmeasured' else {})}
    return dict(version=VERSION, paramsVersion=params.get('version'), classifierVersion=kc.spec['version'], pose='THREE_ANGLE',
                tone=front['tone'], regions=regions, skinType=skin_type_from_regions(regions), models=model_manifest())
