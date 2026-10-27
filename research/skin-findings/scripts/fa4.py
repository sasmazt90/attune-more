"""Finding classifiers per capture set: front+20°, front+wide (~25-28°), front+20°+wide.
Side poses contribute only the side facing the camera (side_1/pos -> image-left crops, side_2/neg -> image-right).
Test persons = pilot32 ∪ val28 (never in training); training = all other persons, front + 20° crops only."""
import json, sys, numpy as np, cv2, torch, mediapipe as mp, collections, os
from PIL import Image
from mediapipe.tasks.python import vision, BaseOptions
from transformers import AutoImageProcessor, AutoModel
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'; torch.set_num_threads(4)
_src = open(f'{S}/rf/finding_clf.py').read(); exec('CROPS = {' + _src.split('CROPS = {', 1)[1].split("st = {p['id']")[0])   # CROPS, TASKS, NEW
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
proc = AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm = AutoModel.from_pretrained('facebook/dinov2-small').eval()
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
SIDE_OK = {'pos': lambda n: not n.endswith('_R'), 'neg': lambda n: not n.endswith('_L')}
rows = []
def add(kid, path, view, src):
    img = cv2.imread(path)
    if img is None: return
    r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: return
    h, w = img.shape[:2]; P = np.array([[q.x * w, q.y * h] for q in r.face_landmarks[0]]); fw = P[:, 0].max() - P[:, 0].min()
    for name, (idx, pad, _) in CROPS.items():
        if view != 'front' and not SIDE_OK[view](name): continue
        x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
        c = img[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)]
        if c.size: rows.append(dict(kid=kid, crop=name, src=src, img=cv2.cvtColor(cv2.resize(c, (224, 224)), cv2.COLOR_BGR2RGB)))
for kid in st:
    add(kid, f'{S}/gen/approved/{kid}/{kid}-front.png', 'front', 'front')
    add(kid, f'{S}/gen/approved/{kid}/{kid}-side_1.png', 'pos', 's20'); add(kid, f'{S}/gen/approved/{kid}/{kid}-side_2.png', 'neg', 's20')
    if kid in test:
        for d in ('side32', 'side28'):
            add(kid, f'{S}/gen/{d}/{kid}-side_1.png', 'pos', 'wide'); add(kid, f'{S}/gen/{d}/{kid}-side_2.png', 'neg', 'wide')
CACHE = f'{S}/rf/finding_angle4_emb.npz'
E = []
if os.path.exists(CACHE):
    z = np.load(CACHE, allow_pickle=True); E = [z['E']]; rows = list(z['meta'])
else:
  with torch.no_grad():
    for i in range(0, len(rows), 48):
        o = dm(**proc(images=[Image.fromarray(r['img']) for r in rows[i:i + 48]], return_tensors='pt')).last_hidden_state
        E.append(torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy())
  rows = [dict(kid=r['kid'], crop=r['crop'], src=r['src']) for r in rows]
  np.savez(CACHE, E=np.concatenate(E), meta=np.array(rows, dtype=object))
E = np.concatenate(E)
kid = np.array([r['kid'] for r in rows]); crop = np.array([r['crop'] for r in rows]); src = np.array([r['src'] for r in rows])
CONF = {'Ön + 20°': ('front', 's20'), 'Ön + ~25°': ('front', 'wide'), 'Ön + 20° + ~25°': ('front', 's20', 'wide')}

from thr_rule import thr_prev
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
print('| Bulgu | Kurgu | Confidence Threshold | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Test |')
for task, (crops, yl, valid) in [(t, TASKS[t]) for t in ('Göz altı torbası', 'Uçuk', 'Kaz ayakları', 'Alın kırışıklığı', 'Akne izi', 'Melazma', 'Güneş lekesi', 'Ben')]:
    sel = np.isin(crop, crops) & np.array([valid(k) for k in kid])
    tr = sel & ~np.isin(kid, list(test)) & np.isin(src, ('front', 's20'))
    ytr = np.array([yl(st[k]) for k in kid[tr]])
    mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.02, max_iter=4000, class_weight='balanced'))
    oof = np.zeros(tr.sum()); gtr = kid[tr]; models = []
    for a, b in GroupKFold(10).split(E[tr], ytr, gtr):
        m = mk().fit(E[tr][a], ytr[a]); oof[b] = m.predict_proba(E[tr][b])[:, 1]; models.append(m)
    tks = sorted(set(gtr)); tps = np.array([oof[gtr == k].max() for k in tks]); typ = np.array([yl(st[k]) for k in tks])
    thr = thr_prev(typ, tps)
    pr = np.mean([m.predict_proba(E)[:, 1] for m in models], 0)
    ks = sorted({k for k in test if valid(k)}); yp = np.array([yl(st[k]) for k in ks])
    for cname, srcs in CONF.items():
        ps = np.array([pr[sel & (kid == k) & np.isin(src, srcs)].max() if (sel & (kid == k) & np.isin(src, srcs)).any() else 0 for k in ks])
        auc = roc_auc_score(yp, ps) if 0 < yp.sum() < len(yp) else float('nan')
        if thr is None: print(f'| {task} | {cname} | eşik yok | | | | | | | {auc:.2f} | {yp.sum()}/{len(ks)} |'); continue
        k = ps >= thr; tp = (k & yp).sum(); P = tp / max(k.sum(), 1); R = tp / max(yp.sum(), 1); F = 2 * P * R / max(P + R, 1e-9)
        print(f'| {task} | {cname} | {thr:.2f} | {tp} | {(k & ~yp).sum()} | {(~k & yp).sum()} | {P:.2f} | {R:.2f} | {F:.2f} | {auc:.2f} | {yp.sum()}/{len(ks)} |', flush=True)
