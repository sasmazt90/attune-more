#!/usr/bin/env python3
"""Targeted Dryness Material Classifier Diagnosis and Calibration.

Investigates:
1. Geometric vs visual feature contribution to native / half-source discrepancy.
2. The root cause of C13 negative support explosion (216px at scale 0.5):
   Is it caused by feature_group_sizes=[1280, 1280, 12] suppressing visual features 10x?
3. The root cause of 0/0 support on glasses-free 24031977 and missed C00/C09 material:
   Is it caused by the overly negative intercept (-0.5775)?
4. Fits calibrated classifier on TRAIN components (63 rows, 15 groups):
   - Without artificial visual suppression
   - Preserving true material (y=1) in C00, C09, and 24031977 >= 0.50
   - Ensuring verified negative validation components stay < 0.20
   - Eliminating the 216px C13 half-source false support
"""

import sys
import os
import json
import hashlib
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

OUT_DIR = ROOT / 'audit-results/material-closeout-20261014'
OUT_DIR.mkdir(parents=True, exist_ok=True)

OLD = LIVE_TEST / 'audit-results/native-material-contour-20261013'
CASE = LIVE_TEST / 'audit-results/native-camera-scope-20261013'
CLOSEOUT = LIVE_TEST / 'audit-results/material-closeout-20261013'


def read(p):
    return json.loads(p.read_text('utf8'))


def main():
    print("=== TOGG Attune Dryness Material Head Diagnosis & Calibration ===", flush=True)

    controls = read(LIVE_TEST / 'audit-results/dry-sag-component-followup-20261013/object-labels.json')['controls']
    review = read(OLD / 'added-components-reviewed.json')['rows']
    sources = read(OLD / 'added-train-source-selection.json')
    prior = read(LIVE_TEST / 'audit-results/native-dry-scale-20261013/native-gate-reviewed.json')['rows']
    scale = read(LIVE_TEST / 'audit-results/native-dry-scale-20261013/independent-v3-comparison.json')['rows']
    optical = read(CASE / 'single-crop-comparison.json')['rows']
    baseline = read(OLD / 'material-encoder-balanced-comparison.json')

    records = []
    cases = []
    case_index = 0

    def collect(meta, metric, density, labeled):
        nonlocal case_index
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

    print(f"Total reconstructed component records: {len(records)} across {len(cases)} cases", flush=True)

    with np.load(OLD / baseline['cacheFile']) as f:
        features = f['features'].copy()
    assert features.shape == (len(records), 2560)
    X = np.c_[features, np.array([r['geometry'] for r in records])]

    train = [i for i, r in enumerate(records) if r['split'] == 'train' and r['factor'] == 1 and r['label'] is not None]
    val_indices = [i for i, r in enumerate(records) if r['split'] == 'validation' and r['factor'] == 1 and r['label'] is not None]

    print(f"Train labeled components: {len(train)} (15 groups)")
    print(f"Validation labeled components: {len(val_indices)}")

    # Load CDC existing source-group-head
    cdc_head = read(CLOSEOUT / 'source-group-head.json')
    cdc_p = M.predict(X, cdc_head)

    def evaluate_predictions(p):
        rows = []
        for case in cases:
            if case['scope'] != 'preserved':
                continue
            c = controls[case['controlIndex']]
            meta = next(r for r in optical if r['control'] == case['controlIndex'] and r['factor'] == case['factor'])
            a, b = meta['origin']
            w, h = meta['cropShape']
            local_control = {**c, 'roi': [c['roi'][0] - a, c['roi'][1] - b, *c['roi'][2:]]}
            known, objects = masks((h, w), local_control)
            with np.load(case['path']) as f:
                ids = f['ids']
                field = f['field']
                component_ids = f['componentIds']
                allowed = np.zeros(int(ids.max()) + 1, bool)
                allowed[component_ids] = p[case['indices']] >= 0.5
                field = field * allowed[ids]

            def local_mask(mask):
                return mask > 0 if case['factor'] == 1 else cv2.resize(mask, (field.shape[1], field.shape[0]), interpolation=cv2.INTER_NEAREST) > 0

            rows.append(dict(
                control=case['controlIndex'],
                source=c['sourceSHA256'],
                split=case['split'],
                factor=case['factor'],
                kind=case['kind'],
                objects=[dict(index=o['index'], label=o['label'], measure=measure(field, local_mask(o['mask']), case['factor'])) for o in objects],
                negative=measure(field, local_mask(known['reviewed-non-flake']), case['factor'])
            ))
        return rows

    def summarize(eval_rows):
        res = []
        for factor in [1.0, 0.5]:
            for split in ['train', 'validation']:
                hits = sum(o['measure']['objectHit'] for r in eval_rows if r['factor'] == factor and r['split'] == split for o in r['objects'] if o['label'] == 'visible-material')
                total_objs = sum(1 for r in eval_rows if r['factor'] == factor and r['split'] == split for o in r['objects'] if o['label'] == 'visible-material')
                neg_px = sum(r['negative']['activeSourcePixels'] for r in eval_rows if r['factor'] == factor and r['split'] == split)
                res.append(dict(factor=factor, split=split, hits=hits, totalObjects=total_objs, negativeSourcePixels=neg_px))
        return res

    print("\n--- CDC Baseline Evaluation (source-group-head.json) ---")
    cdc_eval = evaluate_predictions(cdc_p)
    cdc_sum = summarize(cdc_eval)
    for s in cdc_sum:
        print(f"  Factor {s['factor']} {s['split']:10s} -> Hits: {s['hits']}/{s['totalObjects']} | Neg Px: {s['negativeSourcePixels']}")

    # Let's inspect C13 specifically under CDC head
    c13_case = next(c for c in cases if c.get('controlIndex') == 13 and c['factor'] == 0.5)
    print(f"C13 (scale 0.5) max prob in CDC head: {float(cdc_p[c13_case['indices']].max()):.4f}, num components: {len(c13_case['indices'])}")

    # Now let's explore training without artificial 10x visual suppression:
    # 1. Standard normalization (feature_group_sizes=None)
    # 2. Balanced loss per group
    # 3. Regularization sweep
    print("\n--- Exploring Calibrated Classifier Fits ---")

    y_train = [records[i]['label'] for i in train]
    g_train = [records[i]['group'] for i in train]
    X_train = X[train]

    candidates = [
        ("NoGroupSizes_C1.0", dict(regularization=1.0, feature_group_sizes=None, group_balanced_loss=True)),
        ("NoGroupSizes_C2.0", dict(regularization=2.0, feature_group_sizes=None, group_balanced_loss=True)),
        ("NoGroupSizes_C0.5", dict(regularization=0.5, feature_group_sizes=None, group_balanced_loss=True)),
        ("EqualBlockNorm_C1.0", dict(regularization=1.0, feature_group_sizes=[1280, 1280, 12], group_balanced_loss=True)), # baseline
        ("VisualBalanced_C1.0", dict(regularization=1.0, feature_group_sizes=[2560, 12], group_balanced_loss=True)),
    ]

    best_head = None
    best_summary = None
    best_name = None

    for name, kwargs in candidates:
        if kwargs['feature_group_sizes'] == [2560, 12]:
            # Custom normalization: scale visual by sqrt(2560) and geometry by sqrt(12), or don't scale
            # Actually let's test feature_group_sizes=[2560, 12] in fit_classifier
            head = M.fit_classifier(X_train, y_train, g_train, regularization=kwargs['regularization'], feature_group_sizes=[2560, 12], group_balanced_loss=kwargs['group_balanced_loss'])
        else:
            head = M.fit_classifier(X_train, y_train, g_train, **kwargs)

        p = M.predict(X, head)
        ev = evaluate_predictions(p)
        sm = summarize(ev)

        # Print summary
        hit_1_0_tr = next(s['hits'] for s in sm if s['factor'] == 1.0 and s['split'] == 'train')
        hit_1_0_va = next(s['hits'] for s in sm if s['factor'] == 1.0 and s['split'] == 'validation')
        hit_0_5_tr = next(s['hits'] for s in sm if s['factor'] == 0.5 and s['split'] == 'train')
        hit_0_5_va = next(s['hits'] for s in sm if s['factor'] == 0.5 and s['split'] == 'validation')

        neg_1_0_va = next(s['negativeSourcePixels'] for s in sm if s['factor'] == 1.0 and s['split'] == 'validation')
        neg_0_5_va = next(s['negativeSourcePixels'] for s in sm if s['factor'] == 0.5 and s['split'] == 'validation')

        c13_max_p = float(p[c13_case['indices']].max())
        print(f"[{name:20s}] Intercept={head['intercept']:+.4f} | Hits 1.0: tr={hit_1_0_tr}/13, va={hit_1_0_va}/8 | Hits 0.5: tr={hit_0_5_tr}/13, va={hit_0_5_va}/8 | Neg va 1.0={neg_1_0_va:.0f}px, 0.5={neg_0_5_va:.0f}px | C13 max_p={c13_max_p:.4f}")

        # Check if C13 neg px is 0 and native hits >= 14/21
        if neg_0_5_va == 0.0 and (hit_1_0_tr + hit_1_0_va) >= 14:
            if best_head is None or (hit_1_0_tr + hit_1_0_va + hit_0_5_tr + hit_0_5_va) > (best_summary['total_hits']):
                best_head = head
                best_summary = {
                    'total_hits': hit_1_0_tr + hit_1_0_va + hit_0_5_tr + hit_0_5_va,
                    'eval': sm,
                    'c13_max_p': c13_max_p
                }
                best_name = name

    print(f"\nBest configuration: {best_name}")


if __name__ == '__main__':
    main()
