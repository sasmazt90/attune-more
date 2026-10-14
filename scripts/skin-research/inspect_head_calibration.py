#!/usr/bin/env python3
"""Calibrate Dryness Material Classifier Intercept and Threshold."""

import sys
import os
import json
from pathlib import Path
import numpy as np

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
import cv2

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
val = [i for i, r in enumerate(records) if r['split'] == 'validation' and r['factor'] == 1 and r['label'] is not None]

y_train = [records[i]['label'] for i in train]
g_train = [records[i]['group'] for i in train]
X_train = X[train]

# Fit NoGroupSizes model
head = M.fit_classifier(X_train, y_train, g_train, regularization=1.0, feature_group_sizes=None, group_balanced_loss=True)

# Calculate un-intercepted logits z @ beta
z = (X - head['mean']) / head['std']
raw_logits = z @ np.asarray(head['coefficients'])

# Let's inspect raw_logits on train positives vs train negatives vs val positives vs val negatives
print("Raw logits (before intercept):")
print(f"  Train positive (19 rows): min={raw_logits[train][np.array(y_train)==1].min():.2f}, mean={raw_logits[train][np.array(y_train)==1].mean():.2f}, max={raw_logits[train][np.array(y_train)==1].max():.2f}")
print(f"  Train negative (44 rows): min={raw_logits[train][np.array(y_train)==0].min():.2f}, mean={raw_logits[train][np.array(y_train)==0].mean():.2f}, max={raw_logits[train][np.array(y_train)==0].max():.2f}")

y_val = np.array([records[i]['label'] for i in val])
print(f"  Val positive ({sum(y_val==1)} rows): min={raw_logits[val][y_val==1].min():.2f}, mean={raw_logits[val][y_val==1].mean():.2f}, max={raw_logits[val][y_val==1].max():.2f}")
print(f"  Val negative ({sum(y_val==0)} rows): min={raw_logits[val][y_val==0].min():.2f}, mean={raw_logits[val][y_val==0].mean():.2f}, max={raw_logits[val][y_val==0].max():.2f}")

c13_case = next(c for c in cases if c.get('controlIndex') == 13 and c['factor'] == 0.5)
c13_logits = raw_logits[c13_case['indices']]
print(f"  C13 (scale 0.5 pore texture, {len(c13_logits)} components): max raw logit = {c13_logits.max():.2f}, mean = {c13_logits.mean():.2f}")

# Look at separation:
val_neg_max = raw_logits[val][y_val==0].max()
c13_max = c13_logits.max()
max_negative_logit = max(val_neg_max, c13_max)
print(f"\nMax negative logit across all val negatives & C13: {max_negative_logit:.2f}")

val_pos_sorted = np.sort(raw_logits[val][y_val==1])
print(f"Val positive logits (sorted): {[round(float(v), 2) for v in val_pos_sorted]}")

# If we set intercept such that max_negative_logit has prob < 0.20 (e.g. logit <= -1.39)
# Or threshold tuning:
def test_intercept(intercept_val):
    test_head = dict(head)
    test_head['intercept'] = float(intercept_val)
    p = M.predict(X, test_head)
    # Evaluate
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
            allowed[component_ids] = p[case['indices']] >= 0.5
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
    print(f"Intercept={intercept_val:+.2f} | Native Hits: {hits_1_tr+hits_1_va}/21 (tr={hits_1_tr}, va={hits_1_va}) | Half Hits: {hits_05_tr+hits_05_va}/21 | Neg va 1.0={neg_1_va:.0f}px, 0.5={neg_05_va:.0f}px | C13 max_p={c13_p:.4f}")

print("\n--- Sweeping Intercept ---")
for b in [-2.5, -2.0, -1.8, -1.5, -1.2, -1.0, -0.8, -0.5, -0.2]:
    test_intercept(b)
