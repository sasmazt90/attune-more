"""Frozen v1 vs v3 on the prepared 15-photo positive supplement (photo-eval-packs-20261016/01_positive_supplement). No training,
calibration or threshold change. Packages are read-only inputs; outputs go to audit-results/acne-pos-supplement (local) and the
status folder claude-progress/acne-v1-v3-positive-supplement-20261016 (no photos).
Stages: init | preflight | sheets | masks | infer | score | figures"""
import datetime, hashlib, json, os, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
PK = TOGG / 'photo-eval-packs-20261016'; POS = PK / '01_positive_supplement'; NEG = PK / '02_negative_reference'
O = CODE / 'audit-results/acne-pos-supplement'; ST = TOGG / 'claude-progress/acne-v1-v3-positive-supplement-20261016'
sys.path[:0] = [str(HERE), str(HERE / 'external_acne')]
TASK = TOGG / 'attune-live-test/audit-results/skin-capabilities-20261008/scin/face_landmarker.task'
H = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()


def status(stage, **kw):
    ST.mkdir(parents=True, exist_ok=True); d = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(), stage=stage, **kw)
    tmp = ST / 'status.json.tmp'; tmp.write_text(json.dumps(d, indent=1)); os.replace(tmp, ST / 'status.json')


def manifest(): return json.loads((POS / 'manifest.json').read_text())['photos']


def init():
    O.mkdir(parents=True, exist_ok=True); fm = json.loads((PK / 'frozen-models.json').read_text())
    import run_acne_v2_pilot as v2, acne_verifier_photo as P
    w = TOGG / 'attune-live-test' / v2.TAKEOVER / 'models/step0.safetensors'
    zips = {z: H(PK / z) for z in ('Attune_Pozitif_Ek_Karsilastirma_15.zip', 'Attune_Negatif_Referans_17.zip')}
    exp = {'Attune_Pozitif_Ek_Karsilastirma_15.zip': '143d8769600d16449094df07d8f98b468c6799936bb1b5f37e4fc5ca2faec124', 'Attune_Negatif_Referans_17.zip': '41e07f845e7d80ec6cbbd56b2d56461d06706b8d99402d46d83e6f003f687843'}
    assert zips == exp, zips
    ph = manifest(); photos = {}
    for p in ph:
        s = H(POS / p['file']); assert s == p['sha256'], p['id']; photos[p['id']] = dict(sha256=s, file=p['file'])
    import zipfile
    z = zipfile.ZipFile(PK / 'Attune_Pozitif_Ek_Karsilastirma_15.zip'); inzip = {hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png'))}
    assert {p['sha256'] for p in ph} <= inzip, 'ZIP_PHOTO_MISMATCH'
    models = dict(v1=dict(path=str(P.MODELS['v1'][0]), sha256=H(P.MODELS['v1'][0])), v3=dict(path=str(P.MODELS['v3'][0]), sha256=H(P.MODELS['v3'][0])), step0=dict(path=str(w), sha256=H(w)))
    assert models['v1']['sha256'] == fm['v1Sha256'] and models['v3']['sha256'] == fm['v3Sha256'] and models['step0']['sha256'] == fm['step0Sha256']
    code = {f: H(CODE / f) for f in ['scripts/skin-research/acne_candidate_verifier.py', 'scripts/skin-research/acne_verifier_photo.py', 'scripts/skin-research/eval_acne_v5_independent.py',
            'scripts/skin-research/acne_landmarks_v2.py', 'scripts/skin-research/prepare_acne_data_v2.py', 'scripts/skin-research/external_acne/common_scope_compare.py',
            'scripts/skin-research/external_acne/relabel_compare.py', 'scripts/skin-research/unused_test_masks.py', 'scripts/skin-research/pos_supplement.py']}
    import acne_takeover_support as ats, acne_box_support_staging as bs
    code.update({'acne_takeover_support.py': H(ats.__file__), 'acne_box_support_staging.py': H(bs.__file__), 'face_landmarker.task': H(TASK)})
    idx = dict(packages=zips, positivePhotos=photos, negativeReference=dict(labels=H(NEG / 'labels-frozen.json'), results=H(NEG / 'acne-unused-test-results-20261016.json')),
               models=models, frozenModelsJson='match', settings=dict(conf=.30, nms=.30, tiles='384 / stride 288, budget 64', filter='old box filter (principled_accepted_boxes)',
               matching='source-pixel centres, r = 0.03 x face width (landmarks 234-454), deterministic one-to-one (max cardinality, min distance)', defaultVerifier='v1'), code=code,
               git=subprocess.run(['git', 'log', '--oneline', '-1'], cwd=CODE, capture_output=True, text=True, env=dict(os.environ)).stdout.strip())
    (O / 'index.json').write_text(json.dumps(idx, indent=1)); ST.mkdir(parents=True, exist_ok=True); (ST / 'index.json').write_text(json.dumps(idx, indent=1))
    status('init: hashes verified, list fixed', photosTotal=15, done=0, outputs=[str(ST / 'index.json')])
    print(json.dumps(models, indent=1))


def preflight():
    ph = manifest(); items = {p['sha256']: POS / p['file'] for p in ph}
    (O / 'items.json').write_text(json.dumps([dict(sha256=s, path=str(f)) for s, f in items.items()]))
    if not (O / 'landmarks.jsonl').exists() or sum(1 for _ in open(O / 'landmarks.jsonl')) < 15:
        subprocess.run([str(Path.home() / 'envmp/bin/python'), str(HERE / 'acne_landmarks_v2.py'), '--task', str(TASK), '--items', str(O / 'items.json'), '--out', str(O / 'landmarks.jsonl')], check=True)
    import eval_acne_v5_independent as v5; v5.setup(); import prepare_acne_data_v2 as prep, cv2
    prep.run_replay(CODE, O / 'landmarks.jsonl', items, TOGG, O / 'replay.jsonl')
    rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}; st = {}
    for p in ph:
        r = rp.get(p['sha256'])
        if r is None: st[p['id']] = dict(status='no-replay-row'); continue
        pl = v5.plan(cv2.imread(str(items[p['sha256']])), r)
        st[p['id']] = dict(sha256=p['sha256'], status=pl['status'], tiles=len(pl['rects']), pose=r.get('matchedAngle'), yaw=(r.get('alignment') or {}).get('yaw'), reasons=r.get('reasons'))
    passed = sorted(k for k, v in st.items() if v['status'].startswith('replay-pass'))
    rec = dict(rule='unchanged product preflight: local MediaPipe (product .task) -> frontend replay (quality, pose, snapshot; eyewear not replayed = UNKNOWN) -> photo_input plan', status=st,
               passed=passed, rejected={k: v['status'] for k, v in st.items() if k not in passed})
    (O / 'eligibility.json').write_text(json.dumps(rec, indent=1))
    status('preflight done', photosTotal=15, passed=len(passed), rejected=len(st) - len(passed), rejectedIds=rec['rejected'], outputs=[str(O / 'eligibility.json')])
    print(json.dumps({k: (v['status'], v.get('pose')) for k, v in st.items()}, indent=1))


def sheets():
    import make_label_sheets as M
    el = json.loads((O / 'eligibility.json').read_text()); ph = {p['id']: p for p in manifest()}
    pack = O / 'labelpack'; pack.mkdir(exist_ok=True)
    (pack / 'manifest.json').write_text(json.dumps([dict(sha256=ph[i]['sha256'], kind='positive-photo', file=str((POS / ph[i]['file']).resolve())) for i in el['passed']]))
    M.main(str(pack), [str(O / 'replay.jsonl')], str(O / 'sheets'))
    status('label sheets ready (original pixels + grid only; no source boxes, no predictions)', photosTotal=15, passed=len(el['passed']))


def masks():
    import unused_test_masks as UM
    UM.O = O
    lab = json.loads((O / 'labels.json').read_text())
    for ph, p in lab['photos'].items(): p['_file'] = p['file']
    # reuse the same mask rule; photo path differs
    import cv2
    from make_label_sheets import OVAL
    rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}; (O / 'masks').mkdir(exist_ok=True)
    for ph, p in lab['photos'].items():
        img = cv2.imread(str(POS / p.pop('_file'))); h, w = img.shape[:2]
        P = np.array([[l['x'] * w, l['y'] * h] for l in rp[p['sha256']]['landmarks']], np.float32)
        m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [np.round(P[OVAL]).astype(np.int32)], 255); cut = np.zeros_like(m)
        for g in (UM.EYE_L, UM.EYE_R, UM.BROW_L, UM.BROW_R): cv2.fillPoly(cut, [cv2.convexHull(np.round(P[g]).astype(np.int32))], 255)
        k = max(1, int(round(.03 * p['faceWidthPx']))); cut = cv2.dilate(cut, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
        cv2.fillPoly(cut, [cv2.convexHull(np.round(P[UM.LIPS]).astype(np.int32))], 255); m[cut > 0] = 0
        for x0, y0, x1, y1 in p['coverage']['exclude']: m[max(0, y0):y1, max(0, x0):x1] = 0
        black = cv2.dilate((img.max(2) < 12).astype(np.uint8), np.ones((7, 7), np.uint8)); m[black > 0] = 0
        cv2.imwrite(str(O / 'masks' / f'{ph}.png'), m)
        p['mask'] = dict(file=f'masks/{ph}.png', sha256=H(O / 'masks' / f'{ph}.png'), maskPx=int((m > 0).sum()),
                         targetsInsideMask=sum(1 for q in p['points'] if q['cat'] == 'TARGET' and m[int(q['y']), int(q['x'])]))
    s = json.dumps(lab, indent=1); (O / 'labels-frozen.json').write_text(s)
    status('labels and masks frozen (before inference)', labelsSha256=hashlib.sha256(s.encode()).hexdigest(), outputs=[str(O / 'labels-frozen.json')])
    print(hashlib.sha256(s.encode()).hexdigest(), {k: (v['mask']['maskPx'], len([q for q in v['points'] if q['cat'] == 'TARGET']), v['mask']['targetsInsideMask']) for k, v in lab['photos'].items()})


def infer():
    import eval_acne_v5_independent as v5, acne_candidate_verifier as V, acne_verifier_photo as P, cv2, torch, resource
    from heavy_job_lease import HeavyJobLease
    el = json.loads((O / 'eligibility.json').read_text()); ph = {p['id']: p for p in manifest()}; rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}
    vers = {k: V.Verifier(P.MODELS[k][0]) for k in ('v1', 'v3')}
    for k in vers: assert H(P.MODELS[k][0]) == P.MODELS[k][1]
    out = O / 'infer'; out.mkdir(exist_ok=True)
    with HeavyJobLease('CLAUDE-acne-pos-supplement', peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        v2 = v5.setup(); torch.set_num_threads(2); net = v2.build_net(v5.TOGG); net.eval(); before = P.param_digest(net)
        for n, i in enumerate(el['passed']):
            if (out / f'{i}.json').exists(): continue
            lease.check(); s = ph[i]['sha256']; f = POS / ph[i]['file']; assert H(f) == s
            t0 = time.perf_counter(); r = V.run_chain_with_features(net, cv2.imread(str(f)), rp[s]); F = r['features']
            rec = dict(id=i, sha256=s, status=r['status'], final=[[round(x, 3) for x in b[:4]] + [b[4]] for b in r['final']], chainSec=r.get('chainSec'), featureBytes=r.get('featureBytes'),
                       totalSec=time.perf_counter() - t0, maxRssMiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, verifiers={})
            for k, ver in vers.items():
                t = time.perf_counter(); p = ver.proba(F) if len(F) else np.zeros(0)
                rec['verifiers'][k] = dict(proba=p.tolist(), keep=(p >= ver.threshold).tolist(), sec=time.perf_counter() - t)
            np.savez_compressed(out / f'{i}.npz', features=F); (out / f'{i}.json').write_text(json.dumps(rec))
            status('inference', photosTotal=len(el['passed']), done=n + 1); print(i, len(rec['final']), {k: sum(v['keep']) for k, v in rec['verifiers'].items()}, flush=True)
        assert P.param_digest(net) == before, 'STEP0_PARAMETERS_CHANGED'
    status('inference complete (one Step0 run per photo; v1/v3 on the same candidates)', photosTotal=len(el['passed']), done=len(el['passed']), step0ParamDigest=before)


def score():
    import cv2, relabel_compare as RC, common_scope_compare as CS
    CL = ['matched', 'false', 'duplicate', 'onUncertain', 'onOther', 'nearOutOfScopeTarget', 'unreviewedInOval', 'nonSkin', 'unreviewedPhoto']
    lab = json.loads((O / 'labels-frozen.json').read_text()); rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}
    el = json.loads((O / 'eligibility.json').read_text()); ids = sorted(lab['photos'])
    rec = {i: json.loads((O / 'infer' / f'{i}.json').read_text()) for i in ids}
    preds = {'Step0': {i: [b[:4] for b in rec[i]['final']] for i in ids}}
    for k in ('v1', 'v3'): preds[k] = {i: [b[:4] for b, kk in zip(rec[i]['final'], rec[i]['verifiers'][k]['keep']) if kk] for i in ids}
    res = {n: {} for n in preds}
    for n in preds:
        for i in ids:
            L = lab['photos'][i]; m = cv2.imread(str(O / 'masks' / f'{i}.png'), cv2.IMREAD_GRAYSCALE)
            res[n][i] = CS.classify(L, preds[n][i], m > 0, RC.oval_mask(rp[L['sha256']], m.shape[1], m.shape[0]), .03 * L['faceWidthPx'])
    per = {i: dict(pose=el['status'][i]['pose'], targetsInScope=len(res['Step0'][i]['inScope']), targetsOutOfMask=len(res['Step0'][i]['outOfScope']),
                   **{n: dict(points=len(preds[n][i]), found=len(res[n][i]['hitIds']), hitIds=res[n][i]['hitIds'], **{c: res[n][i]['classes'].count(c) for c in CL}) for n in preds}) for i in ids}
    tab = {}
    for n in preds:
        fp = [per[i][n]['false'] for i in ids]; T = sum(per[i]['targetsInScope'] for i in ids); F = sum(per[i][n]['found'] for i in ids)
        tab[n] = dict(photos=len(ids), targets=T, found=F, rate=round(F / T, 3) if T else None, points=sum(per[i][n]['points'] for i in ids), false=sum(fp),
                      falseMeanPerPhoto=round(float(np.mean(fp)), 3) if fp else None, falseMedianPerPhoto=float(np.median(fp)) if fp else None,
                      **{c: sum(per[i][n][c] for i in ids) for c in CL if c not in ('false', 'matched')})
    hit = {n: {(i, h) for i in ids for h in per[i][n]['hitIds']} for n in preds}; fmt = lambda s: sorted(f'{a}#{b}' for a, b in s)
    rng = np.random.default_rng(20261016)
    def boot(a, b, k):
        d = np.array([per[i][b][k] - per[i][a][k] for i in ids]); return dict(delta=int(d.sum()), ci95=[float(x) for x in np.percentile([d[rng.integers(0, len(d), len(d))].sum() for _ in range(10000)], [2.5, 97.5])])
    removed = {}
    for k in ('v1', 'v3'):
        removed[k] = []
        for i in ids:
            cl = dict(zip([tuple(b[:4]) for b in rec[i]['final']], res['Step0'][i]['classes']))
            for b, kk, p in zip(rec[i]['final'], rec[i]['verifiers'][k]['keep'], rec[i]['verifiers'][k]['proba']):
                if not kk: removed[k].append(dict(photo=i, box=b[:4], proba=round(p, 4), classUnderStep0=cl[tuple(b[:4])]))
    sub = {}
    for name, f in (('FRONT', lambda i: per[i]['pose'] == 'FRONT'), ('side', lambda i: per[i]['pose'] != 'FRONT')):
        s_ = [i for i in ids if f(i)]
        sub[name] = dict(photos=len(s_), targets=sum(per[i]['targetsInScope'] for i in s_), **{n: dict(found=sum(per[i][n]['found'] for i in s_), false=sum(per[i][n]['false'] for i in s_)) for n in preds})
    out = dict(set='A positive supplement (15 photos; all inferred by Step0 on 2026-10-15; not an independent test)', table=tab,
               targets=dict(v3vsV1=dict(lost=fmt(hit['v1'] - hit['v3']), gained=fmt(hit['v3'] - hit['v1'])), v1vsStep0=dict(lost=fmt(hit['Step0'] - hit['v1'])), v3vsStep0=dict(lost=fmt(hit['Step0'] - hit['v3']))),
               CI95={f'{b}-{a} {k}': boot(a, b, k) for a, b in (('Step0', 'v1'), ('Step0', 'v3'), ('v1', 'v3')) for k in ('false', 'found', 'points')},
               removed=removed, subgroups=sub, perPhoto=per, rejectedByPreflight=el['rejected'],
               cost=dict(chainSecMedian=float(np.median([rec[i]['chainSec'] or 0 for i in ids])) if ids else None, maxRssMiB=max([rec[i]['maxRssMiB'] for i in ids], default=None)),
               referenceB=json.loads((NEG / 'acne-unused-test-results-20261016.json').read_text())['table'])
    (O / 'results.json').write_text(json.dumps(out, indent=1)); (ST / 'results.json').write_text(json.dumps(out, indent=1))
    status('scored', photosTotal=15, passed=len(ids), outputs=[str(ST / 'results.json')])
    print(json.dumps({k: out[k] for k in ('table', 'targets', 'CI95', 'subgroups')}, indent=1))


def figures():
    import cv2
    lab = json.loads((O / 'labels-frozen.json').read_text()); res = json.loads((O / 'results.json').read_text()); ph = {p['id']: p for p in manifest()}
    COL = {('keep', 'keep'): (0, 200, 0), ('keep', 'drop'): (0, 140, 255), ('drop', 'keep'): (255, 0, 255), ('drop', 'drop'): (0, 0, 255)}
    TXT = {('keep', 'keep'): 'kept by v1 and v3', ('keep', 'drop'): 'kept by v1, removed by v3', ('drop', 'keep'): 'removed by v1, kept by v3', ('drop', 'drop'): 'removed by v1 and v3'}
    (O / 'figures').mkdir(exist_ok=True)
    for i, L in lab['photos'].items():
        rec = json.loads((O / 'infer' / f'{i}.json').read_text()); S = 2
        img = cv2.resize(cv2.imread(str(POS / ph[i]['file'])), None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
        m = cv2.resize(cv2.imread(str(O / 'masks' / f'{i}.png'), cv2.IMREAD_GRAYSCALE), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)
        cs, _ = cv2.findContours((m > 0).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(img, cs, -1, (255, 255, 0), 1)
        lost = {t.split('#')[1] for t in res['targets']['v3vsV1']['lost'] if t.startswith(i + '#')}
        for q in L['points']:
            c = (int(q['x'] * S), int(q['y'] * S))
            if q['cat'] == 'TARGET':
                cv2.drawMarker(img, c, (0, 0, 255) if q['id'] in lost else (255, 255, 255), cv2.MARKER_CROSS, 16, 2)
                if q['id'] in lost: cv2.putText(img, q['id'] + ' lost by v3', (c[0] + 8, c[1] - 8), 0, .45, (0, 0, 255), 1)
            else: cv2.drawMarker(img, c, (160, 160, 160), cv2.MARKER_DIAMOND, 12, 1)
        for j, b in enumerate(rec['final']):
            k = ('keep' if rec['verifiers']['v1']['keep'][j] else 'drop', 'keep' if rec['verifiers']['v3']['keep'][j] else 'drop')
            cv2.circle(img, (int((b[0] + b[2]) / 2 * S), int((b[1] + b[3]) / 2 * S)), 11, COL[k], 2)
        h = np.full((26 * 8, img.shape[1], 3), 255, np.uint8); y = 20
        for k, t in TXT.items(): cv2.circle(h, (14, y - 5), 7, COL[k], 2); cv2.putText(h, 'Step0 point ' + t, (30, y), 0, .5, (0, 0, 0), 1); y += 26
        cv2.drawMarker(h, (14, y - 5), (0, 0, 0), cv2.MARKER_CROSS, 14, 2); cv2.putText(h, 'reviewed TARGET (red cross = found by v1, lost by v3)', (30, y), 0, .5, (0, 0, 0), 1); y += 26
        cv2.drawMarker(h, (14, y - 5), (120, 120, 120), cv2.MARKER_DIAMOND, 12, 1); cv2.putText(h, 'UNCERTAIN / other category', (30, y), 0, .5, (0, 0, 0), 1); y += 26
        p = res['perPhoto'][i]; cv2.putText(h, f"{i}: targets {p['targetsInScope']}; found Step0/v1/v3 {p['Step0']['found']}/{p['v1']['found']}/{p['v3']['found']}; false {p['Step0']['false']}/{p['v1']['false']}/{p['v3']['false']}. Research only.", (6, y), 0, .5, (0, 0, 0), 1)
        cv2.imwrite(str(O / 'figures' / f'{i}-step0-v1-v3.jpg'), np.vstack([img, h]), [cv2.IMWRITE_JPEG_QUALITY, 92])
    status('figures written (local only)', outputs=[str(O / 'figures')])


if __name__ == '__main__': dict(init=init, preflight=preflight, sheets=sheets, masks=masks, infer=infer, score=score, figures=figures)[sys.argv[1]]()
