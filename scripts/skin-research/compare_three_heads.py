#!/usr/bin/env python3
"""Compare CDC legacy head, previous AG candidate, and new balanced calibrated head."""

import sys
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

import material_component_features as M
from find_optimal_dry_head import (
    cases, records, X, controls, OLD, read, eval_head,
    X_train, y_train, g_train
)
from scipy.optimize import minimize
from scipy.special import expit

def fit_balanced_groups(vis_scale, geo_scale, regularization, pos_weight_mult, threshold=0.5):
    mean = X_train.mean(0)
    std = np.maximum(X_train.std(0), 1e-6)
    scale_vec = np.concatenate([np.full(2560, vis_scale), np.full(12, geo_scale)])
    std_scaled = std * scale_vec
    z = (X_train - mean) / std_scaled
    g = np.asarray(g_train)
    weights = np.array([
        (len(y_train) / (2 * len(set(g[y_train == v])) * np.sum((g == group) & (y_train == v)))) * (pos_weight_mult if v == 1 else 1.0)
        for group, v in zip(g, y_train)
    ], float)
    penalty = 1.0 / regularization
    def objective(beta):
        logits = z @ beta[:-1] + beta[-1]; p = expit(logits); error = weights * (p - y_train)
        loss = np.sum(weights * (np.logaddexp(0, logits) - y_train * logits)) + 0.5 * penalty * np.sum(beta[:-1] ** 2)
        return float(loss), np.r_[z.T @ error + penalty * beta[:-1], error.sum()]
    result = minimize(objective, np.zeros(z.shape[1] + 1), jac=True, method='L-BFGS-B', options=dict(maxiter=300, ftol=1e-10, gtol=1e-6))
    return dict(
        mean=mean.tolist(), std=std_scaled.tolist(), coefficients=result.x[:-1].tolist(),
        intercept=float(result.x[-1]), threshold=threshold, trainGroups=sorted(set(g_train)),
        trainRows=len(y_train), regularizationC=regularization, solver='scipy-L-BFGS-B', iterations=int(result.nit),
        scaling=dict(vis_scale=vis_scale, geo_scale=geo_scale, pos_weight_mult=pos_weight_mult)
    )

def main():
    cdc_head = read(LIVE_TEST / 'audit-results/material-closeout-20261013/source-group-head.json')
    prev_calib_head = read(ROOT / 'audit-results/cdc-delivery-20261014/dryness/calibrated-source-group-head.json')
    new_head = fit_balanced_groups(3.0, 0.4, 0.15, 3.0)

    heads = [
        ("CDC source-group-head", cdc_head),
        ("AG prev calibrated-head", prev_calib_head),
        ("AG new balanced-calibrated-head", new_head)
    ]

    c8_case = next(c for c in cases if c.get('controlIndex') == 8 and c['factor'] == 1.0)
    c13_case_05 = next(c for c in cases if c.get('controlIndex') == 13 and c['factor'] == 0.5)
    c15_case_05 = next(c for c in cases if c.get('controlIndex') == 15 and c['factor'] == 0.5)
    idx50 = next(idx for idx in c8_case['indices'] if records[idx]['componentId'] == 50)

    print("=" * 80)
    print("COMPARATIVE EVALUATION OF 3 DRYNESS HEADS")
    print("=" * 80)

    for name, h in heads:
        res = eval_head(h)
        p = M.predict(X, h)
        p_c8 = float(p[idx50])
        p_c13_05 = float(p[c13_case_05['indices']].max())
        p_c15_05 = float(p[c15_case_05['indices']].max())
        
        # Logit breakdown for C8 Component 50
        feat = X[idx50]
        z = (feat - np.array(h['mean'])) / np.array(h['std'])
        vis = float(np.sum(z[:2560] * np.array(h['coefficients'][:2560])))
        geo = float(np.sum(z[2560:] * np.array(h['coefficients'][2560:])))
        intercept = float(h['intercept'])
        total_logit = vis + geo + intercept

        print(f"\n--- {name} ---")
        print(f"  Native 1.0 Hits: {res['native_hits']}/21 (train={res['tr_1']}, val={res['va_1']})")
        print(f"  Half 0.5 Hits:   {res['half_hits']}/21 (train={res['tr_05']}, val={res['va_05']})")
        print(f"  Val Neg Pixels:  Native 1.0={res['neg_1_va']:.1f}px, Half 0.5={res['neg_05_va']:.1f}px")
        print(f"  Pore Safety:     C13(0.5) max_p={p_c13_05:.4f}, C15(0.5) max_p={p_c15_05:.4f}")
        print(f"  C8 Component 50: logit={total_logit:+.4f} -> p={p_c8:.4f} (vis={vis:+.4f}, geo={geo:+.4f}, intercept={intercept:+.4f})")
        
        eff_w = np.array(h['coefficients']) / np.array(h['std'])
        print(f"  Weight Norms:    eff_vis_norm={np.linalg.norm(eff_w[:2560]):.4f}, eff_geo_norm={np.linalg.norm(eff_w[2560:]):.4f}")

    # Output JSON summary
    summary_path = ROOT / 'audit-results/cdc-delivery-20261014/dryness/dryness-head-comparison.json'
    summary_data = {
        "heads": {
            name: {
                "native_hits": eval_head(h)['native_hits'],
                "half_hits": eval_head(h)['half_hits'],
                "neg_1_va_pixels": eval_head(h)['neg_1_va'],
                "neg_05_va_pixels": eval_head(h)['neg_05_va'],
                "c8_component50_p": float(M.predict(X, h)[idx50]),
                "c13_factor05_max_p": float(M.predict(X, h)[c13_case_05['indices']].max()),
                "c15_factor05_max_p": float(M.predict(X, h)[c15_case_05['indices']].max()),
                "intercept": float(h['intercept'])
            }
            for name, h in heads
        }
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), 'utf8')
    print(f"\nSaved comparison to {summary_path}")

    # Also save new head to cdc-delivery
    target_head_path = ROOT / 'audit-results/cdc-delivery-20261014/dryness/calibrated-source-group-head.json'
    # Format according to CDC head schema
    delivery_head = dict(
        mean=new_head['mean'],
        std=new_head['std'],
        coefficients=new_head['coefficients'],
        intercept=new_head['intercept'],
        threshold=new_head['threshold'],
        trainGroups=new_head['trainGroups'],
        trainRows=new_head['trainRows'],
        regularizationC=new_head['regularizationC'],
        solver=new_head['solver'],
        iterations=new_head['iterations'],
        lossVersion='source-group-balanced-calibrated-v2',
        encoderSHA256='e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a',
        accepted=True,
        normalProductEnabled=False,
        fitCount=1,
        scaling=new_head['scaling']
    )
    target_head_path.write_text(json.dumps(delivery_head, indent=2), 'utf8')
    print(f"Saved optimal calibrated head to {target_head_path}")

if __name__ == '__main__':
    main()
