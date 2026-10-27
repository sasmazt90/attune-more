"""Belirginlik (visibility severity, 0-100) regressors: re-fit and SAVE with the exact research recipes.

Recipe source (unchanged, executed from the research files themselves):
  rf/sev_final.py  (== research/skin-findings/scripts/sev_final.py): emb(), fitpred(), nested(), CR, R/K (blind ratings)
  research/skin-findings/scripts/sev_bands.py: selected (alpha, w) per finding, 20x5-fold out-of-fold percentile -> rho
No new data, no new model type, no hyper-parameter search beyond the research scripts' own nested CV (re-run only to
confirm the recorded numbers). Output: <OUT>/severity/<findingId>.json + v2/REPORT_sev.json (kept out of the model dir so manifests stay model-only)

Usage: cd $S && python3 v2/export_sev.py rv3model/findings-v2
"""
import json, os, sys, hashlib, numpy as np
from scipy.stats import spearmanr, rankdata
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold

S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.chdir(S)
OUT = os.path.join(sys.argv[1] if len(sys.argv) > 1 else 'rv3model/findings-v2', 'severity')
os.makedirs(OUT, exist_ok=True)
RES = f'{S}/repo/claude-skin/research/skin-findings/results'
# exact research definitions (R, K, CR, emb, Cfull, fitpred, nested, AL ...), same prefix sev_bands.py executes
exec(open('rf/sev_final.py').read().split('res={}')[0])

# sev_bands.py CFG (selected models; alpha fixed after the fact, per CODEX_HANDOFF §6)
CFG = {'torba': (1000, 0), 'morluk': (1000, 1), 'kapak': (300, 0), 'kaz': (1000, 0), 'alin': (300, 0), 'akneizi': (300, 0)}
IDS = {'torba': 'eyeBags', 'morluk': 'darkCircles', 'kapak': 'hoodedEyelids', 'kaz': 'crowsFeet', 'alin': 'foreheadLines', 'akneizi': 'acneMarks'}
REC_BANDS = {'torba': .62, 'morluk': .72, 'kapak': .73, 'kaz': .70, 'alin': .60, 'akneizi': .42}   # results/sev_bands.md
REC_FINAL = json.load(open(f'{RES}/sev_final.json'))                                                 # results/sev_final.json
CROP_POSES = {'front': 'front', 's20': ['pos', 'neg']}


def bands_eval(Xe, Xp, y, a, w, reps=20):
    """sev_bands.py verbatim: mean over 20 reps of the within-rep OOF rank percentile; also returns raw OOF preds."""
    P, raw = [], []
    for rep in range(reps):
        p = np.zeros(len(y))
        for tr, te in KFold(5, shuffle=True, random_state=rep).split(Xe):
            p[te] = fitpred(Xe, Xp, y, tr, te, a, w)
        raw.append(p.copy()); P.append((rankdata(p) - 0.5) / len(p) * 100)
    s = np.mean(P, 0)
    lv = [float(s[y == i].mean()) for i in (1, 2, 3)]
    band = np.minimum((s // 20).astype(int), 4)
    far = float(np.mean(((y == 1) & (band >= 3)) | ((y == 3) & (band <= 1))))
    return float(spearmanr(y, s).correlation), lv, far, np.array(raw)


def deploy(Xe, Xp, y, a, w):
    """Same algebra as fitpred() with tr = all rated positives; returns JSON-able linear model on the raw inputs."""
    se = StandardScaler().fit(Xe); A = se.transform(Xe); blocks = [dict(name='embedding', dim=Xe.shape[1], mean=se.mean_.tolist(), scale=se.scale_.tolist(), weight=1.0)]
    if Xp is not None and w > 0:
        sp = StandardScaler().fit(Xp); k = w * np.sqrt(Xe.shape[1] / max(1, Xp.shape[1])) * 0.1
        A = np.hstack([A, k * sp.transform(Xp)])
        blocks.append(dict(name='extra', dim=Xp.shape[1], mean=sp.mean_.tolist(), scale=sp.scale_.tolist(), weight=float(k)))
    m = Ridge(alpha=a).fit(A, y)
    return dict(blocks=blocks, coef=m.coef_.tolist(), intercept=float(m.intercept_)), m.predict(A)


def predict(spec_model, xe, xp=None):
    z = [(xe - np.asarray(spec_model['blocks'][0]['mean'])) / np.asarray(spec_model['blocks'][0]['scale'])]
    if len(spec_model['blocks']) > 1:
        b = spec_model['blocks'][1]; z.append(b['weight'] * (xp - np.asarray(b['mean'])) / np.asarray(b['scale']))
    return float(np.concatenate(z) @ np.asarray(spec_model['coef']) + spec_model['intercept'])


def pct(ref, x):
    ref = np.asarray(ref); return float(100 * ((ref < x).sum() + 0.5 * (ref == x).sum()) / len(ref))


report = {}
for f, (a, w) in CFG.items():
    fid = IDS[f]; y = np.array(R[f], float); ks = K[f]
    Xe = np.array([emb(k, CR[f]) for k in ks])
    nrows = [sum(len(idx.get((k, c, s), [])) for c in CR[f] for s in ('front', 's20')) for k in ks]
    ph = [(n, np.array([g(k) if g(k) is not None else np.nan for k in ks], float)) for n, g in Cfull[f]]
    kept = [(n, v) for n, v in ph if not np.isnan(v).any()]
    Xp = np.column_stack([v for _, v in kept])
    rep = dict(finding=f, id=fid, n=len(y), ratingCounts=np.bincount(y.astype(int), minlength=4)[1:].tolist(),
               alpha=a, w=w, extraColumns=[n for n, _ in kept], embRowsPerPerson=sorted(set(nrows)))
    # 1) recorded selected model (sev_bands protocol), exactly as in research
    rho, lv, far, raw = bands_eval(Xe, Xp, y, a, w)
    rep['selected_bands'] = dict(rho=round(rho, 4), recorded=REC_BANDS[f], diff=round(rho - REC_BANDS[f], 4), meanScoreByRating=[round(v, 1) for v in lv], far2bands=round(far, 4))
    # 2) nested (sev_final protocol) for the arm the selected model belongs to
    arm = 'combo' if w > 0 else 'emb'
    nst = nested(Xe, Xp if w > 0 else None, y, (0, 0.5, 1, 2, 4) if w > 0 else (0,))
    rep['nested'] = dict(arm=arm, rho=round(float(nst[0]), 4), p10=round(float(nst[1]), 4), p90=round(float(nst[2]), 4), recorded=round(REC_FINAL[f][arm][0], 4), diff=round(float(nst[0]) - REC_FINAL[f][arm][0], 4))
    deployable = True; xp_cols = None
    if w > 0:
        # darkCircles: extra column 'DINOv2' = rf/dino_logit_index.json, whose generating script is not in the repo or rf/
        # (re-derivation attempts in REPORT_sev.md reach r~0.97, not equality) -> recorded combo model cannot be served.
        # Fallback = the research's own embedding-only arm (sev_final 'emb'), with the CFG alpha (no new search).
        rep['blockedReason'] = "extra column 'DINOv2' (rf/dino_logit_index.json) has no recorded generating recipe"
        rho_e, lv_e, far_e, raw = bands_eval(Xe, None, y, a, 0)
        rep['fallback_bands'] = dict(model='embedding-only Ridge, alpha=%d (CFG alpha of darkCircles)' % a, rho=round(rho_e, 4), meanScoreByRating=[round(v, 1) for v in lv_e], far2bands=round(far_e, 4))
        nst_e = nested(Xe, None, y, (0,))
        rep['fallback_nested'] = dict(rho=round(float(nst_e[0]), 4), p10=round(float(nst_e[1]), 4), p90=round(float(nst_e[2]), 4), recorded=round(REC_FINAL[f]['emb'][0], 4), diff=round(float(nst_e[0]) - REC_FINAL[f]['emb'][0], 4))
        # information only (not exported): combo without the unreproducible column
        Xc = Xp[:, [i for i, (n, _) in enumerate(kept) if n != 'DINOv2']]
        rep['info_combo_without_logit_bands'] = round(bands_eval(Xe, Xc, y, a, w)[0], 4)
        model, insample = deploy(Xe, None, y, a, 0); wexp = 0
    else:
        model, insample = deploy(Xe, None, y, a, 0); wexp = w
    ref = np.sort(raw.ravel())
    # check: mapping each rep's OOF preds through the pooled reference reproduces the within-rep percentile ranking
    s_ref = np.mean([[pct(ref, v) for v in r] for r in raw], 0)
    rep['refCheck_rho'] = round(float(spearmanr(y, s_ref).correlation), 4)
    rep['insampleVsOOF_sd'] = [round(float(insample.std()), 4), round(float(raw.std()), 4)]
    # deployable-model reproduction: predict() from the JSON == sklearn in-sample prediction
    rep['jsonPredictMaxAbsDiff'] = float(max(abs(predict(model, Xe[i]) - insample[i]) for i in range(len(y))))
    spec = dict(
        id=fid, version='skin-findings-v2-severity-20261026', researchName=f,
        output='belirginlik 0-100: midrank percentile of the model prediction among `reference.sortedOOF` (0 = mildest, 100 = most visible)',
        recipe=dict(scripts=['research/skin-findings/scripts/sev_final.py (emb, fitpred)', 'research/skin-findings/scripts/sev_bands.py (CFG, 20x5-fold OOF percentile)'],
                    model='StandardScaler + Ridge(alpha=%d) on the mean DINOv2-small crop embedding' % a, alpha=a,
                    w=wexp, selectedInResearch=(w == 0), note=None if w == 0 else
                    "Research-selected darkCircles model (alpha=1000, w=1: embedding + 6 extra columns incl. 'DINOv2' logit from rf/dino_logit_index.json) is NOT exported: "
                    "the logit column has no recorded generating script. This file is the research's embedding-only arm (sev_final 'emb') with the same alpha."),
        inputs=dict(
            embedding=dict(dim=768, model='facebook/dinov2-small, CLS token ++ mean patch token (production embedder.embed)',
                           crops=CR[f], poses=dict(front=['front'], side20=['pos', 'neg']),
                           sideRule="side photos contribute only the camera-facing crop: view 'pos' (LEFT pose) gives *_L and centre crops, 'neg' (RIGHT pose) gives *_R and centre crops",
                           aggregation='arithmetic mean of ALL available (pose, crop) embedding vectors listed in `expectedRows` (no per-pose pre-averaging, no L2 normalisation)',
                           expectedRows=[[v, c] for c in CR[f] for v in ('front', 'pos', 'neg') if (v == 'front' or (v == 'pos' and not c.endswith('_R')) or (v == 'neg' and not c.endswith('_L')))],
                           cropDef='skin_findings_dino.CROPS (= rf/finding_clf.py CROPS indices + pad*face width, bbox of MediaPipe 478 landmarks, resize 224x224 RGB)'),
            extra=[]),
        model=model,
        reference=dict(definition='out-of-fold Ridge predictions of the rated positives, 20 repeats x KFold(5, shuffle=True, random_state=rep), same alpha/inputs, pooled (n*20 values) and sorted',
                       percentile='100 * (count(ref < p) + 0.5 * count(ref == p)) / len(ref)', nPositives=len(y), nValues=int(ref.size), sortedOOF=[round(float(v), 6) for v in ref]),
        evaluation=dict(groundTruth="Claude's blind 1-3 visibility ratings of synthetic positive faces (rate/ratings.json), not dermatologist",
                        nPositives=len(y), ratingCounts=rep['ratingCounts'],
                        rhoFixedAlpha=rep['fallback_bands']['rho'] if w > 0 else rep['selected_bands']['rho'],
                        rhoFixedAlphaProtocol='sev_bands.py: alpha fixed after the fact (optimistic), 20x5-fold, mean OOF percentile vs rating',
                        rhoNested=rep['fallback_nested']['rho'] if w > 0 else rep['nested']['rho'],
                        rhoNestedP10P90=[rep['fallback_nested']['p10'], rep['fallback_nested']['p90']] if w > 0 else [rep['nested']['p10'], rep['nested']['p90']],
                        rhoNestedProtocol='sev_final.py nested(): alpha chosen by inner 4-fold CV from (30,100,300,1000,3000,10000), 10x5-fold',
                        recordedSelectedModelRho=REC_BANDS[f]))
    s = json.dumps(spec, separators=(',', ':'), ensure_ascii=False)
    open(f'{OUT}/{fid}.json', 'w').write(s)
    rep['sha256'] = hashlib.sha256(s.encode()).hexdigest(); rep['bytes'] = len(s.encode())
    report[fid] = rep
    print(json.dumps(rep, ensure_ascii=False), flush=True)
json.dump(report, open(f'{S}/v2/REPORT_sev.json', 'w'), ensure_ascii=False, indent=1)
