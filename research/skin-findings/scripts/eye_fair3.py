"""Fair (nested, leave-persons-out) evaluation on the 140 age-independent characters (K-181..320), front photo only.
Göz altı morluğu: light-corrected colour comparison (+ optional DINOv2 under-eye embedding).
Sarkma kapak / göz dış köşe: landmark geometry (+ optional DINOv2 lid/corner embedding).
Outer: repeated stratified 5-fold over persons. Inner: threshold for >=0.80 precision chosen on the training fold's own
out-of-fold scores, then applied unchanged to the held-out fold. Pooled TP/FP/FN are averaged over repeats."""
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
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved' and int(p['id'][2:]) >= 181}
dc = json.load(open(f'{S}/rf/darkcircle.json')); sg = json.load(open(f'{S}/rf/sag_geo.json'))
_src = open(f'{S}/rf/finding_clf.py').read(); exec('CROPS = {' + _src.split('CROPS = {', 1)[1].split('NEW = ')[0])
CACHE = f'{S}/rf/eye_fair_emb.npz'
if os.path.exists(CACHE):
    z = np.load(CACHE, allow_pickle=True); EMB = z['E'].item()
else:
    from transformers import AutoImageProcessor, AutoModel
    torch.set_num_threads(4)
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
    proc = AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm = AutoModel.from_pretrained('facebook/dinov2-small').eval()
    EMB = {}
    for kid in sorted(st):
        img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png')
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        if not r.face_landmarks: continue
        h, w = img.shape[:2]; P = np.array([[q.x * w, q.y * h] for q in r.face_landmarks[0]]); fw = P[:, 0].max() - P[:, 0].min()
        ims, names = [], []
        for name in ('under_L', 'under_R', 'lid_L', 'lid_R', 'corner_L', 'corner_R'):
            idx, pad, _ = CROPS[name]; x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
            ims.append(Image.fromarray(cv2.cvtColor(cv2.resize(img[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)], (224, 224)), cv2.COLOR_BGR2RGB))); names.append(name)
        with torch.no_grad():
            o = dm(**proc(images=ims, return_tensors='pt')).last_hidden_state
        e = torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy()
        EMB[kid] = {n: e[i] for i, n in enumerate(names)}
    np.savez(CACHE, E=np.array(EMB, dtype=object))

def colour(k):
    dL, Lc, da, db = dc[k]['corr']; return [np.log(Lc / max(Lc - dL, 1e-3)), da, db]
def geo(k): return list(sg[k]['f'].values())
def emb(k, a, b): return np.concatenate([(EMB[k][a] + EMB[k][b]) / 2])
TASKS = {
    'Göz altı morluğu': ('göz altı morluğu', {'Renk kıyası (ışık düzeltmeli)': lambda k: colour(k),
                                             'Renk kıyası + DINOv2': lambda k: np.concatenate([colour(k), emb(k, 'under_L', 'under_R')])}),
    'Sarkma: kapak': ('sarkma: göz', {'Geometri': lambda k: geo(k),
                                     'Geometri + DINOv2': lambda k: np.concatenate([geo(k), emb(k, 'lid_L', 'lid_R')])}),
    'Sarkma: göz dış köşe': ('sarkma: göz dış köşe', {'Geometri': lambda k: geo(k),
                                                     'Geometri + DINOv2': lambda k: np.concatenate([geo(k), emb(k, 'corner_L', 'corner_R')])}),
}
def model(dim):
    steps = [StandardScaler()]
    if dim > 50: steps.append(PCA(n_components=20, random_state=0))
    return make_pipeline(*steps, LogisticRegression(C=0.1 if dim > 50 else 1.0, max_iter=4000, class_weight='balanced'))
from thr_rule import thr_prev
def thr_p80(y, s):
    return thr_prev(y, s)
def _old_thr(y, s):
    for t in np.sort(np.unique(s)):
        k = s >= t
        if k.sum() >= 3 and y[k].mean() >= .8: return t
    return None
REP = 10
print('| Bulgu | Yöntem | Confidence Threshold (ort.) | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Kişi |')
for task, (lab, methods) in TASKS.items():
    ks = [k for k in sorted(st) if k in dc and 'corr' in dc[k] and k in sg and k in EMB]
    y = np.array([lab in st[k]['extras'] for k in ks])
    for mname, fx in methods.items():
        X = np.array([fx(k) for k in ks], float); tot = np.zeros(3); aucs = []; thrs = []; none = 0
        for rep in range(REP):
            sc = np.zeros(len(ks))
            for a, b in StratifiedKFold(5, shuffle=True, random_state=rep).split(X, y):
                inner = np.zeros(len(a))
                for ia, ib in StratifiedKFold(5, shuffle=True, random_state=100 + rep).split(X[a], y[a]):
                    inner[ib] = model(X.shape[1]).fit(X[a][ia], y[a][ia]).predict_proba(X[a][ib])[:, 1]
                t = thr_p80(y[a], inner)
                m = model(X.shape[1]).fit(X[a], y[a]); s = m.predict_proba(X[b])[:, 1]; sc[b] = s
                if t is None: none += 1; continue
                thrs.append(t); k = s >= t
                tot += [(k & y[b]).sum(), (k & ~y[b]).sum(), (~k & y[b]).sum()]
            aucs.append(roc_auc_score(y, sc))
        tp, fp, fn = tot / REP; P = tp / max(tp + fp, 1e-9); R = tp / max(tp + fn, 1e-9)
        note = f' ({none}/50 katta %80 eşiği bulunamadı)' if none else ''
        print(f'| {task} | {mname} | {np.mean(thrs) if thrs else float("nan"):.2f} | {tp:.1f} | {fp:.1f} | {fn:.1f} | {P:.2f} | {R:.2f} | {2*P*R/max(P+R,1e-9):.2f} | {np.mean(aucs):.2f} | {y.sum()}/{len(ks)} |{note}')
