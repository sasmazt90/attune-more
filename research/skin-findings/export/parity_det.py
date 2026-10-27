"""Feature parity for the det-family finding classifiers (acne, redness): production code vs the research cache
(rf/feats2_k10.json). Two levels:
  L1 'component': research inputs (1024 crop, research landmarks/polygons, cached RF-DETR predictions, cached wrinkle mask)
                  fed to the production functions -> isolates feature DEFINITIONS.
  L2 'full'     : the original source photo + MediaPipe landmarks on that photo through regional_skin_v3.analyze_photo
                  (fresh RF-DETR inference, production crop, production wrinkle/beard/lesion masks), polygons from the
                  source landmarks transformed into the crop (what analyze_photo does today).
  L3 'full+crop-landmarks': as L2, but features from skin_findings_det.photo_inputs (landmarks re-detected on the
                  1024 crop = research recipe) -> the recommended production path.
Usage: python3 parity_det.py L1|L2 K-265 K-258 ...  -> prints a table and writes v2/parity_det_<level>.json"""
import os, sys, json, re, numpy as np, cv2
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR'] = f'{S}/rv3model'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R, skin_findings_det as SFD
LEVEL = sys.argv[1]; KIDS = sys.argv[2:]
TAG = '_k10'
I = {it['key']: it for it in json.load(open(f'{S}/rf/items{TAG}.json'))}
F2 = {(r['id'], r['region']): r['f'] for r in json.load(open(f'{S}/rf/feats2{TAG}.json'))}
MD = f'{S}/rv3model'; SP = SFD.specs(MD)
FEATS = list(dict.fromkeys([n for sp in SP.values() for n in sp['features'] if not n.startswith('region_onehot_')]))
POSE = {'front': ('FRONT', 'front'), 'side_1': ('LEFT', 'pos'), 'side_2': ('RIGHT', 'neg')}
params = json.load(open(f'{MD}/params.json'))
cats = {n: {int(k): v for k, v in d['classes'].items()} for n, d in params['detectors'].items() if d.get('role') != 'wrinkle-mask'}


def research_scores(iid, view):
    ev = {rk: F2[(iid, rk)] for rk in SFD.FACE if (iid, rk) in F2}
    extra = dict(bare={rk: {'c_red': f.get('c_red')} for rk, f in ev.items()}, color={rk: {'cv_red': f.get('cv_red'), 'cv_redp90': f.get('cv_redp90')} for rk, f in ev.items()},
                 ita=next(iter(ev.values())).get('ita') if ev else None)
    return SFD.photo_scores(ev, extra, view, MD)


def level1(it, view):
    crop = cv2.imread(it['path']); rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    polys = {k: np.array(it['regions'][k], float) for k in R.REG}; face_w = float(it['faceW'])
    P = {m: json.load(open(f'{S}/rf/pred{TAG}_{m}.json')).get(str(it['id']), []) for m in ('skinmap', 'findings', 'acnes', 'regional')}
    dets = {m: [(int(c), float(s), [float(v) for v in b]) for c, s, b in d] for m, d in P.items()}
    sc = 400 / max(face_w, 1)
    ev = R.model_evidence(dets, cats, polys, (max(1, round(1024 * sc)), max(1, round(1024 * sc))), sc)
    wm = cv2.imread(f"{S}/rf/wmask{TAG}/{it['id']}.png", 0); wrinkle = (wm > 0).astype(np.uint8)
    beard = R.hair_mask(crop, polys, face_w) | R.lesion_mask(dets, cats, (1024, 1024))
    bare, _ = R.bare_skin_features(rgb, polys, face_w, wrinkle, beard)
    hair = R.hair_mask(crop, polys, face_w)
    return ev, dict(bare=bare, color=SFD.color_features(rgb, polys, face_w, wrinkle, hair, dets, cats), ita=R.ita_angle(rgb, polys))


_cap = {}
def _wrap(name):
    f = getattr(R, name)
    def g(*a, **k):
        out = f(*a, **k); _cap[name] = (a, out); return out
    setattr(R, name, g)
if LEVEL in ('L2', 'L3'):
    for n in ('model_evidence', 'bare_skin_features', 'ita_angle'):
        _wrap(n)
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    LM = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))


def level2(kid, f, pose):
    bgr = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{f}.png')
    L = [{'x': q.x, 'y': q.y} for q in LM.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))).face_landmarks[0]]
    R.analyze_photo(bgr, L, pose=pose)
    (dets, cats_, *_), ev = _cap['model_evidence']; (rgb, polys, face_w, wrinkle, _b), (bare, _) = _cap['bare_skin_features']; ita = _cap['ita_angle'][1]
    if LEVEL == 'L3':   # production path with the module's photo_inputs (landmarks re-detected on the crop)
        ev, extra, source = SFD.photo_inputs(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), polys, face_w, dets, cats_, wrinkle)
        print('  redness', SFD.redness_measures(extra, POSE[f][1]))
        assert source == 'crop-landmarks', source
        return ev, extra
    hair = R.hair_mask(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), polys, face_w)
    return ev, dict(bare=bare, color=SFD.color_features(rgb, polys, face_w, wrinkle, hair, dets, cats_), ita=ita)


RFJ = json.load(open(f'{S}/rf/redness_feats.json')); mdiff = {'toneDiff[2]': [], 'areaPct[3] (fraction)': [], 'acne countRaw vs sum n35': []}; mmiss = []
diffs = {n: [] for n in FEATS}; pdiff = {fid: [] for fid in SP}; rowsout = []; flips = []
for kid in KIDS:
    for f, (pose, view) in POSE.items():
        it = I[f'{kid}-{f}.png']; iid = it['id']
        ev, extra = level1(it, view) if LEVEL == 'L1' else level2(kid, f, pose)
        prod = SFD.photo_scores(ev, extra, view, MD); res = research_scores(iid, view)
        if 'lightRedness' in extra:
            ref = RFJ.get(str(iid), {})
            for rk in SFD.FACE:
                a_, b_ = (extra['lightRedness'] or {}).get(rk), ref.get(rk)
                if (a_ is None) != (b_ is None): mmiss.append((kid, f, rk, a_ is not None, b_ is not None)); continue
                if a_ is None: continue
                mdiff['toneDiff[2]'].append(abs(a_[2] - b_[2])); mdiff['areaPct[3] (fraction)'].append(abs(a_[3] - b_[3]))
            for rk, v in extra.get('acneBoxes', {}).items():
                if (iid, rk) in F2:
                    n35 = sum(F2[(iid, rk)].get(f'{m}_n35') or 0 for m in ('findings_Akne', 'findings_Siyah_Nokta', 'findings_Beyaz_Nokta', 'acnes_papule', 'acnes_pustule', 'acnes_blackhead', 'acnes_whitehead'))
                    mdiff['acne countRaw vs sum n35'].append(abs(v['countRaw'] - n35))
        for rk in SFD.FACE:
            if (iid, rk) not in F2 or extra['bare'].get(rk) is None:
                if ((iid, rk) in F2) != (extra['bare'].get(rk) is not None):
                    print('  usable mismatch', kid, f, rk, 'research', (iid, rk) in F2, 'prod', extra['bare'].get(rk) is not None)
                continue
            fr = F2[(iid, rk)]
            for n in FEATS:
                a = SFD._value(n, rk, ev, extra); b = fr.get(n)
                diffs[n].append(abs(float(a or 0) - float(b or 0)))
        for fid in SP:
            for app, p in res[fid].items():
                if app in prod[fid]:
                    pdiff[fid].append(abs(prod[fid][app] - p)); rowsout.append((kid, f, fid, app, round(p, 4), round(prod[fid][app], 4)))
                    t = SP[fid]['threshold']
                    if (p >= t) != (prod[fid][app] >= t): flips.append((kid, f, fid, app, round(p, 3), round(prod[fid][app], 3)))
        print('done', kid, f, flush=True)

# scale reference: std of each feature over all cached k10 rows (5 face regions)
allf = [r for (i, rk), r in F2.items() if rk in SFD.FACE]
sd = {n: float(np.std([float(r.get(n) or 0) for r in allf])) for n in FEATS}
summ = {}
print(f'\n{LEVEL}: {len(KIDS)} persons x 3 poses; {len(diffs[FEATS[0]])} usable regions')
print('| feature | max abs diff | median abs diff | cache std | max/std |')
for n in FEATS:
    d = np.array(diffs[n]); summ[n] = dict(max=float(d.max()), median=float(np.median(d)), std=sd[n], n=int(len(d)))
    print(f'| {n} | {d.max():.4g} | {np.median(d):.4g} | {sd[n]:.4g} | {d.max() / max(sd[n], 1e-12):.3f} |')
for fid, d in pdiff.items():
    d = np.array(d); summ['prob_' + fid] = dict(max=float(d.max()), median=float(np.median(d)), n=int(len(d)))
    print(f'| probability {fid} (fold mean, per photo x region) | {d.max():.4g} | {np.median(d):.4g} | | |')
print('threshold flips (per photo x region):', flips)
for n, d in mdiff.items():
    if d: d = np.array(d); summ['measure_' + n] = dict(max=float(d.max()), median=float(np.median(d)), n=int(len(d))); print(f'| measure {n} | {d.max():.4g} | {np.median(d):.4g} | n={len(d)} |')
print('measure availability mismatches (kid, pose, region, prod, research):', mmiss)
json.dump(dict(level=LEVEL, kids=KIDS, features=summ, flips=flips, rows=rowsout), open(f'{S}/v2/parity_det_{LEVEL}.json', 'w'), indent=1, ensure_ascii=False)
