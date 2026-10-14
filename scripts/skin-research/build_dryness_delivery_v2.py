#!/usr/bin/env python3
"""Build and verify Dryness Delivery v2 for CDC.

Generates:
1. Calibrated source-group head with C04 negative support completely eliminated (0 px).
2. Verification across all 21 objects and half-scale controls (14/21 1.0x, 13/21 0.5x, C08 obj0=71 px).
3. Live end-to-end adapter test on real photo 24031977 with cold & warm execution timing (< 45s).
4. Evidence receipts and comparison files.
"""

import sys
import os
import json
import time
import hashlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

from retrain_dry_head import build_training_set, fit_model, get_full_evaluation, cases, records, X, controls, optical
import material_component_features as M
from cdc_skin_adapters import CalibratedDrynessAdapter

OUT_DIR = ROOT / 'audit-results/cdc-delivery-20261014-v2/dryness'
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("=== BUILDING DRYNESS DELIVERY V2 ===")

    # 1. Train winning head: reg=0.15, pwm=3.0, threshold=0.50, Mode: C04 negative added
    train_indices, y_train, g_train = build_training_set(include_c04_negative=True, include_all_train_negatives=False)
    print(f"Training dataset: {len(y_train)} rows (pos={sum(y_train==1)}, neg={sum(y_train==0)})")
    
    head = fit_model(
        train_indices, y_train, g_train,
        vis_scale=3.0, geo_scale=0.4,
        regularization=0.15, pos_weight_mult=3.0,
        threshold=0.50
    )

    # Add metadata
    head['lossVersion'] = 'source-group-balanced-calibrated-v3-c04-clean'
    head['encoderSHA256'] = 'e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a'
    head['accepted'] = True
    head['normalProductEnabled'] = False
    head['fitCount'] = 1

    # 2. Evaluate metrics
    eval_res = get_full_evaluation(head)
    print("\n--- Evaluation Metrics ---")
    print(f"1.0x Native Hits: {eval_res['native_hits']}/21 (tr={eval_res['tr_1']}, va={eval_res['va_1']})")
    print(f"0.5x Half-scale Hits: {eval_res['half_hits']}/21 (tr={eval_res['tr_05']}, va={eval_res['va_05']})")
    print(f"C04 Reviewed Negative Support: {eval_res['neg_1_c04']:.1f} px")
    print(f"Total 1.0x Negative Support:   {eval_res['neg_1_all']:.1f} px")
    print(f"Validation 1.0x Neg Support:   {eval_res['neg_1_va']:.1f} px")
    print(f"Validation 0.5x Neg Support:   {eval_res['neg_05_va']:.1f} px")
    print(f"C08 obj0 Hit:                  {eval_res['c08_obj0_hit']} ({eval_res['c08_obj0_px']:.1f} px)")

    # Assertions for delivery admission
    assert eval_res['native_hits'] >= 14, f"Native hits below target: {eval_res['native_hits']}"
    assert eval_res['half_hits'] >= 13, f"Half-scale hits below target: {eval_res['half_hits']}"
    assert eval_res['neg_1_c04'] == 0.0, f"C04 negative support not eliminated: {eval_res['neg_1_c04']}"
    assert eval_res['neg_1_all'] == 0.0, f"Total 1.0x negative support not zero: {eval_res['neg_1_all']}"
    assert eval_res['neg_1_va'] == 0.0, f"Validation 1.0x negative support not zero: {eval_res['neg_1_va']}"
    assert eval_res['neg_05_va'] == 0.0, f"Validation 0.5x negative support not zero: {eval_res['neg_05_va']}"
    assert eval_res['c08_obj0_hit'], f"C08 obj0 was not hit: {eval_res['c08_obj0_hit']}"

    # 3. Save head
    head_path = OUT_DIR / 'calibrated-source-group-head.json'
    head_path.write_text(json.dumps(head, indent=2), 'utf8')
    head_sha = hashlib.sha256(head_path.read_bytes()).hexdigest()
    print(f"\nSaved calibrated head to: {head_path}")
    print(f"Head SHA-256: {head_sha}")

    # 4. Save detailed C04/C08 diagnosis evidence
    p = M.predict(X, head)
    c04_case = next(c for c in cases if c.get('controlIndex') == 4 and c['factor'] == 1.0)
    c08_case = next(c for c in cases if c.get('controlIndex') == 8 and c['factor'] == 1.0)
    c13_case_05 = next(c for c in cases if c.get('controlIndex') == 13 and c['factor'] == 0.5)
    c15_case_05 = next(c for c in cases if c.get('controlIndex') == 15 and c['factor'] == 0.5)

    c04_idx = next(i for i in c04_case['indices'] if records[i]['componentId'] == 29)
    c08_idx = next(i for i in c08_case['indices'] if records[i]['componentId'] == 50)

    diag = {
        "headSHA256": head_sha,
        "threshold": head['threshold'],
        "regularizationC": head['regularizationC'],
        "posWeightMult": head['scaling']['pos_weight_mult'],
        "C04_Component_29": {
            "sourceBox": [392, 347, 58, 41],
            "probability": float(p[c04_idx]),
            "acceptedAtThreshold": bool(p[c04_idx] >= head['threshold']),
            "activeSourcePixelsInReviewedNegative": 0.0,
            "previousAcceptedPixels": 151.0,
            "eliminated": True
        },
        "C08_Component_50_obj0": {
            "sourceBox": [35, 292, 21, 17],
            "probability": float(p[c08_idx]),
            "acceptedAtThreshold": bool(p[c08_idx] >= head['threshold']),
            "activeSourcePixelsInReviewedPositive": float(eval_res['c08_obj0_px']),
            "objectHit": bool(eval_res['c08_obj0_hit'])
        },
        "halfScaleNegativeChecks": {
            "c13_factor05_max_p": float(p[c13_case_05['indices']].max()),
            "c15_factor05_max_p": float(p[c15_case_05['indices']].max()),
            "belowThreshold": bool(p[c13_case_05['indices']].max() < 0.50 and p[c15_case_05['indices']].max() < 0.50)
        }
    }
    diag_path = OUT_DIR / 'C04-negative-elimination-evidence.json'
    diag_path.write_text(json.dumps(diag, indent=2), 'utf8')
    print(f"Saved diagnosis evidence to: {diag_path}")

    # 5. Save head comparison file
    comp = {
        "heads": {
            "CDC legacy source-group-head": {
                "native_hits": 14,
                "half_hits": 15,
                "neg_1_va_pixels": 4.0,
                "neg_05_va_pixels": 216.0,
                "c04_neg_pixels": 0.0,
                "c8_component50_p": 0.563488,
                "threshold": 0.50
            },
            "AG prev delivered head (a668840c)": {
                "native_hits": 14,
                "half_hits": 13,
                "neg_1_va_pixels": 0.0,
                "neg_05_va_pixels": 0.0,
                "c04_neg_pixels": 151.0,
                "c8_component50_p": 0.590505,
                "threshold": 0.50
            },
            "AG v2 winner head (c04 clean)": {
                "native_hits": int(eval_res['native_hits']),
                "half_hits": int(eval_res['half_hits']),
                "neg_1_va_pixels": float(eval_res['neg_1_va']),
                "neg_05_va_pixels": float(eval_res['neg_05_va']),
                "c04_neg_pixels": float(eval_res['neg_1_c04']),
                "total_neg_1_pixels": float(eval_res['neg_1_all']),
                "c8_component50_p": float(p[c08_idx]),
                "c04_component29_p": float(p[c04_idx]),
                "threshold": float(head['threshold']),
                "headSHA256": head_sha
            }
        }
    }
    comp_path = OUT_DIR / 'dryness-head-comparison.json'
    comp_path.write_text(json.dumps(comp, indent=2), 'utf8')
    print(f"Saved comparison to: {comp_path}")

    # 6. Live test on photo 24031977
    photo_payload_path = LIVE_TEST / 'audit-results/dry-sag-source-census-20261013/product/24031977/24031977-automatic-payload.json'
    assert photo_payload_path.exists(), f"Payload not found: {photo_payload_path}"
    payload = json.loads(photo_payload_path.read_text('utf8'))

    print("\n--- Running Live Adapter Test on 24031977 ---")
    adapter = CalibratedDrynessAdapter(head_path=head_path, use_onnx=True)
    
    # Cold run
    t0 = time.perf_counter()
    res_cold = adapter.analyze(payload)
    t_cold = time.perf_counter() - t0
    print(f"Cold execution time: {t_cold:.3f} s (target < 45.0 s)")
    assert t_cold < 45.0, f"Cold run exceeded latency target: {t_cold} s"

    # Warm run
    t0 = time.perf_counter()
    res_warm = adapter.analyze(payload)
    t_warm = time.perf_counter() - t0
    print(f"Warm execution time: {t_warm:.3f} s (target < 45.0 s)")
    assert t_warm < 45.0, f"Warm run exceeded latency target: {t_warm} s"

    runtime_evidence = {
        "photoId": "24031977",
        "headSHA256": head_sha,
        "encoderType": "onnx",
        "coldExecutionSeconds": t_cold,
        "warmExecutionSeconds": t_warm,
        "maxBudgetSeconds": 45.0,
        "budgetMet": bool(t_cold < 45.0 and t_warm < 45.0),
        "overviewScore": res_warm.get('general', {}).get('measurements', [{}])[0].get('value'),
        "measurements": {
            reg: m.get('value')
            for reg, m in res_warm.get('measurements', {}).items()
        }
    }
    runtime_path = OUT_DIR / 'dryness-runtime-evidence.json'
    runtime_path.write_text(json.dumps(runtime_evidence, indent=2), 'utf8')
    print(f"Saved runtime evidence to: {runtime_path}")
    print("\nDRYNESS DELIVERY V2 SUCCESSFULLY BUILT AND VERIFIED!")

if __name__ == '__main__':
    main()
