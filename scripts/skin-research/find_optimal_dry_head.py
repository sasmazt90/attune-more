#!/usr/bin/env python3
"""Find optimal calibrated material classifier head without visual suppression."""

import sys
import os
import json
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))
sys.path.insert(0, str(LIVE_TEST / 'scripts/skin-research'))

import material_component_features as M
from component_flake_gate import masks
from trial_region_flake_proposal import measure

OLD = LIVE_TEST / 'audit-results/native-material-contour-20261013'
CASE = LIVE_TEST / 'audit-results/native-camera-scope-20261013'
CLOSEOUT = LIVE_TEST / 'audit-results/material-closeout-20261013'

def read(p): return json.loads(p.read_text('utf8'))

controls = read(LIVE_TEST / 'audit-results/dry-sag-component-followup-20261013/object-labels.json')['controls']
review = read(OLD / 'added-components-reviewed.json')['rows']
sources = read(OLD / 'added-train-source-selection.json')
prior = read(LIVE_TEST / 'audit-results/native-dry-scale-20261013/native-gate-reviewed.json')['rows']
scale = read(LIVE_TEST / 'audit-results/native-dry-scale-20261013/independent-v3-comparison.json')['rows']
optical = read(CASE / 'single-crop-comparison.json')['rows']
baseline = read(OLD / 'material-encoder-balanced-comparison.json')

records, cases = [], []
case_index = 0

def collect(meta, metric, density, labeled):
    global case_index
    path = CASE / f'conditioned-case-{case_index:02d}.npz'
    with np.load(path) as f:
        ids = f['ids']
        component_ids = f['componentIds']
        geometry = f['X'][:, -12:].copy()
    _, _, stats, _ = cv2.connectedComponentsWithStats((ids > 0).astype(np.uint8), 8)
    indices = []
    for j, cid in enumerate(component_ids):
        row = dict(componentId=int(cid), rect=stats[cid, :4].astype(int).tolist(), geometry=geometry[j].tolist())
        indices.append(len(records))
        records.append(dict(**meta, **row, cropBoxes=M.component_crop_boxes(row, metric, density), **labeled.get(int(cid), dict(label=None, **{'class': 'UNKNOWN'}))))
    cases.append(dict(**meta, path=str(path), indices=indices))
    case_index += 1

for si, source in enumerate(sources):
    picked = [r for r in review if r['sourceIndex'] == si and r['label'] is not None]
    if picked:
        collect(dict(scope='added', sourceSHA256=source['sha256'], group=picked[0]['group'], split='train', factor=1., sourceIndex=si),
                picked[0]['coordinateScale'], 1., {r['componentId']: {k: r[k] for k in ['label', 'class']} for r in picked})

for c in controls:
    s = scale[c['controlIndex']]['referenceSpan'] / 640
    labeled = {r['nativeComponentId']: dict(label=r['label'], **{'class': 'material' if r['label'] == 1 else 'reviewed-non-flake'}) for r in prior if r['controlIndex'] == c['controlIndex']}
    for factor in [1., .5]:
        collect(dict(scope='preserved', sourceSHA256=c['sourceSHA256'], group=c['group'], split=c['split'], factor=factor, controlIndex=c['controlIndex'], kind=c['kind']),
                s * factor, factor, labeled if factor == 1 else {})

with np.load(OLD / baseline['cacheFile']) as f:
    features = f['features'].copy()
X = np.c_[features, np.array([r['geometry'] for r in records])]
train = [i for i, r in enumerate(records) if r['split'] == 'train' and r['factor'] == 1 and r['label'] is not None]

y_train = np.array([records[i]['label'] for i in train])
g_train = [records[i]['group'] for i in train]
X_train = X[train]

c13_case = next(c for c in cases if c.get('controlIndex') == 13 and c['factor'] == 0.5)

def eval_head(head):
    p = M.predict(X, head)
    rows = []
    for case in cases:
        if case['scope'] != 'preserved': continue
        c = controls[case['controlIndex']]
        meta = next(r for r in optical if r['control'] == case['controlIndex'] and r['factor'] == case['factor'])
        a, b = meta['origin']; w, h = meta['cropShape']
        local_control = {**c, 'roi': [c['roi'][0]-a, c['roi'][1]-b, *c['roi'][2:]]}
        known, objects = masks((h, w), local_control)
        with np.load(case['path']) as f:
            ids = f['ids']; field = f['field']; component_ids = f['componentIds']
            allowed = np.zeros(int(ids.max()) + 1, bool)
            allowed[component_ids] = p[case['indices']] >= head['threshold']
            field = field * allowed[ids]
        def local_mask(mask):
            return mask > 0 if case['factor'] == 1 else cv2.resize(mask, (field.shape[1], field.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
        rows.append(dict(
            control=case['controlIndex'], factor=case['factor'], split=case['split'],
            objects=[dict(index=o['index'], label=o['label'], measure=measure(field, local_mask(o['mask']), case['factor'])) for o in objects],
            negative=measure(field, local_mask(known['reviewed-non-flake']), case['factor'])
        ))
    hits_1_tr = sum(o['measure']['objectHit'] for r in rows if r['factor']==1.0 and r['split']=='train' for o in r['objects'] if o['label']=='visible-material')
    hits_1_va = sum(o['measure']['objectHit'] for r in rows if r['factor']==1.0 and r['split']=='validation' for o in r['objects'] if o['label']=='visible-material')
    hits_05_tr = sum(o['measure']['objectHit'] for r in rows if r['factor']==0.5 and r['split']=='train' for o in r['objects'] if o['label']=='visible-material')
    hits_05_va = sum(o['measure']['objectHit'] for r in rows if r['factor']==0.5 and r['split']=='validation' for o in r['objects'] if o['label']=='visible-material')
    neg_1_va = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0 and r['split']=='validation')
    neg_05_va = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==0.5 and r['split']=='validation')
    c13_p = p[c13_case['indices']].max()
    return {
        'native_hits': hits_1_tr + hits_1_va,
        'half_hits': hits_05_tr + hits_05_va,
        'tr_1': hits_1_tr, 'va_1': hits_1_va,
        'tr_05': hits_05_tr, 'va_05': hits_05_va,
        'neg_1_va': neg_1_va, 'neg_05_va': neg_05_va,
        'c13_max_p': float(c13_p)
    }

# Let's test custom fitting on TRAIN with balanced class weighting:
from scipy.optimize import minimize
from scipy.special import expit

def fit_custom(regularization=1.0, pos_weight_mult=1.0, threshold=0.5):
    mean = X_train.mean(0)
    std = np.maximum(X_train.std(0), 1e-6)
    z = (X_train - mean) / std
    
    # Group balanced loss with pos_weight_mult
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

    result = minimize(objective, np.zeros(z.shape[1] + 1), jac=True, method='L-BFGS-B', options=dict(maxiter=300, ftol=1e-10, gtol=1e-6))
    return dict(
        mean=mean.tolist(), std=std.tolist(), coefficients=result.x[:-1].tolist(),
        intercept=float(result.x[-1]), threshold=threshold, trainGroups=sorted(set(g_train)),
        trainRows=len(y_train), regularizationC=regularization, solver='scipy-L-BFGS-B', iterations=int(result.nit)
    )

if __name__ == '__main__':
    print("--- Testing higher pos_weight_mult values with C=0.5 ---")
    for pwm in [3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0]:
        h = fit_custom(regularization=0.5, pos_weight_mult=pwm)
        res = eval_head(h)
        print(f"C=0.5, pos_mult={pwm:.1f} | Intercept={h['intercept']:+.3f} | Native={res['native_hits']}/21 (tr={res['tr_1']}, va={res['va_1']}) | Half={res['half_hits']}/21 (tr={res['tr_05']}, va={res['va_05']}) | Neg va 1.0={res['neg_1_va']:.0f}px, 0.5={res['neg_05_va']:.0f}px | C13 max_p={res['c13_max_p']:.4f}")

