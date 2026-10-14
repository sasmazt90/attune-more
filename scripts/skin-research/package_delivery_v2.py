#!/usr/bin/env python3
"""Package and finalize CDC Delivery v2 Manifest and Artifacts."""

import os
import sys
import json
import shutil
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELIVERY_DIR = ROOT / 'audit-results/cdc-delivery-20261014-v2'

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("=== PACKAGING CDC DELIVERY V2 ===")

    # 1. Weights and ONNX for Acne
    weights_dir = DELIVERY_DIR / 'weights'
    onnx_dir = DELIVERY_DIR / 'onnx'
    weights_dir.mkdir(parents=True, exist_ok=True)
    onnx_dir.mkdir(parents=True, exist_ok=True)

    src_weights = ROOT / 'audit-results/cdc-delivery-20261014/weights/candidate-selected.safetensors'
    src_onnx = ROOT / 'audit-results/cdc-delivery-20261014/onnx/model.onnx'
    src_receipt = ROOT / 'audit-results/cdc-delivery-20261014/onnx/onnx-parity-receipt.json'

    dst_weights = weights_dir / 'candidate-selected.safetensors'
    dst_onnx = onnx_dir / 'model.onnx'
    dst_receipt = onnx_dir / 'onnx-parity-receipt.json'

    if not dst_weights.exists():
        shutil.copy2(src_weights, dst_weights)
    if not dst_onnx.exists():
        shutil.copy2(src_onnx, dst_onnx)
    if not dst_receipt.exists():
        shutil.copy2(src_receipt, dst_receipt)

    # 2. Acne evaluation summary
    acne_dir = DELIVERY_DIR / 'acne'
    acne_dir.mkdir(parents=True, exist_ok=True)
    acne_summary = {
        "modelName": "YOLOX-S-P2-small-foci",
        "selectedModel": "Epoch 2 Baseline Winner",
        "weightsSha256": sha256_file(dst_weights),
        "onnxSha256": sha256_file(dst_onnx),
        "productGateAccepted": False,
        "metrics": {
            "confidenceThreshold": 0.30,
            "nmsThreshold": 0.30,
            "iou50Recall": "15/53 (28.3%)",
            "lesionSizeBreakdown": {
                "lessThan8px": "0/7 (0.0%)",
                "8to16px": "5/31 (16.1%)",
                "16to32px": "10/15 (66.7%)"
            },
            "falsePositivesAcross15NegativePhotos": 3,
            "falsePositivesPerPhoto": 0.20
        },
        "continuationEvaluation": {
            "oversampledContinuation_20815477": {
                "iou50Recall": "14/53",
                "lessThan8px": "0/7",
                "8to16px": "6/31",
                "16to32px": "8/15",
                "falsePositives": 3,
                "outcome": "Regressed overall recall from 15/53 to 14/53 by losing two 16-32px lesions for one 8-16px lesion."
            },
            "balancedContinuation_8605be68": {
                "iou50Recall": "14/53",
                "lessThan8px": "0/7",
                "8to16px": "6/31",
                "16to32px": "8/15",
                "falsePositives": 4,
                "outcome": "Regressed overall recall to 14/53 with 4 FP."
            }
        },
        "subResolutionLimitationAnalysis": {
            "microLesionsTested": 7,
            "detected": 0,
            "finding": "The 7 micro-lesions (<8 px, e.g. 6 lesions on photo 2d271d2b) have sub-resolution optical contrast deltas of only 1.06 to 7.56 intensity units on an 8-bit scale across 30-52 px^2, placing them below the camera sensor optical noise floor without higher-resolution optical capture.",
            "recommendation": "Preserve 15/53 baseline winner cf3a2ba4 without falsification; maintain productGateAccepted: false until optical zoom or multispectral sensor inputs are provided."
        }
    }
    (acne_dir / 'acne-evaluation-summary.json').write_text(json.dumps(acne_summary, indent=2), 'utf8')

    # 3. Copy adapter to delivery root
    src_adapter = ROOT / 'services/core-api/cdc_skin_adapters.py'
    dst_adapter = DELIVERY_DIR / 'cdc_skin_adapters.py'
    shutil.copy2(src_adapter, dst_adapter)

    # 4. Generate delivery manifest
    manifest = {
        "deliveryVersion": "cdc-delivery-20261014-v2",
        "createdAt": "2026-10-14T12:28:00+02:00",
        "workspaceContext": {
            "agRepo": "C:\\Users\\PC\\Desktop\\AI Workspace\\TOGG\\attune-antigravity-skin",
            "agHeadCommit": "eeb68b692475b6cf383fae09d3bebfd16ab6e0f2",
            "cdcRepo": "C:\\Users\\PC\\Desktop\\AI Workspace\\TOGG\\attune-live-test",
            "cdcHeadCommit": "72b90172084711cd200637cedab831f80e3fb973",
            "notes": "Delivery package for CDC integration. CDC workspace remains strictly read-only."
        },
        "summary": {
            "dryness": {
                "status": "DELIVERED_AND_VERIFIED",
                "productGateAccepted": True,
                "nativeHits": "14/21",
                "halfScaleHits": "13/21",
                "c04NegativeSupportPixels": 0.0,
                "total1xNegativeSupportPixels": 0.0,
                "val1xNegativeSupportPixels": 0.0,
                "valHalfScaleNegativeSupportPixels": 0.0,
                "c08Obj0RecoveryPixels": 71.0,
                "c04Component29Prob": 0.016312,
                "c08Component50Prob": 0.555462,
                "livePhoto24031977ColdSeconds": 1.954,
                "livePhoto24031977WarmSeconds": 1.465,
                "maxBudgetSeconds": 45.0
            },
            "sagging": {
                "status": "DELIVERED_AND_VERIFIED",
                "productGateAccepted": True,
                "restingFullLips4d05d72b": "PASSED (expressionReason: null, chin: 0.0%)",
                "restingFullLips29cc4ba7": "PASSED (expressionReason: null, chin: 0.0%)",
                "neutralControl40c7edda": "PASSED (chin: 0.0%)",
                "roundFaceE35b68b8": "PASSED (0.0% false protrusion)",
                "cheekFoldDedbb492": "PASSED (leftCheek fold: 6.21%, chin gated by HARD_DIRECTIONAL_SHADOW)",
                "submentalNeckCrease": "EXCLUDED from chin boundary via anatomical mesh bounding"
            },
            "acne": {
                "status": "BASELINE_WINNER_PRESERVED",
                "productGateAccepted": False,
                "modelId": "cf3a2ba4",
                "iou50Recall": "15/53",
                "breakdown": "<8px: 0/7, 8-16px: 5/31, 16-32px: 10/15",
                "falsePositivesAcross15Negatives": 3,
                "reason": "Continuation runs plateau at 14/53. Micro-lesions (<8 px) are at optical contrast sensor noise limit (1.06-7.56 delta). Baseline winner cf3a2ba4 is preserved without false promotion."
            }
        },
        "files": {}
    }

    # Index all delivery files
    for root, dirs, files in os.walk(DELIVERY_DIR):
        for f in files:
            if f == 'delivery-manifest.json':
                continue
            f_path = Path(root) / f
            rel_path = f_path.relative_to(DELIVERY_DIR).as_posix()
            manifest['files'][rel_path] = {
                "sha256": sha256_file(f_path),
                "sizeBytes": f_path.stat().st_size
            }

    manifest_path = DELIVERY_DIR / 'delivery-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), 'utf8')
    print(f"Saved Delivery Manifest to: {manifest_path}")

    # Print summary table
    print("\n" + "=" * 90)
    print("CDC DELIVERY V2 MANIFEST SUMMARY")
    print("=" * 90)
    for rel_p, meta in sorted(manifest['files'].items()):
        print(f"  {rel_p:50s} | {meta['sizeBytes']:10d} B | {meta['sha256']}")
    print("=" * 90)

if __name__ == '__main__':
    main()
