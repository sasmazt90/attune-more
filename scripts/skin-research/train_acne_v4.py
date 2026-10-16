"""Acne v4: controlled objectness training with explicit anchor states and a fixed-budget negative term.

Anchor states per 384x384 native tile (P2..P5 cells, same order as the YOLOX head):
  POSITIVE   SimOTA-assigned foreground of a positive box (head assignment, unchanged)
  KNOWN_NEG  cell centre inside a reviewed negative ROI (Clear engineering mask / CDC reviewed mask), inside an explicit confounder
             box (Mole, Freckles, Pigmentation, pores, Dark-Spots), or in tile padding outside the image
  IGNORE     everything else: unlabeled skin of positive photos, ignore boxes, cut lesions  -> zero objectness loss

Objectness loss actually optimised (one tile = one image, batch 1):
  L_obj = (1/num_fg) * sum_{a in POS} BCE(o_a, 1)                                         [0 when num_fg = 0]
        + LAMBDA_NEG / K_BUDGET * ( W_HARD * sum_{a in HARD} BCE(o_a, 0) + W_RAND * sum_{a in RAND} BCE(o_a, 0) )
  HARD = the K_HARD KNOWN_NEG cells with the highest current objectness; RAND = K_RAND further KNOWN_NEG cells drawn uniformly
  (seeded per step/tile). K_BUDGET = K_HARD + K_RAND is a constant: a tile with few known negatives contributes less, never more,
  and the term does not grow with the number of negative pixels. Box (IoU x5), class and L1 terms are YOLOX's, over POS only.
The shared head divides the positive sum by num_fg and the negative sum by (#negatives it sees) x 20; BudgetedObjLoss pre-scales its
per-anchor values so that the head's arithmetic yields exactly the formula above (no double scaling) - checked by tests.
"""
import argparse, hashlib, json, math, random, sys, time, zipfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TILE = 384
STEP0_SHA256 = '18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'
CFG = dict(seed=20261016, accum=8, k_hard=64, k_rand=192, w_hard=1.0, w_rand=1.0, lambda_neg=None,   # lambda_neg fixed by the TRAIN probe
           p_negative_photo=.40, p_focus=.85, lr=None, warmup=None, clip=None, pilot_steps=150, ckpt_every=25,
           trainable='YOLOX head + PAFPN neck convs; BatchNorm frozen (eval); backbone frozen', start='CDC Step0 ' + STEP0_SHA256)
HEAD_NEG_WEIGHT = 20.0   # the shared head multiplies its mean-over-seen-negatives by 20 (yolox_p2.py)


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_json(p): return json.loads(Path(p).read_text('utf8'))
def bw(b): return b[2] - b[0]
def bh(b): return b[3] - b[1]
def overlaps(a, b): return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


# ---------------------------------------------------------------- loss
def budgeted_loss_class():
    import torch, torch.nn.functional as F
    from focal_objectness_loss import SigmoidFocalObjectnessLoss

    class BudgetedObjLoss(SigmoidFocalObjectnessLoss):
        def __init__(self, k_hard, k_rand, w_hard, w_rand, lambda_neg):
            super().__init__()
            self.k_hard, self.k_rand, self.w_hard, self.w_rand, self.lambda_neg = k_hard, k_rand, w_hard, w_rand, lambda_neg
            self.known_negative = None; self.generator = None; self.stats = {}

        def select(self, logits, truth):
            """Return (hard, rand) boolean masks over anchors; only KNOWN_NEG anchors that are not positive are eligible."""
            elig = (self.known_negative & ~(truth > 0)).view(-1)
            idx = torch.nonzero(elig).view(-1); hard = torch.zeros_like(elig); rand = torch.zeros_like(elig)
            if len(idx):
                kh = min(self.k_hard, len(idx)); order = torch.argsort(logits.detach().view(-1)[idx], descending=True)
                hard[idx[order[:kh]]] = True
                rest = idx[order[kh:]]; kr = min(self.k_rand, len(rest))
                if kr: rand[rest[torch.randperm(len(rest), generator=self.generator)[:kr]]] = True
            return hard.view(-1, 1), rand.view(-1, 1)

        def forward(self, logits, truth):
            if self.known_negative is None or self.known_negative.shape != logits.shape: raise ValueError('KNOWN_NEGATIVE_MASK_REQUIRED')
            is_pos = truth > 0; hard, rand = self.select(logits, truth); sel = hard | rand
            self.known = sel   # the head counts exactly the selected negatives (plus nothing else) as 'known negatives'
            n_sel = float(sel.sum()); k_budget = float(self.k_hard + self.k_rand)
            bce = F.binary_cross_entropy_with_logits(logits, truth, reduction='none')
            w = torch.zeros_like(bce)
            w = torch.where(is_pos, torch.ones_like(bce), w)
            scale = self.lambda_neg * max(n_sel, 1.0) / (HEAD_NEG_WEIGHT * k_budget)
            w = torch.where(hard, torch.full_like(bce, self.w_hard * scale), w)
            w = torch.where(rand, torch.full_like(bce, self.w_rand * scale), w)
            with torch.no_grad():
                p = torch.sigmoid(logits)
                self.stats = dict(pos=int(is_pos.sum()), knownNegAvailable=int((self.known_negative & ~is_pos).sum()), hard=int(hard.sum()), rand=int(rand.sum()),
                                  hardMeanP=float(p[hard].mean()) if hard.any() else None, posMeanP=float(p[is_pos].mean()) if is_pos.any() else None)
            return bce * w

        def record_normalized(self, **k): pass
    return BudgetedObjLoss


def make_loss(cfg):
    return budgeted_loss_class()(cfg['k_hard'], cfg['k_rand'], cfg['w_hard'], cfg['w_rand'], cfg['lambda_neg'] if cfg['lambda_neg'] is not None else 1.0)


def expected_obj_loss(logits, truth, hard, rand, cfg, num_fg):
    """Reference implementation of the documented formula (used by tests)."""
    import torch.nn.functional as F
    bce = F.binary_cross_entropy_with_logits(logits, truth, reduction='none')
    pos = bce[truth > 0].sum() / max(num_fg, 1) if (truth > 0).any() else bce.sum() * 0
    lam = cfg['lambda_neg'] if cfg['lambda_neg'] is not None else 1.0
    neg = lam / (cfg['k_hard'] + cfg['k_rand']) * (cfg['w_hard'] * bce[hard].sum() + cfg['w_rand'] * bce[rand].sum())
    return pos + neg


# ---------------------------------------------------------------- data
class Files:
    def __init__(self, root): self.root = Path(root)
    def read(self, rel):
        import cv2
        b = (self.root / rel).read_bytes(); return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR)
    def mask(self, rel):
        import cv2
        return cv2.imread(str(self.root / rel), cv2.IMREAD_GRAYSCALE) > 0


def anchor_centers():
    cs = []
    for stride in (4, 8, 16, 32):
        c = (np.arange(TILE // stride) + .5) * stride; xx, yy = np.meshgrid(c, c); cs.append(np.stack([xx.ravel(), yy.ravel()], 1))
    return np.concatenate(cs)


CENTERS = anchor_centers()


def cells(known_px):
    """pixel known-negative map (TILE x TILE bool) -> per-anchor bool, head order."""
    xi = CENTERS[:, 0].astype(int); yi = CENTERS[:, 1].astype(int)
    return known_px[yi, xi]


def photo_scale(p, side, rng=None):
    """Downscale only (s<=1): never enlarge positives or 250px Clear photos."""
    if p['kind'] != 'positive-photo' or not p['positive']: return 1.0
    med = float(np.median([max(bw(b['box']), bh(b['box'])) for b in p['positive']]))
    return float(np.clip(side / med, .15, 1.0))


def make_tile(img, p, s, rng, focus, aug, negmask=None):
    """-> tile (BGR uint8), known-negative pixel map, positive targets (tile px), stats. Padding (outside the image) is KNOWN_NEG."""
    import cv2
    h, w = img.shape[:2]
    im = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA) if s < 1 else img
    H, W = im.shape[:2]; S = lambda b: [v * s for v in b]
    pos = [S(b['box']) for b in p.get('positive', [])]; ign = [S(b['box']) for b in p.get('ignore', [])]; nbx = [S(b['box']) for b in p.get('negativeBoxes', [])]
    nm = None
    if negmask is not None: nm = cv2.resize(negmask.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST) > 0 if s < 1 else negmask
    if focus and pos: b = pos[rng.randrange(len(pos))]; cx, cy = (b[0] + b[2]) / 2 + rng.uniform(-150, 150), (b[1] + b[3]) / 2 + rng.uniform(-150, 150)
    elif nm is not None and nm.any():
        ys, xs = np.nonzero(nm); k = rng.randrange(len(xs)); cx, cy = xs[k] + rng.uniform(-64, 64), ys[k] + rng.uniform(-64, 64)
    elif nbx and rng.random() < .5: b = nbx[rng.randrange(len(nbx))]; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    else: cx, cy = rng.uniform(0, W), rng.uniform(0, H)
    x0 = int(np.clip(cx - TILE / 2, 0, max(0, W - TILE))); y0 = int(np.clip(cy - TILE / 2, 0, max(0, H - TILE)))
    x = np.full((TILE, TILE, 3), 114, np.uint8); patch = im[y0:y0 + TILE, x0:x0 + TILE]; x[:patch.shape[0], :patch.shape[1]] = patch
    known = np.zeros((TILE, TILE), bool); known[patch.shape[0]:, :] = True; known[:, patch.shape[1]:] = True   # padding
    if nm is not None: known[:patch.shape[0], :patch.shape[1]] |= nm[y0:y0 + TILE, x0:x0 + TILE]
    loc = lambda b: [b[0] - x0, b[1] - y0, b[2] - x0, b[3] - y0]
    def paint(b, val, grow=0.):
        g = grow * max(bw(b), bh(b), 4); a = [int(max(0, b[0] - g)), int(max(0, b[1] - g)), int(min(TILE, math.ceil(b[2] + g))), int(min(TILE, math.ceil(b[3] + g)))]
        if a[2] > a[0] and a[3] > a[1]: known[a[1]:a[3], a[0]:a[2]] = val
    for b in nbx:
        if overlaps(b, [x0, y0, x0 + TILE, y0 + TILE]): paint(loc(b), True)
    targets = []
    rect = [x0, y0, x0 + TILE, y0 + TILE]
    for b in pos:
        if not overlaps(b, rect): continue
        l = loc(b); c = [max(0, l[0]), max(0, l[1]), min(TILE, l[2]), min(TILE, l[3])]
        kept = max(0, bw(c)) * max(0, bh(c)) / max(1e-6, bw(l) * bh(l))
        if kept >= .7 and bw(c) >= 2 and bh(c) >= 2: targets.append(c)
        paint(l, False, .3)   # never a negative near/over a lesion (cut lesions included)
    for b in ign:
        if overlaps(b, rect): paint(loc(b), False, .3)
    if aug:
        if rng.random() < .5: x = x[:, ::-1].copy(); known = known[:, ::-1].copy(); targets = [[TILE - t[2], t[1], TILE - t[0], t[3]] for t in targets]
        if rng.random() < .8: a_, b_ = rng.uniform(.85, 1.15), rng.uniform(-15, 15); x = np.clip(x.astype(np.float32) * a_ + b_, 0, 255).astype(np.uint8)
        if rng.random() < .3: x = cv2.GaussianBlur(x, (0, 0), rng.uniform(.3, 1.0))
        if rng.random() < .3: ok, enc = cv2.imencode('.jpg', x, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(60, 95)]); x = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return x, known, targets


def sample_tile(step, j, P, files, cfg, sides):
    rng = random.Random(cfg['seed'] * 1000003 + step * 97 + j)
    negs = [p for p in P if p['kind'] == 'negative-photo']; poss = [p for p in P if p['kind'] == 'positive-photo']
    if rng.random() < cfg['p_negative_photo']:
        p = negs[rng.randrange(len(negs))]; img = files.read(p['file']); m = files.mask(p['mask'])
        x, known, tg = make_tile(img, p, 1.0, rng, False, True, m); src = p['negativeSource']
    else:
        p = poss[rng.randrange(len(poss))]; img = files.read(p['file'])
        side = sides[rng.randrange(len(sides))] * rng.uniform(.8, 1.25)
        m = files.mask(p['mask']) if p.get('mask') else None   # v5 core: reviewed clean ROI on a positive photo (absent in v4 manifests)
        x, known, tg = make_tile(img, p, photo_scale(p, side), rng, rng.random() < cfg['p_focus'], True, m); src = 'positive-photo'
    return x, known, tg, src, rng


# ---------------------------------------------------------------- model
def setup_paths(cloud):
    if cloud: sys.path[:0] = [str(Path(cloud) / 'scripts'), str(Path(cloud) / 'yolox_src')]
    else:
        code = HERE.parents[1]; togg = code.parent
        sys.path[:0] = [str(HERE), str(code / 'services/core-api'), str(togg / 'attune-live-test/audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee')]


def step0_net(path):
    from safetensors.torch import load_file
    from yolox_p2 import build_yolox_p2_model
    if sha_file(path) != STEP0_SHA256: raise RuntimeError('STEP0_HASH')
    net = build_yolox_p2_model(); net.load_state_dict(load_file(str(path)), strict=True); return net


def trainable_name(n):
    return (n.startswith('head.') or n.startswith('backbone.') and ('.lateral_conv' in n or '.reduce_conv' in n or '.C3_' in n or '.bu_conv' in n)) and '.bn.' not in n


def forward_loss(net, loss, x, known, tg, gen):
    import torch
    ten = torch.from_numpy(x.transpose(2, 0, 1).copy()).float()[None]
    loss.known_negative = torch.from_numpy(cells(known))[:, None]; loss.generator = gen
    y = torch.zeros((1, max(1, len(tg)), 5))
    for i, t in enumerate(tg): y[0, i] = torch.tensor([0, (t[0] + t[2]) / 2, (t[1] + t[3]) / 2, t[2] - t[0], t[3] - t[1]])
    out = net(ten, y); h = net.head
    comp = dict(total=float(out['total_loss']), box=float(out['iou_loss']), cls=float(out['cls_loss']), l1=float(out['l1_loss']) if torch.is_tensor(out['l1_loss']) else float(out['l1_loss']),
                posObj=float(h.last_norm_pos), negObj=float(h.last_norm_neg), **loss.stats)
    return out['total_loss'], comp


# ---------------------------------------------------------------- phases
def probe(man, files, step0, cfg, n=64):
    """TRAIN-only, Step0 weights, no update: objectness magnitudes and gradient norms to FIX lambda_neg, clip and LR."""
    import torch
    torch.set_num_threads(2); torch.manual_seed(cfg['seed'])
    P = [p for p in man['photos'] if p['role'] == 'TRAIN']; sides = man['targetSidePx']['values']
    net = step0_net(step0); [p.requires_grad_(trainable_name(nm)) for nm, p in net.named_parameters()]; net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    c = dict(cfg, lambda_neg=1.0); loss = make_loss(c); net.head.obj_focal_loss = loss
    rows = []
    for j in range(n):
        x, known, tg, src, rng = sample_tile(-1, j, P, files, c, sides)
        g = torch.Generator().manual_seed(cfg['seed'] + j)
        L, comp = forward_loss(net, loss, x, known, tg, g); net.zero_grad(); L.backward()
        gn = float(torch.nn.utils.clip_grad_norm_([p for p in net.parameters() if p.requires_grad], 1e12))
        rows.append(dict(src=src, targets=len(tg), gradNorm=gn, **comp))
    pos = [r['posObj'] for r in rows if r['pos'] > 0]; neg = [r['negObj'] for r in rows]
    lam = float(np.mean(pos) / max(np.mean(neg), 1e-9))
    return dict(rows=rows, meanPosObjPerPositiveTile=float(np.mean(pos)), meanNegObjPerTileAtLambda1=float(np.mean(neg)), lambdaNeg=lam,
                rule='lambda_neg = mean positive-objectness term over positive tiles / mean budgeted negative term (lambda=1) over all tiles, Step0, TRAIN tiles')


def train(man, files, step0, cfg, out, steps, max_seconds, name):
    import torch
    from safetensors.torch import save_file, load_file
    torch.set_num_threads(2); torch.manual_seed(cfg['seed'])
    P = [p for p in man['photos'] if p['role'] == 'TRAIN' and (not cfg.get('positiveSubset') or p['kind'] == 'negative-photo' or p['sha256'] in set(cfg['positiveSubset']))]
    sides = man['targetSidePx']['values']
    target = out / name; target.mkdir(parents=True, exist_ok=True)
    if (target / 'DONE.json').exists(): raise RuntimeError('COMPLETED_RUN_NOT_REPEATED')
    net = step0_net(step0)
    for nm, p in net.named_parameters(): p.requires_grad_(trainable_name(nm))
    tnames = [nm for nm, p in net.named_parameters() if p.requires_grad]
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    frozen_sha = lambda: hashlib.sha256(b''.join(v.detach().cpu().numpy().tobytes() for k, v in sorted(net.state_dict().items()) if k not in tnames)).hexdigest()
    frozen0 = frozen_sha(); init = {k: v.detach().clone() for k, v in net.named_parameters() if v.requires_grad}
    loss = make_loss(cfg); net.head.obj_focal_loss = loss
    params = [p for p in net.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=cfg['lr'], weight_decay=.01)
    total = cfg['schedule_steps']
    lam = lambda s: (s + 1) / cfg['warmup'] if s < cfg['warmup'] else .05 + .95 * .5 * (1 + math.cos(math.pi * (s - cfg['warmup']) / max(1, total - cfg['warmup'])))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lam); start, logs = 0, []
    if (target / 'CURRENT').exists():
        cur = read_json(target / 'CURRENT'); d = target / cur['directory']
        for n_, h in cur['hashes'].items():
            if sha_file(d / n_) != h: raise RuntimeError('CHECKPOINT_HASH')
        st = read_json(d / 'state.json')
        if st['cfgSHA'] != hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest() or st['manifestSHA'] != man['_sha']: raise RuntimeError('RESUME_IDENTITY')
        net.load_state_dict(load_file(str(d / 'model.safetensors')), strict=True); tens = load_file(str(d / 'optim.safetensors'))
        opt.load_state_dict(dict(state={int(i): {k: (tens[v['tensor']] if isinstance(v, dict) and 'tensor' in v else v) for k, v in s.items()} for i, s in st['optimizerState'].items()}, param_groups=st['paramGroups']))
        sched.load_state_dict(st['scheduler']); start, logs = st['step'], st['logs']

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
        (d / 'state.json').write_text(json.dumps(dict(step=step, optimizerState=states, paramGroups=state['param_groups'], scheduler=sched.state_dict(), logs=logs,
                                                      cfgSHA=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(), manifestSHA=man['_sha'],
                                                      sampleOrder='stateless: Random(seed*1000003+step*97+j); torch.Generator(seed*7919+step*31+j)')))
        hashes = {n_: sha_file(d / n_) for n_ in ('model.safetensors', 'optim.safetensors', 'state.json')}
        tmp = target / 'CURRENT.tmp'; tmp.write_text(json.dumps(dict(directory=d.name, step=step, hashes=hashes))); tmp.replace(target / 'CURRENT')
        for old in target.glob('step-*'):
            if old != d and (old / 'optim.safetensors').exists(): (old / 'optim.safetensors').unlink()

    t0 = time.monotonic()
    for step in range(start, steps):
        opt.zero_grad(set_to_none=True); agg = {}; tiles = []
        for j in range(cfg['accum']):
            x, known, tg, src, rng = sample_tile(step, j, P, files, cfg, sides)
            g = torch.Generator().manual_seed(cfg['seed'] * 7919 + step * 31 + j)
            L, comp = forward_loss(net, loss, x, known, tg, g)
            if not torch.isfinite(L): raise RuntimeError('NONFINITE_LOSS')
            (L / cfg['accum']).backward(); tiles.append(dict(src=src, **{k: comp[k] for k in ('pos', 'knownNegAvailable', 'hard', 'rand')}))
            for k in ('total', 'box', 'cls', 'l1', 'posObj', 'negObj'): agg[k] = agg.get(k, 0.) + comp[k] / cfg['accum']
        if not all(p.grad is None or torch.isfinite(p.grad).all() for p in params): raise RuntimeError('NONFINITE_GRADIENT')
        pre = float(torch.nn.utils.clip_grad_norm_(params, cfg['clip'])); post = min(pre, cfg['clip'])
        opt.step(); sched.step()
        logs.append(dict(step=step + 1, **{k: round(v, 5) for k, v in agg.items()}, gradPre=round(pre, 4), gradPost=round(post, 4), clipped=pre > cfg['clip'],
                         lr=sched.get_last_lr()[0], posAnchors=sum(t['pos'] for t in tiles), negSelected=sum(t['hard'] + t['rand'] for t in tiles),
                         negAvailable=sum(t['knownNegAvailable'] for t in tiles), negativeTiles=sum(t['src'] != 'positive-photo' for t in tiles)))
        if (step + 1) % 10 == 0: print(json.dumps(dict(**logs[-1], sec=round(time.monotonic() - t0, 1))), flush=True)
        if (step + 1) % cfg['ckpt_every'] == 0:
            save(step + 1); per = (time.monotonic() - t0) / (step + 1 - start)
            if step + 1 < steps and time.monotonic() - t0 + cfg['ckpt_every'] * per > max_seconds: return dict(partial=True, step=step + 1, secPerStep=round(per, 2))
    if frozen_sha() != frozen0: raise RuntimeError('FROZEN_PARAMETERS_CHANGED')
    cur = dict(net.named_parameters()); unchanged = [k for k in tnames if torch.equal(cur[k].detach(), init[k])]
    if unchanged: raise RuntimeError('TRAINABLE_NOT_UPDATED')
    (target / 'DONE.json').write_text(json.dumps(dict(steps=steps, frozenUnchanged=True, trainableUpdated=len(tnames))))
    return dict(done=True, steps=steps)


# ---------------------------------------------------------------- tile-level evaluation (TRAIN probe / DEV)
def tiles_for(H, W):
    xs = list(range(0, max(1, W - TILE) + 1, 288)) or [0]; ys = list(range(0, max(1, H - TILE) + 1, 288)) or [0]
    if xs[-1] + TILE < W: xs.append(W - TILE)
    if ys[-1] + TILE < H: ys.append(H - TILE)
    return [[x, y, x + TILE, y + TILE] for y in ys for x in xs]


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = bw(a) * bh(a) + bw(b) * bh(b) - i
    return i / u if u > 0 else 0.


def nms(boxes, scores, thr=.30):
    order = np.argsort(-np.asarray(scores)); keep = []
    for i in order:
        if all(iou(boxes[i], boxes[j]) < thr for j in keep): keep.append(i)
    return keep


def evaluate(man, files, weights, role, side, limit=None, conf=.30, subset=None):
    """Positive photos: targets found (one-to-one IoU>=.50 and >=.30), best target score, matched box area ratio.
    Negative photos: candidates whose centre lies in the reviewed negative mask (only those count as FP)."""
    import torch, cv2
    from safetensors.torch import load_file
    net = step0_net(weights['step0'])
    if weights.get('model'): net.load_state_dict(load_file(str(weights['model'])), strict=True)
    net.eval(); torch.set_num_threads(2)
    P = [p for p in man['photos'] if p['role'] == role]
    pos = sorted([p for p in P if p['kind'] == 'positive-photo' and (subset is None or p['sha256'] in subset)], key=lambda p: p['sha256'])[:limit]
    neg = sorted([p for p in P if p['kind'] == 'negative-photo'], key=lambda p: p['sha256'])
    res = dict(pos=[], neg=[])
    for p in pos + neg:
        img = files.read(p['file']); s = photo_scale(p, side) if p['kind'] == 'positive-photo' else 1.0
        im = cv2.resize(img, (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))), interpolation=cv2.INTER_AREA) if s < 1 else img
        H, W = im.shape[:2]; boxes, scores, allb, alls = [], [], [], []
        for r in tiles_for(H, W):
            x = np.full((TILE, TILE, 3), 114, np.uint8); q = im[r[1]:r[3], r[0]:r[2]]; x[:q.shape[0], :q.shape[1]] = q
            with torch.no_grad(): o = net(torch.from_numpy(x.transpose(2, 0, 1).copy()).float()[None])[0].numpy()
            sc = o[:, 4] * o[:, 5]
            for v in np.where(sc >= .001)[0]:
                cx, cy, w_, h_ = o[v, :4]; b = [(cx - w_ / 2 + r[0]) / s, (cy - h_ / 2 + r[1]) / s, (cx + w_ / 2 + r[0]) / s, (cy + h_ / 2 + r[1]) / s]
                allb.append(b); alls.append(float(sc[v]))
                if sc[v] >= conf: boxes.append([float(c) for c in b]); scores.append(float(sc[v]))
        keep = nms(boxes, scores) if boxes else []; pred = [boxes[i] for i in keep]
        if p['kind'] == 'positive-photo':
            T = [b['box'] for b in p['positive']]; row = dict(sha=p['sha256'][:12], targets=len(T), sides=[float(max(bw(t), bh(t))) for t in T])
            for thr in (.5, .3):
                pr = sorted(((iou(t, q), i, j) for i, t in enumerate(T) for j, q in enumerate(pred)), reverse=True); ut, up, m = set(), set(), []
                for v, i, j in pr:
                    if v < thr: break
                    if i in ut or j in up: continue
                    ut.add(i); up.add(j); m.append((i, j))
                row[f'hit{int(thr * 100)}'] = sorted(i for i, _ in m)
                if thr == .3: row['areaRatio'] = [float(bw(pred[j]) * bh(pred[j]) / max(1e-6, bw(T[i]) * bh(T[i]))) for i, j in m]
            row['bestScore'] = [max([sc for b, sc in zip(allb, alls) if iou(t, b) >= .5], default=0.) for t in T]
            row['candidates'] = len(pred); res['pos'].append(row)
        else:
            m = files.mask(p['mask']); fp = 0
            for b in pred:
                cx, cy = int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2)
                if 0 <= cy < m.shape[0] and 0 <= cx < m.shape[1] and m[cy, cx]: fp += 1
            res['neg'].append(dict(sha=p['sha256'][:12], source=p['negativeSource'], fpInMask=fp, candidates=len(pred)))
    return res


def summarize(res):
    P = res['pos']; N = res['neg']; T = sum(r['targets'] for r in P)
    sides = [s for r in P for s in r['sides']]; hits = {(k, i) for k, r in enumerate(P) for i in r['hit50']}
    small = [(k, i) for k, r in enumerate(P) for i, s in enumerate(r['sides']) if s < 16]; med = [(k, i) for k, r in enumerate(P) for i, s in enumerate(r['sides']) if s >= 16]
    ar = [a for r in P for a in r['areaRatio']]; bs = [b for r in P for b in r['bestScore']]
    return dict(photos=len(P), targets=T, hit50=sum(len(r['hit50']) for r in P), hit30=sum(len(r['hit30']) for r in P),
                recall50=round(sum(len(r['hit50']) for r in P) / max(1, T), 4), smallTargets=len(small), smallHit50=sum(1 for x in small if x in hits),
                mediumTargets=len(med), mediumHit50=sum(1 for x in med if x in hits), medianAreaRatio=round(float(np.median(ar)), 3) if ar else None,
                medianBestScore=round(float(np.median(bs)), 4) if bs else None, candidatesPerPositivePhoto=round(np.mean([r['candidates'] for r in P]), 2) if P else None,
                negativePhotos=len(N), fpInMaskTotal=sum(r['fpInMask'] for r in N), fpInMaskPerPhoto=round(sum(r['fpInMask'] for r in N) / max(1, len(N)), 3),
                fpPerPhotoMax=max([r['fpInMask'] for r in N], default=0), fpBySource={s: sum(r['fpInMask'] for r in N if r['source'] == s) for s in {r['source'] for r in N}})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--cloud'); ap.add_argument('--step0', required=True); ap.add_argument('--config'); ap.add_argument('--name', default='pilot')
    ap.add_argument('--steps', type=int); ap.add_argument('--max-seconds', type=float, default=520); ap.add_argument('--model'); ap.add_argument('--role', default='TRAIN'); ap.add_argument('--limit', type=int)
    a = ap.parse_args(); setup_paths(a.cloud); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    mf = Path(a.data) / ('manifest-v5.json' if (Path(a.data) / 'manifest-v5.json').exists() else 'manifest-v4.json')
    man = read_json(mf); man['_sha'] = sha_file(mf); files = Files(a.data)
    if a.phase == 'probe':
        r = probe(man, files, a.step0, CFG); (out / 'probe.json').write_text(json.dumps(r, indent=1))
        print(json.dumps({k: v for k, v in r.items() if k != 'rows'}), 'gradNorm p50/p90', np.percentile([x['gradNorm'] for x in r['rows']], [50, 90]).round(2).tolist())
    elif a.phase == 'pilot-subset':
        ps = sorted((p['sha256'] for p in man['photos'] if p['role'] == 'TRAIN' and p['kind'] == 'positive-photo' and p['positive']),
                    key=lambda s: hashlib.sha256((s + 'pilot-v4').encode()).hexdigest())[:120]
        print(json.dumps(ps))
    elif a.phase == 'train':
        cfg = read_json(a.config)['config']; print(json.dumps(train(man, files, a.step0, cfg, out, a.steps, a.max_seconds, a.name)))
    elif a.phase == 'eval':
        side = float(np.median(man['targetSidePx']['values']))
        sub = set(read_json(a.config)['config']['positiveSubset']) if a.config else None
        r = evaluate(man, files, dict(step0=a.step0, model=a.model), a.role, side, a.limit, subset=sub)
        tag = (Path(a.model).parent.name if a.model else 'step0') + f'-{a.role}' + (f'-{a.limit}' if a.limit else '')
        (out / f'eval-{a.name}-{tag}.json').write_text(json.dumps(r)); print(tag, json.dumps(summarize(r)))
