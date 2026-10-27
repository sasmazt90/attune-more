"""In-domain finding classifiers (no age input): DINOv2-small embeddings of landmark crops, logistic regression,
leave-persons-out (GroupKFold). Person score = max over crops/poses. Reports AUC, recall at >=80% precision, and the
age-control groups (young positives found? old 'botox' faces kept clean?)."""
import json, re, sys, numpy as np, cv2, torch, mediapipe as mp, collections
from PIL import Image
from mediapipe.tasks.python import vision, BaseOptions
from transformers import AutoImageProcessor, AutoModel
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'; torch.set_num_threads(4)
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
proc = AutoImageProcessor.from_pretrained('facebook/dinov2-small'); dm = AutoModel.from_pretrained('facebook/dinov2-small').eval()
# crop name -> (landmarks, pad as fraction of face width, poses where it is read)
CROPS = {
 'under_L': ([33,7,163,144,145,153,154,155,133,128,121,120,119,118,117,111,226], .03, ('front',)),
 'under_R': ([263,249,390,373,374,380,381,382,362,357,350,349,348,347,346,340,446], .03, ('front',)),
 'lid_L': ([70,63,105,66,107,33,246,161,160,159,158,157,173,133], .02, ('front',)),
 'lid_R': ([300,293,334,296,336,263,466,388,387,386,385,384,398,362], .02, ('front',)),
 'corner_L': ([33,130,226,247,113,225,46,70,124,35], .05, ('front',)),
 'corner_R': ([263,359,446,467,342,445,276,300,353,265], .05, ('front',)),
 'lip': ([61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146], .04, ('front',)),
 'cheek_L': ([116,117,118,119,100,142,203,206,216,212,214,192,213,147,123], .01, ('front', 'pos')),
 'cheek_R': ([345,346,347,348,329,371,423,426,436,432,434,416,433,376,352], .01, ('front', 'neg')),
 'jaw': ([172,136,150,149,176,148,152,377,400,378,379,365,397,288,58,132,361], .03, ('front', 'pos', 'neg')),
 'forehead': ([54,103,67,109,10,338,297,332,284,293,334,296,336,9,107,66,105,63], .01, ('front',)),
}
NEW = lambda k: int(k[2:]) >= 181          # age-independent batches (labels for every finding)
TASKS = {  # finding -> (crops, label fn, persons with valid labels)
 'Göz altı torbası': (('under_L', 'under_R'), lambda p: 'göz altı torbası' in p['extras'], lambda k: True),
 'Göz altı morluğu': (('under_L', 'under_R'), lambda p: 'göz altı morluğu' in p['extras'], NEW),
 'Uçuk': (('lip',), lambda p: 'dudakta uçuk' in p['extras'], lambda k: True),
 'Kaz ayakları': (('corner_L', 'corner_R'), lambda p: 'kaz ayağı' in p['extras'], lambda k: True),
 'Alın kırışıklığı': (('forehead',), lambda p: 'alın kırışıklığı' in p['extras'], lambda k: True),
 'Sarkma: kapak': (('lid_L', 'lid_R'), lambda p: 'sarkma: göz' in p['extras'], NEW),
 'Sarkma: göz dış köşe': (('corner_L', 'corner_R', 'lid_L', 'lid_R'), lambda p: 'sarkma: göz dış köşe' in p['extras'], NEW),
 'Sarkma: yanak': (('cheek_L', 'cheek_R'), lambda p: 'sarkma: yanak' in p['extras'], NEW),
 'Sarkma: çene hattı': (('jaw',), lambda p: 'sarkma: çene hattı' in p['extras'], NEW),
 'Akne izi': (('cheek_L', 'cheek_R', 'jaw'), lambda p: 'akne izi' in p['extras'], NEW),
 'Melazma': (('cheek_L', 'cheek_R'), lambda p: 'melazma (yanaklarda)' in p['extras'], lambda k: True),
 'Güneş lekesi': (('cheek_L', 'cheek_R', 'forehead'), lambda p: 'güneş lekesi' in p['extras'], lambda k: True),
 'Ben': (('cheek_L', 'cheek_R'), lambda p: 'ben (yanakta)' in p['extras'], lambda k: True),
}
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
rows = []
for kid, p in st.items():
    for v, view in (('front', 'front'), ('side_1', 'pos'), ('side_2', 'neg')):
        img = cv2.imread(f"{S}/gen/approved/{kid}/{kid}-{v}.png"); r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        if not r.face_landmarks: continue
        h, w = img.shape[:2]; P = np.array([[q.x * w, q.y * h] for q in r.face_landmarks[0]]); fw = P[:, 0].max() - P[:, 0].min()
        for name, (idx, pad, views) in CROPS.items():
            if view not in views: continue
            x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
            c = img[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)]
            if c.size == 0: continue
            rows.append(dict(kid=kid, crop=name, img=cv2.cvtColor(cv2.resize(c, (224, 224)), cv2.COLOR_BGR2RGB)))
print('crops', len(rows), file=sys.stderr)
E = []
with torch.no_grad():
    for i in range(0, len(rows), 48):
        o = dm(**proc(images=[Image.fromarray(r['img']) for r in rows[i:i + 48]], return_tensors='pt')).last_hidden_state
        E.append(torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy())
E = np.concatenate(E); np.save(f'{S}/rf/finding_emb.npy', E)
json.dump([dict(kid=r['kid'], crop=r['crop']) for r in rows], open(f'{S}/rf/finding_rows.json', 'w'))
YOUNG = ('18-25', '26-35', '36-45'); out = {}
def p80(y, s):
    for t in np.sort(np.unique(s)):
        k = s >= t
        if k.sum() >= 3 and y[k].mean() >= .8: return float(t), float((k & y).sum() / y.sum())
    return None, None
for task, (crops, yl, valid) in TASKS.items():
    ix = [i for i, r in enumerate(rows) if r['crop'] in crops and valid(r['kid'])]
    X = E[ix]; G = np.array([rows[i]['kid'] for i in ix]); y = np.array([yl(st[g]) for g in G])
    if y.sum() < 5: print(f'{task}: yetersiz pozitif ({y.sum()})'); continue
    oof = np.zeros(len(ix))
    for tr, te in GroupKFold(10).split(X, y, G):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.02, max_iter=4000, class_weight='balanced')).fit(X[tr], y[tr]); oof[te] = m.predict_proba(X[te])[:, 1]
    ks = sorted(set(G)); ps = np.array([oof[G == k].max() for k in ks]); yp = np.array([yl(st[k]) for k in ks])
    auc = roc_auc_score(yp, ps); t, rec = p80(yp, ps)
    line = f"{task:22s} kişi={len(ks):3d} pozitif={yp.sum():3d} AUC={auc:.2f} | İsabet≥0.8: {'yok' if t is None else f'yakalama {rec:.2f}'}"
    if t is not None:
        yng = np.array([st[k]['age'] in YOUNG for k in ks]); old_smooth = np.array(['pürüzsüz (botoks)' in st[k]['extras'] for k in ks])
        yp_y = yp & yng
        if yp_y.sum(): line += f" | genç pozitif yakalama {((ps >= t) & yp_y).sum()}/{yp_y.sum()}"
        if old_smooth.sum() and task in ('Göz altı torbası', 'Kaz ayakları', 'Alın kırışıklığı') or (old_smooth.sum() and task.startswith('Sarkma')):
            line += f" | pürüzsüz yaşlıda yanlış alarm {((ps >= t) & old_smooth).sum()}/{old_smooth.sum()}"
    print(line); out[task] = dict(n=len(ks), pos=int(yp.sum()), auc=round(auc, 3), thr=t, recall=rec)
json.dump(out, open(f'{S}/rf/finding_eval.json', 'w'), ensure_ascii=False, indent=1)
