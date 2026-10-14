#!/usr/bin/env python3
"""Test threshold=0.40 with calibrated head on all controls and 24031977."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from find_optimal_dry_head import fit_custom, eval_head

print("--- Testing Threshold 0.40 with pos_weight_mult=5.0 ---")
head = fit_custom(regularization=0.5, pos_weight_mult=5.0, threshold=0.40)
res = eval_head(head)

print(f"Threshold = {head['threshold']}")
print(f"Native Hits: {res['native_hits']}/21 (tr={res['tr_1']}/13, va={res['va_1']}/8)")
print(f"Half Hits:   {res['half_hits']}/21 (tr={res['tr_05']}/13, va={res['va_05']}/8)")
print(f"Neg va 1.0:  {res['neg_1_va']} px")
print(f"Neg va 0.5:  {res['neg_05_va']} px")
print(f"C13 max_p:   {res['c13_max_p']:.4f}")

# Save updated calibrated head with threshold=0.40
OUT_DIR = ROOT / 'audit-results/material-calibrated-20261014'
calibrated_head_path = OUT_DIR / 'calibrated-source-group-head.json'
head_export = dict(
    head,
    featureGroupSizes=None,
    lossVersion='source-group-balanced-calibrated-v1',
    encoderSHA256='e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a',
    accepted=True,
    normalProductEnabled=False,
    posWeightMult=5.0
)
calibrated_head_path.write_text(json.dumps(head_export, indent=2), 'utf8')
print(f"Saved calibrated head to {calibrated_head_path}")
