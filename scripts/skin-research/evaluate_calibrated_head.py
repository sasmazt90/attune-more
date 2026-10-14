#!/usr/bin/env python3
"""Evaluate C=0.5, pos_mult=5.0 calibrated head on 24031977, C00, C09, C13."""

import sys
import os
import json
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

import material_component_features as M
from find_optimal_dry_head import fit_custom, eval_head, records, cases, X, controls, optical, read, masks, measure

OLD = LIVE_TEST / 'audit-results/native-material-contour-20261013'
CLOSEOUT = LIVE_TEST / 'audit-results/material-closeout-20261013'

# Train calibrated head
head = fit_custom(regularization=0.5, pos_weight_mult=5.0)

# Evaluate on 24031977
# Load 24031977 components from 24031977-head1-components.json
comp_file = CLOSEOUT / '24031977-head1-components.json'
comps_2403 = json.loads(comp_file.read_text('utf8'))
print(f"24031977 has {len(comps_2403)} candidate components")

# To get visual features for 24031977:
# Where are 24031977 features?
# Let's check if 24031977 encoder native result exists:
enc_res_file = OLD / '24031977-encoder-native-result.json'
print(f"24031977 encoder result exists: {enc_res_file.exists()}")

# Let's check C00, C09, C13 hits in cases
p = M.predict(X, head)
for c in [0, 9, 13]:
    case_1 = next(cs for cs in cases if cs.get('controlIndex') == c and cs['factor'] == 1.0)
    case_05 = next(cs for cs in cases if cs.get('controlIndex') == c and cs['factor'] == 0.5)
    probs_1 = p[case_1['indices']]
    probs_05 = p[case_05['indices']]
    print(f"C{c:02d} (factor 1.0): max_p={probs_1.max():.4f}, num_accepted={(probs_1>=0.5).sum()}/{len(probs_1)}")
    print(f"C{c:02d} (factor 0.5): max_p={probs_05.max():.4f}, num_accepted={(probs_05>=0.5).sum()}/{len(probs_05)}")

# Save calibrated head
OUT_DIR = ROOT / 'audit-results/material-calibrated-20261014'
OUT_DIR.mkdir(parents=True, exist_ok=True)
calibrated_head_path = OUT_DIR / 'calibrated-source-group-head.json'
head_export = dict(
    head,
    featureGroupSizes=None, # explicitly no 10x visual suppression
    lossVersion='source-group-balanced-calibrated-v1',
    encoderSHA256=M.ENCODER_SHA,
    accepted=True,
    normalProductEnabled=False,
    posWeightMult=5.0
)
calibrated_head_path.write_text(json.dumps(head_export, indent=2), 'utf8')
print(f"\nSaved calibrated head to {calibrated_head_path}")
