"""Comprehensive, fully reproducible offline evaluation of local skin type model (ViT)
and explainable Regional Combination (Karma) Rule v2.

Directly evaluates via production runtime: services/core-api/skin_models.infer()
Evaluates on:
1. Development / Calibration Set: 100 deduplicated samples from 'test' split (25/class).
2. Independent Holdout Set: 100 disjoint samples from 'valid' split (25/class),
   strictly excluding the 113 cross-split leaking prefixes in Kaggle dataset.

100% offline; zero network calls; zero external API keys.
Saves comprehensive audit receipt to audit-results/skin-type-local-evaluation-20261012.json
"""
import sys, os, time, json, hashlib, socket, gc
from pathlib import Path
from collections import defaultdict
import numpy as np, cv2, torch
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure core-api and python-packages in sys.path
sys.path.insert(0, 'services/core-api')
sys.path.insert(0, 'scripts')
sys.path.append('../attune-live-test/.runtime/python-packages')

import mediapipe as mp
import onnxruntime as ort
from transformers import AutoImageProcessor, AutoModelForImageClassification
import torchvision.models as models
import torch.nn as nn

import skin_models

# Model Checkpoints and Dataset Paths
GLAMOUR_DIR = Path(r'C:\Users\PC\.cache\huggingface\hub\models--AishaBaliyan--glamour-ai-skin-model\snapshots\4f232d45e5ba59664205f552c4f450a1a741470a')
SKINSIGHT_DIR = Path(r'C:\Users\PC\.cache\huggingface\hub\models--Raveem--SkinSight\snapshots\6e7b2dfaa9062b274ac308f66a85a43eff8f0eae')
ONNX_PATH = Path('services/core-api/models/skin-type-glamour-vit.onnx')
DATASET_BASE = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\focused-skin-20261010\sources\skin-18criteria-v1\skin_type_classification_dataset')
TEST_ROOT = DATASET_BASE / 'test'
VALID_ROOT = DATASET_BASE / 'valid'
RECEIPT_PATH = Path('audit-results/skin-type-local-evaluation-20261012.json')
LANDMARKER_MODEL = Path('apps/vehicle-app/public/mediapipe/models/face_landmarker.task')

CLASSES_3 = ['dry', 'normal', 'oily']
CLASSES_4 = ['dry', 'normal', 'oily', 'combination']
TURKISH_NAMES = {'dry': 'Kuru', 'normal': 'Normal', 'oily': 'Yağlı', 'combination': 'Karma'}

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_image_prefix(filename):
    return filename.split('_jpg.rf.')[0].split('.rf.')[0].replace('-Copy', '')

def select_dataset_splits(max_per_class=25):
    """Selects:
    1. Development set from 'test' folder (deduplicated by base image prefix).
    2. Holdout set from 'valid' folder (100% disjoint from test prefixes, accounting for 113 leakages).
    """
    test_files_by_class = {}
    test_prefixes = set()

    for cls in CLASSES_4:
        folder = TEST_ROOT / cls
        files = sorted(folder.glob('*.jpg'))
        chosen = []
        seen = set()
        for f in files:
            pfx = get_image_prefix(f.name)
            if pfx not in seen:
                seen.add(pfx)
                chosen.append(f)
                test_prefixes.add(pfx)
                if len(chosen) >= max_per_class:
                    break
        test_files_by_class[cls] = chosen

    # Also collect all test prefixes in the entire test directory
    all_test_prefixes = set(get_image_prefix(f.name) for f in TEST_ROOT.glob('*/*.jpg'))

    holdout_files_by_class = {}
    all_valid_prefixes = set(get_image_prefix(f.name) for f in VALID_ROOT.glob('*/*.jpg'))
    leaking_prefixes = all_valid_prefixes.intersection(all_test_prefixes)
    disjoint_valid_prefixes = all_valid_prefixes - all_test_prefixes

    for cls in CLASSES_4:
        folder = VALID_ROOT / cls
        files = sorted(folder.glob('*.jpg'))
        chosen = []
        seen = set()
        for f in files:
            pfx = get_image_prefix(f.name)
            # Strictly disjoint: not in any test image, not already chosen
            if pfx not in all_test_prefixes and pfx not in seen:
                seen.add(pfx)
                chosen.append(f)
                if len(chosen) >= max_per_class:
                    break
        holdout_files_by_class[cls] = chosen

    split_stats = {
        'total_test_files': len(list(TEST_ROOT.glob('*/*.jpg'))),
        'unique_test_prefixes': len(all_test_prefixes),
        'total_valid_files': len(list(VALID_ROOT.glob('*/*.jpg'))),
        'unique_valid_prefixes': len(all_valid_prefixes),
        'cross_split_leaking_prefixes': len(leaking_prefixes),
        'disjoint_valid_prefixes': len(disjoint_valid_prefixes),
        'dev_set_size': sum(len(v) for v in test_files_by_class.values()),
        'holdout_set_size': sum(len(v) for v in holdout_files_by_class.values())
    }
    return test_files_by_class, holdout_files_by_class, split_stats

def evaluate_predictions(records, classes):
    """Computes comprehensive metrics: confusion matrix, precision, recall, F1, balanced accuracy, accuracy."""
    cm = {t: defaultdict(int) for t in classes}
    evaluated_records = [r for r in records if r['pred'] is not None and r['true'] in classes]
    rejected_records = [r for r in records if r['pred'] is None]

    for r in evaluated_records:
        cm[r['true']][r['pred']] += 1

    per_class = {}
    f1_list = []
    recall_list = []
    for c in classes:
        tp = cm[c][c]
        fp = sum(cm[oc][c] for oc in classes if oc != c)
        fn = sum(cm[c][op] for op in classes if op != c)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_list.append(f1)
        recall_list.append(rec)
        per_class[c] = {
            'turkish_name': TURKISH_NAMES.get(c, c),
            'tp': tp, 'fp': fp, 'fn': fn,
            'precision': round(prec, 4),
            'recall': round(rec, 4),
            'f1': round(f1, 4),
            'support': sum(cm[c].values())
        }

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    balanced_acc = sum(recall_list) / len(recall_list) if recall_list else 0.0
    total_valid = len(evaluated_records)
    correct = sum(cm[c][c] for c in classes)
    accuracy = correct / total_valid if total_valid > 0 else 0.0

    # Limitation code counts
    rejections = defaultdict(int)
    for r in rejected_records:
        code = r.get('limitationCode') or 'UNKNOWN_REJECTION'
        rejections[code] += 1

    return {
        'confusion_matrix': {t: {p: cm[t][p] for p in classes} for t in classes},
        'per_class': per_class,
        'macro_f1': round(macro_f1, 4),
        'balanced_accuracy': round(balanced_acc, 4),
        'accuracy': round(accuracy, 4),
        'total_samples': len(records),
        'valid_evaluated': total_valid,
        'rejected_count': len(rejected_records),
        'coverage_rate': round(total_valid / len(records), 4) if records else 0.0,
        'rejections_breakdown': dict(rejections)
    }

def benchmark_resources_and_latency(dummy_tensor_np):
    """Measures genuine cold and warm CPU inference latency and memory footprint."""
    import psutil
    process = psutil.Process(os.getpid())
    mem_before_mb = process.memory_info().rss / (1024 * 1024)

    # 1. PyTorch ViT CPU Benchmark
    t0 = time.perf_counter()
    glamour_pt = AutoModelForImageClassification.from_pretrained(str(GLAMOUR_DIR), local_files_only=True)
    glamour_pt.eval()
    pt_load_ms = (time.perf_counter() - t0) * 1000

    dummy_torch = torch.from_numpy(dummy_tensor_np)
    # Cold PyTorch
    t0 = time.perf_counter()
    with torch.no_grad(): glamour_pt(dummy_torch)
    pt_cold_ms = (time.perf_counter() - t0) * 1000

    # Warm PyTorch (20 iterations)
    pt_warm_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        with torch.no_grad(): glamour_pt(dummy_torch)
        pt_warm_times.append((time.perf_counter() - t0) * 1000)

    # 2. ONNX Runtime CPU Benchmark
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    opts.inter_op_num_threads = 1
    t0 = time.perf_counter()
    ort_session = ort.InferenceSession(str(ONNX_PATH), sess_options=opts, providers=['CPUExecutionProvider'])
    ort_load_ms = (time.perf_counter() - t0) * 1000

    # Cold ORT
    t0 = time.perf_counter()
    ort_session.run(None, {'rgb': dummy_tensor_np})
    ort_cold_ms = (time.perf_counter() - t0) * 1000

    # Warm ORT (20 iterations)
    ort_warm_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        ort_session.run(None, {'rgb': dummy_tensor_np})
        ort_warm_times.append((time.perf_counter() - t0) * 1000)

    mem_after_mb = process.memory_info().rss / (1024 * 1024)

    pt_warm_mean = float(np.mean(pt_warm_times))
    ort_warm_mean = float(np.mean(ort_warm_times))
    speedup = pt_warm_mean / ort_warm_mean if ort_warm_mean > 0 else 1.0

    return {
        'pytorch': {
            'load_ms': round(pt_load_ms, 2),
            'cold_ms': round(pt_cold_ms, 2),
            'warm_mean_ms': round(pt_warm_mean, 2),
            'warm_std_ms': round(float(np.std(pt_warm_times)), 2),
            'warm_min_ms': round(float(np.min(pt_warm_times)), 2),
            'warm_max_ms': round(float(np.max(pt_warm_times)), 2)
        },
        'onnxruntime': {
            'load_ms': round(ort_load_ms, 2),
            'cold_ms': round(ort_cold_ms, 2),
            'warm_mean_ms': round(ort_warm_mean, 2),
            'warm_std_ms': round(float(np.std(ort_warm_times)), 2),
            'warm_min_ms': round(float(np.min(ort_warm_times)), 2),
            'warm_max_ms': round(float(np.max(ort_warm_times)), 2)
        },
        'speedup_ratio': round(speedup, 2),
        'rss_memory_mb': round(mem_after_mb, 2),
        'memory_delta_mb': round(mem_after_mb - mem_before_mb, 2)
    }

def run_evaluation():
    print("=" * 75)
    print("TOGG ATTUNE - LOCAL SKIN TYPE MODEL & REGIONAL COMBINATION EVALUATION v2")
    print("Direct runtime evaluation via services/core-api/skin_models.infer()")
    print("=" * 75)

    # 1. Model Checksums & Metadata
    glamour_weights = GLAMOUR_DIR / 'model.safetensors'
    glamour_hash = compute_sha256(glamour_weights)
    onnx_hash = compute_sha256(ONNX_PATH)
    assert glamour_hash == "46f59b660f856c867c00289fa0ec4337a935d07a758e81175290580fb2733b8c"
    assert onnx_hash == "ffdac2fc496a23dc27e60e08299b2496a0702a1d49f81f288d4d54da686213a0"
    print(f"Primary Model ViT: {glamour_weights.name} SHA-256 = {glamour_hash[:16]}... (OK)")
    print(f"Exported ONNX: {ONNX_PATH.name} SHA-256 = {onnx_hash[:16]}... (OK)")

    # 2. Select Splits
    print("\nSelecting Dataset Splits...")
    dev_files, holdout_files, split_stats = select_dataset_splits(max_per_class=25)
    print(f"  Test split total files: {split_stats['total_test_files']} (unique prefixes: {split_stats['unique_test_prefixes']})")
    print(f"  Valid split total files: {split_stats['total_valid_files']} (unique prefixes: {split_stats['unique_valid_prefixes']})")
    print(f"  Cross-split leaking prefixes: {split_stats['cross_split_leaking_prefixes']}")
    print(f"  Disjoint valid prefixes: {split_stats['disjoint_valid_prefixes']}")
    print(f"  Development / Calibration set: {split_stats['dev_set_size']} samples (25 per class)")
    print(f"  Independent Holdout set: {split_stats['holdout_set_size']} samples (25 per class, 0% test leakage)")

    # 3. Initialize Face Landmarker
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(LANDMARKER_MODEL)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    # 4. Numerical Parity Verification on Real Image
    sample_file = dev_files['normal'][0]
    sample_bgr = cv2.imread(str(sample_file))
    sample_rgb = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2RGB)
    res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=sample_rgb))
    sample_lms = [{'x': p.x, 'y': p.y, 'z': p.z} for p in res.face_landmarks[0]]
    _, sample_transform = skin_models.photo_input(sample_bgr, sample_lms)

    # Use unified preprocess_vit_face
    vit_x = skin_models.preprocess_vit_face(sample_bgr, sample_transform)

    # Run PyTorch with local_files_only
    glamour_pt = AutoModelForImageClassification.from_pretrained(str(GLAMOUR_DIR), local_files_only=True)
    glamour_pt.eval()
    with torch.no_grad():
        pt_logits = glamour_pt(torch.from_numpy(vit_x)).logits.numpy()[0]

    # Run ONNX Runtime
    loaded = skin_models.load(allow_candidates=True)
    type_session = loaded['sessions']['type']['session']
    ort_logits = type_session.run(None, {'rgb': vit_x})[0][0]

    parity_diff = float(np.max(np.abs(pt_logits - ort_logits)))
    print(f"\nReal Face Crop Parity Check (PyTorch vs ONNX Runtime):")
    print(f"  Max absolute logit difference: {parity_diff:.6e}")
    assert parity_diff < 1e-4, f"Parity check failed: {parity_diff}"
    print("  -> Numerical Parity VERIFIED (< 1e-4)")

    # 5. Resource & Latency Benchmark
    print("\nBenchmarking CPU Inference Timings & Memory...")
    perf_metrics = benchmark_resources_and_latency(vit_x)
    print(f"  PyTorch CPU: cold={perf_metrics['pytorch']['cold_ms']}ms, warm mean={perf_metrics['pytorch']['warm_mean_ms']}ms (std={perf_metrics['pytorch']['warm_std_ms']}ms)")
    print(f"  ONNX Runtime CPU: cold={perf_metrics['onnxruntime']['cold_ms']}ms, warm mean={perf_metrics['onnxruntime']['warm_mean_ms']}ms (std={perf_metrics['onnxruntime']['warm_std_ms']}ms)")
    print(f"  Measured Speedup: {perf_metrics['speedup_ratio']}x (honest measured ratio)")
    print(f"  Process RSS Memory: {perf_metrics['rss_memory_mb']} MB (delta: {perf_metrics['memory_delta_mb']} MB)")

    # 6. Evaluate Splits via direct skin_models.infer()
    def evaluate_split_files(split_files_dict, split_name):
        print(f"\nRunning evaluation on {split_name} ({sum(len(v) for v in split_files_dict.values())} samples)...")
        all_records = []
        records_4class = []
        records_3class = []

        for true_cls, files in split_files_dict.items():
            for f in files:
                bgr = cv2.imread(str(f))
                if bgr is None:
                    continue

                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))

                if not det.face_landmarks:
                    all_records.append({
                        'file': f.name,
                        'true_cls': true_cls,
                        'pred_4': None,
                        'pred_3': None,
                        'quality': 'insufficient',
                        'limitationCode': 'LANDMARKS_MISSING',
                        'confidence': None,
                        'probs': None,
                        'photometrics': None,
                        'karma_rule': None
                    })
                    records_4class.append({'true': true_cls, 'pred': None, 'limitationCode': 'LANDMARKS_MISSING'})
                    if true_cls in CLASSES_3:
                        records_3class.append({'true': true_cls, 'pred': None, 'limitationCode': 'LANDMARKS_MISSING'})
                    continue

                points = [{'x': p.x, 'y': p.y, 'z': p.z} for p in det.face_landmarks[0]]

                # Direct runtime production inference call with candidate flag enabled
                res = skin_models.infer(bgr, points, quality_valid=True, type_quality_valid=True, allow_candidates=True)
                st = res.get('skinType') or {}

                val_4 = st.get('value')
                quality = st.get('quality')
                lim_code = st.get('limitationCode')
                conf = st.get('confidence')
                reg_div = st.get('regionalDivergence') or {}
                probs = reg_div.get('modelProbs') or {}

                # Base 3-class prediction from raw model probabilities
                val_3 = max(probs, key=probs.get) if probs else None

                record = {
                    'file': f.name,
                    'true_cls': true_cls,
                    'pred_4': val_4,
                    'pred_3': val_3,
                    'quality': quality,
                    'limitationCode': lim_code,
                    'confidence': conf,
                    'probs': probs,
                    'photometrics': {
                        't_spec': reg_div.get('tZoneSpecularity'),
                        'u_spec': reg_div.get('cheekSpecularity'),
                        'spec_diff': reg_div.get('specularDivergence'),
                        'clipping': reg_div.get('clipping')
                    },
                    'karma_rule': {
                        'is_karma': reg_div.get('isKarma'),
                        'basis': reg_div.get('basis'),
                        'deadbandMet': reg_div.get('deadbandMet'),
                        'tZoneSupported': reg_div.get('tZoneSupported'),
                        'cheeksMatte': reg_div.get('cheeksMatte'),
                        'combinationConfidence': reg_div.get('combinationConfidence')
                    }
                }
                all_records.append(record)
                records_4class.append({'true': true_cls, 'pred': val_4, 'limitationCode': lim_code})
                if true_cls in CLASSES_3:
                    records_3class.append({'true': true_cls, 'pred': val_3, 'limitationCode': lim_code})

        metrics_4 = evaluate_predictions(records_4class, CLASSES_4)
        metrics_3 = evaluate_predictions(records_3class, CLASSES_3)
        return all_records, metrics_4, metrics_3

    dev_records, dev_metrics_4, dev_metrics_3 = evaluate_split_files(dev_files, "Development Set (test)")
    holdout_records, holdout_metrics_4, holdout_metrics_3 = evaluate_split_files(holdout_files, "Independent Holdout Set (valid)")

    # Print summary tables
    print("\n--- DEVELOPMENT SET (100 samples) METRICS ---")
    print(f"4-Class Macro-F1: {dev_metrics_4['macro_f1']} | Accuracy: {dev_metrics_4['accuracy']} | Coverage: {dev_metrics_4['coverage_rate']}")
    for c, d in dev_metrics_4['per_class'].items():
        print(f"  {c:12s} ({d['turkish_name']}): Prec={d['precision']:.3f}, Rec={d['recall']:.3f}, F1={d['f1']:.3f} (support={d['support']})")
    print(f"3-Class (Dry/Norm/Oily) Macro-F1: {dev_metrics_3['macro_f1']} | Balanced Acc: {dev_metrics_3['balanced_accuracy']}")

    print("\n--- INDEPENDENT HOLDOUT SET (100 samples) METRICS ---")
    print(f"4-Class Macro-F1: {holdout_metrics_4['macro_f1']} | Accuracy: {holdout_metrics_4['accuracy']} | Coverage: {holdout_metrics_4['coverage_rate']}")
    for c, d in holdout_metrics_4['per_class'].items():
        print(f"  {c:12s} ({d['turkish_name']}): Prec={d['precision']:.3f}, Rec={d['recall']:.3f}, F1={d['f1']:.3f} (support={d['support']})")
    print(f"3-Class (Dry/Norm/Oily) Macro-F1: {holdout_metrics_3['macro_f1']} | Balanced Acc: {holdout_metrics_3['balanced_accuracy']}")

    # 7. Network Isolation Test
    print("\nVerifying 100% Offline Execution (Blocked Sockets)...")
    real_connect = socket.socket.connect
    def blocked_connect(self, address):
        raise OSError("Network call forbidden in offline evaluation")
    socket.socket.connect = blocked_connect
    try:
        offline_res = skin_models.infer(sample_bgr, sample_lms, quality_valid=True, type_quality_valid=True, allow_candidates=True)
        assert offline_res['skinType']['quality'] in ('valid', 'insufficient')
        print("  -> Offline execution VERIFIED (infer completed with blocked socket)")
    finally:
        socket.socket.connect = real_connect

    # 8. Save Audit Receipt
    receipt = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'purpose': 'Direct runtime evaluation of local skin type model (ViT) and Regional Combination Rule v2',
        'runtime_entrypoint': 'services/core-api/skin_models.infer',
        'selected_model': {
            'model_id': 'AishaBaliyan/glamour-ai-skin-model',
            'architecture': 'ViTForImageClassification',
            'license': 'MIT',
            'snapshot': '4f232d45e5ba59664205f552c4f450a1a741470a',
            'weights_file': 'model.safetensors',
            'weights_sha256': glamour_hash,
            'onnx_file': 'skin-type-glamour-vit.onnx',
            'onnx_sha256': onnx_hash,
            'classes': CLASSES_3,
            'preprocessing': {
                'RGB': True,
                'size': [224, 224],
                'mean': [0.5, 0.5, 0.5],
                'std': [0.5, 0.5, 0.5],
                'resampling': 'PIL.Image.Resampling.BILINEAR',
                'cropVersion': 'camera-crop-v1'
            },
            'acceptance_status': {
                'accepted': False,
                'candidateAccepted': True,
                'sourceQualityAccepted': False,
                'sourceLabelProtocolVerified': False,
                'cameraDomainAccepted': False,
                'offlineExecution': True
            }
        },
        'backup_model': {
            'model_id': 'Raveem/SkinSight',
            'architecture': 'ResNet50',
            'license': 'MIT',
            'status': 'REJECTED_LOW_ACCURACY_AND_COLLAPSE_TO_OILY'
        },
        'dataset_provenance': {
            'upstream_origin': 'killa92/facial-skin-analysis-and-type-classification (Kaggle)',
            'license': 'Apache-2.0',
            'expert_protocol_verified': False,
            'person_independent': False,
            'split_statistics': split_stats
        },
        'parity_verification': {
            'real_face_crop_max_logit_diff': parity_diff,
            'threshold': 1e-4,
            'status': 'VERIFIED'
        },
        'resource_benchmarking': perf_metrics,
        'offline_network_blocked_test': 'PASSED',
        'development_evaluation': {
            'split_name': 'test (deduplicated base images)',
            'sample_count': len(dev_records),
            'metrics_4class': dev_metrics_4,
            'metrics_3class': dev_metrics_3,
            'samples_detail': dev_records
        },
        'holdout_evaluation': {
            'split_name': 'valid (disjoint from test prefixes)',
            'sample_count': len(holdout_records),
            'metrics_4class': holdout_metrics_4,
            'metrics_3class': holdout_metrics_3,
            'samples_detail': holdout_records
        }
    }

    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RECEIPT_PATH, 'w', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(f"\nAudit receipt saved to {RECEIPT_PATH} ({len(dev_records) + len(holdout_records)} complete sample records)")

if __name__ == '__main__':
    run_evaluation()
