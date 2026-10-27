"""Re-fits and SAVES the three eye-area finding classifiers with the exact research recipes (no new data, no new model
type, no hyper-parameter search). Cached features only:
  darkCircles       <- research eye_grid3.py, row 'Renk kıyası (ışık düzeltmeli) | Ön' (rf/eye_pose_rows.npz 'col' + pose
                       one-hot; model trained on front + 20° rows of the training persons, person score = front row)
  hoodedEyelids     <- research eye_fair3.py, 'Sarkma: kapak | Geometri + DINOv2' (sag_geo.json + eye_fair_emb lid_L/R mean)
  downturnedCorners <- research eye_fair3.py, 'Sarkma: göz dış köşe | Geometri + DINOv2' (sag_geo.json + corner_L/R mean)
1) Re-runs the research nested evaluation (same folds/seeds) and compares with the recorded tables.
2) Deployable model = same pipeline fitted on ALL valid persons; threshold = thr_prev on 5-fold out-of-fold person
   scores of those persons (StratifiedKFold(5, shuffle=True, random_state=100) = the research inner split of repeat 0).
Usage: python3 export_eye.py <out_dir>"""
import json, sys, hashlib, collections, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
import sklearn
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
OUT = sys.argv[1]
sys.path.insert(0, f'{S}/rf'); from thr_rule import thr_prev, P0
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api'); import skin_findings_eye as SE
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved' and int(p['id'][2:]) >= 181}
REP = 10

def model(dim):   # identical to eye_fair3.py / eye_grid3.py
    steps = [StandardScaler()] + ([PCA(n_components=20, random_state=0)] if dim > 50 else [])
    return make_pipeline(*steps, LogisticRegression(C=0.1 if dim > 50 else 1.0, max_iter=4000, class_weight='balanced'))

def dump(m):
    sc = m.named_steps['standardscaler']; lr = m.named_steps['logisticregression']; pca = m.named_steps.get('pca')
    return dict(scaler=dict(mean=sc.mean_.tolist(), scale=sc.scale_.tolist()),
                pca=(dict(mean=pca.mean_.tolist(), components=pca.components_.tolist(), whiten=False) if pca is not None else None),
                lr=dict(coef=lr.coef_[0].tolist(), intercept=float(lr.intercept_[0])))

def summ(tot, aucs, thrs, none):
    tp, fp, fn = tot / REP
    return dict(TP=round(float(tp), 1), FP=round(float(fp), 1), FN=round(float(fn), 1), precision=round(tp / max(tp + fp, 1e-9), 2),
                recall=round(tp / max(tp + fn, 1e-9), 2), auc=round(float(np.mean(aucs)), 2), meanThreshold=round(float(np.mean(thrs)), 2) if thrs else None,
                foldsWithoutThreshold=none)

report = {}
# ================================================================ eye_fair3.py recipe (hoodedEyelids, downturnedCorners)
dc = json.load(open(f'{S}/rf/darkcircle.json')); sg = json.load(open(f'{S}/rf/sag_geo.json'))
EMB = np.load(f'{S}/rf/eye_fair_emb.npz', allow_pickle=True)['E'].item()
assert all(list(sg[k]['f']) == list(SE.GEO_ORDER) for k in sg)
geo = lambda k: list(sg[k]['f'].values())
emb = lambda k, a, b: (EMB[k][a] + EMB[k][b]) / 2
FAIR = {'hoodedEyelids': ('sarkma: göz', ('lid_L', 'lid_R'), 'Sarkma: kapak', 'Geometri + DINOv2',
                          dict(TP=24.5, FP=5.0, FN=6.5, precision=0.83, recall=0.79, auc=0.97, meanThreshold=0.65, foldsWithoutThreshold=0)),
        'downturnedCorners': ('sarkma: göz dış köşe', ('corner_L', 'corner_R'), 'Sarkma: göz dış köşe', 'Geometri + DINOv2',
                              dict(TP=16.4, FP=3.7, FN=15.9, precision=0.82, recall=0.51, auc=0.92, meanThreshold=0.82, foldsWithoutThreshold=1))}
ks = [k for k in sorted(st) if k in dc and 'corr' in dc[k] and k in sg and k in EMB]
for fid, (lab, (ca, cb), task, mname, recorded) in FAIR.items():
    y = np.array([lab in st[k]['extras'] for k in ks]); X = np.array([np.concatenate([geo(k), emb(k, ca, cb)]) for k in ks], float)
    tot = np.zeros(3); aucs = []; thrs = []; none = 0
    for rep in range(REP):
        sc = np.zeros(len(ks))
        for a, b in StratifiedKFold(5, shuffle=True, random_state=rep).split(X, y):
            inner = np.zeros(len(a))
            for ia, ib in StratifiedKFold(5, shuffle=True, random_state=100 + rep).split(X[a], y[a]):
                inner[ib] = model(X.shape[1]).fit(X[a][ia], y[a][ia]).predict_proba(X[a][ib])[:, 1]
            t = thr_prev(y[a], inner)
            s = model(X.shape[1]).fit(X[a], y[a]).predict_proba(X[b])[:, 1]; sc[b] = s
            if t is None: none += 1; continue
            thrs.append(t); k_ = s >= t; tot += [(k_ & y[b]).sum(), (k_ & ~y[b]).sum(), (~k_ & y[b]).sum()]
        aucs.append(roc_auc_score(y, sc))
    ev = summ(tot, aucs, thrs, none)
    # deployable model + threshold
    m = model(X.shape[1]).fit(X, y); oof = np.zeros(len(ks))
    for ia, ib in StratifiedKFold(5, shuffle=True, random_state=100).split(X, y):
        oof[ib] = model(X.shape[1]).fit(X[ia], y[ia]).predict_proba(X[ib])[:, 1]
    thr = thr_prev(y, oof); dm = dump(m)
    np_p = np.array([SE.predict_proba(dict(model=dm), x) for x in X]); sk_p = m.predict_proba(X)[:, 1]
    insample = dict(TP=int(((sk_p >= thr) & y).sum()), FP=int(((sk_p >= thr) & ~y).sum()), FN=int(((sk_p < thr) & y).sum()))
    oofc = dict(TP=int(((oof >= thr) & y).sum()), FP=int(((oof >= thr) & ~y).sum()), FN=int(((oof < thr) & y).sum()))
    feats = [dict(name=f'geo.{g}', source='research sag_geo.py (roll-normalised landmark geometry; eye values = mean of both eyes)') for g in SE.GEO_ORDER] + \
            [dict(name=f'dino.{"lid" if ca.startswith("lid") else "corner"}_mean[{i}]', source=f'mean of DINOv2-small embeddings of crops {ca} and {cb} (index {i}: 0-383 CLS token, 384-767 mean patch token)') for i in range(768)]
    spec = dict(id=fid, version='skin-findings-v2-eye-20261026', family='eye', region=SE.REGION, views=['front'], poses=['FRONT'],
                label=lab, recipe=dict(script='research/skin-findings/scripts/eye_fair3.py', row=f'{task} | {mname}', cache='rf/sag_geo.json + rf/eye_fair_emb.npz'),
                features=dict(kind='geometry+dino', count=X.shape[1], geometryOrder=list(SE.GEO_ORDER), dinoCrops=[ca, cb],
                              cropRecipe='finding_clf.py CROPS indices/pad x face width (all landmarks), cv2.resize 224 (default bilinear), BGR->RGB; AutoImageProcessor+AutoModel dinov2-small; concat(CLS, mean patch tokens)',
                              combine='(emb[crop_L] + emb[crop_R]) / 2', order=[f['name'] for f in feats[:7]] + ['dino_mean[0..767]']),
                model=dm, pipeline='StandardScaler -> PCA(n_components=20, random_state=0) -> LogisticRegression(C=0.1, class_weight=balanced, max_iter=4000)',
                predict='z=(x-scaler.mean)/scaler.scale; z=(z-pca.mean)@pca.components.T; p=1/(1+exp(-(lr.coef@z+lr.intercept)))',
                threshold=thr, thresholdRule=f'thr_prev (rf/thr_rule.py, P0={P0}, target precision 0.80) on 5-fold out-of-fold scores of all {len(ks)} training persons, StratifiedKFold(5, shuffle=True, random_state=100)',
                decision="'seen' if probability >= threshold else 'notSeen' (front photo only)",
                training=dict(persons=len(ks), positives=int(y.sum()), sklearn=sklearn.__version__, outOfFoldAtThreshold=oofc, inSampleAtThreshold=insample),
                evaluation=dict(protocol='nested repeated stratified 5-fold over persons (10 repeats, outer seeds 0-9, inner seeds 100-109), threshold thr_prev on the training fold only; pooled counts averaged over repeats',
                                persons=len(ks), positives=int(y.sum()), **ev, recorded=recorded))
    report[fid] = dict(spec=spec, npMaxAbsDiff=float(np.abs(np_p - sk_p).max()))
    print(fid, 'nested', ev, '| recorded', recorded, '| thr', round(thr, 4), 'np-vs-sklearn', report[fid]['npMaxAbsDiff'], flush=True)

# ================================================================ eye_grid3.py recipe (darkCircles, 'Ön')
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
raw = list(np.load(f'{S}/rf/eye_pose_rows.npz', allow_pickle=True)['rows']) + list(np.load(f'{S}/rf/eye_wide_rows.npz', allow_pickle=True)['rows'])
g = collections.defaultdict(list)
for r in raw: g[(r['kid'], r['pose'])].append(r)
rows = [dict(kid=k, pose=p, **{f: np.mean([r[f] for r in rs], 0) for f in ('col', 'geo', 'under', 'lid', 'corner')}) for (k, p), rs in g.items()]
kid = np.array([r['kid'] for r in rows]); pose = np.array([r['pose'] for r in rows])
POH = lambda p: [p == 'front', p != 'front']
TRAIN_POSES = ('front', 'side_1', 'side_2'); lab = 'göz altı morluğu'
X = np.array([np.concatenate([r['col'], POH(r['pose'])]) for r in rows], float)
def fit(persons):
    ix = np.where(np.isin(kid, persons) & np.isin(pose, TRAIN_POSES))[0]
    return model(X.shape[1]).fit(X[ix], np.array([lab in st[k]['extras'] for k in kid[ix]]))
def pscore(m, persons, srcs):
    ix = np.where(np.isin(kid, persons) & np.isin(pose, srcs))[0]; p = m.predict_proba(X[ix])[:, 1]
    return np.array([p[kid[ix] == k].mean() if (kid[ix] == k).any() else np.nan for k in persons])
def oof_scores(persons, y, srcs, seed):
    sc = np.zeros(len(persons))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=seed).split(persons, y):
        sc[b] = pscore(fit(persons[a]), persons[b], tuple(s for s in srcs if s in TRAIN_POSES))
    return sc
persons = np.array(sorted(set(kid))); yp = np.array([lab in st[k]['extras'] for k in persons]); srcs = ('front',)
tot = np.zeros(3); aucs = []; thrs = []; none = 0
for rep in range(REP):
    sc = np.zeros(len(persons))
    for a, b in StratifiedKFold(5, shuffle=True, random_state=rep).split(persons, yp):
        t = thr_prev(yp[a], oof_scores(persons[a], yp[a], srcs, 100 + rep))
        s = pscore(fit(persons[a]), persons[b], srcs); sc[b] = s
        if t is None: none += 1; continue
        thrs.append(t); k_ = s >= t; tot += [(k_ & yp[b]).sum(), (k_ & ~yp[b]).sum(), (~k_ & yp[b]).sum()]
    aucs.append(roc_auc_score(yp, sc))
ev = summ(tot, aucs, thrs, none)
recorded = dict(TP=24.9, FP=3.0, FN=29.1, precision=0.89, recall=0.46, auc=0.86, meanThreshold=0.82, foldsWithoutThreshold=0)
m = fit(persons); oof = oof_scores(persons, yp, srcs, 100); thr = thr_prev(yp, oof); dm = dump(m)
fx = np.array([X[(kid == k) & (pose == 'front')][0] for k in persons])
np_p = np.array([SE.predict_proba(dict(model=dm), x) for x in fx]); sk_p = m.predict_proba(fx)[:, 1]
ntr = int((np.isin(pose, TRAIN_POSES)).sum())
spec = dict(id='darkCircles', version='skin-findings-v2-eye-20261026', family='eye', region=SE.REGION, views=['front'], poses=['FRONT'],
            label=lab, recipe=dict(script='research/skin-findings/scripts/eye_grid3.py', row='A) Göz altı morluğu | Renk kıyası (ışık düzeltmeli) | Ön',
                                   featureScript='research/skin-findings/scripts/eye_pose.py (colour block) + light.py', cache='rf/eye_pose_rows.npz'),
            features=dict(kind='colour', count=5, order=['col.log_Lc_over_Lu', 'col.da', 'col.db', 'pose.front', 'pose.side'],
                          definitions={'col.*': 'per eye (L,R): light.analyze (Delaunay normals from x,y,z landmarks, Huber light fit, 400 px face) -> Lab of corrected image; '
                                                'band = lower-lid points shifted down 0.012..0.10 face width; usable band pixels (not clipped, not black); darkest 40 % of band (Lu); '
                                                'cheek = same-side light.SKIN cheek polygon & usable; Lc = median L of cheek; dL = Lc - median(Lu); '
                                                'values [log(Lc / max(Lc - dL, 1e-3)), median a(band40) - median a(cheek), median b(band40) - median b(cheek)]; '
                                                'an eye with < 30 band or cheek pixels is skipped; front value = mean over the readable eyes',
                                       'pose.front': '1 for the front photo (always 1 in production)', 'pose.side': '0 for the front photo'},
                          requires='MediaPipe landmark z (normals); no z -> finding not computed'),
            model=dm, pipeline='StandardScaler -> LogisticRegression(C=1.0, class_weight=balanced, max_iter=4000) (dim 5, no PCA)',
            predict='z=(x-scaler.mean)/scaler.scale; p=1/(1+exp(-(lr.coef@z+lr.intercept)))',
            threshold=thr, thresholdRule=f'thr_prev (rf/thr_rule.py, P0={P0}, target precision 0.80) on 5-fold out-of-fold FRONT-row person scores of all {len(persons)} persons, StratifiedKFold(5, shuffle=True, random_state=100) (= eye_grid3 inner_thr seed of repeat 0)',
            decision="'seen' if probability >= threshold else 'notSeen' (front photo only)",
            training=dict(persons=len(persons), positives=int(yp.sum()), rows=ntr, rowPoses=list(TRAIN_POSES), note='as in eye_grid3.fit(): training rows are the front row and the two 20° side rows (one eye each) of every person; pose one-hot distinguishes them',
                          sklearn=sklearn.__version__, outOfFoldAtThreshold=dict(TP=int(((oof >= thr) & yp).sum()), FP=int(((oof >= thr) & ~yp).sum()), FN=int(((oof < thr) & yp).sum())),
                          inSampleAtThreshold=dict(TP=int(((sk_p >= thr) & yp).sum()), FP=int(((sk_p >= thr) & ~yp).sum()), FN=int(((sk_p < thr) & yp).sum()))),
            evaluation=dict(protocol='eye_grid3.py A): nested repeated stratified 5-fold over persons (10 repeats, outer seeds 0-9, inner seeds 100-109), threshold thr_prev on training persons only, person score = front row',
                            persons=len(persons), positives=int(yp.sum()), **ev, recorded=recorded))
report['darkCircles'] = dict(spec=spec, npMaxAbsDiff=float(np.abs(np_p - sk_p).max()))
print('darkCircles nested', ev, '| recorded', recorded, '| thr', round(thr, 4), 'np-vs-sklearn', report['darkCircles']['npMaxAbsDiff'], flush=True)

summary = {}
for fid in ('darkCircles', 'hoodedEyelids', 'downturnedCorners'):
    s = json.dumps(report[fid]['spec'], separators=(',', ':'), ensure_ascii=False); open(f'{OUT}/{fid}.json', 'w').write(s)
    e = report[fid]['spec']['evaluation']
    summary[fid] = dict(sha256=hashlib.sha256(s.encode()).hexdigest(), threshold=report[fid]['spec']['threshold'], npMaxAbsDiff=report[fid]['npMaxAbsDiff'],
                        reproduced={k: e[k] for k in ('TP', 'FP', 'FN', 'precision', 'recall', 'auc', 'meanThreshold', 'foldsWithoutThreshold')}, recorded=e['recorded'],
                        training=report[fid]['spec']['training'])
json.dump(summary, open(f'{S}/v2/export_eye_summary.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
