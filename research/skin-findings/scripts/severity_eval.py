"""Evaluate candidate severity measurements on the age-independent characters.
For each finding: AUC (finding vs none), Spearman with level 0/1/2 (none / hafif / belirgin), AUC hafif<belirgin among
positives, repeatability = Pearson r between the front and the 20° photo of the same eye/side."""
import json, collections, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
F = json.load(open(f'{S}/rf/severity_feats.json'))
by = collections.defaultdict(dict)
for k, v in F.items():
    kid, pose = k.split('|'); by[kid][pose] = v
def lvl(k, lab): return 0 if lab not in st[k]['extras'] else (1 if st[k].get('intensity') == 'hafif' else 2)
SIDE = {'L': 'side_1', 'R': 'side_2'}
def eye_feature(name):
    def front(k):
        v = [by[k]['front'].get(f'{name}_{s}') for s in 'LR']; v = [x for x in v if x is not None and np.isfinite(x)]
        return np.mean(v) if v else None
    def pairs(k):
        return [(by[k]['front'][f'{name}_{s}'], by[k][SIDE[s]][f'{name}_{s}']) for s in 'LR'
                if SIDE[s] in by[k] and f'{name}_{s}' in by[k]['front'] and f'{name}_{s}' in by[k][SIDE[s]]]
    return front, pairs
def front_only(name):
    return (lambda k: by[k]['front'].get(name)), (lambda k: [])
def acne_marks():
    def front(k):
        v = [by[k]['front'].get(n) for n in ('pig_frac_L', 'pig_frac_R', 'pig_frac_chin')]; v = [x for x in v if x is not None]
        return np.mean(v) if v else None
    return front, eye_feature('pig_frac')[1]
C = {
    'Göz altı torbası — profil (ham)': ('göz altı torbası', eye_feature('bag_raw')),
    'Göz altı torbası — profil (düzeltilmiş)': ('göz altı torbası', eye_feature('bag_corr')),
    'Göz altı torbası — oluk eğimi (ham)': ('göz altı torbası', eye_feature('bag_raw_slope')),
    'Kaz ayakları — çizgi gücü': ('kaz ayağı', eye_feature('crow')),
    'Alın çizgileri — yatay çizgi gücü': ('alın kırışıklığı', front_only('fore_h')),
    'Alın çizgileri — yatay çizgi p90': ('alın kırışıklığı', front_only('fore_h_p90')),
    'Alın çizgileri — çizgi gücü (tüm yönler)': ('alın kırışıklığı', front_only('fore_any')),
    'Akne izi — pigment alanı': ('akne izi', acne_marks()),
    'Akne izi — leke sayısı': ('akne izi', eye_feature('pig_blobs')),
}
for name, (lab, (fx, px)) in C.items():
    ks = [k for k in by if 'front' in by[k] and fx(k) is not None and np.isfinite(fx(k))]
    v = np.array([fx(k) for k in ks], float); L = np.array([lvl(k, lab) for k in ks])
    if (L > 0).sum() < 5: continue
    auc = roc_auc_score(L > 0, v); flip = auc < 0.5
    if flip: v = -v; auc = 1 - auc
    sev = roc_auc_score(L[L > 0] == 2, v[L > 0]) if (L == 1).sum() and (L == 2).sum() else float('nan')
    pr = np.array([p for k in ks for p in px(k)], float)
    rep = np.corrcoef(pr[:, 0], pr[:, 1])[0, 1] if len(pr) > 10 else float('nan')
    med = [float(np.median(v[L == i])) for i in range(3)]
    print(f'{name:42s} n={len(ks)} (0/1/2={[(L==i).sum() for i in range(3)]}) {"(ters) " if flip else ""}AUC={auc:.2f} '
          f'Spearman={spearmanr(L, v).correlation:.2f} hafif<belirgin={sev:.2f} tekrar={rep:.2f} medyan={np.round(med, 3)}')
