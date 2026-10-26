"""Physical measurements for findings that have no severity index yet (age-independent characters, 3 poses).
All on the face rescaled to 500 px face width, after the normal-based lighting correction (light.py).
- bags: under-eye vertical luminance profile — bulge brightness minus the groove below it (raw and corrected), relative to cheek L
- crow's feet: valley (dark line) strength at the outer eye corner (Hessian largest eigenvalue), relative to the cheek's
- forehead lines: horizontal-valley strength (positive d2L/dy2) on the forehead, relative to the cheek's
- acne marks: pigment-mask fraction and blob count on cheeks + chin (light.tone_maps)
Per eye/side features are kept separately with the pose, so the front-vs-20° repeatability can be checked."""
import json, sys, os, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/rf'); import light
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved' and p.get('ageIndependent')}
OUT = f'{S}/rf/severity_feats.json'
out = json.load(open(OUT)) if os.path.exists(OUT) else {}
LID = {'L': [33, 7, 163, 144, 145, 153, 154, 155, 133], 'R': [263, 249, 390, 373, 374, 380, 381, 382, 362]}
CORNER = {'L': 33, 'R': 263}; INNER = {'L': 133, 'R': 362}
CHK = {'L': 'cheek_imgL', 'R': 'cheek_imgR'}
POSES = {'front': ('L', 'R'), 'side_1': ('L',), 'side_2': ('R',)}
def hessian(L, s):
    Lxx = cv2.GaussianBlur(cv2.Sobel(L, cv2.CV_32F, 2, 0, ksize=3), (0, 0), s)
    Lyy = cv2.GaussianBlur(cv2.Sobel(L, cv2.CV_32F, 0, 2, ksize=3), (0, 0), s)
    Lxy = cv2.GaussianBlur(cv2.Sobel(L, cv2.CV_32F, 1, 1, ksize=3), (0, 0), s)
    tr = Lxx + Lyy; d = np.sqrt(((Lxx - Lyy) / 2) ** 2 + Lxy ** 2)
    return np.maximum(tr / 2 + d, 0), np.maximum(Lyy, 0)          # valley strength (any direction), horizontal-valley strength
n = 0
for kid in sorted(st):
    for pose, eyes in POSES.items():
        key = f'{kid}|{pose}'
        if key in out and (pose != 'front' or 'fore_h_p90' in out[key]): continue
        img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{pose}.png')
        if img is None: continue
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        if not r.face_landmarks: continue
        try: R = light.analyze(img, r.face_landmarks[0], scale_to=500)
        except Exception: continue
        P2 = R['P'][:, :2]; fw = P2[:, 0].max() - P2[:, 0].min(); H, W = R['skin'].shape
        Lc, _, _ = light.lab(R['corr'][..., ::-1]); Lr, _, _ = light.lab(np.clip(R['lin'], 0, 1)[..., ::-1])
        ok = (R['img'].max(-1) < 0.97) & (R['lin'].mean(-1) > 0.01)
        rm = light.region_masks(R)
        anyv, horiz = hessian(Lc.astype(np.float32), 1.2)
        f = {}
        for s in eyes:
            ck = rm[CHK[s]]
            if ck.sum() < 50: continue
            ck_line = float(np.median(anyv[ck])) + 1e-3; ckL = float(np.median(Lc[ck]))
            # under-eye profile: columns over the central 60% of the eye
            lid = P2[LID[s]]; x0, x1 = sorted([P2[CORNER[s]][0], P2[INNER[s]][0]]); xm0, xm1 = x0 + 0.2 * (x1 - x0), x1 - 0.2 * (x1 - x0)
            ylid = float(np.max(lid[(lid[:, 0] >= x0) & (lid[:, 0] <= x1), 1]))
            ys = np.arange(int(ylid + 0.01 * fw), int(min(H - 1, ylid + 0.17 * fw)))
            xs = np.arange(int(xm0), int(xm1))
            if len(ys) > 10 and len(xs) > 5:
                cols = []
                for img_L, nm in ((Lr, 'raw'), (Lc, 'corr')):
                    prof = np.array([np.median(img_L[y, xs][ok[y, xs]]) if ok[y, xs].sum() > 3 else np.nan for y in ys])
                    k = len(prof); up = np.nanmax(prof[: int(k * 0.5)]); low = np.nanmin(prof[int(k * 0.35):])
                    f[f'bag_{nm}_{s}'] = float((up - low) / max(ckL, 1))
                    f[f'bag_{nm}_slope_{s}'] = float(np.nanmax(-np.diff(prof)) / max(ckL, 1) * 100)
            # crow's feet: lateral to the outer corner
            c = P2[CORNER[s]]; side = -1 if P2[CORNER[s]][0] < P2[INNER[s]][0] else 1
            m = np.zeros((H, W), np.uint8)
            cv2.ellipse(m, (int(c[0] + side * 0.06 * fw), int(c[1] + 0.01 * fw)), (int(0.05 * fw), int(0.07 * fw)), 0, 0, 360, 1, -1)
            m = (m > 0) & ok
            if m.sum() > 30: f[f'crow_{s}'] = float(np.mean(anyv[m]) / ck_line)
            # acne marks: pigment on this cheek
            tm = light.tone_maps(R)
            pm = tm['pigment'] & ck
            f[f'pig_frac_{s}'] = float(pm.sum() / max(ck.sum(), 1))
            nlab, _, stats, _ = cv2.connectedComponentsWithStats(pm.astype(np.uint8))
            f[f'pig_blobs_{s}'] = int(((stats[1:, cv2.CC_STAT_AREA] >= 4) & (stats[1:, cv2.CC_STAT_AREA] <= 400)).sum())
            f[f'ckline_{s}'] = ck_line
        if pose == 'front':
            fh = rm['forehead']
            cks = rm['cheek_imgL'] | rm['cheek_imgR']
            if fh.sum() > 50 and cks.sum() > 50:
                f['fore_h'] = float(np.mean(horiz[fh]) / (np.mean(horiz[cks]) + 1e-3)); f['fore_h_p90'] = float(np.percentile(horiz[fh], 90) / (np.percentile(horiz[cks], 90) + 1e-3))
                f['fore_any'] = float(np.mean(anyv[fh]) / (np.median(anyv[cks]) + 1e-3))
            chin = rm['chin']
            if chin.sum() > 50:
                tm = light.tone_maps(R); f['pig_frac_chin'] = float((tm['pigment'] & chin).sum() / chin.sum())
        out[key] = f; n += 1
        if n % 25 == 0: json.dump(out, open(OUT, 'w')); print('n', len(out), flush=True)
json.dump(out, open(OUT, 'w')); print('done', len(out))
