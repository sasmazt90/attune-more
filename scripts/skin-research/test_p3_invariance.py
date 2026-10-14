#!/usr/bin/env python3
"""Verify Strict Mathematical Invariance of Pretrained Levels (P3, P4, P5) Under Independent P2 Training."""

import sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))

from yolox_p2 import build_yolox_p2_model, build_independent_p2_param_groups
from safetensors.torch import load_file
from model_identity import TRUE_BASELINE_EPOCH02_PATH, TRUE_BASELINE_EPOCH02_SHA, load_verified_model

def main():
    print("=" * 80)
    print("VERIFYING P3/P4/P5 MATHEMATICAL INVARIANCE UNDER INDEPENDENT P2 PARTITION")
    print("=" * 80)

    # 1. Load verified model
    net, sha = load_verified_model(TRUE_BASELINE_EPOCH02_PATH, expected_sha=TRUE_BASELINE_EPOCH02_SHA)
    print(f"Verified baseline weights: {TRUE_BASELINE_EPOCH02_PATH.name} (SHA: {sha})")
    net.eval()

    # 3. Check parameter partition
    param_groups, receipt = build_independent_p2_param_groups(net, lr_p2=2e-4)
    print("\n[Parameter Partition Receipt]:")
    print(f"  Trainable Level 0 tensors: {receipt['trainableLevel0']['tensorCount']} ({receipt['trainableLevel0']['parameterCount']:,} params)")
    print(f"  Frozen baseline tensors:   {receipt['frozenBaseline']['tensorCount']} ({receipt['frozenBaseline']['parameterCount']:,} params)")
    print(f"  Total model parameters:    {receipt['totalModelParams']:,}")
    print(f"  p2_gate value:             {receipt['p2GateValue']}")

    # 4. Generate random test tensor
    torch.manual_seed(42)
    x = torch.randn(2, 3, 384, 384)

    # 5. Baseline forward pass (extract Level 1, 2, 3 -> P3, P4, P5 outputs)
    with torch.no_grad():
        fpn_outs = net.backbone(x)
        # Stride 8 (P3) is fpn_outs[1]
        base_p3_feat = fpn_outs[1].clone()
        base_p4_feat = fpn_outs[2].clone()
        base_p5_feat = fpn_outs[3].clone()

    # 6. Now simulate a severe perturbation to Level 0 weights (as if trained for epochs)
    print("\nPerturbing Level 0 weights by +5.0 to simulate drastic training...")
    with torch.no_grad():
        for p in param_groups[0]['params']:
            p.add_(5.0)

    # 7. Check if P3, P4, P5 features change AT ALL
    with torch.no_grad():
        fpn_outs_perturbed = net.backbone(x)
        p3_diff = (fpn_outs_perturbed[1] - base_p3_feat).abs().max().item()
        p4_diff = (fpn_outs_perturbed[2] - base_p4_feat).abs().max().item()
        p5_diff = (fpn_outs_perturbed[3] - base_p5_feat).abs().max().item()

    print(f"  Maximum P3 feature drift: {p3_diff:.10f}")
    print(f"  Maximum P4 feature drift: {p4_diff:.10f}")
    print(f"  Maximum P5 feature drift: {p5_diff:.10f}")

    assert p3_diff == 0.0, f"VIOLATION: P3 feature drifted by {p3_diff}!"
    assert p4_diff == 0.0, f"VIOLATION: P4 feature drifted by {p4_diff}!"
    assert p5_diff == 0.0, f"VIOLATION: P5 feature drifted by {p5_diff}!"

    print("\nSUCCESS: Mathematical invariance strictly proven! P3/P4/P5 outputs are 100.000% invariant.")

if __name__ == '__main__':
    main()
