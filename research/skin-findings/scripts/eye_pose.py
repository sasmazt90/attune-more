"""Göz altı morluğu / sarkma: kapak / sarkma: göz dış köşe on the 140 age-independent characters, per capture set.
Rows = (person, pose, eye). Front gives both eyes; a 20° side pose gives only the eye facing the camera.
Features per row: light-corrected colour comparison (under-eye vs same-side cheek), eye geometry (roll-normalised),
DINOv2 crop embedding (PCA inside the model), pose one-hot. Person score = mean of row probabilities over the poses
in the capture set. Same nested fair protocol as eye_fair.py (threshold chosen on training persons only)."""
import json, os, sys, numpy as np, cv2, torch, mediapipe as mp
from PIL import Image
from mediapipe.tasks.python import vision, BaseOptions
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/rf'); import light
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved' and int(p['id'][2:]) >= 181}
_src = open(f'{S}/rf/finding_clf.py').read(); exec('CROPS = {' + _src.split('CROPS = {', 1)[1].split('NEW = ')[0])
LID = {'L': [33, 7, 163, 144, 145, 153, 154, 155, 133], 'R': [263, 249, 390, 373, 374, 380, 381, 382, 362]}
E = {'L': dict(inner=133, outer=33, up=159, lo=145, brow=105, crease=27), 'R': dict(inner=362, outer=263, up=386, lo=374, brow=334, crease=257)}
CHK = {'L': 'cheek_imgL', 'R': 'cheek_imgR'}
POSES = {'front': ('L', 'R'), 'side_1': ('L',), 'side_2': ('R',)}   # side_1 (yaw>0) shows the image-left eye
CACHE = f'{S}/rf/eye_pose_rows.npz'
if os.path.exists(CACHE):
    rows = list(np.load(CACHE, allow_pickle=True)['rows'])
else:
    from transformers import AutoImageProcessor, AutoModel
    torch.set_num_threads(4)
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
    proc = AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm = AutoModel.from_pretrained('facebook/dinov2-small').eval()
    rows = []
    for kid in sorted(st):
        for pose, eyes in POSES.items():
            img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{pose}.png')
            r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            if not r.face_landmarks: continue
            h, w = img.shape[:2]; P = np.array([[q.x * w, q.y * h] for q in r.face_landmarks[0]]); fw = P[:, 0].max() - P[:, 0].min()
            R = light.analyze(img, r.face_landmarks[0]); P2 = R['P'][:, :2]; Hh, Ww = R['skin'].shape; fws = P2[:, 0].max() - P2[:, 0].min()
            L_, a_, b_ = light.lab(R['corr'][..., ::-1]); rm = light.region_masks(R)
            c = (P[33] + P[263]) / 2; v = P[263] - P[33]; ang = np.arctan2(v[1], v[0])
            Rot = np.array([[np.cos(-ang), -np.sin(-ang)], [np.sin(-ang), np.cos(-ang)]]); Q = (P - c) @ Rot.T
            for s in eyes:
                # colour
                lid = P2[LID[s]]; band = np.concatenate([lid + [0, 0.012 * fws], (lid + [0, 0.10 * fws])[::-1]])
                m = np.zeros((Hh, Ww), np.uint8); cv2.fillPoly(m, [band.astype(np.int32)], 1)
                ue = (m > 0) & (R['img'].max(-1) < 0.97) & (R['lin'].mean(-1) > 0.01); ck = rm[CHK[s]]
                if ue.sum() < 30 or ck.sum() < 30: continue
                Lu = L_[ue]; q = Lu <= np.percentile(Lu, 40); Lc = np.median(L_[ck]); dL = Lc - np.median(Lu[q])
                col = [np.log(Lc / max(Lc - dL, 1e-3)), np.median(a_[ue][q]) - np.median(a_[ck]), np.median(b_[ue][q]) - np.median(b_[ck])]
                # geometry (per eye)
                e = E[s]; ew = abs(Q[e['outer'], 0] - Q[e['inner'], 0])
                geo = [(Q[e['inner'], 1] - Q[e['outer'], 1]) / ew, (Q[e['lo'], 1] - Q[e['up'], 1]) / ew,
                       (Q[e['up'], 1] - Q[e['brow'], 1]) / ew, (Q[e['up'], 1] - Q[e['crease'], 1]) / ew]
                # DINOv2 crops
                ims = []
                for nm in (f'under_{s}', f'lid_{s}', f'corner_{s}'):
                    idx, pad, _ = CROPS[nm]; x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
                    ims.append(Image.fromarray(cv2.cvtColor(cv2.resize(img[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)], (224, 224)), cv2.COLOR_BGR2RGB)))
                with torch.no_grad():
                    o = dm(**proc(images=ims, return_tensors='pt')).last_hidden_state
                em = torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy()
                rows.append(dict(kid=kid, pose=pose, eye=s, col=np.array(col), geo=np.array(geo), under=em[0], lid=em[1], corner=em[2]))
        print(kid, len(rows), file=sys.stderr, flush=True)
    np.savez(CACHE, rows=np.array(rows, dtype=object))
kid = np.array([r['kid'] for r in rows]); pose = np.array([r['pose'] for r in rows])
POH = lambda p: [p == 'front', p != 'front']
TASKS = {
    'Göz altı morluğu': ('göz altı morluğu', 'Renk kıyası', lambda r: np.concatenate([r['col'], POH(r['pose'])])),
    'Sarkma: kapak': ('sarkma: göz', 'Geometri + DINOv2', lambda r: np.concatenate([r['geo'], POH(r['pose']), r['lid']])),
    'Sarkma: göz dış köşe': ('sarkma: göz dış köşe', 'Geometri + DINOv2', lambda r: np.concatenate([r['geo'], POH(r['pose']), r['corner']])),
}
CONF = {'Ön': ('front',), 'Ön + 20°': ('front', 'side_1', 'side_2')}
def model(dim):
    steps = [StandardScaler()] + ([PCA(n_components=20, random_state=0)] if dim > 50 else [])
    return make_pipeline(*steps, LogisticRegression(C=0.1 if dim > 50 else 1.0, max_iter=4000, class_weight='balanced'))
def thr_p80(y, s):
    ts = np.sort(np.unique(s))
    for t in ts:
        if (s >= t).sum() >= 3 and all(y[s >= u].mean() >= .8 for u in ts[ts >= t] if (s >= u).sum() >= 3): return t
    return None
def person_scores(m, X, ix, persons, srcs):
    p = m.predict_proba(X[ix])[:, 1]; out = []
    for k in persons:
        sel = (kid[ix] == k) & np.isin(pose[ix], srcs); out.append(p[sel].mean() if sel.any() else np.nan)
    return np.array(out)
REP = 10
print('| Bulgu | Yöntem | Kurgu | Confidence Threshold (ort.) | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Kişi |')
for task, (lab, mname, fx) in TASKS.items():
    X = np.array([fx(r) for r in rows], float); persons = np.array(sorted(set(kid))); yp = np.array([lab in st[k]['extras'] for k in persons])
    for cname, srcs in CONF.items():
        tot = np.zeros(3); aucs = []; thrs = []; none = 0
        for rep in range(REP):
            sc = np.full(len(persons), np.nan)
            for a, b in StratifiedKFold(5, shuffle=True, random_state=rep).split(persons, yp):
                pa = persons[a]; inner = np.full(len(pa), np.nan)
                for ia, ib in StratifiedKFold(5, shuffle=True, random_state=100 + rep).split(pa, yp[a]):
                    ixa = np.where(np.isin(kid, pa[ia]))[0]; ixb = np.where(np.isin(kid, pa[ib]))[0]
                    yr = np.array([lab in st[k]['extras'] for k in kid[ixa]])
                    inner[ib] = person_scores(model(X.shape[1]).fit(X[ixa], yr), X, ixb, pa[ib], srcs)
                t = thr_p80(yp[a], inner)
                ixa = np.where(np.isin(kid, pa))[0]; yr = np.array([lab in st[k]['extras'] for k in kid[ixa]])
                ixb = np.where(np.isin(kid, persons[b]))[0]
                s = person_scores(model(X.shape[1]).fit(X[ixa], yr), X, ixb, persons[b], srcs); sc[b] = s
                if t is None: none += 1; continue
                thrs.append(t); k = s >= t; yb = yp[b]
                tot += [(k & yb).sum(), (k & ~yb).sum(), (~k & yb).sum()]
            aucs.append(roc_auc_score(yp, sc))
        tp, fp, fn = tot / REP; P = tp / max(tp + fp, 1e-9); R = tp / max(tp + fn, 1e-9)
        note = f' ({none}/50 katta eşik bulunamadı)' if none else ''
        print(f'| {task} | {mname} | {cname} | {np.mean(thrs) if thrs else float("nan"):.2f} | {tp:.1f} | {fp:.1f} | {fn:.1f} | {P:.2f} | {R:.2f} | {2*P*R/max(P+R,1e-9):.2f} | {np.mean(aucs):.2f} | {yp.sum()}/{len(persons)} |{note}', flush=True)
