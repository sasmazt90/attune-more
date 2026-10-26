"""[Teslim yeniden üretimi: redness_eval.py + thr_prev eşik kuralı] Kızarıklık (genel) per capture set and method. Region-level rows (item x region), label = region in sensRegions.
Person score = max over regions of the mean probability over the poses of the capture set (a cheek only from the
front or the side pose that shows it). Model + threshold from training persons only (inner 5-fold OOF, stable >=0.80
precision rule), applied unchanged to the 80 test persons."""
import json, re, os, collections, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
RF = json.load(open(f'{S}/rf/redness_feats.json'))
APP = {'forehead': 'forehead', 'nose': 'nose', 'chin': 'chin', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek'}
DET = ['skinmap_Redness_max', 'skinmap_Redness_cov20', 'skinmap_Redness_cov30', 'findings_Rozasea_max', 'findings_Rozasea_cov20', 'findings_Egzema_max',
       'findings_Egzema_cov20', 'findings_Sedef_ve_Dokuntu_max', 'c_red', 'cv_red', 'cv_redp90', 'ita']
rows = []
for tag in ('_k5', '_k6', '_k8', '_k9', '_k10'):
    I = {it['id']: it for it in json.load(open(f'{S}/rf/items{tag}.json'))}
    F1 = json.load(open(f'{S}/rf/feats{tag}.json')); D = np.load(f'{S}/rf/dino{tag}.npy')
    dino = {(r['id'], r['region']): D[i] for i, r in enumerate(F1)}
    for r in json.load(open(f'{S}/rf/feats2{tag}.json')):
        if r['region'] not in APP: continue
        key = I[r['id']]['key']; kid = re.match(r'(K-\d+)', key).group(1)
        if kid not in st or str(r['id']) not in RF or r['region'] not in RF[str(r['id'])]: continue
        if 'front' in key: src, view = 'front', 'front'
        elif re.search(r'side(32|28)_', key): src, view = 'wide', 'pos' if key.rstrip('.png').endswith('_1') else 'neg'
        else: src, view = 's20', 'pos' if 'side_1' in key else 'neg'
        if view == 'pos' and r['region'] == 'cheek_imgR': continue
        if view == 'neg' and r['region'] == 'cheek_imgL': continue
        p = st[kid]; y = p['sens'] != 'yok' and APP[r['region']] in p['sensRegions']
        rows.append(dict(kid=kid, src=src, reg=r['region'], y=y, det=np.array([float(r['f'].get(k) or 0) for k in DET]),
                         col=np.array(RF[str(r['id'])][r['region']]), dino=dino[(r['id'], r['region'])],
                         onehot=np.eye(5)[list(APP).index(r['region'])]))
kid = np.array([r['kid'] for r in rows]); src = np.array([r['src'] for r in rows]); reg = np.array([r['reg'] for r in rows]); Y = np.array([r['y'] for r in rows])
METH = {'Dedektör': lambda r: np.concatenate([r['det'], r['onehot']]),
        'Renk kıyası (ışık düzeltmeli) + dedektör': lambda r: np.concatenate([r['det'], r['col'], r['onehot']]),
        'Renk kıyası + dedektör + DINOv2': lambda r: np.concatenate([r['det'], r['col'], r['onehot'], r['dino']])}
CONF = {'Ön + 20°': ('front', 's20'), 'Ön + ~25°': ('front', 'wide'), 'Ön + 20° + ~25°': ('front', 's20', 'wide')}
TR = ('front', 's20')
def model(dim):
    steps = [StandardScaler()] + ([PCA(n_components=30, random_state=0)] if dim > 100 else [])
    return make_pipeline(*steps, LogisticRegression(C=0.05 if dim > 100 else 0.5, max_iter=4000, class_weight='balanced'))
def fit(X, persons):
    ix = np.isin(kid, persons) & np.isin(src, TR); return model(X.shape[1]).fit(X[ix], Y[ix])
def pscore(m, X, persons, srcs):
    ix = np.where(np.isin(kid, persons) & np.isin(src, srcs))[0]; p = m.predict_proba(X[ix])[:, 1]; out = []
    for k in persons:
        s = ix[kid[ix] == k]; pk = p[kid[ix] == k]
        out.append(max(pk[reg[s] == g].mean() for g in set(reg[s])) if len(s) else np.nan)
    return np.array(out)
import sys as _s; _s.path.insert(0, f'{S}/rf'); from thr_rule import thr_prev
def thr(y, s): return thr_prev(y, s)
lab = lambda k: st[k]['sens'] != 'yok'
trp = np.array(sorted(set(kid[np.isin(src, TR)]) - test)); ytr = np.array([lab(k) for k in trp])
tep = np.array(sorted(k for k in test if all((kid == k)[np.isin(src, c)].any() for c in CONF.values()))); yte = np.array([lab(k) for k in tep])
print(f'eğitim {len(trp)} kişi ({ytr.sum()} pozitif), test {len(tep)} kişi ({yte.sum()} pozitif)')
print('| Bulgu | Yöntem | Kurgu | Confidence Threshold | TP | FP | FN | Precision | Recall | F1 | AUC |')
for mname, fx in METH.items():
    X = np.array([fx(r) for r in rows], float); m = fit(X, trp)
    for cname, srcs in CONF.items():
        inner = np.zeros(len(trp))
        for a, b in StratifiedKFold(5, shuffle=True, random_state=0).split(trp, ytr):
            inner[b] = pscore(fit(X, trp[a]), X, trp[b], tuple(s for s in srcs if s in TR))
        t = thr(ytr, inner); s = pscore(m, X, tep, srcs); auc = roc_auc_score(yte, s)
        if t is None: print(f'| Kızarıklık | {mname} | {cname} | eşik yok | | | | | | | {auc:.2f} |'); continue
        k = s >= t; tp = (k & yte).sum(); fp = (k & ~yte).sum(); fn = (~k & yte).sum(); P = tp / max(k.sum(), 1); R = tp / max(yte.sum(), 1)
        print(f'| Kızarıklık | {mname} | {cname} | {t:.2f} | {tp} | {fp} | {fn} | {P:.2f} | {R:.2f} | {2*P*R/max(P+R,1e-9):.2f} | {auc:.2f} |', flush=True)
