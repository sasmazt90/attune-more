"""Fair test of the labelled-data detectors (findings model) for ben / melazma / güneş lekesi.
Threshold chosen on training persons (not in pilot32/val28, front + 20° only) for >=0.80 precision,
applied unchanged to the 80 test persons under the three capture sets. Also prints a full threshold sweep on test."""
import json, re, os, collections, numpy as np
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
# per (kid, src, region) -> features
by = collections.defaultdict(dict)
for tag in ('_k5', '_k6', '_k8', '_k9', '_k10', '_k11'):
    if not os.path.exists(f'{S}/rf/feats2{tag}.json'): continue
    I = {it['id']: it for it in json.load(open(f'{S}/rf/items{tag}.json'))}
    for r in json.load(open(f'{S}/rf/feats2{tag}.json')):
        key = I[r['id']]['key']; kid = re.match(r'(K-\d+)', key).group(1)
        if 'front' in key: src, view = 'front', 'front'
        elif re.search(r'side(32|28)_', key): src, view = 'wide', 'pos' if key.rstrip('.png').endswith('_1') else 'neg'
        else: src, view = 's20', 'pos' if 'side_1' in key else 'neg'
        reg = r['region']
        # a cheek is read only from the front or from the side pose that shows it
        if view == 'pos' and reg == 'cheek_imgR': continue
        if view == 'neg' and reg == 'cheek_imgL': continue
        by[(kid, src)][(key, reg)] = r['f']
CHEEK = ('cheek_imgL', 'cheek_imgR'); ALL = ('forehead', 'nose', 'cheek_imgL', 'cheek_imgR', 'chin')
TASKS = {
    'Ben': (lambda p: 'ben (yanakta)' in p['extras'], CHEEK, 'findings_Riskli_Ben_max'),
    'Melazma': (lambda p: 'melazma (yanaklarda)' in p['extras'], CHEEK, 'findings_Gunes_Lekesi_max'),
    'Güneş lekesi': (lambda p: 'güneş lekesi' in p['extras'], ALL, 'findings_Gunes_Lekesi_max'),
}
def score(kid, srcs, regs, key):
    v = [float(f.get(key) or 0) for s in srcs for (k, rg), f in by.get((kid, s), {}).items() if rg in regs]
    return max(v) if v else None
CONF = {'Ön + 20°': ('front', 's20'), 'Ön + ~25°': ('front', 'wide'), 'Ön + 20° + ~25°': ('front', 's20', 'wide')}
print('| Bulgu | Kurgu | Confidence Threshold | TP | FP | FN | Precision | Recall | F1 | AUC | Pozitif/Test |')
sweep = []
for task, (yl, regs, key) in TASKS.items():
    trk = [k for k in st if k not in test and score(k, ('front', 's20'), regs, key) is not None]
    s = np.array([score(k, ('front', 's20'), regs, key) for k in trk]); y = np.array([yl(st[k]) for k in trk])
    thr = None
    for t in np.sort(np.unique(s)):
        kk = s >= t
        if kk.sum() >= 3 and y[kk].mean() >= .8: thr = float(t); break
    flag = ''
    if thr is None:
        f1 = lambda t: 2 * ((s >= t) & y).sum() / max((s >= t).sum() + y.sum(), 1); thr = float(max(np.unique(s), key=f1)); flag = '*'
    tr_auc = roc_auc_score(y, s)
    ks = sorted(k for k in test if all(score(k, c, regs, key) is not None for c in CONF.values()))
    yp = np.array([yl(st[k]) for k in ks])
    for cname, srcs in CONF.items():
        ps = np.array([score(k, srcs, regs, key) for k in ks]); kk = ps >= thr
        tp = (kk & yp).sum(); fp = (kk & ~yp).sum(); fn = (~kk & yp).sum(); P = tp / max(kk.sum(), 1); R = tp / max(yp.sum(), 1)
        print(f'| {task} | {cname} | {thr:.2f}{flag} | {tp} | {fp} | {fn} | {P:.2f} | {R:.2f} | {2*P*R/max(P+R,1e-9):.2f} | {roc_auc_score(yp, ps):.2f} | {yp.sum()}/{len(ks)} |')
        for t in np.round(np.arange(0.05, 1.0, 0.05), 2):
            kk = ps >= t; tp = (kk & yp).sum(); fp = (kk & ~yp).sum(); fn = (~kk & yp).sum(); P = tp / max(kk.sum(), 1); R = tp / max(yp.sum(), 1)
            sweep.append(f'| {task} | {cname} | {t:.2f} | {tp} | {fp} | {fn} | {P:.2f} | {R:.2f} | {2*P*R/max(P+R,1e-9):.2f} |')
    print(f'   (eğitim kişileri: {len(trk)}, pozitif {y.sum()}, AUC {tr_auc:.2f})')
open(f'{S}/rf/det_fair_sweep.md', 'w').write('\n'.join(sweep))
