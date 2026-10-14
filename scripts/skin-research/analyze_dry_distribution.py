#!/usr/bin/env python3
"""Analyze full probability distribution of all TRAIN and validation components."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

from find_optimal_dry_head import cases, records, X, controls, OLD, read, eval_head
import material_component_features as M

def main():
    head = read(ROOT / 'audit-results/cdc-delivery-20261014/dryness/calibrated-source-group-head.json')
    p = M.predict(X, head)

    train_pos = []
    train_neg = []
    val_pos = []
    val_neg = []

    for idx, r in enumerate(records):
        label = r.get('label')
        split = r.get('split')
        factor = r.get('factor')
        if factor != 1.0 or label is None:
            continue
        prob = float(p[idx])
        item = (prob, idx, r)
        if label == 1:
            if split == 'train':
                train_pos.append(item)
            else:
                val_pos.append(item)
        elif label == 0:
            if split == 'train':
                train_neg.append(item)
            else:
                val_neg.append(item)

    print("=== PROBABILITY DISTRIBUTION (head threshold = 0.50) ===")
    print(f"TRAIN Positives ({len(train_pos)}): min={min(x[0] for x in train_pos):.4f}, max={max(x[0] for x in train_pos):.4f}, median={np.median([x[0] for x in train_pos]):.4f}")
    print(f"TRAIN Negatives ({len(train_neg)}): min={min(x[0] for x in train_neg):.4f}, max={max(x[0] for x in train_neg):.4f}, median={np.median([x[0] for x in train_neg]):.4f}")
    if val_pos:
        print(f"VAL Positives   ({len(val_pos)}): min={min(x[0] for x in val_pos):.4f}, max={max(x[0] for x in val_pos):.4f}, median={np.median([x[0] for x in val_pos]):.4f}")
    if val_neg:
        print(f"VAL Negatives   ({len(val_neg)}): min={min(x[0] for x in val_neg):.4f}, max={max(x[0] for x in val_neg):.4f}, median={np.median([x[0] for x in val_neg]):.4f}")

    print("\n--- TRAIN Negatives with prob >= 0.40 ---")
    for prob, idx, r in sorted(train_neg, key=lambda x: x[0], reverse=True):
        if prob >= 0.35:
            print(f"  Control {r.get('controlIndex')} | CID {r['componentId']:3d} | rect={r['rect']} | prob={prob:.4f}")

    print("\n--- TRAIN Positives with prob <= 0.70 ---")
    for prob, idx, r in sorted(train_pos, key=lambda x: x[0]):
        if prob <= 0.70:
            print(f"  Control {r.get('controlIndex')} | CID {r['componentId']:3d} | rect={r['rect']} | prob={prob:.4f}")

    print("\n--- VAL Positives with prob <= 0.70 ---")
    for prob, idx, r in sorted(val_pos, key=lambda x: x[0]):
        if prob <= 0.70:
            print(f"  Control {r.get('controlIndex')} | CID {r['componentId']:3d} | rect={r['rect']} | prob={prob:.4f}")

if __name__ == '__main__':
    main()
