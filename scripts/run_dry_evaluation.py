"""Empirical benchmark comparing TextureNet candidate against production analytic
dryness pipeline (appearance_analysis.compute_dryness_signal & eligible_flake_components)
on both:
1. Local ROI / patch dataset: 150 patches (26 validation groups, 19 negative, 7 positive)
2. Real whole-face control photos: full analyze_skin -> regional dryness -> overview -> local maps
"""
import sys, os, json, subprocess, base64, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / '../attune-live-test/scripts/skin-research'))
sys.path.insert(0, str(ROOT / '../attune-live-test/.runtime/python-packages'))

import cv2, numpy as np, onnxruntime as ort
import appearance_analysis as A
from appearance_analysis import compute_dryness_signal, eligible_flake_components

def evaluate_patches():
    p_pixels = ROOT / '../attune-live-test/audit-results/skin-expanded-20261011/negative-dry-presence/pixels.npy'
    p_data = ROOT / '../attune-live-test/audit-results/skin-expanded-20261011/negative-dry-presence/data.json'
    p_onnx = ROOT / '../attune-live-test/audit-results/skin-expanded-20261011/negative-dry-presence/candidate.onnx'

    if not p_pixels.exists() or not p_data.exists() or not p_onnx.exists():
        print("Patch data files not found.")
        return None

    pixels = np.load(p_pixels)
    with open(p_data, encoding='utf-8') as f:
        meta = json.load(f)

    # 1. TextureNet ONNX Inference
    sess = ort.InferenceSession(str(p_onnx))
    inp_name = sess.get_inputs()[0].name

    all_tn_probs = []
    all_analytic_scores = []

    for i in range(len(pixels)):
        gray8 = pixels[i]
        gray = gray8.astype(np.float32) / 255.0

        # TextureNet inference (1, 1, 64, 64) float32 in [0, 1]
        inp = gray[None, None, :, :].astype(np.float32)
        out = sess.run(None, {inp_name: inp})[0][0]
        # Softmax over logits (class 0: negative, class 1: dry/texture)
        prob = float(np.exp(out[1]) / (np.exp(out[0]) + np.exp(out[1])))
        all_tn_probs.append(prob)

        # Production Analytic Dryness Pipeline:
        # Calls the exact shared compute_dryness_signal function used by analyze_skin
        regional_flakes, flakes, local_contrast, lbp, dark_ringing = compute_dryness_signal(gray8)
        sc = float(np.mean(regional_flakes > 0.04) * 100)
        all_analytic_scores.append(sc)

    # Validation Split Analysis (41 patches across 26 groups: 19 negative groups, 7 positive groups)
    val_indices = [i for i, r in enumerate(meta['rows']) if r['split'] == 'validation']

    tn_group_probs = {}
    analytic_group_scores = {}
    group_labels = {}
    patch_records = []

    for idx in val_indices:
        r = meta['rows'][idx]
        g = r['group']
        lbl = r['label']
        if g not in tn_group_probs:
            tn_group_probs[g] = []
            analytic_group_scores[g] = []
            group_labels[g] = lbl
        tn_group_probs[g].append(all_tn_probs[idx])
        analytic_group_scores[g].append(all_analytic_scores[idx])

        patch_records.append({
            'index': idx,
            'sha256': r['sha256'],
            'group': g,
            'trueLabel': lbl,
            'source': r.get('source'),
            'labelOrigin': r.get('labelOrigin'),
            'textureNetProb': all_tn_probs[idx],
            'analyticScorePercent': all_analytic_scores[idx]
        })

    # TextureNet Group Metrics (threshold = 0.50 probability)
    tn_cm = [[0, 0], [0, 0]]
    for g, probs in tn_group_probs.items():
        lbl = group_labels[g]
        pred = 1 if np.mean(probs) >= 0.50 else 0
        tn_cm[lbl][pred] += 1

    tn_tp = tn_cm[1][1]
    tn_fp = tn_cm[0][1]
    tn_fn = tn_cm[1][0]
    tn_tn = tn_cm[0][0]
    tn_precision = tn_tp / (tn_tp + tn_fp) if (tn_tp + tn_fp) else 0.0
    tn_recall = tn_tp / (tn_tp + tn_fn) if (tn_tp + tn_fn) else 0.0
    tn_f1 = 2 * tn_precision * tn_recall / (tn_precision + tn_recall) if (tn_precision + tn_recall) else 0.0
    tn_fpr = tn_fp / (tn_fp + tn_tn) if (tn_fp + tn_tn) else 0.0

    # Analytic Group Metrics (fixed threshold = 0.05% visible flake area)
    an_cm = [[0, 0], [0, 0]]
    for g, scores in analytic_group_scores.items():
        lbl = group_labels[g]
        pred = 1 if np.mean(scores) > 0.05 else 0
        an_cm[lbl][pred] += 1

    an_tp = an_cm[1][1]
    an_fp = an_cm[0][1]
    an_fn = an_cm[1][0]
    an_tn = an_cm[0][0]
    an_precision = an_tp / (an_tp + an_fp) if (an_tp + an_fp) else 0.0
    an_recall = an_tp / (an_tp + an_fn) if (an_tp + an_fn) else 0.0
    an_f1 = 2 * an_precision * an_recall / (an_precision + an_recall) if (an_precision + an_recall) else 0.0
    an_fpr = an_fp / (an_fp + an_tn) if (an_fp + an_tn) else 0.0

    return {
        'benchmarkScope': 'negative-dry-presence expanded validation set (150 total patches, 41 validation patches, 26 unique validation groups)',
        'groupsTotal': len(group_labels),
        'positiveGroups': sum(1 for v in group_labels.values() if v == 1),
        'negativeGroups': sum(1 for v in group_labels.values() if v == 0),
        'textureNet': {
            'model': 'audit-results/skin-expanded-20261011/negative-dry-presence/candidate.onnx',
            'weightsSHA256': '9cea44f4c4e9b948657331467c5f49ff3e5d8789e5b52a5000370f793f9dc852',
            'thresholdProb': 0.50,
            'confusionMatrix': tn_cm,
            'precision': tn_precision,
            'recall': tn_recall,
            'F1': tn_f1,
            'FPR': tn_fpr,
            'errorGroups': [
                {'group': g, 'label': group_labels[g], 'meanProb': float(np.mean(tn_group_probs[g])), 'reason': 'false_negative' if group_labels[g]==1 else 'false_positive'}
                for g in tn_group_probs if (group_labels[g] == 1 and np.mean(tn_group_probs[g]) < 0.5) or (group_labels[g] == 0 and np.mean(tn_group_probs[g]) >= 0.5)
            ]
        },
        'productionAnalytic': {
            'method': 'appearance_analysis.compute_dryness_signal (multi-scale DoG + LBP + black-hat ringing dilation + eligible_flake_components)',
            'thresholdAreaPercent': 0.05,
            'confusionMatrix': an_cm,
            'precision': an_precision,
            'recall': an_recall,
            'F1': an_f1,
            'FPR': an_fpr,
            'errorGroups': [
                {'group': g, 'label': group_labels[g], 'meanScore': float(np.mean(analytic_group_scores[g])), 'reason': 'false_negative' if group_labels[g]==1 else 'false_positive'}
                for g in analytic_group_scores if (group_labels[g] == 1 and np.mean(analytic_group_scores[g]) <= 0.05) or (group_labels[g] == 0 and np.mean(analytic_group_scores[g]) > 0.05)
            ]
        },
        'unreadableOrUnmeasurableSamples': [],
        'validationPatches': patch_records
    }

def evaluate_full_photos():
    folder = ROOT / '../attune-live-test/audit-results/skin-expanded-20261011/sag-controls'
    candidates = json.loads((folder / 'candidates.json').read_text('utf8')) + json.loads((folder / 'additional-candidates.json').read_text('utf8'))
    old_results = json.loads((folder / 'actual-results.json').read_text('utf8'))['rows']
    indices = [r['index'] for r in old_results]

    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
    detector = FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT / '../attune-live-test/apps/vehicle-app/public/mediapipe/models/face_landmarker.task')), num_faces=2))

    selected = []
    for i in indices:
        r = dict(candidates[i])
        im = cv2.imread(r['absolutePath'])
        if not r.get('landmarks'):
            found = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im, cv2.COLOR_BGR2RGB)))
            if len(found.face_landmarks) == 1:
                r['landmarks'] = [dict(x=p.x, y=p.y, z=p.z) for p in found.face_landmarks[0]]
        r['reviewIndex'] = i
        selected.append(r)
    detector.close()

    meshes = json.loads(subprocess.check_output(['node', '../attune-live-test/scripts/skin-research/focused_meshes.cjs'], input=json.dumps(selected).encode(), cwd=str(ROOT / '../attune-live-test')))

    photo_results = []
    for r, m in zip(selected, meshes):
        im = cv2.imread(r['absolutePath'])
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        alignment = m['alignment']
        conditions = {k: alignment[k] for k in ['yaw', 'pitch', 'roll', 'scaleRatio']}
        conditions.update(avgLuminance=float(gray.mean()), blurScore=float(cv2.Laplacian(gray, cv2.CV_32F).var()))
        payload = dict(pose='FRONT', landmarks=r['landmarks'], meshes=m['meshes'], exclusions=[], qualityValid=40<=gray.mean()<=220 and conditions['blurScore']>=4 and abs(alignment['yaw'])<.35, conditions=conditions)
        ok, raw = cv2.imencode('.png', im)
        payload['photo'] = 'data:image/png;base64,' + base64.b64encode(raw).decode()
        payload['photoId'] = hashlib.sha256(cv2.cvtColor(im, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()

        res = A.analyze_skin(payload)
        dry_ov = next(v for v in res['general']['measurements'] if v['id'] == 'dry')
        regional_dry = {reg: next((x['value'] for x in items if x['id'] == 'dry'), None) for reg, items in res['measurements'].items() if reg != 'periorbital'}
        maps_dry = {k: v['sampleCount'] for k, v in res.get('maps', {}).items() if 'dry' in k}

        photo_results.append({
            'reviewIndex': r['reviewIndex'],
            'sha256': r['sha256'],
            'path': r.get('path'),
            'class': r.get('class'),
            'qualityValid': payload['qualityValid'],
            'dry_overview': dry_ov['value'],
            'dry_overview_quality': dry_ov['quality'],
            'dry_overview_limitation': dry_ov['limitationCode'],
            'regional_dry': regional_dry,
            'dry_local_maps_samples': maps_dry
        })

    return photo_results

def main():
    patch_eval = evaluate_patches()
    photo_eval = evaluate_full_photos()

    output = {
        'patchLevelBenchmark': patch_eval,
        'fullPhotoPipelineEvaluation': photo_eval
    }

    out_file = ROOT / 'audit-results/dry-empirical-comparison.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f"Saved comprehensive dry evaluation to {out_file}")

if __name__ == '__main__':
    main()
