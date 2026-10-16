"""Acne v3: multi-source training with the standard background rule plus safeguards (owner-approved 2026-10-15).

Owner decision: unlabeled skin may be background ("standard method + safeguards") because no source supplies verified
clean skin and the calibrated visual review failed its own gate. Safeguards:
  * scar/post-acne marks, comedones, region-type classes (redness, oiliness, ...), conflicting and tile-cut lesions -> IGNORED
  * small confounder labels (mole, freckle, dark spot, pigmentation, pore) not touching an acne label -> explicit NEGATIVE
  * missing-label guard: anchors the current model already scores >= GUARD that lie outside every label get NO gradient
  * independent test = every photo group that touches the "Skin care v5" publisher set (never trained), plus the frozen
    product-chain sets of the v2 pilot (Scope B / controls development, 20 unused-eval photos)

Phases: plan | register | train | evaltiles | evalproduct | decide.  Everything resumable within <=180 s calls.
Only hashes, boxes and metrics are written to docs; images, tiles and checkpoints stay in audit-results (Git-ignored).
"""
import argparse, hashlib, io, json, math, random, sys, time, zipfile, collections
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import acne_inventory_v3 as inv

SEED = 20261015
STEPS, ACCUM, CKPT_EVERY = 1800, 8, 50
SELECT_EVERY, VAL_PHOTOS = 300, 150
CONTROLLED_RUN = dict(
    name='acne-v3-fix-objloss-20261016',
    question='Does implementing the declared standard background rule correctly change the product-chain regression of the failed v3 run?',
    onlyChange='objectness loss: shared-head mean-over-known-negatives x20 + sigmoid focal (alpha .25, gamma 2)  ->  standard YOLOX BCE summed over positives + known negatives / num_fg. '
               'This changes BOTH the normalisation AND focal->BCE weighting; an effect cannot be attributed to the measured ~180x hard-negative gradient ratio alone.',
    unchanged='plan-v3.json (same SHA), groups, per-step sample order and seed, augmentation, scale targets, missing-label guard, trainable layers, BatchNorm handling, AdamW, LR 2e-4, '
              'warmup 100, cosine over 1,800 steps (not compressed), ACCUM 8, conf .30, NMS .30, evaluators',
    start='CDC Step0 (SHA 18e94a95...), fresh optimizer; the failed run (code 688301e7..., step-001250) is preserved and NOT resumed',
    firstStage='stop after optimizer step 300 (LR at stop = schedule value at step 300 of 1,800); no automatic continuation',
    comparisons='validation (150 photos, IoU .30/.50, conf .30) and unchanged v2 product chain (IoU .50 primary; .30 reported separately) for Step0, failed step-300 and fixed step-300; '
                'Step0 and failed-run records are reused where already saved',
    readout='targets found, false candidates (reviewed negatives, unmatched), gained/lost targets and matched-box area ratio are read together; '
            'fewer false candidates or a lower loss alone is not success; a failed short run is not proof that the architecture cannot learn',
    sealed='Skin care v5 independent test stays closed; frozen CDC acceptance (acceptance.json 90dc84fa..., 2026-10-10) unchanged; production stays accepted:false')
# First stage of the corrected-rule run stops here; the 1,800-step LR schedule is NOT compressed.
STOP_AT = 300
LR, WARMUP = 2e-4, 100
GUARD = .50
# Objectness background term. The owner approved "standard method": unlabeled skin is background as in public detectors,
# i.e. YOLOX objectness BCE summed over positive AND background anchors / num_fg. The 2026-10-15 run (code 688301e7...)
# instead reused the shared head's sparse-negative normalisation (mean over known negatives x 20 + focal). With ~12k known
# anchors per tile that made the push on a hard background anchor ~0.6% of the standard YOLOX value (measured median
# 0.0056 on step-900 training tiles). 'standard-yolox-bce' implements the declared rule; 'shared-head-mean-x20' reproduces
# the failed run for audit only.
OBJ_LOSS = 'standard-yolox-bce'
TILE = 384
TEST_ARCHIVE = 'Skin care.v5i.coco.zip'
TRAIN_ARCHIVES = ['SmartSkinCare.v8i.coco.zip', 'Skin-Problem-Detection-Relabel-Clean3.v1-skin-disease-detection-.coco.zip',
                  'Skin Analysis.v11-augmentation_version.coco-segmentation.zip', 'ciltanalizi.v12i.coco.zip',
                  'skin_face_detection.v1i.coco.zip', 'Wrinkles Detector.v2i.coco-segmentation.zip']
CONFOUNDER = {'mole', 'freckles', 'dark-spots', 'pigmentation', 'hyperpigmentation', 'enlarged pores', 'englarged-pores', 'pores', 'gozenek'}
REGION_LIKE = {'redness', 'skin-redness', 'kizariklik', 'oily', 'oily-skin', 'oilness', 'dry-skin', 'pul', 'texture', 'melasma', 'vascular'}
DECISION = dict(
    selection='checkpoints at steps 300,600,...,1800 (and Step0); the one with the best validation F1 (IoU>=.30, conf>=.30) is the candidate; test sets are never read for selection',
    productGate='frozen CDC native-acne-acceptance (SHA 90dc84fa...): precision, recall and F1 >= .80 at one-to-one IoU>=.30, unignored unmatched = FP, '
                '>=50 positive + >=50 negative independent photos, negative FP <= 1/photo',
    outcome=dict(A='candidate meets the productGate numbers on the cross-source test AND, on the product-chain sets, gains targets vs Step0 with Scope B '
                   'reviewed-negative FP <= Step0 (3) and unusedEval unmatched candidates <= 1.5 x Step0 (254)',
                 Bplus='candidate is better than Step0 on cross-source F1 by >= .10 and does not violate the product-chain FP limits above, but misses the productGate numbers',
                 B='otherwise'),
    frozen='no change of thresholds, IoU, denominators, test sets or steps after the first test prediction')


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_json(p): return json.loads(Path(p).read_text('utf8'))


def box_w(b): return b[2] - b[0]
def box_h(b): return b[3] - b[1]
def iou(a, b): return inv.iou(a, b)
def overlaps(a, b): return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def split_labels(anns, w):
    """-> positives, ignore, confounder negatives (source pixels). Never renames a conflicting label."""
    acne = [a for a in anns if inv.role_of(a['cls']) == 'acne']
    rest = [a for a in anns if inv.role_of(a['cls']) != 'acne']
    pos, ign, neg = [], [], []
    for a in acne:
        b = a['box']
        if box_w(b) > .15 * w: ign.append(b); continue                       # region box, not a lesion
        if any(iou(b, o['box']) >= .5 for o in rest): ign.append(b); continue  # same spot, two classes -> UNKNOWN
        pos.append(b)
    for o in rest:
        c, b = inv.norm(o['cls']), o['box']
        if inv.role_of(o['cls']) in ('comedo', 'scar_mark') or c in REGION_LIKE: ign.append(b)
        elif c in CONFOUNDER and box_w(b) <= .08 * w and not any(overlaps(b, a['box']) for a in acne): neg.append(b)
        # other classes (wrinkle, eyebag, face parts, dark circle) are ordinary background under the owner's rule
    return pos, ign, neg


def plan(out, v2_manifest):
    rows = [json.loads(l) for a in TRAIN_ARCHIVES + [TEST_ARCHIVE] for l in (out / 'hash' / (a + '.ndjson')).read_text().splitlines()]
    rows = [r for r in rows if not r.get('decodeError') and r.get('anns') is not None]
    gid = read_json(out / 'groups.json')['groupOf']; key = lambda r: r['archive'] + '::' + r['path']
    v2 = read_json(v2_manifest)
    reserved_sha = {p['sha256'] for p in v2['photos'] if p['role'] != 'TRAIN_AUXILIARY'} | set(v2.get('devShas', [])) | set(v2.get('priorValidationShas', []))
    test_groups = {gid[key(r)] for r in rows if r['archive'] == TEST_ARCHIVE}
    reserved_groups = {gid[key(r)] for r in rows if r['archive'] == 'SmartSkinCare.v8i.coco.zip' and r['fileSha'] in reserved_sha}
    smart_sides = []
    items = []
    for r in rows:
        g = gid[key(r)]; pos, ign, neg = split_labels(r['anns'], r['w'])
        role = 'TEST_CROSS_SOURCE' if g in test_groups else 'RESERVED_V2_EVAL' if g in reserved_groups else 'TRAIN'
        if role == 'TEST_CROSS_SOURCE' and r['archive'] != TEST_ARCHIVE: role = 'EXCLUDED_TEST_GROUP_COPY'
        items.append(dict(archive=r['archive'], path=r['path'], fileSha=r['fileSha'], group=g, w=r['w'], h=r['h'], role=role, pos=pos, ign=ign, neg=neg))
        if role == 'TRAIN' and r['archive'] == 'SmartSkinCare.v8i.coco.zip' and pos:
            smart_sides.append(float(np.median([max(box_w(b), box_h(b)) for b in pos])))
    # validation: 10% of TRAIN groups (deterministic by group hash), used only for checkpoint selection
    for it in items:
        if it['role'] == 'TRAIN' and int(hashlib.sha256(it['group'].encode()).hexdigest(), 16) % 10 == 0: it['role'] = 'VALIDATION'
    # one copy per (group, archive) photo family is enough; augmented copies stay in the same role through the group
    c = collections.Counter((i['role'], bool(i['pos'])) for i in items)
    target = sorted(smart_sides)
    p = dict(version='acne-v3-plan-1', rule='owner-approved standard background + safeguards', decision=DECISION, trainArchives=TRAIN_ARCHIVES, testArchive=TEST_ARCHIVE,
             targetLesionSidePx=dict(source='median Pimple side per SmartSkinCare TRAIN photo (product-like 1280 frames)', values=target),
             counts={f'{k[0]}:{"acne" if k[1] else "noAcne"}': v for k, v in sorted(c.items())},
             positiveBoxes={r: sum(len(i['pos']) for i in items if i['role'] == r) for r in ('TRAIN', 'VALIDATION', 'TEST_CROSS_SOURCE')},
             confounderNegatives={r: sum(len(i['neg']) for i in items if i['role'] == r) for r in ('TRAIN', 'VALIDATION', 'TEST_CROSS_SOURCE')},
             items=items)
    (out / 'plan-v3.json').write_text(json.dumps(p)); print(json.dumps({k: v for k, v in p.items() if k not in ('items', 'targetLesionSidePx', 'decision')}, indent=1))
    print('targetSide median', float(np.median(target)) if target else None, 'n', len(target))


# ------------------------------------------------------------------ tiles
def scale_for(it, target_side):
    s = [max(box_w(b), box_h(b)) for b in it['pos']]
    if not s: return None
    return float(np.clip(target_side / float(np.median(s)), .15, 1.5))


def make_tile(img, it, s, rng, focus=True, aug=True):
    import cv2
    h, w = img.shape[:2]; S = lambda b: [v * s for v in b]
    im = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    H, W = im.shape[:2]; pos = [S(b) for b in it['pos']]; ign = [S(b) for b in it['ign']]; neg = [S(b) for b in it['neg']]
    if focus and pos:
        b = pos[rng.randrange(len(pos))]; cx, cy = (b[0] + b[2]) / 2 + rng.uniform(-150, 150), (b[1] + b[3]) / 2 + rng.uniform(-150, 150)
    elif neg and rng.random() < .7:
        b = neg[rng.randrange(len(neg))]; cx, cy = (b[0] + b[2]) / 2 + rng.uniform(-150, 150), (b[1] + b[3]) / 2 + rng.uniform(-150, 150)
    else: cx, cy = rng.uniform(0, W), rng.uniform(0, H)
    x0 = int(np.clip(cx - TILE / 2, 0, max(0, W - TILE))); y0 = int(np.clip(cy - TILE / 2, 0, max(0, H - TILE)))
    rect = [x0, y0, x0 + TILE, y0 + TILE]
    x = np.full((TILE, TILE, 3), 114, np.uint8); patch = im[y0:y0 + TILE, x0:x0 + TILE]; x[:patch.shape[0], :patch.shape[1]] = patch
    known = np.ones((TILE, TILE), np.uint8); targets = []
    def local(b): return [b[0] - x0, b[1] - y0, b[2] - x0, b[3] - y0]
    def clear(b, grow=.3):
        g = grow * max(box_w(b), box_h(b), 4); a = [int(max(0, b[0] - g)), int(max(0, b[1] - g)), int(min(TILE, b[2] + g + 1)), int(min(TILE, b[3] + g + 1))]
        if a[2] > a[0] and a[3] > a[1]: known[a[1]:a[3], a[0]:a[2]] = 0
    for b in pos:
        if not overlaps(b, rect): continue
        l = local(b); c = [max(0, l[0]), max(0, l[1]), min(TILE, l[2]), min(TILE, l[3])]
        kept = max(0, box_w(c)) * max(0, box_h(c)) / max(1e-6, box_w(l) * box_h(l))
        if kept >= .7 and box_w(c) >= 2 and box_h(c) >= 2: targets.append(c)
        else: clear(l)                                   # cut lesion -> UNKNOWN
    for b in ign:
        if overlaps(b, rect): clear(local(b))
    if aug:
        if rng.random() < .5:
            x = x[:, ::-1].copy(); known = known[:, ::-1].copy(); targets = [[TILE - t[2], t[1], TILE - t[0], t[3]] for t in targets]
        if rng.random() < .8:
            a_, b_ = rng.uniform(.85, 1.15), rng.uniform(-15, 15); x = np.clip(x.astype(np.float32) * a_ + b_, 0, 255).astype(np.uint8)
        if rng.random() < .3: x = cv2.GaussianBlur(x, (0, 0), rng.uniform(.3, 1.0))
        if rng.random() < .3:
            ok, enc = cv2.imencode('.jpg', x, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(60, 95)]); x = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return x, known, targets


def standard_background_loss_class():
    import torch
    import torch.nn.functional as F
    from focal_objectness_loss import SigmoidFocalObjectnessLoss

    class StandardBackgroundObjLoss(SigmoidFocalObjectnessLoss):
        """Per-anchor BCE pre-scaled so the shared head's normalisation
        (pos: sum/num_fg; known neg: mean x 20) equals standard YOLOX: sum BCE over positives + known negatives / num_fg.
        Batch size 1 only (num_fg of the head == positives in this tensor). UNKNOWN anchors still get zero loss."""
        W_NEG_IN_HEAD = 20.0

        def forward(self, logits, truth):
            if self.known is None or self.known.shape != logits.shape: raise ValueError('KNOWN_MASK_REQUIRED')
            is_pos = truth > 0; is_neg = self.known & ~is_pos
            n_pos = max(float(is_pos.sum()), 1.0); n_neg = max(float(is_neg.sum()), 1.0)
            bce = F.binary_cross_entropy_with_logits(logits, truth, reduction='none')
            scale = torch.where(is_pos, torch.ones_like(bce), torch.full_like(bce, n_neg / (self.W_NEG_IN_HEAD * n_pos)))
            self.last_metrics = dict(num_pos=int(n_pos), num_known_neg=int(n_neg), mode='standard-yolox-bce')
            return bce * scale * (is_pos | is_neg).to(bce.dtype)

        def record_normalized(self, **k): pass
    return StandardBackgroundObjLoss


def make_obj_loss(mode):
    from focal_objectness_loss import SigmoidFocalObjectnessLoss
    if mode == 'standard-yolox-bce': return standard_background_loss_class()()
    if mode == 'shared-head-mean-x20': return SigmoidFocalObjectnessLoss(alpha=.25, gamma=2)
    raise ValueError(mode)


def known_cells_tile(known, targets):
    import torch
    out = []
    for stride in (4, 8, 16, 32):
        c = (np.arange(TILE // stride) + .5) * stride; xx, yy = np.meshgrid(c, c); xi = xx.astype(int); yi = yy.astype(int)
        out.append((known[yi, xi] > 0).ravel())
    return torch.from_numpy(np.concatenate(out)[:, None])


def anchor_centers():
    cs = []
    for stride in (4, 8, 16, 32):
        c = (np.arange(TILE // stride) + .5) * stride; xx, yy = np.meshgrid(c, c); cs.append(np.stack([xx.ravel(), yy.ravel()], 1))
    return np.concatenate(cs)


class Images:
    """Original archives on the desktop, or the byte-identical repacked parts (pack-index.json) in the cloud workspace."""
    def __init__(self, root):
        self.root = Path(root); self.z = {}; idx = self.root / 'pack-index.json'
        self.index = {(a, p): n for a, p, n in read_json(idx)} if idx.exists() else None
    def read(self, archive, path):
        import cv2
        if self.index is None:
            z = self.z.setdefault(archive, zipfile.ZipFile(self.root / archive)); b = z.read(path)
        else:
            n = self.index[(archive, path)]; z = self.z.setdefault(n, zipfile.ZipFile(self.root / f'part{n:02d}.zip')); b = z.read(archive + '/' + path)
        return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)


# ------------------------------------------------------------------ model
def setup_paths(code_root, togg):
    sys.path[:0] = [str(code_root / 'scripts/skin-research'), str(code_root / 'services/core-api'),
                    str(togg / 'attune-live-test/audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee')]


STEP0_SHA256 = '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
STEP0_PATH = None


def step0_net(togg):
    from safetensors.torch import load_file
    from yolox_p2 import build_yolox_p2_model
    path = STEP0_PATH or togg / 'attune-live-test/audit-results/acne-takeover-20261015/models/step0.safetensors'
    if sha_file(path) != STEP0_SHA256: raise RuntimeError('STEP0_HASH')
    net = build_yolox_p2_model(); net.load_state_dict(load_file(str(path)), strict=True); return net


def trainable_name(n): return (n.startswith('head.') or n.startswith('backbone.') and ('.lateral_conv' in n or '.reduce_conv' in n or '.C3_' in n or '.bu_conv' in n)) and '.bn.' not in n


def train(plan_p, out, togg, lease, max_seconds):
    import cv2, torch
    from safetensors.torch import save_file, load_file
    from focal_objectness_loss import SigmoidFocalObjectnessLoss
    P = read_json(plan_p); items = [i for i in P['items'] if i['role'] == 'TRAIN']
    acne = [i for i in items if i['pos']]; conf = [i for i in items if not i['pos'] and i['neg']]
    targets = P['targetLesionSidePx']['values']
    target = out / 'v3'; target.mkdir(exist_ok=True)
    if (target / 'DONE').exists() or (target / f'STAGE-{STOP_AT}.json').exists(): raise RuntimeError('COMPLETED_RUN_NOT_REPEATED')
    torch.set_num_threads(2); torch.manual_seed(SEED)
    net = step0_net(togg)
    for n, p in net.named_parameters(): p.requires_grad_(trainable_name(n))
    tnames = [n for n, p in net.named_parameters() if p.requires_grad]
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    focal = make_obj_loss(OBJ_LOSS); net.head.obj_focal_loss = focal
    params = [p for p in net.parameters() if p.requires_grad]
    frozen_sha = lambda: hashlib.sha256(b''.join(v.detach().cpu().numpy().tobytes() for n, v in sorted(net.state_dict().items()) if n not in tnames)).hexdigest()
    step0_trainable = {n: p.detach().clone() for n, p in net.named_parameters() if p.requires_grad}
    frozen0 = frozen_sha()
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=.01)
    lam = lambda s: (s + 1) / WARMUP if s < WARMUP else .05 + .95 * .5 * (1 + math.cos(math.pi * (s - WARMUP) / (STEPS - WARMUP)))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lam)
    start, logs = 0, []
    if (target / 'CURRENT').exists():
        cur = read_json(target / 'CURRENT'); d = target / cur['directory']
        for n, h in cur['hashes'].items():
            if sha_file(d / n) != h: raise RuntimeError('CHECKPOINT_HASH')
        net.load_state_dict(load_file(str(d / 'model.safetensors')), strict=True); st = read_json(d / 'state.json'); tens = load_file(str(d / 'optim.safetensors'))
        opt.load_state_dict(dict(state={int(i): {k: (tens[v['tensor']] if isinstance(v, dict) and 'tensor' in v else v) for k, v in s.items()} for i, s in st['optimizerState'].items()}, param_groups=st['paramGroups']))
        sched.load_state_dict(st['scheduler']); start, logs = st['step'], st['logs']
    imgs = Images(ROOT)
    centers = anchor_centers()

    def image(it): return imgs.read(it['archive'], it['path'])

    def save(step):
        if frozen_sha() != frozen0: raise RuntimeError('FROZEN_PARAMETERS_CHANGED')
        d = target / f'step-{step:06d}'; d.mkdir(exist_ok=True)
        save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(d / 'model.safetensors'))
        state = opt.state_dict(); tensors, states = {}, {}
        for i, vals in state['state'].items():
            states[str(i)] = {}
            for k, v in vals.items():
                if torch.is_tensor(v): tensors[f'{i}.{k}'] = v; states[str(i)][k] = {'tensor': f'{i}.{k}'}
                else: states[str(i)][k] = v
        save_file(tensors, str(d / 'optim.safetensors'))
        (d / 'state.json').write_text(json.dumps(dict(step=step, optimizerState=states, paramGroups=state['param_groups'], scheduler=sched.state_dict(), logs=logs)))
        hashes = {n: sha_file(d / n) for n in ('model.safetensors', 'optim.safetensors', 'state.json')}
        tmp = target / 'CURRENT.tmp'; tmp.write_text(json.dumps(dict(directory=d.name, step=step, hashes=hashes))); tmp.replace(target / 'CURRENT')
        prev = sorted(target.glob('step-*'))
        for old in prev:  # keep optimizer moments only for the latest checkpoint (disk), models of every checkpoint are kept for selection
            if old != d and (old / 'optim.safetensors').exists(): (old / 'optim.safetensors').unlink()

    t0 = time.monotonic()
    for step in range(start, STEPS):
        if step >= STOP_AT: break
        lease.check(); rng = random.Random(SEED * 1000003 + step)   # stateless per step: resume-exact
        opt.zero_grad(set_to_none=True); tot = 0.; npos = nk = nguard = 0
        for j in range(ACCUM):
            it = acne[rng.randrange(len(acne))] if (rng.random() < .8 or not conf) else conf[rng.randrange(len(conf))]
            img = image(it)
            side = targets[rng.randrange(len(targets))] * rng.uniform(.8, 1.25)
            s = scale_for(it, side)
            if s is None:  # confounder-only photo: scale by its archive's typical lesion size relative to the target
                s = float(np.clip(side / max(4., .02 * it['w']), .15, 1.5))
            x, known, tg = make_tile(img, it, s, rng, focus=bool(it['pos']) and rng.random() < .85)
            k = known_cells_tile(known, tg)
            ten = torch.from_numpy(x.transpose(2, 0, 1).copy()).float()[None]
            # missing-label guard: confident current predictions outside every label get no gradient
            net.eval()
            with torch.no_grad(): o = net(ten)[0]
            net.train()
            for m in net.modules():
                if isinstance(m, torch.nn.BatchNorm2d): m.eval()
            score = (o[:, 4] * o[:, 5]).numpy()
            inside = np.zeros(len(centers), bool)
            for t in tg: inside |= (centers[:, 0] >= t[0] - 4) & (centers[:, 0] <= t[2] + 4) & (centers[:, 1] >= t[1] - 4) & (centers[:, 1] <= t[3] + 4)
            g = (score >= GUARD) & ~inside; nguard += int(g.sum())
            k = k & torch.from_numpy(~g)[:, None]
            focal.known = k; focal.boundary_weights = k.float(); nk += int(k.sum())
            y = torch.zeros((1, max(1, len(tg)), 5))
            for i, t in enumerate(tg): y[0, i] = torch.tensor([0, (t[0] + t[2]) / 2, (t[1] + t[3]) / 2, t[2] - t[0], t[3] - t[1]])
            npos += len(tg)
            loss = net(ten, y)['total_loss']
            if not torch.isfinite(loss): raise RuntimeError('NONFINITE_LOSS')
            (loss / ACCUM).backward(); tot += float(loss.detach()) / ACCUM
        if not all(p.grad is None or torch.isfinite(p.grad).all() for p in params): raise RuntimeError('NONFINITE_GRADIENT')
        gnorm = float(torch.nn.utils.clip_grad_norm_(params, 5.)); opt.step(); sched.step()
        logs.append(dict(step=step + 1, loss=round(tot, 4), pos=npos, known=nk, guarded=nguard, lr=sched.get_last_lr()[0], gradNorm=round(gnorm, 4)))
        if (step + 1) % 10 == 0: print(json.dumps(dict(**logs[-1], sec=round(time.monotonic() - t0, 1))), flush=True)
        if (step + 1) % CKPT_EVERY == 0:
            save(step + 1)
            per = (time.monotonic() - t0) / (step + 1 - start)
            if step + 1 < min(STEPS, STOP_AT) and time.monotonic() - t0 + CKPT_EVERY * per > max_seconds: return dict(partial=True, step=step + 1, secPerStep=round(per, 2))
    if frozen_sha() != frozen0: raise RuntimeError('FROZEN_PARAMETERS_CHANGED')
    cur = dict(net.named_parameters()); unchanged = [n for n in tnames if torch.equal(cur[n].detach(), step0_trainable[n])]
    if unchanged: raise RuntimeError('TRAINABLE_NOT_UPDATED:' + ','.join(unchanged[:5]))
    stage = dict(stoppedAt=min(STEPS, STOP_AT), scheduleSteps=STEPS, lrAtStop=sched.get_last_lr()[0], trainable=tnames, trainableUpdated=len(tnames),
                 frozenStateSHA256=frozen0, frozenUnchanged=True, objLoss=OBJ_LOSS, resource=lease.receipt())
    (target / ('DONE' if STOP_AT >= STEPS else f'STAGE-{STOP_AT}.json')).write_text(json.dumps(stage))
    return dict(done=True, **{k: v for k, v in stage.items() if k not in ('trainable', 'resource')})


# ------------------------------------------------------------------ evaluation on scale-matched full images
def tiles_for(H, W):
    xs = list(range(0, max(1, W - TILE) + 1, 288)) or [0]; ys = list(range(0, max(1, H - TILE) + 1, 288)) or [0]
    if xs[-1] + TILE < W: xs.append(W - TILE)
    if ys[-1] + TILE < H: ys.append(H - TILE)
    return [[x, y, x + TILE, y + TILE] for y in ys for x in xs]


def nms(boxes, scores, thr=.30):
    order = np.argsort(-np.asarray(scores)); keep = []
    for i in order:
        if all(iou(boxes[i], boxes[j]) < thr for j in keep): keep.append(i)
    return keep


def one_to_one(truth, pred, thr):
    pairs = sorted(((iou(t, p), i, j) for i, t in enumerate(truth) for j, p in enumerate(pred)), reverse=True); ut, up, m = set(), set(), []
    for v, i, j in pairs:
        if v < thr: break
        if i in ut or j in up: continue
        ut.add(i); up.add(j); m.append((i, j))
    return m


def evaltiles(plan_p, out, togg, model, role, lease, max_seconds, conf=.30):
    import cv2, torch
    from safetensors.torch import load_file
    P = read_json(plan_p); items = [i for i in P['items'] if i['role'] == role and (i['pos'] or i['neg'])]
    items.sort(key=lambda i: hashlib.sha256((i['archive'] + i['path']).encode()).hexdigest())
    if role == 'VALIDATION': items = items[:VAL_PHOTOS]
    side = float(np.median(P['targetLesionSidePx']['values']))
    torch.set_num_threads(2); net = step0_net(togg)
    if model != 'step0':
        net.load_state_dict(load_file(str(out / 'v3' / model / 'model.safetensors')), strict=True)
    net.eval()
    sink_p = out / f'eval-{role}-{model}.jsonl'
    done = {json.loads(l)['key'] for l in sink_p.read_text().splitlines()} if sink_p.exists() else set()
    sink = sink_p.open('a'); t0 = time.monotonic(); imgs = Images(ROOT)
    for it in items:
        k = it['archive'] + '::' + it['path']
        if k in done: continue
        if time.monotonic() - t0 > max_seconds: sink.close(); return False
        lease.check()
        img = imgs.read(it['archive'], it['path'])
        s = scale_for(it, side) or float(np.clip(side / max(4., .02 * it['w']), .15, 1.5))
        im = cv2.resize(img, (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        H, W = im.shape[:2]; boxes, scores = [], []
        for r in tiles_for(H, W):
            x = np.full((TILE, TILE, 3), 114, np.uint8); p = im[r[1]:r[3], r[0]:r[2]]; x[:p.shape[0], :p.shape[1]] = p
            with torch.no_grad(): o = net(torch.from_numpy(x.transpose(2, 0, 1).copy()).float()[None])[0].numpy()
            sc = o[:, 4] * o[:, 5]
            for v in np.where(sc >= conf)[0]:
                cx, cy, w, h = o[v, :4]; b = [cx - w / 2 + r[0], cy - h / 2 + r[1], cx + w / 2 + r[0], cy + h / 2 + r[1]]
                if b[0] < W and b[1] < H: boxes.append([float(c / s) for c in b]); scores.append(float(sc[v]))
        keep = nms(boxes, scores); pred = [boxes[i] for i in keep]; psc = [scores[i] for i in keep]
        sink.write(json.dumps(dict(key=k, archive=it['archive'], pos=it['pos'], ign=it['ign'], neg=it['neg'], pred=pred, score=psc, scale=s)) + '\n'); sink.flush()
    sink.close(); return True


def metrics(rows, thr=.30, conf=.30):
    tp = fp = fn = negfp = 0; per_pos_photo = []
    for r in rows:
        pred = [p for p, s in zip(r['pred'], r['score']) if s >= conf]
        m = one_to_one(r['pos'], pred, thr); paired = {j for _, j in m}
        un = [p for j, p in enumerate(pred) if j not in paired]
        un = [p for p in un if not any(overlaps(p, g) for g in r['ign'])]     # predictions on ignored labels are not counted
        negfp += sum(1 for p in un if any(iou(p, n) >= .1 for n in r['neg']))
        tp += len(m); fn += len(r['pos']) - len(m); fp += len(un)
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn)
    return dict(photos=len(rows), tp=tp, fp=fp, fn=fn, precision=round(pr, 4), recall=round(rc, 4), f1=round(2 * pr * rc / max(1e-9, pr + rc), 4),
                confounderHits=negfp, fpPerPhoto=round(fp / max(1, len(rows)), 2))


def load_rows(out, role, model): return [json.loads(l) for l in (out / f'eval-{role}-{model}.jsonl').read_text().splitlines()]


def evalproduct(out, togg, code_root, model, lease, max_seconds):
    """The unchanged v2 product-chain evaluator (Scope B/controls development, unused eval, train probe) with a v3 checkpoint."""
    import run_acne_v2_pilot as v2
    from safetensors.torch import load_file
    base = v2.build_net
    def build(t):
        net = base(t); net.load_state_dict(load_file(str(out / 'v3' / model / 'model.safetensors')), strict=True); return net
    v2.build_net = build
    man = read_json(code_root / 'docs/acne-data-v2-manifest-20261015.json')
    try: v2.evaluate('v3-' + model, man, out, togg, code_root, lease, max_seconds); return True
    except TimeoutError: return False


ROOT = None

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--root'); ap.add_argument('--out', required=True)
    ap.add_argument('--v2-manifest'); ap.add_argument('--model', default='step0'); ap.add_argument('--role', default='VALIDATION')
    ap.add_argument('--max-seconds', type=float, default=140); ap.add_argument('--prereg'); ap.add_argument('--cloud', help='cloud workspace dir holding scripts/, yolox_src/, models/')
    a = ap.parse_args(); out = Path(a.out); ROOT = Path(a.root) if a.root else None
    code_root = HERE.parents[1]; togg = code_root.parent
    if a.phase == 'plan': plan(out, Path(a.v2_manifest)); sys.exit()
    if a.phase == 'register':
        pre = Path(a.prereg)
        if (out / 'v3').exists(): raise SystemExit('TRAINING_ALREADY_STARTED')
        if pre.exists(): raise SystemExit('PREREGISTRATION_FROZEN')
        pre.write_text(json.dumps(dict(decision=DECISION, steps=STEPS, selectEvery=SELECT_EVERY, valPhotos=VAL_PHOTOS, accum=ACCUM, lr=LR, warmup=WARMUP, guard=GUARD, objLoss=OBJ_LOSS, stopAt=STOP_AT, seed=SEED, trainArchives=TRAIN_ARCHIVES,
                                       testArchive=TEST_ARCHIVE, planSHA256=sha_file(out / 'plan-v3.json'), codeSHA256=sha_file(Path(__file__)),
                                       controlledRun=CONTROLLED_RUN,
                                       trainable='YOLOX head + PAFPN neck convs (BatchNorm frozen, eval mode); backbone frozen; start = CDC Step0'), indent=1)); print(sha_file(pre)); sys.exit()
    if a.phase == 'metrics':
        for thr in (.3, .5): print(thr, json.dumps(metrics(load_rows(out, a.role, a.model), thr)))
        sys.exit()
    if a.cloud:
        sys.path[:0] = [str(Path(a.cloud) / 'scripts'), str(Path(a.cloud) / 'yolox_src')]; STEP0_PATH = Path(a.cloud) / 'models/step0.safetensors'
        class _Lease:
            def __enter__(s): return s
            def __exit__(s, *e): return False
            def check(s): pass
            def receipt(s): return dict(host='cloud-workspace', note='no user machine resources used')
        lease_cm = _Lease()
    else:
        setup_paths(code_root, togg)
        from heavy_job_lease import HeavyJobLease
        lease_cm = HeavyJobLease('CLAUDE-acne-v3-' + a.phase, peak_mib=1350, minimum_available_mib=1600, memory_metric='private')
    with lease_cm as lease:
        if a.phase == 'train': print(json.dumps(train(out / 'plan-v3.json', out, togg, lease, a.max_seconds)))
        if a.phase == 'evalproduct': print('complete' if evalproduct(out, togg, code_root, a.model, lease, a.max_seconds) else 'partial')
        if a.phase == 'evaltiles': print('complete' if evaltiles(out / 'plan-v3.json', out, togg, a.model, a.role, lease, a.max_seconds) else 'partial')
