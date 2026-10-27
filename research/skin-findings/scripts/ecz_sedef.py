"""Eczema-like appearance and flaking (pullanma): DINOv2 region crops + logistic regression, person score = max over
crops. Fair evaluation: repeated person-level StratifiedKFold; the threshold is chosen only on the training persons
(inner GroupKFold OOF, thr_prev rule) and applied unchanged to the held-out persons."""
import json, sys, numpy as np, collections
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/rf'); from thr_rule import thr_prev
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
z = np.load(f'{S}/rf/finding_angle4_emb.npz', allow_pickle=True); E = z['E']; M = z['meta']
kid = np.array([m['kid'] for m in M]); crop = np.array([m['crop'] for m in M]); src = np.array([m['src'] for m in M])
dry = lambda p: any(v == 'dry' for v in p['regions'].values())
TASKS = {
 'Egzama görünümü': (('cheek_L', 'cheek_R', 'forehead', 'jaw'), lambda p: p['sens'] in ('egzama', 'sedef'), lambda p: True),
 'Pullanma': (('cheek_L', 'cheek_R', 'forehead', 'jaw'), lambda p: (dry(p) and p.get('intensity') != 'hafif') or p['sens'] in ('egzama', 'sedef'),
              lambda p: not (dry(p) and p.get('intensity') == 'hafif' and p['sens'] not in ('egzama', 'sedef'))),
}
REG = {'cheek_L': 'rightCheek', 'cheek_R': 'leftCheek', 'forehead': 'forehead', 'jaw': 'chin'}
REGION = len(sys.argv) > 2 and sys.argv[2] == 'region'
cl = lambda p, c: p['sens'] in ('egzama', 'sedef') and REG[c] in p['sensRegions']
CONF = {'Ön': ('front',), 'Ön + 20°': ('front', 's20')}
C = float(sys.argv[1]) if len(sys.argv) > 1 else 0.02
mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=4000, class_weight='balanced'))
def person(pr, sel, ks, srcs):
    return np.array([pr[sel & (kid == k) & np.isin(src, srcs)].max() for k in ks])
print('| Bulgu | Kurgu | Eşik (ort.) | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif |')
for task, (crops, yl, valid) in [t for t in TASKS.items() if t[0].startswith('Egz')]:
    ks_all = np.array(sorted(k for k in st if valid(st[k]) and k in set(kid)))
    y_all = np.array([yl(st[k]) for k in ks_all])
    for cname, srcs in CONF.items():
        tot = collections.Counter(); thrs = []; aucs = []
        for rep in range(3):
            for tr_i, te_i in StratifiedKFold(5, shuffle=True, random_state=rep).split(ks_all, y_all):
                trk, tek = ks_all[tr_i], ks_all[te_i]
                sel = np.isin(crop, crops) & np.isin(src, srcs)
                rtr = sel & np.isin(kid, trk); ytr = np.array([cl(st[k], c) if REGION else yl(st[k]) for k, c in zip(kid[rtr], crop[rtr])])
                oof = np.zeros(rtr.sum()); models = []
                for a, b in GroupKFold(5).split(E[rtr], ytr, kid[rtr]):
                    m = mk().fit(E[rtr][a], ytr[a]); oof[b] = m.predict_proba(E[rtr][b])[:, 1]; models.append(m)
                g = kid[rtr]; tps = np.array([oof[g == k].max() for k in trk]); typ = np.array([yl(st[k]) for k in trk])
                thr = thr_prev(typ, tps)
                rte = sel & np.isin(kid, tek)
                pr = np.zeros(len(E)); pr[rte] = np.mean([m.predict_proba(E[rte])[:, 1] for m in models], 0)
                ps = np.array([pr[rte & (kid == k)].max() for k in tek]); yp = np.array([yl(st[k]) for k in tek])
                if 0 < yp.sum() < len(yp): aucs.append(roc_auc_score(yp, ps))
                if thr is None: tot['nothr'] += 1; continue
                thrs.append(thr); c = ps >= thr
                tot['tp'] += (c & yp).sum(); tot['fp'] += (c & ~yp).sum(); tot['fn'] += (~c & yp).sum()
        tp, fp, fn = tot['tp'] / 3, tot['fp'] / 3, tot['fn'] / 3
        P = tp / max(tp + fp, 1e-9); R = tp / max(tp + fn, 1e-9); F = 2 * P * R / max(P + R, 1e-9)
        print(f'| {task} | {cname} | {np.mean(thrs) if thrs else float("nan"):.2f} | {tp:.1f} | {fp:.1f} | {fn:.1f} | {P:.2f} | {R:.2f} | {F:.2f} | {np.mean(aucs):.2f} | {y_all.sum()}/{len(ks_all)} | eşiksiz kat: {tot["nothr"]}', flush=True)
