#!/usr/bin/env python3
"""Run full native dry analysis with calibrated head on glasses-free 24031977."""

import sys
import os
import json
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

import native_dry_path as N
import material_component_features as M

OLD = LIVE_TEST / 'audit-results/native-material-contour-20261013'
CLOSEOUT = LIVE_TEST / 'audit-results/material-closeout-20261013'

# 1. Load calibrated head
head_file = ROOT / 'audit-results/material-calibrated-20261014/calibrated-source-group-head.json'
head = json.loads(head_file.read_text('utf8'))

# 2. Load 24031977 payload
payload_path = LIVE_TEST / 'audit-results/dry-sag-source-census-20261013/product/24031977/attempt-2/24031977-automatic-payload.json'
payload = json.loads(payload_path.read_text('utf8'))

# 3. Load encoder (use frozen PyTorch encoder)
encoder_path = LIVE_TEST / 'audit-results/focused-skin-20261010/pretrained/efficientnet_b0_rwightman-7f5810bc.pth.safetensors'
print(f"Encoder safetensors path: {encoder_path} (exists: {encoder_path.exists()})")
encoder = M.FrozenMaterialEncoder(encoder_path)

# 4. Run filter_material_support_streamed with calibrated head
def run_filter(image, field, metric):
    return M.filter_material_support_streamed(image, field, metric, encoder, head)

result = N.analyze_native_dry(payload, run_filter)

print("\n=== Native Dry Analysis Results on 24031977 ===")
for reg, m in result['measurements'].items():
    print(f"  {reg:12s} -> value={m['value']:.4f}%, acceptedPx={m['components']['acceptedMaterialSourcePixels']}/{m['components']['uniqueVisibleSourcePixels']}")

print(f"Overview value: {result['general']['value']:.4f}%, acceptedPx={result['general']['components']['acceptedMaterialSourcePixels']}")
print(f"Total accepted components: {result['nativeMetadata']['acceptedComponents']}/{result['nativeMetadata']['candidateComponents']}")
