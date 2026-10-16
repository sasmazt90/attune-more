"""Focused checks for the acne v3 trainer (synthetic inputs; no dataset images, no training)."""
import random, sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research')]
import train_acne_v3 as t


def _scene():
    img = np.full((900, 1200, 3), 60, np.uint8)
    pos = [[300, 200, 320, 220], [700, 500, 716, 516]]; ign = [[500, 300, 540, 340]]
    for b in pos: img[b[1]:b[3], b[0]:b[2]] = 250
    return img, dict(pos=pos, ign=ign, neg=[], w=1200, h=900)


def test_tile_targets_follow_scaling_jitter_and_flip():
    bad = n = 0
    for seed in range(120):
        rng = random.Random(seed); img, it = _scene()
        x, known, tg = t.make_tile(img, it, rng.uniform(.3, 1.5), rng, focus=True, aug=True)
        g = x.mean(2)
        for b in tg:
            n += 1; c = [int(round(v)) for v in b]
            bad += g[max(0, c[1]):c[3], max(0, c[0]):c[2]].mean() < 150
    assert n > 100 and bad == 0


def test_cut_lesions_and_ignore_boxes_are_unknown():
    for seed in range(120):
        rng = random.Random(seed); img, it = _scene()
        img[300:340, 500:540] = 180
        x, known, tg = t.make_tile(img, it, rng.uniform(.3, 1.5), rng, focus=True, aug=False)
        g = x[..., 0].astype(int); cover = np.zeros(g.shape, bool)
        for b in tg:
            c = [int(round(v)) for v in b]; cover[max(0, c[1] - 1):c[3] + 1, max(0, c[0] - 1):c[2] + 1] = True
        stray = (g >= 245) & ~cover
        assert not (stray.any() and known[stray].any())             # a cut lesion never becomes background
        sel = g == 180
        if sel.sum() > 4: assert known[sel].mean() < .01             # ignore box (<=1 resampled corner pixel)


def _yolox():
    try:
        sys.path[:0] = [str(ROOT.parent / 'attune-live-test/audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee')]
        import torch
        from yolox_p2 import build_yolox_p2_model
        return torch, build_yolox_p2_model
    except Exception as e:
        pytest.skip(f'YOLOX source unavailable: {e}')


def _loss_grad(torch, net, mode):
    torch.manual_seed(0)
    f = t.make_obj_loss(mode); net.head.obj_focal_loss = f
    f.known = torch.ones(12240, 1, dtype=torch.bool); f.boundary_weights = torch.ones(12240, 1)
    x = torch.rand(1, 3, 384, 384) * 255; y = torch.tensor([[[0, 100., 100., 14., 14.], [0, 250., 180., 12., 12.]]])
    out = net(x, y); o = net.head.last_obj_preds; o.retain_grad(); out['total_loss'].backward()
    g = o.grad.view(-1).detach(); p = torch.sigmoid(o.detach().view(-1)); neg = net.head.last_is_neg.view(-1); pos = net.head.last_is_pos.view(-1)
    net.zero_grad(); return g, p, neg, float(pos.sum())


def test_anchor_order_and_standard_background_gradient():
    torch, build = _yolox()
    net = build(); net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    cap = {}; orig = net.head.get_losses
    def spy(*a, **k): cap['x'], cap['y'], cap['s'] = a[1], a[2], a[3]; return orig(*a, **k)
    net.head.get_losses = spy
    g, p, neg, nfg = _loss_grad(torch, net, 'standard-yolox-bce')
    xs, ys, st = (torch.cat(cap[k], 1)[0] for k in 'xys')
    assert np.allclose(np.stack([((xs + .5) * st).numpy(), ((ys + .5) * st).numpy()], 1), t.anchor_centers())   # mask order == head order
    # standard YOLOX objectness: d(sum BCE / num_fg)/d logit = p / num_fg on every background anchor
    assert torch.allclose(g[neg], p[neg] / nfg, rtol=1e-4, atol=1e-9)
    g_old, p_old, neg_old, nfg_old = _loss_grad(torch, net, 'shared-head-mean-x20')
    ratio = (g_old[neg_old] / (p_old[neg_old] / nfg_old)).median()
    assert ratio < .05   # the failed run's background push was a small fraction of the declared standard rule


def test_trainer_uses_declared_background_rule():
    assert t.OBJ_LOSS == 'standard-yolox-bce'


def test_first_stage_keeps_the_full_schedule():
    assert (t.STEPS, t.STOP_AT, t.WARMUP, t.LR, t.ACCUM, t.SEED) == (1800, 300, 100, 2e-4, 8, 20261015)
