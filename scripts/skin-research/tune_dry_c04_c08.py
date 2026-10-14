#!/usr/bin/env python3
"""Evaluate global threshold sweep and C04/C08 behavior on dry head."""

import sys
import json
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
sys.path.insert(0, str(LIVE_TEST / 'services/core-api'))

from find_optimal_dry_head import cases, records, X, controls, OLD, read, optical
import material_component_features as M
from component_flake_gate import masks
from trial_region_flake_proposal import measure

def evaluate_threshold(head, t):
    p = M.predict(X, head)
    rows = []
    for case in cases:
        if case['scope'] != 'preserved':
            continue
        c = controls[case['controlIndex']]
        meta = next(r for r in optical if r['control'] == case['controlIndex'] and r['factor'] == case['factor'])
        a, b = meta['origin']
        w, h_crop = meta['cropShape']
        local_control = {**c, 'roi': [c['roi'][0]-a, c['roi'][1]-b, *c['roi'][2:]]}
        known, objects = masks((h_crop, w), local_control)
        with np.load(case['path']) as f:
            ids = f['ids']
            field = f['field']
            component_ids = f['componentIds']
            allowed = np.zeros(int(ids.max()) + 1, bool)
            allowed[component_ids] = p[case['indices']] >= t
            field = field * allowed[ids]

        def local_mask(mask):
            return mask > 0 if case['factor'] == 1 else cv2.resize(mask, (field.shape[1], field.shape[0]), interpolation=cv2.INTER_NEAREST) > 0

        rows.append(dict(
            control=case['controlIndex'], factor=case['factor'], split=case['split'],
            objects=[dict(index=o['index'], label=o['label'], measure=measure(field, local_mask(o['mask']), case['factor'])) for o in objects],
            negative=measure(field, local_mask(known['reviewed-non-flake']), case['factor'])
        ))

    hits_1 = sum(o['measure']['objectHit'] for r in rows if r['factor']==1.0 for o in r['objects'] if o['label']=='visible-material')
    hits_05 = sum(o['measure']['objectHit'] for r in rows if r['factor']==0.5 for o in r['objects'] if o['label']=='visible-material')
    neg_1_all = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0)
    neg_1_c04 = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0 and r['control']==4)
    neg_1_val = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==1.0 and r['split']=='validation')
    neg_05_all = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==0.5)
    neg_05_val = sum(r['negative']['activeSourcePixels'] for r in rows if r['factor']==0.5 and r['split']=='validation')
    c08_obj0 = next(o for r in rows if r['control']==8 and r['factor']==1.0 for o in r['objects'] if o['index']==0)

    # Let's check which objects are hit/lost at 1.0 and 0.5
    obj_hits_1 = [(r['control'], o['index']) for r in rows if r['factor']==1.0 for o in r['objects'] if o['label']=='visible-material' and o['measure']['objectHit']]
    obj_hits_05 = [(r['control'], o['index']) for r in rows if r['factor']==0.5 for o in r['objects'] if o['label']=='visible-material' and o['measure']['objectHit']]

    return {
        'threshold': t,
        'hits_1': hits_1,
        'hits_05': hits_05,
        'neg_1_c04': neg_1_c04,
        'neg_1_all': neg_1_all,
        'neg_1_val': neg_1_val,
        'neg_05_all': neg_05_all,
        'neg_05_val': neg_05_val,
        'c08_obj0_hit': c08_obj0['measure']['objectHit'],
        'c08_obj0_px': c08_obj0['measure']['activeSourcePixels'],
        'obj_hits_1': obj_hits_1,
        'obj_hits_05': obj_hits_05,
    }

def check_all_overlaps():
    print("\n--- Component Overlaps with reviewed masks (factor 1.0) ---")
    for case in cases:
        if case['scope'] != 'preserved' or case['factor'] != 1.0:
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
                idx = next(i for i in case['indices'] if records[i]['componentId'] == cid)
                r = records[idx]
                if pos_px > 0 or neg_px > 0 or r['label'] is not None:
                    print(f"C{ci:02d} ({c['split']:10s}) | CID {cid:3d} | pos_px={pos_px:3d} | neg_px={neg_px:3d} | label={str(r['label']):5s} class={r['class']}")

def main():
    check_all_overlaps()
    head = read(ROOT / 'audit-results/cdc-delivery-20261014/dryness/calibrated-source-group-head.json')
    res50 = evaluate_threshold(head, 0.50)
    res53 = evaluate_threshold(head, 0.53)
    lost_1 = set(res50['obj_hits_1']) - set(res53['obj_hits_1'])
    print(f"Objects lost at 1.0x when moving from T=0.50 to T=0.53: {lost_1}")

    print("\nEvaluating existing head across threshold sweep:")
    for t in [0.50, 0.51, 0.515, 0.52, 0.527, 0.53, 0.535, 0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.60]:
        res = evaluate_threshold(head, t)
        print(f"T={t:.3f} | 1.0x Hits: {res['hits_1']}/21 | 0.5x Hits: {res['hits_05']}/21 | "
              f"C04 Neg: {res['neg_1_c04']:.0f} px | Total 1.0x Neg: {res['neg_1_all']:.0f} px (Val: {res['neg_1_val']:.0f} px) | "
              f"0.5x Neg: {res['neg_05_all']:.0f} px | C08 obj0: hit={res['c08_obj0_hit']} ({res['c08_obj0_px']:.0f} px)")

if __name__ == '__main__':
    main()
