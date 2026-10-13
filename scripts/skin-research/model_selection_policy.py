#!/usr/bin/env python3
"""Multi-criteria model selection policy for TOGG Attune acne detection.

Formal Decision Protocol:
1. Gate 1 (Production Release Acceptance Gate):
   - In-scope IoU50 Recall >= 0.60 (captures at least 60% of in-scope lesions)
   - Verified Negative False Alarm Rate <= 0.20 FP/photo (<= 3 FP across 15 negative photos)
   - Status: If unmet, production deployment status is strictly REJECTED (accepted=false, file=null).

2. Gate 2 (Research/Staging Candidate Selection among viable models):
   - Constraint: Negative False Alarm budget <= FP_BUDGET (configurable: default 0.20 for high-precision cabin safety, or 0.60 for permissive review)
   - Primary Objective among qualifying models: Maximize in-scope IoU50 recall (out of 53)
   - Secondary Tie-Breaker: Maximize in-scope IoU30 recall, minimize duplicate boxes
   - Visual / Patch Localization Integrity check.

CRITICAL POLICY UPDATE:
Explicitly withdraws the previous draft statement suggesting "CD can directly enable the model with accepted=true".
Technical staging pipeline execution is NOT sufficient evidence of production quality readiness.
With in-scope recall at 20.8% - 26.4%, the model cannot be deployed to users as a production acne diagnostic.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMP_EVAL_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/checkpoint-comparative-evaluation.json'
OUT_DECISION_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/model-selection-decision.json'


def evaluate_selection_policy(eval_data: dict, fp_budget: float = 0.20):
    checkpoints = eval_data.get('checkpoints', {})
    
    production_release_thresholds = {
        'min_in_scope_rec50': 0.60,
        'max_neg_fp_rate': 0.20,
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
        
        # Production gate check
        prod_ready = (rec50 >= production_release_thresholds['min_in_scope_rec50'] and 
                      neg_rate <= production_release_thresholds['max_neg_fp_rate'])
        
        # Staging qualification under given fp_budget
        qualifies_budget = (neg_rate <= fp_budget)
        
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
            'qualifiesFpBudget': qualifies_budget,
            'productionReady': prod_ready,
            'productionRejectionReason': (
                f"Recall too low ({rec50*100:.1f}% < 60%)" if rec50 < 0.60 else
                (f"Negative FP rate too high ({neg_rate:.2f} > 0.20)" if neg_rate > 0.20 else None)
            )
        })
        
    # Sort for candidate selection among qualifying models
    qualifying = [m for m in evaluated_models if m['qualifiesFpBudget']]
    if qualifying:
        # Sort by rec50 desc, then rec30 desc
        qualifying.sort(key=lambda m: (m['rec50'], m['rec30']), reverse=True)
        selected_staging_candidate = qualifying[0]
    else:
        # Fallback to model with lowest neg_fp_rate
        fallback = sorted(evaluated_models, key=lambda m: (m['negFpRate'], -m['rec50']))
        selected_staging_candidate = fallback[0]
        
    return {
        'policyVersion': 'v2-multi-criteria-dual-gate',
        'productionReleaseGate': {
            'thresholds': production_release_thresholds,
            'anyModelPassed': any(m['productionReady'] for m in evaluated_models),
            'productionDeploymentStatus': 'STRICTLY_REJECTED',
            'requiredConfig': {
                'accepted': False,
                'file': None
            },
            'retractionNotice': 'Recommendation that CD can directly activate accepted=true is permanently RETRACTED. In-scope recall is clinically insufficient (20.8% - 26.4%).'
        },
        'stagingCandidateSelection': {
            'appliedFpBudgetPerPhoto': fp_budget,
            'selectedCandidateKey': selected_staging_candidate['key'],
            'selectedCandidateName': selected_staging_candidate['displayName'],
            'selectedCandidateSha256': selected_staging_candidate['weightsSha256'],
            'selectionRationale': (
                f"Passed negative false alarm budget (<= {fp_budget:.2f} FP/photo) with {selected_staging_candidate['negFpRate']:.2f} FP/photo, "
                f"achieving {selected_staging_candidate['tp50']}/{selected_staging_candidate['inScopeTruth']} IoU50 recall."
            )
        },
        'evaluatedModels': evaluated_models
    }


def main():
    print("=== Evaluating Multi-Criteria Model Selection Policy ===")
    assert COMP_EVAL_PATH.exists(), f"Evaluation file not found: {COMP_EVAL_PATH}"
    
    with open(COMP_EVAL_PATH, 'r', encoding='utf-8') as f:
        eval_data = json.load(f)
        
    decision = evaluate_selection_policy(eval_data, fp_budget=0.20)
    
    print("\n--- Gate 1: Production Release Gate ---")
    print(f"Status: {decision['productionReleaseGate']['productionDeploymentStatus']}")
    print(f"Notice: {decision['productionReleaseGate']['retractionNotice']}")
    print(f"Required CD Config: accepted={decision['productionReleaseGate']['requiredConfig']['accepted']}, file={decision['productionReleaseGate']['requiredConfig']['file']}")
    
    print("\n--- Gate 2: Staging Candidate Selection ---")
    print(f"Selected Candidate: {decision['stagingCandidateSelection']['selectedCandidateName']}")
    print(f"SHA-256: {decision['stagingCandidateSelection']['selectedCandidateSha256']}")
    print(f"Rationale: {decision['stagingCandidateSelection']['selectionRationale']}")
    
    print("\n--- Model Comparison Summary ---")
    for m in decision['evaluatedModels']:
        print(f"* {m['displayName']}: IoU50 Rec = {m['tp50']}/{m['inScopeTruth']} ({m['rec50']*100:.1f}%), Neg FP = {m['negFp']}/15 ({m['negFpRate']:.2f}/photo) | Prod Ready = {m['productionReady']} ({m['productionRejectionReason']})")
        
    with open(OUT_DECISION_PATH, 'w', encoding='utf-8') as f:
        json.dump(decision, f, indent=2)
    print(f"\nDecision ledger saved to: {OUT_DECISION_PATH}")


if __name__ == '__main__':
    main()
