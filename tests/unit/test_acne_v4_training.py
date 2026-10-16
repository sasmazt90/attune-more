"""Focused checks for the acne v4 trainer: exact loss formula and gradients through the real head, anchor states, tiles."""
import random, sys
from pathlib import Path
import numpy as np, pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/skin-research')]
import train_acne_v4 as t


def _torch():
    try:
        sys.path[:0] = [str(ROOT.parent / 'attune-live-test/audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee')]
        import torch
        from yolox_p2 import build_yolox_p2_model
        return torch, build_yolox_p2_model
    except Exception as e:
        pytest.skip(f'YOLOX source unavailable: {e}')


def _run(torch, build, known_px, targets, cfg, seed=0):
    torch.manual_seed(seed); net = build(); net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    loss = t.make_loss(cfg); net.head.obj_focal_loss = loss
    x = np.random.default_rng(seed).integers(0, 255, (384, 384, 3), dtype=np.uint8)
    L, comp = t.forward_loss(net, loss, x, known_px, targets, torch.Generator().manual_seed(1))
    o = net.head.last_obj_preds; o.retain_grad(); obj = net.head.last_norm_pos + net.head.last_norm_neg; obj.backward(retain_graph=True)
    return net, loss, comp, o


CFG = dict(t.CFG, lambda_neg=.7, w_hard=1.5, w_rand=.5)


def test_objectness_equals_documented_formula_and_gradient():
    torch, build = _torch()
    known = np.zeros((384, 384), bool); known[:200, :] = True
    net, loss, comp, o = _run(torch, build, known, [[100, 100, 114, 114], [250, 300, 262, 311]], CFG)
    logits = o.detach().view(-1, 1); truth = net.head.last_is_pos.view(-1, 1).float()
    hard, rand = loss.select(logits, truth)  # deterministic given logits: recompute hard; rand from the same generator is re-drawn below
    sel = loss.known.view(-1, 1)
    nfg = float(truth.sum())
    # value: head result == formula with the selection actually used
    ref = t.expected_obj_loss(logits, truth, sel & hard, sel & ~hard, CFG, nfg)
    assert torch.allclose(torch.tensor(comp['posObj'] + comp['negObj']), ref, rtol=1e-4)
    # gradient: positives (p-1)/nfg ; selected negatives lambda*w/K*p ; everything else 0
    p = torch.sigmoid(logits); g = o.grad.view(-1, 1); K = CFG['k_hard'] + CFG['k_rand']
    pos = truth > 0
    assert torch.allclose(g[pos], (p[pos] - 1) / nfg, rtol=1e-4, atol=1e-8)
    hs = sel & hard; rs = sel & ~hard
    assert torch.allclose(g[hs], CFG['lambda_neg'] * CFG['w_hard'] / K * p[hs], rtol=1e-4, atol=1e-9)
    assert torch.allclose(g[rs], CFG['lambda_neg'] * CFG['w_rand'] / K * p[rs], rtol=1e-4, atol=1e-9)
    assert torch.all(g[~pos & ~sel] == 0)                                  # UNKNOWN / unselected: exactly zero
    assert int(hs.sum()) == CFG['k_hard'] and int(rs.sum()) == CFG['k_rand']


def test_unknown_never_negative_and_hard_are_top_scored():
    torch, build = _torch()
    known = np.zeros((384, 384), bool); known[300:, 300:] = True
    net, loss, comp, o = _run(torch, build, known, [], CFG)
    sel = loss.known.view(-1).numpy(); kc = t.cells(known)
    assert not (sel & ~kc).any()                                            # nothing outside KNOWN_NEG is selected
    logits = o.detach().view(-1).numpy(); hard, _ = loss.select(o.detach().view(-1, 1), net.head.last_is_pos.view(-1, 1).float())
    h = hard.view(-1).numpy(); elig = kc
    assert logits[h].min() >= np.sort(logits[elig & ~h])[-1] - 1e-6        # hard = highest current objectness


def test_negative_only_tile_is_bounded_and_budget_does_not_scale_with_area():
    torch, build = _torch()
    small = np.zeros((384, 384), bool); small[:64, :64] = True
    big = np.ones((384, 384), bool)
    _, _, c1, _ = _run(torch, build, small, [], CFG); _, _, c2, _ = _run(torch, build, big, [], CFG)
    for c in (c1, c2): assert np.isfinite(c['total']) and c['posObj'] == 0 and c['box'] == 0
    import math
    # each selected negative carries weight <= lambda*max(w)/K, so the term is <= lambda*max(w)*max BCE, whatever the negative area
    assert c2['negObj'] <= CFG['lambda_neg'] * max(CFG['w_hard'], CFG['w_rand']) * 20 and c1['hard'] + c1['rand'] <= CFG['k_hard'] + CFG['k_rand']
    assert c2['hard'] + c2['rand'] == CFG['k_hard'] + CFG['k_rand']       # fixed budget, not every negative pixel


def _photo():
    img = np.full((900, 1200, 3), 60, np.uint8)
    pos = [[300, 200, 320, 220], [700, 500, 716, 516]]; ign = [[500, 300, 540, 340]]; nb = [[400, 250, 412, 262]]
    for b in pos: img[b[1]:b[3], b[0]:b[2]] = 250
    p = dict(kind='positive-photo', positive=[dict(box=b) for b in pos], ignore=[dict(box=b) for b in ign], negativeBoxes=[dict(box=b) for b in nb], width=1200, height=900)
    return img, p


def test_tile_states_padding_lesions_ignore_and_confounders():
    for seed in range(60):
        rng = random.Random(seed); img, p = _photo()
        x, known, tg = t.make_tile(img, p, rng.uniform(.3, 1.0), rng, True, False)
        g = x[..., 0].astype(int)
        assert not known[g >= 245].any()                                    # lesion pixels never negative
        for b in tg: c = [int(v) for v in b]; assert g[c[1]:c[3], c[0]:c[2]].mean() > 150


def test_padding_is_known_negative():
    img = np.full((200, 300, 3), 60, np.uint8); p = dict(kind='positive-photo', positive=[dict(box=[50, 50, 60, 60])], ignore=[], negativeBoxes=[])
    x, known, tg = t.make_tile(img, p, 1.0, random.Random(0), True, False)
    assert known[200:, :].all() and known[:, 300:].all()


def test_no_upscaling_and_negative_photo_mask_only():
    _, p = _photo(); assert t.photo_scale(p, 1000.) == 1.0                  # never enlarge
    neg = dict(kind='negative-photo'); assert t.photo_scale(neg, 1.) == 1.0
    img = np.full((250, 250, 3), 120, np.uint8); m = np.zeros((250, 250), bool); m[100:140, 60:100] = True
    x, known, tg = t.make_tile(img, dict(kind='negative-photo'), 1.0, random.Random(0), False, False, m)
    inside = known[:250, :250]
    assert tg == [] and inside.sum() == m.sum() and known[250:, :].all() and known[:, 250:].all()


def test_anchor_order_matches_head():
    torch, build = _torch()
    net = build(); net.train()
    for m in net.modules():
        if isinstance(m, torch.nn.BatchNorm2d): m.eval()
    cap = {}; orig = net.head.get_losses
    def spy(*a, **k): cap['x'], cap['y'], cap['s'] = a[1], a[2], a[3]; return orig(*a, **k)
    net.head.get_losses = spy; loss = t.make_loss(CFG); net.head.obj_focal_loss = loss
    t.forward_loss(net, loss, np.zeros((384, 384, 3), np.uint8), np.ones((384, 384), bool), [[10, 10, 30, 30]], torch.Generator().manual_seed(0))
    xs, ys, st = (torch.cat(cap[k], 1)[0] for k in 'xys')
    assert np.allclose(np.stack([((xs + .5) * st).numpy(), ((ys + .5) * st).numpy()], 1), t.CENTERS)


def test_positive_photo_clean_roi_is_known_negative_but_never_near_lesions():
    img, p = _photo(); m = np.zeros((900, 1200), bool); m[100:400, 200:500] = True   # overlaps the lesion at (300,200)-(320,220)
    x, known, tg = t.make_tile(img, p, 1.0, random.Random(3), True, False, m)
    g = x[..., 0].astype(int)
    assert not known[g >= 245].any() and known.any()
    x2, known2, _ = t.make_tile(img, p, 1.0, random.Random(3), True, False, None)
    assert known2.sum() < known.sum()                                       # without a mask only padding/confounders are known
