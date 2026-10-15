"""Bounded learning check on the v2 acne input (<=150 optimizer steps, single process).

Phases: register (pre-registration, before any training) -> train (immutable
checkpoints every 25 steps, CURRENT pointer, resume) -> evaluate (step0 and the
pilot with ONE fixed product evaluator) -> compare (pixel-free evidence).
Research only: no product activation; production acne stays accepted:false,
file:null. Reads CDC files read-only; writes only to output-root and docs.
"""
import argparse, base64, hashlib, json, math, random, sys, time
from pathlib import Path

import numpy as np

STEP0_SHA256 = '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
STEPS, ACCUM, SEED = 150, 4, 20261015
TAKEOVER = 'audit-results/acne-takeover-20261015'
SCOPE_POS = ['55d380f7', '695ed248', '4a1762ee']
SCOPE_NEG = ['36e4010b', '20031f35', '02386f86', '0597e811', '0560bfd8', '0f3354ae', '0d891a03', '33da7a52', '02413bf9']


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_json(p): return json.loads(Path(p).read_text('utf8'))


def setup_paths(code_root, togg):
    sys.path[:0] = [str(code_root / 'scripts/skin-research'), str(code_root / 'services/core-api'),
                    str(togg / 'attune-live-test/audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee')]


PREREGISTRATION = dict(
    model=dict(start='CDC Step0 (takeover models/step0.safetensors)', sha256=STEP0_SHA256, architecture='existing YOLOX-S P2 (scripts/skin-research/yolox_p2.py), 1 class'),
    trainable='every head.* parameter except BatchNorm (stems, cls/reg/obj convs and preds); backbone/FPN frozen; all BatchNorm in eval mode',
    optimizer=dict(type='AdamW', lr=1e-4, weightDecay=.01, warmupSteps=30, schedule='cosine to step 150', clipNorm=5., microbatch=1, accumulation=ACCUM, steps=STEPS, seed=SEED),
    loss='existing YOLOX P2 loss (IoU box, BCE cls) with the existing SigmoidFocalObjectnessLoss: assigned positives always supervised; '
         'known negatives ONLY inside reviewed clean negative support; every other anchor UNKNOWN (zero gradient)',
    data='docs/acne-data-v2-manifest-20261015.json pilotOrder: 540 TRAIN positive product tiles + 60 reviewed-negative tiles (every 10th), fixed seed order',
    evaluation=dict(rule='one fixed product evaluator for Step0 and pilot: product photo_input tiles, conf obj*cls>=.30, hard NMS .30, current staging anatomical filter, IoU>=.50 one-to-one',
                    sets=dict(trainProbe='first 40 distinct TRAIN photos of the pilot order that have a replay snapshot (learning on training examples, NOT generalisation)',
                              development='Scope B 12 photos/14 fixed targets + 9 reviewed negative photos FP, and the 3 product-pass controls/29 targets (browser preflight; exposed development/regression)',
                              unusedEval='UNUSED_EVAL_CANDIDATE photos that pass the replayed product gates (eyewear UNKNOWN): pre-registered by rule before any model output; candidates outside labels are UNKNOWN, not FP')),
    decision=dict(A='development: >=2 targets gained and 0 lost vs Step0 over Scope B+controls, reviewed-negative FP <= Step0; unused eval: >=3 targets gained and lost <= gained/3; train probe recall not lower',
                  B='otherwise (including any development target lost or FP increase)',
                  frozen='no threshold, denominator or rule change after seeing results; no automatic longer training'),
    budget=dict(process='single heavy process under HeavyJobLease (1350 MiB private peak / 1600 MiB available, the CDC training precedent); the desktop VM ends every call after <=180 s, so training resumes from the 25-step checkpoints and evaluation resumes per photo', torchThreads=2, environment='python 3.10, torch 1.12.1 CPU, numpy 1.26.4, opencv-headless 4.12.0, scikit-image 0.25.2 (only CPU torch reachable here)',
                checkpoints='every 25 steps: model, optimizer moments, scheduler, torch/python/numpy RNG, CURRENT pointer'))


def build_net(togg):
    from safetensors.torch import load_file
    from yolox_p2 import build_yolox_p2_model
    path = togg / 'attune-live-test' / TAKEOVER / 'models/step0.safetensors'
    if sha_file(path) != STEP0_SHA256: raise RuntimeError('STEP0_HASH')
    net = build_yolox_p2_model(); net.load_state_dict(load_file(str(path)), strict=True); return net


# --------------------------------------------------------------------- train
def train(man, out, togg, lease, max_seconds):
    import cv2, torch
    from safetensors.torch import save_file, load_file
    from focal_objectness_loss import SigmoidFocalObjectnessLoss
    from acne_takeover_support import known_cells, strict_clean_mask
    from prepare_acne_data_v2 import map_windows
    target = out / 'pilot'
    if (target / 'model.safetensors').exists(): raise RuntimeError('COMPLETED_PILOT_NOT_REPEATED')
    target.mkdir(exist_ok=True)
    torch.set_num_threads(2); torch.manual_seed(SEED); np.random.seed(SEED); random.seed(SEED)
    net = build_net(togg)
    for name, p in net.named_parameters(): p.requires_grad_(name.startswith('head.') and '.bn.' not in name)
    trainable = [n for n, p in net.named_parameters() if p.requires_grad]
    frozen_before = hashlib.sha256(b''.join(t.detach().numpy().tobytes() for n, t in sorted(net.state_dict().items()) if not n.startswith('head.') or '.bn.' in n)).hexdigest()
    net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    focal = SigmoidFocalObjectnessLoss(alpha=.25, gamma=2); net.head.obj_focal_loss = focal
    opt = torch.optim.AdamW([p for p in net.parameters() if p.requires_grad], lr=1e-4, weight_decay=.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / 30 if s < 30 else .5 * (1 + math.cos(math.pi * (s - 30) / 120)))
    start, logs = 0, []
    if (target / 'CURRENT').exists():
        cur = read_json(target / 'CURRENT'); d = target / cur['directory']
        for n, h in cur['hashes'].items():
            if sha_file(d / n) != h: raise RuntimeError('CHECKPOINT_HASH')
        net.load_state_dict(load_file(str(d / 'model.safetensors')), strict=True); st = read_json(d / 'state.json'); tens = load_file(str(d / 'optimizer-rng.safetensors'))
        opt.load_state_dict(dict(state={int(i): {k: (tens[v['tensor']] if isinstance(v, dict) and 'tensor' in v else v) for k, v in s.items()} for i, s in st['optimizerState'].items()}, param_groups=st['paramGroups']))
        sched.load_state_dict(st['scheduler']); torch.set_rng_state(tens['torch_rng']); random.setstate((st['pythonRNG'][0], tuple(st['pythonRNG'][1]), st['pythonRNG'][2]))
        np.random.set_state((st['numpyRNG'][0], np.array(st['numpyRNG'][1], np.uint32), *st['numpyRNG'][2:])); start, logs = st['step'], st['logs']
    tiles = man['tiles']; order = man['pilotOrder']
    paths = {p['sha256']: p['path'] for p in man['photos']}
    inv = read_json(out.parent / 'acne-data-v2-20261015/inventory.json')
    abs_paths = {i['sha256']: map_windows(i['absolutePath'], togg) for i in inv['items'] + inv['negatives']}
    ledger = {r['sha256']: r for r in read_json(togg / 'attune-live-test' / TAKEOVER / 'inputs/original-reviewed-detector-data.json')['rows']}
    cache = {}

    def image_and_mask(s, negative):
        if cache.get('sha') != s:
            bgr = cv2.imread(str(abs_paths[s]))
            if negative:
                sup = cv2.imread(str(togg / 'attune-live-test' / TAKEOVER / 'train-clean-support' / (s + '.png')), cv2.IMREAD_GRAYSCALE)
                mask, weight = strict_clean_mask(ledger[s], bgr, reviewed_support=sup)
            else:
                mask = np.zeros(bgr.shape[:2], np.uint8); weight = np.zeros(bgr.shape[:2], np.float32)
            cache.clear(); cache.update(sha=s, bgr=bgr, mask=mask, weight=weight)
        return cache['bgr'], cache['mask'], cache['weight']

    def save(step):
        d = target / f'checkpoint-step-{step:06d}'; d.mkdir(exist_ok=False)
        save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(d / 'model.safetensors'))
        state = opt.state_dict(); tensors, states = {}, {}
        for i, vals in state['state'].items():
            states[str(i)] = {}
            for k, v in vals.items():
                if torch.is_tensor(v): tensors[f'{i}.{k}'] = v; states[str(i)][k] = {'tensor': f'{i}.{k}'}
                else: states[str(i)][k] = v
        tensors['torch_rng'] = torch.get_rng_state(); save_file(tensors, str(d / 'optimizer-rng.safetensors'))
        ns = np.random.get_state()
        (d / 'state.json').write_text(json.dumps(dict(step=step, optimizerState=states, paramGroups=state['param_groups'], scheduler=sched.state_dict(),
                                                      pythonRNG=list(random.getstate()), numpyRNG=[ns[0], ns[1].tolist(), *ns[2:]], logs=logs)), 'utf8')
        hashes = {n: sha_file(d / n) for n in ('model.safetensors', 'optimizer-rng.safetensors', 'state.json')}
        tmp = target / 'CURRENT.tmp'; tmp.write_text(json.dumps(dict(directory=d.name, step=step, hashes=hashes)), 'utf8'); tmp.replace(target / 'CURRENT')

    t0 = time.monotonic()
    for step in range(start, STEPS):
        lease.check(); opt.zero_grad(set_to_none=True); tot = 0.; npos = 0; nneg = 0
        for k in order[step * ACCUM:(step + 1) * ACCUM]:
            t = tiles[k]; neg = t['kind'] == 'negative'
            bgr, mask, weight = image_and_mask(t['sha256'], neg)
            a, b, c, d = t['rect']; x = np.full((384, 384, 3), 114, np.uint8); patch = bgr[b:d, a:c]; x[:patch.shape[0], :patch.shape[1]] = patch
            focal.known, focal.boundary_weights = known_cells(mask, weight, t['rect']); nneg += int(focal.known.sum())
            y = torch.zeros((1, max(1, len(t['boxes'])), 5))
            for i, bx in enumerate(t['boxes']):
                x0, y0, x1, y1 = bx['tile']; y[0, i] = torch.tensor([0, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0])
            npos += len(t['boxes'])
            loss = net(torch.from_numpy(x.transpose(2, 0, 1).copy()).float()[None], y)['total_loss']
            if not torch.isfinite(loss): raise RuntimeError('NONFINITE_LOSS')
            (loss / ACCUM).backward(); tot += float(loss.detach()) / ACCUM
        torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad], 5.); opt.step(); sched.step()
        logs.append(dict(step=step + 1, loss=tot, positiveBoxes=npos, knownNegativeCells=nneg, lr=sched.get_last_lr()[0], seconds=time.monotonic() - t0))
        if (step + 1) % 10 == 0 or step == start: print(json.dumps(logs[-1]), flush=True)
        if (step + 1) % 25 == 0:
            save(step + 1)
            per = (time.monotonic() - t0) / (step + 1 - start)
            if step + 1 < STEPS and time.monotonic() - t0 + 25 * per > max_seconds:
                return dict(partial=True, step=step + 1, secondsPerStep=per)
    frozen_after = hashlib.sha256(b''.join(t.detach().numpy().tobytes() for n, t in sorted(net.state_dict().items()) if not n.startswith('head.') or '.bn.' in n)).hexdigest()
    if frozen_after != frozen_before: raise RuntimeError('FROZEN_PARAMETERS_CHANGED')
    final = target / f'checkpoint-step-{STEPS:06d}'
    import shutil
    shutil.copyfile(final / 'model.safetensors', target / 'model.safetensors')
    receipt = dict(steps=STEPS, start=STEP0_SHA256, modelSHA256=sha_file(target / 'model.safetensors'), trainable=trainable, frozenStateSHA256=frozen_before,
                   frozenUnchanged=True, pilotOrderSHA256=man['pilotOrderSHA256'], logs=logs, resource=lease.receipt())
    (target / 'receipt.json').write_text(json.dumps(receipt, indent=1), 'utf8'); return receipt


# ------------------------------------------------------------------ evaluate
def evaluate(model_name, man, out, togg, code_root, lease, max_seconds):
    import cv2, torch
    from safetensors.torch import load_file
    from acne_takeover_support import current_product_masks, tile_rectangles, infer_tiles, one_to_one, strict_clean_mask
    from acne_box_support_staging import principled_accepted_boxes
    from source_skin_support import known_skin_scope
    from prepare_acne_data_v2 import map_windows
    torch.set_num_threads(2)
    net = build_net(togg)
    if model_name == 'pilot':
        r = read_json(out / 'pilot/receipt.json')
        if sha_file(out / 'pilot/model.safetensors') != r['modelSHA256']: raise RuntimeError('PILOT_HASH')
        net.load_state_dict(load_file(str(out / 'pilot/model.safetensors')), strict=True)
    net.eval()
    live = togg / 'attune-live-test' / TAKEOVER
    pre = {r['sha256']: r for r in read_json(live / 'browser-preflight.json')['rows']}
    ev = {r['sha256']: r for r in read_json(live / 'evaluation-step0/summary.json')['rows']}
    ledger = {r['sha256']: r for r in read_json(live / 'inputs/original-reviewed-detector-data.json')['rows']}
    scope = {r['sha256']: r for r in read_json(live / 'inputs/annotation-scope-manifest.json')['images']}
    replay = {json.loads(l)['sha256']: json.loads(l) for l in (out.parent / 'acne-data-v2-20261015/replay.jsonl').read_text('utf8').splitlines() if l.strip()}
    inv = read_json(out.parent / 'acne-data-v2-20261015/inventory.json'); abs_paths = {i['sha256']: map_windows(i['absolutePath'], togg) for i in inv['items']}

    def run(image, points, snapshot, quality_valid, truth, clean=None):
        raw, trace = infer_tiles(net, image, tile_rectangles(image, points), lease.check)
        pixel_id = hashlib.sha256(cv2.cvtColor(image, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
        ok, png = cv2.imencode('.png', image)
        payload = dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=pixel_id, landmarks=points,
                       meshes=snapshot['meshes'], exclusions=snapshot['exclusions'], qualityValid=quality_valid, conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0))
        masks = current_product_masks(payload)
        assigned, _ = principled_accepted_boxes(raw, masks['acne_envelopes'], masks['acne_skin'], masks['hair'], masks['acne_exclusion'], pixel_id, masks['scale'], masks['origin'],
                                                visible_regions=list(snapshot['meshes']), landmarks=points, source_shape=image.shape[:2], bgr=image)
        final = [b for v in assigned.values() for b in v]; pred = [[b['x'], b['y'], b['x'] + b['width'], b['y'] + b['height']] for b in final]
        pairs = one_to_one(truth, pred); matched = sorted({p[0] for p in pairs}); paired = {p[1] for p in pairs}; fps = 0; unknown = 0
        for i, b in enumerate(pred):
            if i in paired: continue
            cx, cy = int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2)
            if clean is not None and 0 <= cy < clean.shape[0] and 0 <= cx < clean.shape[1] and clean[cy, cx]: fps += 1
            else: unknown += 1
        return dict(targets=len(truth), matched=matched, pairs=pairs, cleanFP=fps, unknownCandidates=unknown, candidates=len(pred),
                    bands=['micro' if max(b[2] - b[0], b[3] - b[1]) < 8 else 'small' if max(b[2] - b[0], b[3] - b[1]) < 16 else 'medium' for b in truth])

    t0 = time.monotonic(); part = out / f'evaluation-{model_name}.jsonl'
    done = {(r['set'], r['sha256']) for r in map(json.loads, part.read_text('utf8').splitlines())} if part.exists() else set()
    sink = part.open('a', encoding='utf8')
    results = dict(model=model_name, development=[], unusedEval=[], trainProbe=[])
    def emit(key, row):
        sink.write(json.dumps(dict(set=key, **row)) + '\n'); sink.flush()
        if time.monotonic() - t0 > max_seconds: raise TimeoutError('CHUNK_DONE')
    for s, a in pre.items():
        cohort = 'scopeB' if s[:8] in SCOPE_POS + SCOPE_NEG else 'controls' if a['cohort'] == 'heldout-train' and ev[s]['fullStaticProductPass'] else None
        if not cohort or ('development', s) in done: continue
        lease.check(); snap = a.get('snapshot')
        # As the CDC evaluator: snapshot pixels when the product produced a snapshot, else the source file.
        image = cv2.imread(str(live / 'product-inputs' / s / 'snapshot.png')) if snap else cv2.imread(str(map_windows(a['path'], togg)))
        if image is None or image.shape[1] != a['width'] or image.shape[0] != a['height']: raise RuntimeError('DEV_IMAGE:' + s[:8])
        r = ledger[s]; anns = [v for v in scope[s]['annotations'] if v['scopeCategory'] == 'IN_SCOPE_VISIBLE_REGION'] if s in scope else r.get('annotations', [])
        truth = [v['box'] for v in anns]; clean = None
        if r.get('negativeROI') and not r.get('annotations') and a['alignment'].get('landmarks'):
            clean = known_skin_scope({**r, 'landmarks': a['alignment']['landmarks']}, image) > 0
        if not snap: emit('development', dict(sha256=s, cohort=cohort, valid=False, targets=len(truth), matched=[], cleanFP=0, bands=[])); continue
        row = run(image, a['alignment']['landmarks'], snap, a['quality']['isValid'], truth, clean)
        emit('development', dict(sha256=s, cohort=cohort, valid=bool(ev[s]['fullStaticProductPass']), **row)); print(json.dumps(dict(model=model_name, set='dev', sha=s[:8], hit=len(row['matched']), t=row['targets'], fp=row['cleanFP'])), flush=True)
    photos = {p['sha256']: p for p in man['photos']}
    unused = [p for p in man['photos'] if p['role'] == 'UNUSED_EVAL_CANDIDATE' and p['replay']['gatePassedWithoutEyewear']]
    seen, probe = set(), []
    for k in man['pilotOrder']:
        s = man['tiles'][k]['sha256']
        if s in seen or s not in photos: continue
        seen.add(s)
        if replay.get(s, {}).get('snapshot'): probe.append(photos[s])
        if len(probe) == 40: break
    for key, rows in (('unusedEval', unused), ('trainProbe', probe)):
        for p in rows:
            if (key, p['sha256']) in done: continue
            lease.check(); rp = replay[p['sha256']]; image = cv2.imread(str(abs_paths[p['sha256']]))
            row = run(image, rp['landmarks'], rp['snapshot'], rp['quality']['isValid'], [t['box'] for t in p['targets']])
            row['targetIds'] = [t['id'] for t in p['targets']]
            emit(key, dict(sha256=p['sha256'], **row)); print(json.dumps(dict(model=model_name, set=key, sha=p['sha256'][:8], hit=len(row['matched']), t=row['targets'])), flush=True)
    sink.close()
    for r in map(json.loads, part.read_text('utf8').splitlines()): results[r.pop('set')].append(r)
    expected = dict(development=None, unusedEval=len(unused), trainProbe=len(probe))
    if any(v is not None and len(results[k]) != v for k, v in expected.items()): raise RuntimeError('EVALUATION_INCOMPLETE')
    results['setSizes'] = {k: len(results[k]) for k in ('development', 'unusedEval', 'trainProbe')}
    (out / f'evaluation-{model_name}.json').write_text(json.dumps(results), 'utf8')


def summarize(res):
    def agg(rows):
        return dict(photos=len(rows), targets=sum(r['targets'] for r in rows), matched=sum(len(r['matched']) for r in rows),
                    cleanFP=sum(r.get('cleanFP', 0) for r in rows), unknownCandidates=sum(r.get('unknownCandidates', 0) for r in rows),
                    bands={b: dict(targets=sum(x == b for r in rows for x in r.get('bands', [])),
                                   matched=sum(r['bands'][i] == b for r in rows for i in r['matched'])) for b in ('micro', 'small', 'medium')})
    return dict(scopeB=agg([r for r in res['development'] if r['cohort'] == 'scopeB']), controls=agg([r for r in res['development'] if r['cohort'] == 'controls']),
                unusedEval=agg(res['unusedEval']), trainProbe=agg(res['trainProbe']))


def compare(out, docs_evidence, prereg_path, man_path):
    a, b = read_json(out / 'evaluation-step0.json'), read_json(out / 'evaluation-pilot.json')
    def ids(res, key):
        return {(r['sha256'], i) for r in res[key] for i in r['matched']}
    delta = {}
    for key in ('development', 'unusedEval', 'trainProbe'):
        sa, sb = ids(a, key), ids(b, key); delta[key] = dict(gained=sorted([s[:8], i] for s, i in sb - sa), lost=sorted([s[:8], i] for s, i in sa - sb))
    sa, sb = summarize(a), summarize(b)
    dev_gain, dev_loss = len(delta['development']['gained']), len(delta['development']['lost'])
    fp_ok = sb['scopeB']['cleanFP'] <= sa['scopeB']['cleanFP']
    un_gain, un_loss = len(delta['unusedEval']['gained']), len(delta['unusedEval']['lost'])
    probe_ok = sb['trainProbe']['matched'] >= sa['trainProbe']['matched']
    outcome = 'A' if dev_gain >= 2 and dev_loss == 0 and fp_ok and un_gain >= 3 and un_loss <= un_gain / 3 and probe_ok else 'B'
    receipt = read_json(out / 'pilot/receipt.json')
    ev = dict(preregistrationSHA256=sha_file(prereg_path), manifestSHA256=sha_file(man_path), step0=sa, pilot=sb, perTarget=delta,
              decisionInputs=dict(developmentGained=dev_gain, developmentLost=dev_loss, reviewedNegativeFPNotHigher=fp_ok, unusedGained=un_gain, unusedLost=un_loss, trainProbeNotLower=probe_ok),
              outcome=outcome, pilotRun=dict(modelSHA256=receipt['modelSHA256'], steps=receipt['steps'], trainable=len(receipt['trainable']), frozenUnchanged=receipt['frozenUnchanged'],
                                          lossFirst=receipt['logs'][0]['loss'], lossLast=receipt['logs'][-1]['loss'], seconds=receipt['logs'][-1]['seconds']),
              productActivation=False, productionAcne=dict(accepted=False, file=None))
    Path(docs_evidence).write_text(json.dumps(ev, indent=1) + '\n', 'utf8'); print(json.dumps(dict(outcome=outcome, step0=sa, pilot=sb, decision=ev['decisionInputs'])))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('phase', choices=['register', 'train', 'evaluate', 'compare'])
    ap.add_argument('--output-root', required=True); ap.add_argument('--manifest', required=True); ap.add_argument('--preregistration', required=True)
    ap.add_argument('--model', choices=['step0', 'pilot']); ap.add_argument('--evidence')
    ap.add_argument('--max-seconds', type=float, default=140., help='per-call compute chunk; work resumes from checkpoints/partial results')
    ap.add_argument('--code-root', default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args(); code_root = Path(a.code_root).resolve(); togg = code_root.parent; out = Path(a.output_root).resolve(); out.mkdir(parents=True, exist_ok=True)
    if out == togg / 'attune-live-test' or (togg / 'attune-live-test') in out.parents: raise RuntimeError('OUTPUT_IN_CDC_CHECKOUT')
    setup_paths(code_root, togg); man = read_json(a.manifest); pre = Path(a.preregistration)
    if a.phase == 'register':
        if pre.exists(): raise RuntimeError('PREREGISTRATION_FROZEN')
        pre.write_text(json.dumps(dict(**PREREGISTRATION, manifestSHA256=sha_file(a.manifest), pilotOrderSHA256=man['pilotOrderSHA256'],
                                       codeSHA256=sha_file(Path(__file__))), indent=1) + '\n', 'utf8'); print(sha_file(pre)); return
    reg = read_json(pre); code_sha = sha_file(Path(__file__))
    amendments = [read_json(p) for p in sorted(pre.parent.glob(pre.stem + '-amendment*.json'))]
    allowed = {reg['codeSHA256']} | {m['codeSHA256'] for m in amendments if m.get('reason') and m.get('changesDecisionRules') is False}
    if reg['manifestSHA256'] != sha_file(a.manifest) or code_sha not in allowed: raise RuntimeError('PREREGISTRATION_MISMATCH')
    if a.phase == 'compare': compare(out, a.evidence, pre, a.manifest); return
    from heavy_job_lease import HeavyJobLease
    with HeavyJobLease('CLAUDE-acne-v2-' + a.phase + '-' + (a.model or 'pilot'), peak_mib=1350, minimum_available_mib=1600, memory_metric='private') as lease:
        if a.phase == 'train': print(json.dumps({k: v for k, v in train(man, out, togg, lease, a.max_seconds).items() if k not in ('logs', 'resource')}))
        else:
            try: evaluate(a.model, man, out, togg, code_root, lease, a.max_seconds)
            except TimeoutError: print(json.dumps(dict(partial=True)))


if __name__ == '__main__':
    main()
