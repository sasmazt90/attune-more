#!/usr/bin/env python3
"""Model Selection Policy v2: Multi-Threshold Evaluation and Tiered FP Budget Selection.

Contracts & Governance:
1. Evaluates all candidates under identical canonical validation conditions:
   - 43 canonical images (36 truth annotations + 15 verified negative photos, with overlaps)
   - 53 in-scope visible region ground truth lesions
   - Full Filter v5 anatomical and polygon containment pipelines
2. Compares across 3 confidence operating points:
   - conf = 0.30 (high recall, controlled FP)
   - conf = 0.50 (balanced)
   - conf = 0.70 (strict low-FP)
3. Evaluates 3 candidates:
   - Baseline (3-scale YOLOX-S, negative-yolox selected weights)
   - Epoch 1 (4-scale YOLOX-S + P2, step 248)
   - Epoch 2 (4-scale YOLOX-S + P2, step 496)
4. Formalizes Selection Policy v2 across FP Budgets:
   - Tier A: FP <= 0.20 / photo (<= 3 FP / 15 neg photos)
   - Tier B: FP <= 0.50 / photo (<= 7 FP / 15 neg photos)
   - Tier C: FP <= 1.00 / photo (<= 15 FP / 15 neg photos)
   Rule: Maximize in-scope IoU50 recall among models satisfying the FP budget.
         Tie-breaker: lower negTotalFp, then higher inScopeTp30.
"""

import sys
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import torch
import torch.nn as nn
from torchvision.ops import nms as torch_nms
from safetensors.torch import load_file

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.insert(0, str(LIVE_TEST / 'audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))

from yolox.models.yolo_pafpn import YOLOPAFPN
from yolox.models.yolo_head import YOLOXHead
from yolox.models.yolox import YOLOX
from yolox_numeric import install_bounds
from yolox_p2 import build_yolox_p2_model
from prepare_canonical_validation_cache import load_canonical_validation_cache
from train_p2_focal_trial import (
    evaluate_canonical_validation,
    sha256_file
)

TRIAL_DIR = ROOT / 'audit-results/acne-candidate-p2-focal-20261013'
BASELINE_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-yolox/selected.safetensors'
EPOCH1_DIR = TRIAL_DIR / 'checkpoint-epoch-01-step-000248-1791909523358138100'
EPOCH2_DIR = TRIAL_DIR / 'checkpoint-epoch-02-step-000496-1791911067067742300'


def build_baseline_model() -> YOLOX:
    """Instantiate standard 3-scale YOLOX-S detector and install bounds."""
    backbone = YOLOPAFPN(depth=0.33, width=0.5)
    head = YOLOXHead(num_classes=1, width=0.5, strides=[8, 16, 32], in_channels=[256, 512, 1024])
    net = YOLOX(backbone, head)
    install_bounds(net)
    return net


def evaluate_candidate(
    name: str,
    model: nn.Module,
    weights_path: Path,
    cached_images: List[dict],
    conf_thresholds: List[float] = [0.30, 0.50, 0.70]
) -> Dict[str, Any]:
    """Evaluate candidate model across all confidence thresholds."""
    print(f"\n=======================================================", flush=True)
    print(f"Evaluating Candidate: {name}", flush=True)
    print(f"Weights: {weights_path}", flush=True)
    
    sha256 = sha256_file(weights_path)
    state = load_file(str(weights_path))
    model.load_state_dict(state, strict=True)
    model.eval()

    val_metrics = evaluate_canonical_validation(model, cached_images, conf_thresholds=conf_thresholds)
    
    for thresh_k, v in val_metrics.items():
        print(f"  [conf={thresh_k}] In-Scope IoU50: {v['inScopeTp50']}/{v['inScopeTruth']} ({v['rec50']:.1%}) | "
              f"IoU30: {v['inScopeTp30']}/{v['inScopeTruth']} ({v['rec30']:.1%}) | "
              f"Neg FP: {v['negTotalFp']} across {v['negPhotosWithFp']}/{v['totalNegPhotos']} photos ({v['fpPerPhoto']:.2f} FP/photo)", flush=True)
        print(f"    Breakdown: <8px: {v['smallLesionRecall']['tiny_less_8px']['tp50']}/{v['smallLesionRecall']['tiny_less_8px']['total']} | "
              f"8-16px: {v['smallLesionRecall']['small_8_to_16px']['tp50']}/{v['smallLesionRecall']['small_8_to_16px']['total']} | "
              f"16-32px: {v['smallLesionRecall']['medium_16_to_32px']['tp50']}/{v['smallLesionRecall']['medium_16_to_32px']['total']}", flush=True)

    return {
        'candidateName': name,
        'weightsPath': str(weights_path),
        'weightsSha256': sha256,
        'metricsByThreshold': val_metrics
    }


def apply_policy_v2(candidate_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Applies Policy v2 across all candidate x threshold combinations for tiered FP budgets."""
    flattened_entries = []
    for cand in candidate_results:
        name = cand['candidateName']
        sha = cand['weightsSha256']
        for conf_str, met in cand['metricsByThreshold'].items():
            flattened_entries.append({
                'candidateName': name,
                'weightsSha256': sha,
                'confThreshold': float(conf_str),
                'inScopeTruth': met['inScopeTruth'],
                'inScopeTp50': met['inScopeTp50'],
                'rec50': met['rec50'],
                'inScopeTp30': met['inScopeTp30'],
                'rec30': met['rec30'],
                'negTotalFp': met['negTotalFp'],
                'negPhotosWithFp': met['negPhotosWithFp'],
                'totalNegPhotos': met['totalNegPhotos'],
                'fpPerPhoto': met['fpPerPhoto'],
                'smallRecall': met['smallLesionRecall']
            })

    # FP Budget Tiers
    tiers = [
        {'tier': 'A', 'maxFpPerPhoto': 0.20, 'description': 'Strict False Positive Budget (<= 0.20 FP/photo)'},
        {'tier': 'B', 'maxFpPerPhoto': 0.50, 'description': 'Moderate False Positive Budget (<= 0.50 FP/photo)'},
        {'tier': 'C', 'maxFpPerPhoto': 1.00, 'description': 'Relaxed False Positive Budget (<= 1.00 FP/photo)'}
    ]

    tier_selections = {}
    for t in tiers:
        max_fp = t['maxFpPerPhoto']
        eligible = [e for e in flattened_entries if e['fpPerPhoto'] <= max_fp]
        if not eligible:
            tier_selections[t['tier']] = {
                'tier': t['tier'],
                'budget': max_fp,
                'status': 'NO_ELIGIBLE_CANDIDATE',
                'selected': None
            }
        else:
            # Sort rule: maximize rec50/inScopeTp50 DESC, then minimize fpPerPhoto ASC, then maximize inScopeTp30 DESC
            sorted_eligible = sorted(
                eligible,
                key=lambda x: (x['inScopeTp50'], -x['fpPerPhoto'], x['inScopeTp30']),
                reverse=True
            )
            winner = sorted_eligible[0]
            tier_selections[t['tier']] = {
                'tier': t['tier'],
                'budget': max_fp,
                'description': t['description'],
                'status': 'SELECTED',
                'selected': winner,
                'allEligibleCount': len(eligible),
                'ranking': [
                    {
                        'candidate': e['candidateName'],
                        'conf': e['confThreshold'],
                        'tp50': e['inScopeTp50'],
                        'rec50': e['rec50'],
                        'fpPerPhoto': e['fpPerPhoto'],
                        'negTotalFp': e['negTotalFp']
                    }
                    for e in sorted_eligible
                ]
            }

    # Historical Policy v1 comparison (strictly evaluated conf=0.70 with max FP <= 1.00)
    v1_eligible = [e for e in flattened_entries if e['confThreshold'] == 0.70 and e['fpPerPhoto'] <= 1.00]
    v1_winner = sorted(v1_eligible, key=lambda x: (x['inScopeTp50'], -x['fpPerPhoto']), reverse=True)[0] if v1_eligible else None

    return {
        'tierSelections': tier_selections,
        'historicalPolicyV1Selection': {
            'rule': 'Conf=0.70 with FP <= 1.00/photo',
            'selected': v1_winner
        },
        'flattenedEvaluations': flattened_entries
    }


def main():
    print("=== Model Selection Policy v2 Comparative Evaluation ===", flush=True)
    t0 = time.time()
    
    cached_images = load_canonical_validation_cache()
    print(f"Loaded {len(cached_images)} canonical validation images from cache.", flush=True)

    candidates_evaluated = []

    # 1. Baseline Model
    baseline_model = build_baseline_model()
    res_baseline = evaluate_candidate(
        name="Baseline (3-scale YOLOX-S)",
        model=baseline_model,
        weights_path=BASELINE_PATH,
        cached_images=cached_images
    )
    candidates_evaluated.append(res_baseline)

    # 2. Epoch 1 Checkpoint
    epoch1_model = build_yolox_p2_model()
    res_epoch1 = evaluate_candidate(
        name="Epoch 1 (YOLOX-S P2, step 248)",
        model=epoch1_model,
        weights_path=EPOCH1_DIR / 'model.safetensors',
        cached_images=cached_images
    )
    candidates_evaluated.append(res_epoch1)

    # 3. Epoch 2 Checkpoint
    epoch2_model = build_yolox_p2_model()
    res_epoch2 = evaluate_candidate(
        name="Epoch 2 (YOLOX-S P2, step 496)",
        model=epoch2_model,
        weights_path=EPOCH2_DIR / 'model.safetensors',
        cached_images=cached_images
    )
    candidates_evaluated.append(res_epoch2)

    # Policy v2 Analysis
    policy_report = apply_policy_v2(candidates_evaluated)

    output_payload = {
        'generatedAt': time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        'totalDurationSeconds': round(time.time() - t0, 1),
        'canonicalSet': {
            'numImages': len(cached_images),
            'inScopeTruthTotal': 53,
            'verifiedNegativePhotos': 15
        },
        'policyV2Summary': policy_report['tierSelections'],
        'historicalPolicyV1Comparison': policy_report['historicalPolicyV1Selection'],
        'candidateResults': candidates_evaluated,
        'flattenedEvaluations': policy_report['flattenedEvaluations']
    }

    out_file = TRIAL_DIR / 'selection_policy_v2_evaluation.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, indent=2)

    print(f"\n=======================================================", flush=True)
    print(f"Policy v2 Evaluation saved to: {out_file}", flush=True)
    print(f"Execution finished in {time.time() - t0:.1f}s.", flush=True)
    print(f"=======================================================", flush=True)

    # Print summary table
    print("\nSUMMARY TABLE (Selection Policy v2):")
    print(f"{'Tier / Budget':<20} | {'Selected Candidate':<32} | {'Conf':<6} | {'IoU50 Recall':<15} | {'FP / Photo':<12} | {'Total FP':<8}")
    print("-" * 105)
    for tier_k, tier_v in policy_report['tierSelections'].items():
        sel = tier_v.get('selected')
        if sel:
            cand = sel['candidateName']
            conf = f"{sel['confThreshold']:.2f}"
            rec = f"{sel['inScopeTp50']}/53 ({sel['rec50']:.1%})"
            fp_p = f"{sel['fpPerPhoto']:.2f}"
            tot_fp = f"{sel['negTotalFp']}/15"
            print(f"Tier {tier_k} (FP<={tier_v['budget']:.2f})  | {cand:<32} | {conf:<6} | {rec:<15} | {fp_p:<12} | {tot_fp:<8}")


if __name__ == '__main__':
    main()
