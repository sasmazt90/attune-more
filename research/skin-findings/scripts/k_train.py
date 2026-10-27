"""In-domain regional classifier on synthetic in-car K characters (30 hand-made + 100 automated).
Leave-persons-out evaluation (GroupKFold by character). Region labels: oily/dry/normal + sensitive.
Painting rule: a colour is shown only if its probability >= threshold chosen for >=80% precision (OOF); otherwise 'ölçüm notu'."""
import json, re, sys, collections, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
APP = {'forehead': 'forehead', 'nose': 'nose', 'chin': 'chin', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek'}
# ---- labels
exec(open(f'{S}/rf/k_eval.py').read().split("I={it['id']")[0])   # -> EXP (old K sheet)
LAB = {}
for kid, e in EXP.items():
    if e['regions']:
        LAB[kid] = dict(regions=e['regions'], sens=e['sensRegions'])
st = json.load(open(f'{S}/gen/state.json'))
for p in st['plans']:
    if p['status'] == 'approved':
        LAB[p['id']] = dict(regions=p['regions'], sens=set(p['sensRegions']))
# ---- features
SCAL = ['skinmap_Oily_max', 'skinmap_Redness_max', 'regional_oily_max', 'regional_dry_max', 'findings_Yagli_Cilt_max', 'findings_Kuru_Cilt_max',
        'findings_Egzema_max', 'findings_Rozasea_max', 'findings_Sedef_ve_Dokuntu_max', 'c_shine', 'c_p99', 'c_tex', 'c_flake', 'c_red', 'c_matte', 'frac_clean', 'ita']
rows = []
import os
for tag in [t for t in ('_k', '_k4', '_k5', '_k6', '_k7') if os.path.exists(f'{S}/rf/feats2{t}.json')]:
    I = {it['id']: it for it in json.load(open(f'{S}/rf/items{tag}.json'))}
    F1 = json.load(open(f'{S}/rf/feats{tag}.json')); D = np.load(f'{S}/rf/dino{tag}.npy')
    dino = {(r['id'], r['region']): D[i] for i, r in enumerate(F1)}
    for r in json.load(open(f'{S}/rf/feats2{tag}.json')):
        if r['region'] not in APP: continue
        it = I[r['id']]; kid = re.match(r'(K-\d+)', it['key']).group(1)
        if kid not in LAB: continue
        app = APP[r['region']]; y = LAB[kid]['regions'].get(app)
        if y is None: continue
        yaw = it['yaw']; view = 'front' if abs(yaw) < 10.5 else ('pos' if yaw > 0 else 'neg')
        # a cheek is only usable from the front or from the side pose that shows it
        if app == 'rightCheek' and view == 'neg': continue
        if app == 'leftCheek' and view == 'pos': continue
        sc = np.array([r['f'].get(k) if r['f'].get(k) is not None else 0.0 for k in SCAL], float)
        rows.append(dict(kid=kid, app=app, view=view, tag=tag, y=y, sens=app in LAB[kid]['sens'], x=np.concatenate([dino[(r['id'], r['region'])], sc]),
                         reg=['forehead', 'nose', 'chin', 'rightCheek', 'leftCheek'].index(app)))
print('persons', len({r['kid'] for r in rows}), 'rows', len(rows), collections.Counter(r['y'] for r in rows))
X = np.array([np.concatenate([r['x'], np.eye(5)[r['reg']]]) for r in rows]); Y = np.array([r['y'] for r in rows]); G = np.array([r['kid'] for r in rows])
Ys = np.array([r['sens'] for r in rows]).astype(int)
C = ['dry', 'normal', 'oily']
oof = np.zeros((len(rows), 3)); oofs = np.zeros(len(rows))
for tr, te in GroupKFold(n_splits=10).split(X, Y, G):
    m = make_pipeline(StandardScaler(), LogisticRegression(C=float(sys.argv[1]) if len(sys.argv) > 1 else 0.05, max_iter=3000, class_weight='balanced')).fit(X[tr], Y[tr])
    oof[te] = m.predict_proba(X[te])
    ms = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=3000, class_weight='balanced')).fit(X[tr], Ys[tr])
    oofs[te] = ms.predict_proba(X[te])[:, 1]
# ---- aggregate views per person-region (mean probability)
agg = collections.defaultdict(list)
for i, r in enumerate(rows): agg[(r['kid'], r['app'])].append(i)
P = np.array([oof[v].mean(0) for v in agg.values()]); Yt = np.array([rows[v[0]]['y'] for v in agg.values()])
Ps = np.array([oofs[v].mean() for v in agg.values()]); Yst = np.array([rows[v[0]]['sens'] for v in agg.values()])
pred = np.array(C)[P.argmax(1)]
print('\nregion accuracy (all painted):', round((pred == Yt).mean(), 3), 'n', len(Yt))
for c in C:
    tp = ((pred == c) & (Yt == c)).sum(); print(f'  {c:6s} P={tp/max((pred==c).sum(),1):.2f} R={tp/max((Yt==c).sum(),1):.2f} (n={(Yt==c).sum()})')
print('confusion (gerçek→tahmin):', dict(collections.Counter(zip(Yt, pred))))
# abstention: paint only when max prob >= t
print('\nthreshold sweep (paint if max prob >= t):')
for t in (0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8):
    keep = P.max(1) >= t; s = f'  t={t:.2f} coverage={keep.mean():.2f} acc={(pred[keep]==Yt[keep]).mean():.2f} |'
    for c in C:
        k2 = keep & (pred == c); s += f' {c}:P={(Yt[k2]==c).mean() if k2.sum() else 0:.2f}(n={k2.sum()})'
    print(s)
from sklearn.metrics import roc_auc_score
print('\nsensitive AUC', round(roc_auc_score(Yst, Ps), 3), 'pos', Yst.sum(), '/', len(Yst))
for t in (0.5, 0.6, 0.7, 0.8):
    tp = ((Ps >= t) & Yst).sum(); print(f'  t={t} P={tp/max((Ps>=t).sum(),1):.2f} R={tp/max(Yst.sum(),1):.2f}')
np.save(f'{S}/rf/k_oof.npy', dict(P=P, Yt=Yt, Ps=Ps, Yst=Yst, keys=list(agg.keys())), allow_pickle=True)
