#!/usr/bin/env python3
"""Inspect Control 8 obj0 component details, features, and model contributions."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

import material_component_features as M
from find_optimal_dry_head import cases, records, X, controls, OLD, read, eval_head

def main():
    print("=== Control 8 Dissection ===")
    cdc_head = read(OLD / 'encoder-material-balanced-head.json')
    calib_head = read(ROOT / 'audit-results/cdc-delivery-20261014/dryness/calibrated-source-group-head.json')

    c8_cases = [c for c in cases if c.get('controlIndex') == 8]
    print(f"Control 8 cases: {len(c8_cases)}")

    for case in c8_cases:
        factor = case['factor']
        print(f"\n--- Factor {factor} ---")
        inds = case['indices']
        case_recs = [records[i] for i in inds]
        case_X = X[inds]

        p_cdc = M.predict(case_X, cdc_head)
        p_calib = M.predict(case_X, calib_head)

        for i, (r, p1, p2) in enumerate(zip(case_recs, p_cdc, p_calib)):
            cid = r['componentId']
            rect = r['rect']
            geom = r['geometry']
            # obj0 polygon is around y=80..100, x=5..25 in local ROI [20, 220, 160, 160]
            # so source coordinates are around x=25..45, y=300..320
            if p1 >= 0.3 or p2 >= 0.3 or (rect[0] < 60 and rect[1] > 100):
                print(f"Component {cid:3d} | rect={rect} | p_cdc={p1:.4f} | p_calib={p2:.4f}")
                print(f"  Geometry: {geom}")

                # Deconstruct logit for this component
                # x_norm = (X - mean) / std
                feat = case_X[i]
                
                # Calibrated logit deconstruction
                z_calib = (feat - np.array(calib_head['mean'])) / np.array(calib_head['std'])
                vis_contrib_calib = float(np.sum(z_calib[:2560] * np.array(calib_head['coefficients'][:2560])))
                geo_contrib_calib = float(np.sum(z_calib[2560:] * np.array(calib_head['coefficients'][2560:])))
                intercept_calib = float(calib_head['intercept'])
                total_logit_calib = vis_contrib_calib + geo_contrib_calib + intercept_calib
                
                # CDC logit deconstruction
                z_cdc = (feat - np.array(cdc_head['mean'])) / np.array(cdc_head['std'])
                vis_contrib_cdc = float(np.sum(z_cdc[:2560] * np.array(cdc_head['coefficients'][:2560])))
                geo_contrib_cdc = float(np.sum(z_cdc[2560:] * np.array(cdc_head['coefficients'][2560:])))
                intercept_cdc = float(cdc_head['intercept'])
                total_logit_cdc = vis_contrib_cdc + geo_contrib_cdc + intercept_cdc

                print(f"  CDC Logit: {total_logit_cdc:+.4f} (vis: {vis_contrib_cdc:+.4f}, geo: {geo_contrib_cdc:+.4f}, intercept: {intercept_cdc:+.4f})")
                print(f"  Calib Logit: {total_logit_calib:+.4f} (vis: {vis_contrib_calib:+.4f}, geo: {geo_contrib_calib:+.4f}, intercept: {intercept_calib:+.4f})")

if __name__ == '__main__':
    main()
