"""Re-fits and SAVES the two detector-feature finding classifiers with the exact research recipes (no new data, no new
model type, no hyper-parameter search):
  * acne    (Sivilce)    = research/skin-findings/scripts/lesion_eval.py, TASK=Sivilce, method 'Dedektör (öğrenilmiş birleşim)'
  * redness (Kızarıklık) = research/skin-findings/scripts/redness_prev.py, method 'Dedektör'
Same cached features (rf/feats2_k*.json), same labels (gen/state.json), same test persons (pilot32 ∪ val28), same folds
(StratifiedKFold(5, shuffle, seed 0) on training persons), same C / class_weight, same threshold rule (thr_prev on the
training persons' out-of-fold person scores). Row construction and scoring below are copied from the research scripts.
The held-out numbers are recomputed and compared with the recorded tables (results/lesion_eval_sivilce.md,
results/redness_prev.md); the exported JSON is then re-scored in pure numpy (and through the production module
skin_findings_det.py on the cached per-region features) and must give the same numbers.
Usage: python3 export_det.py [OUT_DIR]   (default: $S/rv3model/findings-v2)"""
import json, re, os, sys, hashlib, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
REPO = f'{S}/repo/claude-skin'
OUT = sys.argv[1] if len(sys.argv) > 1 else f'{S}/rv3model/findings-v2'
VERSION = 'skin-findings-v2-det-20261026'
sys.path.insert(0, f'{S}/rf'); from thr_rule import thr_prev
st = {p['id']: p for p in json.load(open(f'{S}/gen/state.json'))['plans'] if p['status'] == 'approved'}
test = set(open(f'{S}/gen/pilot32.txt').read().split()) | set(open(f'{S}/gen/val28.txt').read().split())
APP = {'forehead': 'forehead', 'nose': 'nose', 'chin': 'chin', 'cheek_imgL': 'rightCheek', 'cheek_imgR': 'leftCheek'}
CONF = {'Ön + 20°': ('front', 's20'), 'Ön + ~25°': ('front', 'wide'), 'Ön + 20° + ~25°': ('front', 's20', 'wide')}
TR = ('front', 's20')
ACNE_DET = [f'{m}_{c}' for m in ('findings_Akne', 'findings_Siyah_Nokta', 'findings_Beyaz_Nokta', 'findings_Gunes_Lekesi', 'findings_Riskli_Ben', 'acnes_papule', 'acnes_pustule', 'acnes_blackhead', 'acnes_whitehead') for c in ('max', 'n35', 'cov20')] + ['skinmap_Redness_max', 'skinmap_Redness_cov20', 'skinmap_Redness_cov30', 'findings_Rozasea_max', 'findings_Rozasea_cov20', 'findings_Egzema_max',
       'findings_Egzema_cov20', 'findings_Sedef_ve_Dokuntu_max', 'c_red', 'cv_red', 'cv_redp90', 'ita']
RED_DET = ['skinmap_Redness_max', 'skinmap_Redness_cov20', 'skinmap_Redness_cov30', 'findings_Rozasea_max', 'findings_Rozasea_cov20', 'findings_Egzema_max',
           'findings_Egzema_cov20', 'findings_Sedef_ve_Dokuntu_max', 'c_red', 'cv_red', 'cv_redp90', 'ita']
RF = json.load(open(f'{S}/rf/redness_feats.json'))


def build_rows(task):
    """Verbatim row construction of lesion_eval.py (acne) / redness_prev.py (redness). DINOv2 not loaded: the selected
    methods do not use it."""
    if task == 'acne':
        tags, DET = ('_k5', '_k6', '_k8', '_k9', '_k10', '_k11'), ACNE_DET
        yl = lambda p, app: p['acne'] != 'yok' and app in p['acneRegions']
    else:
        tags, DET = ('_k5', '_k6', '_k8', '_k9', '_k10'), RED_DET
        yl = lambda p, app: p['sens'] != 'yok' and app in p['sensRegions']
    rows = []
    for tag in tags:
        I = {it['id']: it for it in json.load(open(f'{S}/rf/items{tag}.json'))}
        for r in json.load(open(f'{S}/rf/feats2{tag}.json')):
            if r['region'] not in APP: continue
            key = I[r['id']]['key']; kid = re.match(r'(K-\d+)', key).group(1)
            if kid not in st: continue
            if task == 'redness' and (str(r['id']) not in RF or r['region'] not in RF[str(r['id'])]): continue
            if 'front' in key: src, view = 'front', 'front'
            elif re.search(r'side(32|28)_', key): src, view = 'wide', 'pos' if key.rstrip('.png').endswith('_1') else 'neg'
            else: src, view = 's20', 'pos' if 'side_1' in key else 'neg'
            if view == 'pos' and r['region'] == 'cheek_imgR': continue
            if view == 'neg' and r['region'] == 'cheek_imgL': continue
            p = st[kid]; y = yl(p, APP[r['region']])
            rows.append(dict(kid=kid, src=src, view=view, iid=r['id'], reg=r['region'], y=y, f=r['f'],
                             det=np.array([float(r['f'].get(k) or 0) for k in DET]), onehot=np.eye(5)[list(APP).index(r['region'])]))
    return rows, DET


def model(dim):
    steps = [StandardScaler()] + ([PCA(n_components=30, random_state=0)] if dim > 100 else [])
    return make_pipeline(*steps, LogisticRegression(C=0.05 if dim > 100 else 0.5, max_iter=4000, class_weight='balanced'))


def recorded(path, method):
    out = {}
    for line in open(path, encoding='utf-8'):
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) == 11 and c[1] == method:
            out[c[2]] = dict(thr=c[3], TP=c[4], FP=c[5], FN=c[6], P=c[7], R=c[8], F1=c[9], AUC=c[10])
    return out


def run(task):
    rows, DET = build_rows(task)
    kid = np.array([r['kid'] for r in rows]); src = np.array([r['src'] for r in rows]); reg = np.array([r['reg'] for r in rows]); Y = np.array([r['y'] for r in rows])
    X = np.array([np.concatenate([r['det'], r['onehot']]) for r in rows], float)
    def fit(X, persons):
        ix = np.isin(kid, persons) & np.isin(src, TR); return model(X.shape[1]).fit(X[ix], Y[ix])
    def pscore(m, X, persons, srcs):
        ix = np.where(np.isin(kid, persons) & np.isin(src, srcs))[0]; p = m.predict_proba(X[ix])[:, 1]; out = []
        for k in persons:
            s = ix[kid[ix] == k]; pk = p[kid[ix] == k]
            out.append(max(pk[reg[s] == g].mean() for g in set(reg[s])) if len(s) else np.nan)
        return np.array(out)
    lab = (lambda k: st[k]['acne'] != 'yok') if task == 'acne' else (lambda k: st[k]['sens'] != 'yok')
    trp = np.array(sorted(set(kid[np.isin(src, TR)]) - test)); ytr = np.array([lab(k) for k in trp])
    tep = np.array(sorted(k for k in test if all((kid == k)[np.isin(src, c)].any() for c in CONF.values()))); yte = np.array([lab(k) for k in tep])
    print(f'[{task}] eğitim {len(trp)} kişi ({ytr.sum()} pozitif), test {len(tep)} kişi ({yte.sum()} pozitif), rows {len(rows)}')
    splits = list(StratifiedKFold(5, shuffle=True, random_state=0).split(trp, ytr))
    folds = [(a, b, fit(X, trp[a])) for a, b in splits]
    final = [mm for a, b, mm in folds] if task == 'acne' else [fit(X, trp)]   # lesion_eval: fold ensemble; redness_prev: one model on all training persons
    res = {}
    for cname, srcs in CONF.items():
        inner = np.zeros(len(trp))
        for a, b, mm in folds: inner[b] = pscore(mm, X, trp[b], tuple(s for s in srcs if s in TR))
        t = thr_prev(ytr, inner); s = np.mean([pscore(mm, X, tep, srcs) for mm in final], 0); auc = roc_auc_score(yte, s)
        k = s >= t; tp = int((k & yte).sum()); fp = int((k & ~yte).sum()); fn = int((~k & yte).sum()); P = tp / max(k.sum(), 1); R = tp / max(yte.sum(), 1)
        res[cname] = dict(threshold=t, TP=tp, FP=fp, FN=fn, precision=P, recall=R, F1=2 * P * R / max(P + R, 1e-9), auc=auc, scores=dict(zip(tep, s)))
    return dict(rows=rows, DET=DET, kid=kid, src=src, reg=reg, X=X, Y=Y, trp=trp, ytr=ytr, tep=tep, yte=yte, final=final, res=res, lab=lab)


def dump(models):
    return [dict(mean=m[0].mean_.tolist(), scale=m[0].scale_.tolist(), coef=m[-1].coef_[0].tolist(), intercept=float(m[-1].intercept_[0])) for m in models]


SPEC = {
    'acne': dict(name='Sivilce', script='research/skin-findings/scripts/lesion_eval.py (TASK=Sivilce)', method='Dedektör (öğrenilmiş birleşim)',
                 table=f'{REPO}/research/skin-findings/results/lesion_eval_sivilce.md',
                 label='person: plan.acne != "yok"; region (training rows): app region in plan.acneRegions',
                 ensemble='mean over the 5 StratifiedKFold fold models (each fitted on 4/5 of the training persons); person score = mean over folds of the per-fold person score'),
    'redness': dict(name='Kızarıklık', script='research/skin-findings/scripts/redness_prev.py', method='Dedektör',
                    table=f'{REPO}/research/skin-findings/results/redness_prev.md',
                    label='person: plan.sens != "yok"; region (training rows): app region in plan.sensRegions',
                    ensemble='single model fitted on all training persons (folds only used for the out-of-fold threshold)'),
}
FEATURE_SOURCE = {
    'findings_*/acnes_*/skinmap_*': "regional_skin_v3.model_evidence(...)[research_region] (production, unchanged)",
    'c_red': "regional_skin_v3.bare_skin_features(...)[0][research_region]['c_red'] (production, unchanged; None -> 0)",
    'cv_red, cv_redp90': 'skin_findings_det.color_features(rgb, polys, face_w) (research features.py definition: face reference = median a* over all 5 face regions, no bare-skin cleaning)',
    'ita': 'regional_skin_v3.ita_angle(rgb, polys) rounded to 0.1 (research ita.py stores round(ita, 1))',
}


def main():
    os.makedirs(OUT, exist_ok=True)
    sys.path.insert(0, f'{REPO}/services/core-api'); import skin_findings_det as SFD
    report = {}
    for fid in ('acne', 'redness'):
        R = run(fid); sp = SPEC[fid]
        rec = recorded(sp['table'], sp['method'])
        # 1) reproduction vs recorded table (all three capture sets of the selected method, selected row = Ön + 20°)
        cmp = {}
        for cname, r in R['res'].items():
            mine = dict(thr=f"{r['threshold']:.2f}", TP=str(r['TP']), FP=str(r['FP']), FN=str(r['FN']), P=f"{r['precision']:.2f}", R=f"{r['recall']:.2f}", F1=f"{r['F1']:.2f}", AUC=f"{r['auc']:.2f}")
            cmp[cname] = dict(mine=mine, recorded=rec.get(cname), equal=mine == rec.get(cname))
            print(f'  {cname}: mine {mine} | recorded {rec.get(cname)} | equal={mine == rec.get(cname)}')
        assert all(c['equal'] for c in cmp.values()), f'{fid}: reproduction differs from recorded table'
        sel = R['res']['Ön + 20°']
        regions = list(APP)
        spec = dict(
            id=fid, version=VERSION, recipe=f"{sp['script']}, method '{sp['method']}', capture set 'Ön + 20°'",
            features=R['DET'] + [f'region_onehot_{g}' for g in regions],
            featureNotes=dict(missing='a feature value that is None/absent is 0 (research: float(f.get(k) or 0))',
                              onehot='one-hot of the research region in this order: ' + ', '.join(regions), sources=FEATURE_SOURCE),
            regions=regions, regionOf=APP, poses=['FRONT', 'LEFT', 'RIGHT'], viewOfPose={'FRONT': 'front', 'LEFT': 'pos', 'RIGHT': 'neg'},
            visibility='a region is scored from a photo only if its mask has >= 150 px at the 400-px face scale (bare_skin_features not None) '
                       'and it is visible in the pose: view pos (LEFT) never scores cheek_imgR (leftCheek), view neg (RIGHT) never scores cheek_imgL (rightCheek)',
            model=dict(type='StandardScaler -> LogisticRegression(C=0.5, class_weight=balanced, max_iter=4000), no PCA (dim 44/17 <= 100)',
                       probability='p = 1 / (1 + exp(-(coef . ((x - mean) / scale) + intercept)))', ensemble=sp['ensemble'], folds=dump(R['final'])),
            decision=dict(
                region='region score per fold = mean over the poses that score the region of that fold\'s probability; region probability = mean over folds',
                person='person score = mean over folds of (max over regions of the per-fold region score); finding seen <=> person score >= threshold',
                regionSeen='when the person is seen: every region whose region probability >= threshold is seen; if none reaches it, the region with the highest region probability is the one reported seen (research has no region-level decision; this only names where)',
                capture='production capture = FRONT + LEFT(~20°) + RIGHT(~20°) = research "Ön + 20°"'),
            threshold=sel['threshold'], thresholdRule='thr_prev (rf/thr_rule.py: P0=min(0.25, training prevalence), expected precision >= 0.80 at every higher threshold with >= 3 calls) on the training persons\' 5-fold out-of-fold person scores (front + 20°)',
            label=sp['label'], trainPersons=int(len(R['trp'])), trainPositives=int(R['ytr'].sum()), trainRows=int((np.isin(R['kid'], R['trp']) & np.isin(R['src'], TR)).sum()),
            evaluation=dict(TP=sel['TP'], FP=sel['FP'], FN=sel['FN'], precision=round(sel['precision'], 4), recall=round(sel['recall'], 4), auc=round(sel['auc'], 4), threshold=round(sel['threshold'], 4),
                            heldOut=f"{len(R['tep'])} test persons (pilot32 ∪ val28, {int(R['yte'].sum())} positive), capture set Ön + 20° (front + both ~20° sides); the same test persons were also used for method selection in research",
                            recordedTable=sp['table'].replace(REPO + '/', ''), allCaptureSets={c: {k: v for k, v in r.items() if k != 'scores'} for c, r in R['res'].items()}))
        if fid == 'redness':
            spec['evaluation']['note'] = ('CODEX_HANDOFF §6 quotes this method at "Ön + 20° + ~25°" (thr 0.54, P 0.89, R 1.00). The app captures no ~25° frame, '
                                          'so the applicable row is Ön + 20°: same model, same threshold 0.54, TP 30 FP 5 FN 1, P 0.86 R 0.97.')
        txt = json.dumps(spec, separators=(',', ':'), ensure_ascii=False)
        open(f'{OUT}/{fid}.json', 'w', encoding='utf-8').write(txt)
        sha = hashlib.sha256(txt.encode('utf-8')).hexdigest()
        # 2) pure-numpy re-score from the saved JSON (exact research person rule) + 3) through the production module on cached features
        J = json.load(open(f'{OUT}/{fid}.json', encoding='utf-8'))
        Xn = R['X']; P = np.array([[1 / (1 + np.exp(-(np.dot(f['coef'], (x - np.array(f['mean'])) / np.array(f['scale'])) + f['intercept']))) for f in J['model']['folds']] for x in Xn[:2000]])
        Psk = np.array([m.predict_proba(Xn[:2000])[:, 1] for m in R['final']]).T
        maxdp = float(np.abs(P - Psk).max())
        SFD._specs.clear()
        import collections
        dup = collections.Counter((r['kid'], r['src'], r['view'], r['reg']) for r in R['rows'] if r['kid'] in set(R['tep']))
        assert max(dup.values()) == 1, 'duplicate photo rows for a test person/pose'
        mod_scores = {}
        for k in R['tep']:
            by_pose = {}
            for i in np.where((R['kid'] == k) & np.isin(R['src'], TR))[0]:
                r = R['rows'][i]; pose = {'front': 'FRONT', 'pos': 'LEFT', 'neg': 'RIGHT'}[r['view']]
                ev = {r['reg']: r['f']}; extra = dict(bare={r['reg']: {'c_red': r['f'].get('c_red')}}, color={r['reg']: {'cv_red': r['f'].get('cv_red'), 'cv_redp90': r['f'].get('cv_redp90')}}, ita=r['f'].get('ita'))
                ps = SFD.photo_scores(ev, extra, r['view'], os.path.dirname(OUT.rstrip('/')), folds=True)[fid]
                by_pose.setdefault(pose, {}).update(ps)
            mod_scores[k] = SFD.person_score(by_pose, J)
        ms = np.array([mod_scores[k] for k in R['tep']]); rs = np.array([sel['scores'][k] for k in R['tep']])
        c = ms >= J['threshold']; y = R['yte']
        modres = dict(TP=int((c & y).sum()), FP=int((c & ~y).sum()), FN=int((~c & y).sum()), maxAbsPersonScoreDiff=float(np.abs(ms - rs).max()))
        print(f'  saved {OUT}/{fid}.json sha256 {sha}; numpy vs sklearn max|dp| {maxdp:.2e}; module on cached features {modres}')
        assert modres['TP'] == sel['TP'] and modres['FP'] == sel['FP'] and modres['FN'] == sel['FN'] and modres['maxAbsPersonScoreDiff'] < 1e-9
        report[fid] = dict(file=f'{OUT}/{fid}.json', sha256=sha, reproduction=cmp, selected='Ön + 20°', numpyVsSklearnMaxAbsProb=maxdp, moduleOnCachedFeatures=modres,
                           threshold=sel['threshold'], trainPersons=int(len(R['trp'])), trainPositives=int(R['ytr'].sum()), testPersons=int(len(R['tep'])), testPositives=int(R['yte'].sum()))
    json.dump(report, open(f'{S}/v2/export_det_report.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
