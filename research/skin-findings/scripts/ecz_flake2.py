"""Final check for the two new findings with region-level labels: person-level P/R (shows the finding) and
region-level P/R (which regions are marked on the face). Thresholds from training persons only (thr_prev)."""
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
REG = {'cheek_L': 'rightCheek', 'cheek_R': 'leftCheek', 'forehead': 'forehead', 'jaw': 'chin'}
CROPS = tuple(REG)
dry = lambda p: any(v == 'dry' for v in p['regions'].values())
ES = ('egzama', 'sedef')
TASKS = {
 'Egzama veya sedef benzeri görünüm': (lambda p, r: p['sens'] in ES and r in p['sensRegions'], lambda p: True),
 'Pullanma': (lambda p, r: (p['regions'].get(r) == 'dry' and p.get('intensity') != 'hafif') or (p['sens'] in ES and r in p['sensRegions']),
              lambda p: not (dry(p) and p.get('intensity') == 'hafif' and p['sens'] not in ES)),
}
mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.02, max_iter=4000, class_weight='balanced'))
for task, (rl, valid) in TASKS.items():
    pl = lambda k: any(rl(st[k], r) for r in ['forehead', 'nose', 'rightCheek', 'leftCheek', 'chin'])
    ks_all = np.array(sorted(k for k in st if valid(st[k])))
    y_all = np.array([pl(k) for k in ks_all])
    for cname, srcs in {'Ön': ('front',), 'Ön + 20°': ('front', 's20')}.items():
        tot = collections.Counter(); aucs = []
        for rep in range(3):
            for tr_i, te_i in StratifiedKFold(5, shuffle=True, random_state=rep).split(ks_all, y_all):
                trk, tek = ks_all[tr_i], ks_all[te_i]
                sel = np.isin(crop, CROPS) & np.isin(src, srcs)
                rtr = sel & np.isin(kid, trk); ytr = np.array([rl(st[k], REG[c]) for k, c in zip(kid[rtr], crop[rtr])])
                oof = np.zeros(rtr.sum()); models = []
                for a, b in GroupKFold(5).split(E[rtr], ytr, kid[rtr]):
                    m = mk().fit(E[rtr][a], ytr[a]); oof[b] = m.predict_proba(E[rtr][b])[:, 1]; models.append(m)
                g = kid[rtr]
                thr = thr_prev(np.array([pl(k) for k in trk]), np.array([oof[g == k].max() for k in trk]))
                rte = sel & np.isin(kid, tek)
                pr = np.zeros(len(E)); pr[rte] = np.mean([m.predict_proba(E[rte])[:, 1] for m in models], 0)
                ps = np.array([pr[rte & (kid == k)].max() for k in tek]); yp = np.array([pl(k) for k in tek])
                aucs.append(roc_auc_score(yp, ps))
                if thr is None: tot['nothr'] += 1; continue
                c = ps >= thr; tot['tp'] += (c & yp).sum(); tot['fp'] += (c & ~yp).sum(); tot['fn'] += (~c & yp).sum()
                # region level: crop score = mean over the poses of that crop; marked if >= thr
                for k in tek:
                    for cr in CROPS:
                        m_ = rte & (kid == k) & (crop == cr)
                        if not m_.any(): continue
                        on = pr[m_].mean() >= thr; lab = rl(st[k], REG[cr])
                        tot['rtp'] += on & lab; tot['rfp'] += on & (not lab); tot['rfn'] += (not on) & lab
        f = lambda a, b: a / max(a + b, 1e-9)
        print(f"{task} | {cname} | kişi: P={f(tot['tp'], tot['fp']):.2f} R={f(tot['tp'], tot['fn']):.2f} (TP {tot['tp']/3:.1f} FP {tot['fp']/3:.1f} FN {tot['fn']/3:.1f}) AUC={np.mean(aucs):.2f} | bölge: P={f(tot['rtp'], tot['rfp']):.2f} R={f(tot['rtp'], tot['rfn']):.2f} | pozitif {y_all.sum()}/{len(ks_all)} eşiksiz {tot['nothr']}", flush=True)
