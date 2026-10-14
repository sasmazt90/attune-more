#!/usr/bin/env python3
"""Retrain and evaluate dry head to eliminate C04 negative support while maintaining 14/21 native hits."""

import sys
import json
from pathlib import Path
import numpy as np
import cv2
from scipy.optimize import minimize
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

from find_optimal_dry_head import cases, records, X, controls, OLD, read, optical
import material_component_features as M
from component_flake_gate import masks
from trial_region_flake_proposal import measure

def get_full_evaluation(head):
    p = M.predict(X, head)
    rows = []
    for case in cases:
        if case['scope'] != 'preserved':
            continue
        ci = case['controlIndex']
        c = controls[ci]
        meta = next(r for r in optical if r['control'] == ci and r['factor'] == case['factor'])
        a, b = meta['origin']
        w, h_crop = meta['cropShape']
        local_control = {**c, 'roi': [c['roi'][0]-a, c['roi'][1]-b, *c['roi'][2:]]}
        known, objects = masks((h_crop, w), local_control)
        with np.load(case['path']) as f:
            ids = f['ids']
            field = f['field']
            component_ids = f['componentIds']
            allowed = np.zeros(int(ids.max()) + 1, bool)
            allowed[component_ids] = p[case['indices']] >= head['threshold']
            field = field * allowed[ids]

        def local_mask(mask):
            return mask > 0 if case['factor'] == 1 else cv2.resize(mask, (field.shape[1], field.shape[0]), interpolation=cv2.INTER_NEAREST) > 0

        rows.append(dict(
            control=ci, factor=case['factor'], split=case['split'],
            objects=[dict(index=o['index'], label=o['label'], measure=measure(field, local_mask(o['mask']), case['factor'])) for o in objects],
            negative=measure(field, local_mask(known['reviewed-non-flake']), case['factor'])
        ))

    hits_1_tr = sum(o['measure']['objectHit'] for r in rows if r['factor']==1.0 and r['split']=='train' for o in r['objects'] if o['label']=='visible-material')
    hits_1_va = sum(o['measure']['objectHit'] for r in rows if r['factor']==1.0 and r['split']=='validation' for o in r['objects'] if o['label']=='visible-material')
    hits_05_tr = sum(o['measure']['objectHit'] for r in rows if r['factor']==0.5 and r['split']=='train' for o in r['objects'] if o['label']=='visible-material')
    hits_05_va = sum(o['measure']['objectHit'] for r in rows if r['factor']==0.5 and r['split']=='validation' for o in r['objects'] if o['label']=='visible-material')
    
    neg_1_all = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0)
    neg_1_c04 = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0 and r['control']==4)
    neg_1_va = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0 and r['split']=='validation')
    neg_05_all = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==0.5)
    neg_05_va = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==0.5 and r['split']=='validation')

    c08_obj0 = next(o for r in rows if r['control']==8 and r['factor']==1.0 for o in r['objects'] if o['index']==0)

    return {
        'native_hits': hits_1_tr + hits_1_va,
        'half_hits': hits_05_tr + hits_05_va,
        'tr_1': hits_1_tr, 'va_1': hits_1_va,
        'tr_05': hits_05_tr, 'va_05': hits_05_va,
        'neg_1_c04': neg_1_c04,
        'neg_1_all': neg_1_all,
        'neg_1_va': neg_1_va,
        'neg_05_all': neg_05_all,
        'neg_05_va': neg_05_va,
        'c08_obj0_hit': c08_obj0['measure']['objectHit'],
        'c08_obj0_px': c08_obj0['measure']['activeSourcePixels'],
        'threshold': head['threshold']
    }

def build_training_set(include_c04_negative=True, include_all_train_negatives=False):
    train_indices = []
    y_list = []
    g_list = []

    # First, the existing labeled records from train
    for i, r in enumerate(records):
        if r['split'] == 'train' and r['factor'] == 1.0 and r['label'] is not None:
            train_indices.append(i)
            y_list.append(r['label'])
            g_list.append(r['group'])

    # Now, check for C04 or other train components with reviewed negative overlap
    if include_c04_negative:
        # C04 CID 29 (rec idx 90)
        c04_idx = next(i for i, r in enumerate(records) if r.get('controlIndex') == 4 and r['factor'] == 1.0 and r['componentId'] == 29)
        if c04_idx not in train_indices:
            train_indices.append(c04_idx)
            y_list.append(0)
            g_list.append(records[c04_idx]['group'])

    if include_all_train_negatives:
        # Check all train cases for components overlapping with reviewed-non-flake
        for case in cases:
            if case['scope'] != 'preserved' or case['factor'] != 1.0 or case['split'] != 'train':
                continue
            ci = case['controlIndex']
            c = controls[ci]
            meta = next(r for r in optical if r['control'] == ci and r['factor'] == 1.0)
            a, b = meta['origin']
            w, h_crop = meta['cropShape']
            local_control = {**c, 'roi': [c['roi'][0]-a, c['roi'][1]-b, *c['roi'][2:]]}
            known, objects = masks((h_crop, w), local_control)
            with np.load(case['path']) as f:
                ids = f['ids']
                comp_ids = f['componentIds']
                for cid in comp_ids:
                    mask = (ids == cid)
                    pos_px = int((mask & (known['visible-material'] > 0)).sum())
                    neg_px = int((mask & (known['reviewed-non-flake'] > 0)).sum())
                    if neg_px > 0 and pos_px == 0:
                        idx = next(i for i in case['indices'] if records[i]['componentId'] == cid)
                        if idx not in train_indices:
                            train_indices.append(idx)
                            y_list.append(0)
                            g_list.append(records[idx]['group'])

    return train_indices, np.array(y_list), g_list

def fit_model(train_indices, y_train, g_train, vis_scale=3.0, geo_scale=0.4, regularization=0.15, pos_weight_mult=3.0, threshold=0.50):
    X_train = X[train_indices]
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
        logits = z @ beta[:-1] + beta[-1]
        p = expit(logits)
        error = weights * (p - y_train)
        loss = np.sum(weights * (np.logaddexp(0, logits) - y_train * logits)) + 0.5 * penalty * np.sum(beta[:-1] ** 2)
        return float(loss), np.r_[z.T @ error + penalty * beta[:-1], error.sum()]

    result = minimize(objective, np.zeros(z.shape[1] + 1), jac=True, method='L-BFGS-B', options=dict(maxiter=500, ftol=1e-11, gtol=1e-7))
    return dict(
        mean=mean.tolist(), std=std_scaled.tolist(), coefficients=result.x[:-1].tolist(),
        intercept=float(result.x[-1]), threshold=threshold, trainGroups=sorted(set(g_train)),
        trainRows=len(y_train), regularizationC=regularization, solver='scipy-L-BFGS-B', iterations=int(result.nit),
        scaling=dict(vis_scale=vis_scale, geo_scale=geo_scale, pos_weight_mult=pos_weight_mult)
    )

def main():
    print("=== RETRAINING EXPERIMENTS WITH SCALED FEATURES ===")
    
    for mode_name, inc_c04, inc_all in [("C04 only", True, False), ("All train negs", True, True)]:
        train_indices, y_train, g_train = build_training_set(inc_c04, inc_all)
        print(f"\n--- Mode: {mode_name} (train rows={len(y_train)}, pos={sum(y_train==1)}, neg={sum(y_train==0)}) ---")
        
        for reg in [0.08, 0.10, 0.12, 0.15, 0.20, 0.25]:
            for pwm in [2.5, 3.0, 3.5, 4.0]:
                for t in [0.48, 0.50, 0.52]:
                    h = fit_model(train_indices, y_train, g_train, vis_scale=3.0, geo_scale=0.4, regularization=reg, pos_weight_mult=pwm, threshold=t)
                    res = get_full_evaluation(h)
                    if res['native_hits'] >= 14 and res['half_hits'] >= 13 and res['neg_1_c04'] == 0 and res['neg_1_va'] == 0 and res['neg_05_va'] == 0 and res['c08_obj0_hit']:
                        print(f"!!! WINNER FOUND !!! reg={reg:4.2f}, pwm={pwm:3.1f}, t={t:.2f} -> 1.0x: {res['native_hits']}/21 (tr={res['tr_1']}, va={res['va_1']}), 0.5x: {res['half_hits']}/21 (tr={res['tr_05']}, va={res['va_05']}), C04 neg: {res['neg_1_c04']:.0f}px, Tot 1.0 neg: {res['neg_1_all']:.0f}px, Val 1.0 neg: {res['neg_1_va']:.0f}px, C08 obj0: {res['c08_obj0_hit']} ({res['c08_obj0_px']:.0f}px)")
                    elif res['c08_obj0_hit'] and res['neg_1_c04'] == 0 and res['neg_1_va'] == 0:
                        print(f"Candidate: reg={reg:4.2f}, pwm={pwm:3.1f}, t={t:.2f} -> 1.0x: {res['native_hits']}/21, 0.5x: {res['half_hits']}/21, C04 neg: {res['neg_1_c04']:.0f}px, Tot 1.0 neg: {res['neg_1_all']:.0f}px, C08 obj0: {res['c08_obj0_hit']} ({res['c08_obj0_px']:.0f}px)")

if __name__ == '__main__':
    main()
