#!/usr/bin/env python3
"""Save pos_mult 5.2 calibrated head and evaluate on 24031977."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from find_optimal_dry_head import fit_custom, eval_head

head = fit_custom(regularization=0.5, pos_weight_mult=5.2, threshold=0.50)
res = eval_head(head)

print("--- Calibrated Head (C=0.5, pos_mult=5.2, threshold=0.50) ---")
print(f"Native Hits: {res['native_hits']}/21 (tr={res['tr_1']}/13, va={res['va_1']}/8)")
print(f"Half Hits:   {res['half_hits']}/21 (tr={res['tr_05']}/13, va={res['va_05']}/8)")
print(f"Neg va 1.0:  {res['neg_1_va']} px")
print(f"Neg va 0.5:  {res['neg_05_va']} px")
print(f"C13 max_p:   {res['c13_max_p']:.4f}")

OUT_DIR = ROOT / 'audit-results/material-calibrated-20261014'
OUT_DIR.mkdir(parents=True, exist_ok=True)
calibrated_head_path = OUT_DIR / 'calibrated-source-group-head.json'
head_export = dict(
    head,
    featureGroupSizes=None,
    lossVersion='source-group-balanced-calibrated-v1',
    encoderSHA256='e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a',
    accepted=True,
    normalProductEnabled=False,
    posWeightMult=5.2
)
calibrated_head_path.write_text(json.dumps(head_export, indent=2), 'utf8')
print(f"Saved calibrated head to {calibrated_head_path}")
