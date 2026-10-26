"""Dark circles by colour comparison after light correction (no learned embedding).
Under-eye band (below the lower lid) vs the person's own cheek skin, in the light-corrected image:
dL (darker), da (redder/purple), db (bluer = negative). Shading of the concave under-eye area is divided out by the
normal-based lighting model; residual darkness that changes chromaticity is pigment/vascular colour, not shadow."""
import json, sys, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/rf'); import light
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved' and int(p['id'][2:]) >= 181}
LID = {'L': [33, 7, 163, 144, 145, 153, 154, 155, 133], 'R': [263, 249, 390, 373, 374, 380, 381, 382, 362]}
CHK = {'L': 'cheek_imgL', 'R': 'cheek_imgR'}
out = {}
for kid, p in sorted(st.items()):
    img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png')
    r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: continue
    R = light.analyze(img, r.face_landmarks[0]); P2 = R['P'][:, :2]; H, W = R['skin'].shape
    fw = P2[:, 0].max() - P2[:, 0].min()
    raw = np.clip(R['lin'], 0, 1); corr = R['corr']
    feats = {}
    for name, im in (('corr', corr), ('raw', raw)):
        L, a, b = light.lab(im[..., ::-1])
        rm = light.region_masks(R); f = []
        for s in ('L', 'R'):
            lid = P2[LID[s]]; band = np.concatenate([lid + [0, 0.012 * fw], (lid + [0, 0.10 * fw])[::-1]])
            m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [band.astype(np.int32)], 1)
            ue = (m > 0) & (R['img'].max(-1) < 0.97) & (R['lin'].mean(-1) > 0.01)
            ck = rm[CHK[s]]
            if ue.sum() < 30 or ck.sum() < 30: continue
            # darkest 40% of the band (circles sit just under the lid)
            Lu = L[ue]; q = Lu <= np.percentile(Lu, 40)
            f.append([np.median(L[ck]) - np.median(Lu[q]), np.median(L[ck]), np.median(a[ue][q]) - np.median(a[ck]), np.median(b[ue][q]) - np.median(b[ck])])
        if f: feats[name] = np.array(f).mean(0).tolist()
    out[kid] = dict(y='göz altı morluğu' in p['extras'], bag='göz altı torbası' in p['extras'], tone=p['tone'], **feats)
json.dump(out, open(f'{S}/rf/darkcircle.json', 'w'), ensure_ascii=False)
ks = [k for k in out if 'corr' in out[k]]; y = np.array([out[k]['y'] for k in ks]); bag = np.array([out[k]['bag'] for k in ks])
print('kişi', len(ks), 'morluk', y.sum(), 'torba', bag.sum())
for nm in ('raw', 'corr'):
    X = np.array([out[k][nm] for k in ks])
    for j, fn in []:
        s = X[:, j] * (-1 if j == 2 else 1); print(f'{nm:4s} {fn:18s} AUC={roc_auc_score(y, s):.2f}  | torbayla karışma AUC={roc_auc_score(bag[~y], s[~y]):.2f}')
