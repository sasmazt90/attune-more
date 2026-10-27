"""Re-fits and SAVES the DINOv2-crop finding classifiers with the exact research recipes (no new data, no new model
type). Same cached embeddings (rf/finding_angle4_emb.npz), same labels (gen/state.json), same folds, same C, same
threshold rule (thr_prev on training persons' out-of-fold scores). Output: one JSON per finding + a reproduction
report (the held-out numbers must equal the recorded research tables)."""
import json, sys, hashlib, numpy as np, collections
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
OUT = sys.argv[1]
sys.path.insert(0, f'{S}/rf'); from thr_rule import thr_prev
_src = open(f'{S}/rf/finding_clf.py').read(); exec('CROPS = {' + _src.split('CROPS = {', 1)[1].split("NEW = ")[0])
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
z = np.load(f'{S}/rf/finding_angle4_emb.npz', allow_pickle=True); E = z['E']; M = z['meta']
kid = np.array([m['kid'] for m in M]); crop = np.array([m['crop'] for m in M]); src = np.array([m['src'] for m in M])
NEW = lambda k: int(k[2:]) >= 181
REGION = {'under_L': 'periorbital', 'under_R': 'periorbital', 'corner_L': 'periorbital', 'corner_R': 'periorbital', 'lip': 'chin',
          'cheek_L': 'rightCheek', 'cheek_R': 'leftCheek', 'jaw': 'chin', 'forehead': 'forehead'}
mk = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.02, max_iter=4000, class_weight='balanced'))
def dump(models):
    return [dict(mean=m[0].mean_.tolist(), scale=m[0].scale_.tolist(), coef=m[1].coef_[0].tolist(), intercept=float(m[1].intercept_[0])) for m in models]
def save(fid, spec):
    s = json.dumps(spec, separators=(',', ':')); open(f'{OUT}/{fid}.json', 'w').write(s)
    return hashlib.sha256(s.encode()).hexdigest()
report = {}

# ---- fa4 recipe: train = non-test persons (front + 20°), GroupKFold(10) ensemble, evaluated on the 80 test persons
FA4 = {'eyeBags': (('under_L', 'under_R'), 'göz altı torbası', lambda k: True),
       'coldSore': (('lip',), 'dudakta uçuk', lambda k: True),
       'crowsFeet': (('corner_L', 'corner_R'), 'kaz ayağı', lambda k: True),
       'acneMarks': (('cheek_L', 'cheek_R', 'jaw'), 'akne izi', NEW)}
for fid, (crops, lab, valid) in FA4.items():
    yl = lambda p: lab in p['extras']
    sel = np.isin(crop, crops) & np.array([valid(k) for k in kid])
    tr = sel & ~np.isin(kid, list(test)) & np.isin(src, ('front', 's20'))
    ytr = np.array([yl(st[k]) for k in kid[tr]]); gtr = kid[tr]
    oof = np.zeros(tr.sum()); models = []
    for a, b in GroupKFold(10).split(E[tr], ytr, gtr):
        m = mk().fit(E[tr][a], ytr[a]); oof[b] = m.predict_proba(E[tr][b])[:, 1]; models.append(m)
    tks = sorted(set(gtr)); thr = thr_prev(np.array([yl(st[k]) for k in tks]), np.array([oof[gtr == k].max() for k in tks]))
    pr = np.mean([m.predict_proba(E)[:, 1] for m in models], 0)
    ks = sorted(k for k in test if valid(k)); yp = np.array([yl(st[k]) for k in ks])
    ps = np.array([pr[sel & (kid == k) & np.isin(src, ('front', 's20'))].max() for k in ks])
    c = ps >= thr; tp, fp, fn = int((c & yp).sum()), int((c & ~yp).sum()), int((~c & yp).sum())
    ev = dict(protocol='research/skin-findings/scripts/fa4.py, Ön + 20°', heldOut=f'{len(ks)} test persons (pilot32 ∪ val28; also used for method selection)',
              threshold=round(thr, 4), TP=tp, FP=fp, FN=fn, precision=round(tp / max(tp + fp, 1), 2), recall=round(tp / max(tp + fn, 1), 2), auc=round(roc_auc_score(yp, ps), 2))
    spec = dict(id=fid, version='skin-findings-v2-dino-20261026', recipe='fa4', crops=list(crops), poses=['FRONT', 'LEFT', 'RIGHT'],
                regionOf={c_: REGION[c_] for c_ in crops}, decision='person: max over crops and poses of the fold-mean probability >= threshold; region: crop max >= threshold',
                threshold=thr, thresholdRule='thr_prev (training persons only)', trainPersons=len(tks), trainPositives=int(sum(yl(st[k]) for k in tks)),
                folds=dump(models), evaluation=ev)
    report[fid] = dict(sha256=save(fid, spec), **ev); print(fid, report[fid], flush=True)

# ---- nested-CV recipes (alin_repro.py, ecz_flake2.py): deployed model = same recipe fitted on all valid persons
dry = lambda p: any(v == 'dry' for v in p['regions'].values()); ES = ('egzama', 'sedef')
NCV = {'foreheadLines': (('forehead',), lambda p, r: 'alın kırışıklığı' in p['extras'], lambda p: bool(p.get('ageIndependent')),
                         'research/skin-findings/results/alin_repro.md (Ön + 20°): person P 0.86 R 0.85 AUC 0.96; region P 0.99 R 0.66; 190 persons, 3x5 nested CV'),
       'eczema': (('cheek_L', 'cheek_R', 'forehead', 'jaw'), lambda p, r: p['sens'] in ES and r in p['sensRegions'], lambda p: True,
                  'research/skin-findings/results/ecz_flake2.md (Ön + 20°): person P 0.85 R 0.69 AUC 0.96; region P 0.90 R 0.42; 340 persons, 3x5 nested CV'),
       'flaking': (('cheek_L', 'cheek_R', 'forehead', 'jaw'), lambda p, r: (p['regions'].get(r) == 'dry' and p.get('intensity') != 'hafif') or (p['sens'] in ES and r in p['sensRegions']),
                   lambda p: not (dry(p) and p.get('intensity') == 'hafif' and p['sens'] not in ES),
                   'research/skin-findings/results/ecz_flake2.md (Ön + 20°): person P 0.92 R 0.78 AUC 0.95; region P 0.96 R 0.37; 290 persons, 3x5 nested CV')}
for fid, (crops, rl, valid, recorded) in NCV.items():
    ks = np.array(sorted(k for k in st if valid(st[k])))
    pl = lambda k: any(rl(st[k], r) for r in ['forehead', 'nose', 'rightCheek', 'leftCheek', 'chin'])
    sel = np.isin(crop, crops) & np.isin(src, ('front', 's20')) & np.isin(kid, ks)
    ytr = np.array([rl(st[k], REGION[c_]) for k, c_ in zip(kid[sel], crop[sel])]); g = kid[sel]
    oof = np.zeros(sel.sum()); models = []
    for a, b in GroupKFold(5).split(E[sel], ytr, g):
        m = mk().fit(E[sel][a], ytr[a]); oof[b] = m.predict_proba(E[sel][b])[:, 1]; models.append(m)
    thr = thr_prev(np.array([pl(k) for k in ks]), np.array([oof[g == k].max() for k in ks]))
    ev = dict(protocol=recorded, deployedOn=f'all {len(ks)} valid persons (front + 20°)', threshold=round(thr, 4))
    spec = dict(id=fid, version='skin-findings-v2-dino-20261026', recipe=fid, crops=list(crops), poses=['FRONT', 'LEFT', 'RIGHT'],
                regionOf={c_: REGION[c_] for c_ in crops},
                decision='person: max over crops and poses >= threshold; region: mean over the poses that show the crop >= threshold',
                threshold=thr, thresholdRule='thr_prev (out-of-fold, all valid persons)', trainPersons=len(ks), trainPositives=int(sum(pl(k) for k in ks)),
                folds=dump(models), evaluation=ev)
    report[fid] = dict(sha256=save(fid, spec), **ev); print(fid, report[fid], flush=True)
json.dump(report, open(f'{OUT}/REPORT.json', 'w'), ensure_ascii=False, indent=1)
