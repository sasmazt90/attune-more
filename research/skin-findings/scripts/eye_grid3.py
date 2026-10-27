"""Full grid: 3 findings x 2 methods x 4 capture sets.
Rows = (person, pose). Front row = mean of both eyes' features; side rows (20° side_1/2, ~25° wide_1/2) = the eye facing
the camera. Person score = mean of row probabilities over the poses of the capture set.
A) 140 persons, nested repeated 5-fold (Ön, Ön + 20°; ~25° not available for these persons).
B) 22 persons with ~25° poses as hold-out; model + threshold from the other 118 (front + 20° rows), all 4 capture sets.
Threshold rule: smallest t with precision >= 0.80 at every threshold >= t (>=3 predictions), on training persons only."""
import json, numpy as np, collections
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved' and int(p['id'][2:]) >= 181}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
W = sorted(k for k in test if k in st)
raw = list(np.load(f'{S}/rf/eye_pose_rows.npz', allow_pickle=True)['rows']) + list(np.load(f'{S}/rf/eye_wide_rows.npz', allow_pickle=True)['rows'])
g = collections.defaultdict(list)
for r in raw: g[(r['kid'], r['pose'])].append(r)
rows = []
for (k, p), rs in g.items():
    rows.append(dict(kid=k, pose=p, **{f: np.mean([r[f] for r in rs], 0) for f in ('col', 'geo', 'under', 'lid', 'corner')}))
kid = np.array([r['kid'] for r in rows]); pose = np.array([r['pose'] for r in rows])
POH = lambda p: [p == 'front', p != 'front']
FIND = {
    'Göz altı morluğu': ('göz altı morluğu', {'Renk kıyası (ışık düzeltmeli)': lambda r: np.concatenate([r['col'], POH(r['pose'])]),
                                             'Renk kıyası + DINOv2': lambda r: np.concatenate([r['col'], POH(r['pose']), r['under']])}),
    'Sarkma: kapak': ('sarkma: göz', {'Geometri': lambda r: np.concatenate([r['geo'], POH(r['pose'])]),
                                     'Geometri + DINOv2': lambda r: np.concatenate([r['geo'], POH(r['pose']), r['lid']])}),
    'Sarkma: göz dış köşe': ('sarkma: göz dış köşe', {'Geometri': lambda r: np.concatenate([r['geo'], POH(r['pose'])]),
                                                     'Geometri + DINOv2': lambda r: np.concatenate([r['geo'], POH(r['pose']), r['corner']])}),
}
CONF = {'Ön': ('front',), 'Ön + 20°': ('front', 'side_1', 'side_2'), 'Ön + ~25°': ('front', 'wide_1', 'wide_2'),
        'Ön + 20° + ~25°': ('front', 'side_1', 'side_2', 'wide_1', 'wide_2')}
TRAIN_POSES = ('front', 'side_1', 'side_2')
def model(dim):
    steps = [StandardScaler()] + ([PCA(n_components=20, random_state=0)] if dim > 50 else [])
    return make_pipeline(*steps, LogisticRegression(C=0.1 if dim > 50 else 1.0, max_iter=4000, class_weight='balanced'))
from thr_rule import thr_prev
def thr_p80(y, s):
    return thr_prev(y, s)
def _old_thr(y, s):
    ts = np.sort(np.unique(s))
    for t in ts:
        if (s >= t).sum() >= 3 and all(y[s >= u].mean() >= .8 for u in ts[ts >= t] if (s >= u).sum() >= 3): return t
    return None
def fit(X, persons, lab):
    ix = np.where(np.isin(kid, persons) & np.isin(pose, TRAIN_POSES))[0]
    return model(X.shape[1]).fit(X[ix], np.array([lab in st[k]['extras'] for k in kid[ix]]))
def pscore(m, X, persons, srcs):
    ix = np.where(np.isin(kid, persons) & np.isin(pose, srcs))[0]; p = m.predict_proba(X[ix])[:, 1]
    return np.array([p[kid[ix] == k].mean() if (kid[ix] == k).any() else np.nan for k in persons])
def inner_thr(X, persons, y, lab, srcs, seed):
    sc = np.zeros(len(persons))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=seed).split(persons, y):
        sc[b] = pscore(fit(X, persons[a], lab), X, persons[b], tuple(s for s in srcs if s in TRAIN_POSES))
    return thr_p80(y, sc)
fmt = lambda task, m, c, t, tp, fp, fn, auc, pos: (lambda P, R: f'| {task} | {m} | {c} | {t} | {tp} | {fp} | {fn} | {P:.2f} | {R:.2f} | {2*P*R/max(P+R,1e-9):.2f} | {auc:.2f} | {pos} |')(tp / max(tp + fp, 1e-9), tp / max(tp + fn, 1e-9))
print('### A) 140 kişi (iç içe 5-kat, 10 tekrar)')
print('| Bulgu | Yöntem | Kurgu | Confidence Threshold (ort.) | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Kişi |')
persons = np.array(sorted(set(kid)))
for task, (lab, methods) in FIND.items():
    yp = np.array([lab in st[k]['extras'] for k in persons])
    for mname, fx in methods.items():
        X = np.array([fx(r) for r in rows], float)
        for cname in ('Ön', 'Ön + 20°'):
            srcs = CONF[cname]; tot = np.zeros(3); aucs = []; thrs = []; none = 0
            for rep in range(10):
                sc = np.zeros(len(persons))
                for a, b in StratifiedKFold(5, shuffle=True, random_state=rep).split(persons, yp):
                    t = inner_thr(X, persons[a], yp[a], lab, srcs, 100 + rep)
                    s = pscore(fit(X, persons[a], lab), X, persons[b], srcs); sc[b] = s
                    if t is None: none += 1; continue
                    thrs.append(t); k = s >= t; tot += [(k & yp[b]).sum(), (k & ~yp[b]).sum(), (~k & yp[b]).sum()]
                aucs.append(roc_auc_score(yp, sc))
            tp, fp, fn = np.round(tot / 10, 1)
            print(fmt(task, mname, cname, f'{np.mean(thrs):.2f}' if thrs else '–', tp, fp, fn, np.mean(aucs), f'{yp.sum()}/{len(persons)}') + (f' ({none}/50 katta eşik bulunamadı)' if none else ''), flush=True)
print('\n### B) ~25° pozu olan 22 kişi (model ve eşik diğer 118 kişiden)')
print('| Bulgu | Yöntem | Kurgu | Confidence Threshold | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Test |')
trp = np.array([k for k in persons if k not in W]); Wa = np.array(W)
for task, (lab, methods) in FIND.items():
    ytr = np.array([lab in st[k]['extras'] for k in trp]); yw = np.array([lab in st[k]['extras'] for k in Wa])
    for mname, fx in methods.items():
        X = np.array([fx(r) for r in rows], float); m = fit(X, trp, lab)
        for cname, srcs in CONF.items():
            t = inner_thr(X, trp, ytr, lab, srcs, 0); s = pscore(m, X, Wa, srcs)
            auc = roc_auc_score(yw, s) if 0 < yw.sum() < len(yw) else float('nan')
            if t is None: print(f'| {task} | {mname} | {cname} | eşik bulunamadı | | | | | | | {auc:.2f} | {yw.sum()}/{len(Wa)} |'); continue
            k = s >= t
            print(fmt(task, mname, cname, f'{t:.2f}', (k & yw).sum(), (k & ~yw).sum(), (~k & yw).sum(), auc, f'{yw.sum()}/{len(Wa)}'), flush=True)
