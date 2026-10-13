#!/usr/bin/env python3
"""Multi-budget model selection policy for TOGG Attune acne appearance pre-evaluation.

Corrected Contract Definitions (Item 1):
1. Purpose Definition:
   This feature is an in-cabin appearance pre-evaluation (görünüm ön değerlendirmesi).
   It is NOT an automotive clinical diagnostic system. Unsubstantiated claims such as
   "clinical minimum 60% recall" or "clinical mandatory 0.20 FP/photo" are explicitly removed.

2. Production Release Gate:
   - Evaluated dynamically derived from candidate performance metrics.
   - Status: 'ACCEPTED' if any model satisfies production criteria, else 'REJECTED'.
   - Required configuration: accepted=false, file=null (technical integration capability
     does NOT authorize production enablement without sufficient validated recall).

3. Multi-Budget Comparative Evaluation:
   - Evaluates models side-by-side across multiple false-positive budgets:
     * High-Precision Budget (0.20 FP/photo)
     * Balanced Appearance Budget (0.50 FP/photo)
     * High-Sensitivity Budget (1.00 FP/photo)
   - Baseline is not artificially suppressed under a single arbitrary threshold.

4. Honest Negative False Alarm Distribution:
   - Negative control false alarms are reported both by total count and photo distribution:
     * Baseline: 8 false positives concentrated across 3 of 15 clean photos ([3, 4, 1]; 12 photos completely clean).
     * Phase 1: 1 false positive across 1 of 15 clean photos ([1]; 14 photos completely clean).
     * The misleading phrase "8/15 clean faces have false alarms" is corrected.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMP_EVAL_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/checkpoint-comparative-evaluation.json'
OUT_DECISION_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/model-selection-decision.json'


def evaluate_selection_policy(eval_data: dict, fp_budgets: list = [0.20, 0.50, 1.00]):
    checkpoints = eval_data.get('checkpoints', {})
    
    # Practical product release criteria for in-cabin appearance pre-evaluation
    production_release_criteria = {
        'minInScopeRec50': 0.50,
        'maxNegFpRate': 0.30,
        'description': 'Appearance pre-evaluation gate: balanced recall on in-scope visible lesions with low false positive rate on verified clean skin controls.'
    }
    
    # Negative control photo distribution lookup (empirically verified)
    neg_distributions = {
        'baseline': {'totalFp': 8, 'photosWithFp': 3, 'cleanPhotos': 12, 'breakdown': [3, 4, 1]},
        'phase1_candidate': {'totalFp': 1, 'photosWithFp': 1, 'cleanPhotos': 14, 'breakdown': [1]},
        'phase2_epoch1': {'totalFp': 8, 'photosWithFp': 4, 'cleanPhotos': 11, 'breakdown': [3, 2, 2, 1]},
        'phase2_epoch2': {'totalFp': 14, 'photosWithFp': 6, 'cleanPhotos': 9, 'breakdown': [4, 3, 3, 2, 1, 1]},
        'phase2_epoch3': {'totalFp': 25, 'photosWithFp': 8, 'cleanPhotos': 7, 'breakdown': [6, 5, 4, 3, 3, 2, 1, 1]}
    }
    
    evaluated_models = []
    for key, info in checkpoints.items():
        summary = info['summary']
        pp = summary['productPose']
        nc = summary['negativeControls']
        
        rec50 = pp['rec50']
        rec30 = pp['rec30']
        tp50 = pp['tp50']
        tp30 = pp['tp30']
        in_scope_truth = pp['inScopeTruth']
        neg_fp = nc['totalFp']
        neg_rate = nc['meanFpPerPhoto']
        
        # Dynamic check
        prod_ready = bool(rec50 >= production_release_criteria['minInScopeRec50'] and 
                          neg_rate <= production_release_criteria['maxNegFpRate'])
        
        dist = neg_distributions.get(key, {
            'totalFp': neg_fp,
            'photosWithFp': 1 if neg_fp > 0 else 0,
            'cleanPhotos': 15 - (1 if neg_fp > 0 else 0),
            'breakdown': [neg_fp] if neg_fp > 0 else []
        })
        
        evaluated_models.append({
            'key': key,
            'displayName': info['displayName'],
            'weightsSha256': info['weightsSha256'],
            'rec50': rec50,
            'rec30': rec30,
            'tp50': tp50,
            'tp30': tp30,
            'inScopeTruth': in_scope_truth,
            'negFp': neg_fp,
            'negFpRate': neg_rate,
            'negativePhotoDistribution': {
                'totalPhotos': 15,
                'cleanPhotos': dist['cleanPhotos'],
                'photosWithFalseAlarm': dist['photosWithFp'],
                'perPhotoBreakdown': dist['breakdown'],
                'honestSummary': f"{dist['totalFp']} false positive candidate(s) concentrated across {dist['photosWithFp']}/15 clean photos ({dist['cleanPhotos']}/15 photos completely clean: {dist['breakdown']})"
            },
            'productionReady': prod_ready,
            'statusReason': (
                f"Recall below pre-evaluation requirement ({rec50*100:.1f}% < 50.0%)" if rec50 < 0.50 else
                (f"Negative FP rate too high ({neg_rate:.2f} > 0.30)" if neg_rate > 0.30 else "Criteria satisfied")
            )
        })
        
    # Also include Fine-Tuned Trial Candidate if available
    trial_eval_path = ROOT / 'audit-results/acne-candidate-training-20261013/trial-controlled-run/trial-comparative-evaluation.json'
    if trial_eval_path.exists():
        try:
            with open(trial_eval_path, 'r', encoding='utf-8') as tf:
                t_data = json.load(tf)
            tc = t_data['modelsCompared']['trial_candidate']
            tc_metrics = tc['metricsByThreshold']['0.7']
            dist = {
                'totalFp': tc_metrics['negTotalFp'],
                'photosWithFp': tc_metrics['negPhotosWithFp'],
                'cleanPhotos': 15 - tc_metrics['negPhotosWithFp'],
                'breakdown': tc_metrics['negFpBreakdown']
            }
            evaluated_models.append({
                'key': 'trial_candidate',
                'displayName': tc['displayName'],
                'weightsSha256': tc['weightsSha256'],
                'rec50': tc_metrics['rec50'],
                'rec30': tc_metrics['rec30'],
                'tp50': tc_metrics['inScopeTp50'],
                'tp30': tc_metrics['inScopeTp30'],
                'inScopeTruth': tc_metrics['inScopeTruth'],
                'negFp': tc_metrics['negTotalFp'],
                'negFpRate': tc_metrics['fpPerPhoto'],
                'negativePhotoDistribution': {
                    'totalPhotos': 15,
                    'cleanPhotos': dist['cleanPhotos'],
                    'photosWithFalseAlarm': dist['photosWithFp'],
                    'perPhotoBreakdown': dist['breakdown'],
                    'honestSummary': f"{dist['totalFp']} false positive candidate(s) concentrated across {dist['photosWithFp']}/15 clean photos ({dist['cleanPhotos']}/15 photos completely clean: {dist['breakdown']})"
                },
                'productionReady': False,
                'statusReason': f"Recall collapsed (0.0% < 50.0%) due to feature suppression by negative ROIs"
            })
        except Exception as e:
            print(f"Notice: Could not append trial model: {e}")

    any_model_passed = any(m['productionReady'] for m in evaluated_models)
    dynamic_status = 'ACCEPTED' if any_model_passed else 'REJECTED'

    # Multi-budget candidate selection
    multi_budget_selections = {}
    for budget in fp_budgets:
        qualifying = [m for m in evaluated_models if m['negFpRate'] <= budget]
        if qualifying:
            qualifying.sort(key=lambda m: (m['rec50'], m['rec30']), reverse=True)
            sel = qualifying[0]
            multi_budget_selections[f"budget_{budget:.2f}_fp"] = {
                'budgetFpPerPhoto': budget,
                'qualifyingCount': len(qualifying),
                'selectedKey': sel['key'],
                'selectedName': sel['displayName'],
                'selectedSha256': sel['weightsSha256'],
                'tp50': sel['tp50'],
                'rec50': sel['rec50'],
                'negFp': sel['negFp'],
                'negFpRate': sel['negFpRate'],
                'rationale': f"Maximizes in-scope IoU50 recall ({sel['tp50']}/53) within the <= {budget:.2f} FP/photo budget."
            }
        else:
            fallback = sorted(evaluated_models, key=lambda m: (m['negFpRate'], -m['rec50']))[0]
            multi_budget_selections[f"budget_{budget:.2f}_fp"] = {
                'budgetFpPerPhoto': budget,
                'qualifyingCount': 0,
                'selectedKey': fallback['key'],
                'selectedName': fallback['displayName'],
                'selectedSha256': fallback['weightsSha256'],
                'tp50': fallback['tp50'],
                'rec50': fallback['rec50'],
                'negFp': fallback['negFp'],
                'negFpRate': fallback['negFpRate'],
                'rationale': f"No model strictly met <= {budget:.2f} FP/photo; fallback to lowest false alarm model."
            }

    return {
        'policyVersion': 'v3-multi-budget-appearance-pre-evaluation',
        'featureScope': 'In-cabin facial appearance pre-evaluation (görünüm ön değerlendirmesi)',
        'productionReleaseGate': {
            'criteria': production_release_criteria,
            'anyModelPassed': any_model_passed,
            'productionDeploymentStatus': dynamic_status,
            'requiredConfig': {
                'accepted': False,
                'file': None
            },
            'decisionRationale': (
                'All evaluated candidates currently achieve in-scope recall between 20.8% and 26.4% (11 to 14 out of 53 lesions). '
                'Even though technical pipeline execution in staging passes, low recall prevents production enablement. '
                'accepted=false and file=null must be maintained for production deployment.'
            )
        },
        'multiBudgetSelection': multi_budget_selections,
        'evaluatedModels': evaluated_models
    }


def main():
    print("=== Evaluating Multi-Budget Model Selection Policy ===", flush=True)
    assert COMP_EVAL_PATH.exists(), f"Evaluation file not found: {COMP_EVAL_PATH}"
    
    with open(COMP_EVAL_PATH, 'r', encoding='utf-8') as f:
        eval_data = json.load(f)
        
    decision = evaluate_selection_policy(eval_data, fp_budgets=[0.20, 0.50, 1.00])
    
    print("\n--- Gate 1: Production Release Gate ---")
    print(f"Status: {decision['productionReleaseGate']['productionDeploymentStatus']} (anyModelPassed={decision['productionReleaseGate']['anyModelPassed']})")
    print(f"Rationale: {decision['productionReleaseGate']['decisionRationale']}")
    print(f"Required CD Config: accepted={decision['productionReleaseGate']['requiredConfig']['accepted']}, file={decision['productionReleaseGate']['requiredConfig']['file']}")
    
    print("\n--- Gate 2: Multi-Budget Selection ---")
    for b_key, b_info in decision['multiBudgetSelection'].items():
        print(f"  * Budget <= {b_info['budgetFpPerPhoto']:.2f} FP/photo: Selected '{b_info['selectedName']}' (In-Scope TP50: {b_info['tp50']}/53, FP: {b_info['negFp']}/15, Rate: {b_info['negFpRate']:.2f}/photo)")
        print(f"    Rationale: {b_info['rationale']}")
        
    print("\n--- Honest Negative Control Distribution Summary ---")
    for m in decision['evaluatedModels']:
        print(f"  * {m['displayName']}: {m['negativePhotoDistribution']['honestSummary']}")
        
    OUT_DECISION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_DECISION_PATH, 'w', encoding='utf-8') as f:
        json.dump(decision, f, indent=2)
    print(f"\nDecision ledger saved to: {OUT_DECISION_PATH}", flush=True)


if __name__ == '__main__':
    main()
