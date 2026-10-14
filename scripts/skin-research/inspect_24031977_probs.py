#!/usr/bin/env python3
"""Inspect probabilities of all 29 components on 24031977."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

import native_dry_path as N
import material_component_features as M

head_file = ROOT / 'audit-results/material-calibrated-20261014/calibrated-source-group-head.json'
head = json.loads(head_file.read_text('utf8'))

payload_path = LIVE_TEST / 'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json'
payload = json.loads(payload_path.read_text('utf8'))

encoder_path = LIVE_TEST / 'audit-results/focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors'
encoder = M.FrozenMaterialEncoder(encoder_path)

details = []
def run_filter(image, field, metric):
    return M.filter_material_support_streamed(image, field, metric, encoder, head, details=details)

result = N.analyze_native_dry(payload, run_filter)

print(f"Intercept: {head['intercept']}")
for d in details:
    print(f"Cid {d['componentId']:2d} | rect {d['rect']} | area {d['area']:3d} | prob {d['probability']:.4f} | accepted: {d['accepted']}")
