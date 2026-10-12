"""Comparative evaluation of Roboflow 4-class skin type models:
- skin-type-axavj/1 (face-detection-beautysense)
- skin-type-ng2uj/1 (fyp-symvg)

Evaluates on 20 independent test images (5 per class: normal, dry, oily, combination)
from approved development dataset (skin-18criteria-v1).
Strictly deduplicated to ensure zero identity or augmentation leakage.
Computes: Confusion Matrix, Precision, Recall, F1, Macro-F1, and Karma Recall.
NEVER prints, logs or records private API keys.
"""
import os, sys, time, json
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

env_file = Path('.env.local')
api_key = None
if env_file.is_file():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            k, sep, v = line.partition('=')
            if sep and k.strip() in ('ATTUNE_ROBOFLOW_API_KEY', 'ROBOFLOW_API_KEY'):
                api_key = v.strip().strip('"').strip("'")

if not api_key:
    print("ERROR: ATTUNE_ROBOFLOW_API_KEY not found in environment or .env.local", file=sys.stderr)
    sys.exit(1)

from inference_sdk import InferenceConfiguration, InferenceHTTPClient
from inference_sdk.http.errors import HTTPCallErrorError

CLASSES = ['normal', 'dry', 'oily', 'combination']
TURKISH_NAMES = {'normal': 'Normal', 'dry': 'Kuru', 'oily': 'Yağlı', 'combination': 'Karma'}

MODELS = [
    'skin-type-axavj/1',
    'skin-type-ng2uj/1',
]

DATASET_ROOT = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\focused-skin-20261010\sources\skin-18criteria-v1\skin_type_classification_dataset\test')

def select_independent_samples(per_class=5):
    selected = {}
    for cls in CLASSES:
        folder = DATASET_ROOT / cls
        files = sorted(folder.iterdir())
        chosen = []
        seen_prefixes = set()
        for f in files:
            if not f.name.endswith(('.jpg', '.jpeg', '.png')):
                continue
            prefix = f.name.split('_jpg.rf.')[0].split('.rf.')[0].replace('-Copy', '')
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                chosen.append(f)
                if len(chosen) >= per_class:
                    break
        selected[cls] = chosen
    return selected

def compute_metrics(true_labels, pred_labels):
    # Confusion matrix: rows=true, cols=pred
    cm = {t: defaultdict(int) for t in CLASSES}
    for t, p in zip(true_labels, pred_labels):
        if t in cm:
            cm[t][p] += 1

    per_class = {}
    f1_list = []
    for cls in CLASSES:
        tp = cm[cls][cls]
        # Any prediction that is not cls (other class, error, unknown) is a false negative
        fn = sum(v for k, v in cm[cls].items() if k != cls)
        fp = sum(cm[t][cls] for t in CLASSES if t != cls)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        f1_list.append(f1)
        per_class[cls] = {
            'turkish_name': TURKISH_NAMES[cls],
            'tp': tp, 'fp': fp, 'fn': fn,
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4)
        }

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    total = len(true_labels)
    correct = sum(1 for t, p in zip(true_labels, pred_labels) if t == p)
    accuracy = correct / total if total > 0 else 0.0

    return {
        'confusion_matrix': {t: dict(cm[t]) for t in CLASSES},
        'per_class': per_class,
        'macro_f1': round(macro_f1, 4),
        'accuracy': round(accuracy, 4),
        'karma_recall': per_class['combination']['recall'],
        'total_evaluated': total,
        'correct': correct,
    }

def run_comparison():
    client = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=api_key
    )
    client.configure(InferenceConfiguration(api_key_transport="header"))

    samples = select_independent_samples(per_class=5)
    sample_manifest = []
    for cls, flist in samples.items():
        for f in flist:
            sample_manifest.append({
                'true_class': cls,
                'filename': f.name,
                'path': str(f),
                'prefix': f.name.split('_jpg.rf.')[0].replace('-Copy', '')
            })

    print(f"=== ROBOFLOW 4-CLASS COMPARATIVE EVALUATION ({len(sample_manifest)} SAMPLES x {len(MODELS)} MODELS = {len(sample_manifest) * len(MODELS)} CALLS) ===")
    print(f"Dataset: Kaggle facial-skin-analysis-and-type-classification (Apache-2.0)")
    print(f"Classes: {', '.join(CLASSES)} ({', '.join(TURKISH_NAMES.values())})")
    print(f"Sampling: 5 deduplicated, non-leaking test images per class\n")

    eval_results = {}

    for model_id in MODELS:
        print(f"Evaluating {model_id}...")
        true_list = []
        pred_list = []
        conf_list = []
        latency_list = []
        records = []

        for item in sample_manifest:
            img_path = item['path']
            true_cls = item['true_class']
            t0 = time.perf_counter()
            try:
                res = client.infer(img_path, model_id=model_id)
                lat = (time.perf_counter() - t0) * 1000
                top_c = res.get('top') or (res.get('predictions', [{}])[0].get('class') if isinstance(res.get('predictions'), list) and res.get('predictions') else None)
                conf = res.get('confidence') or (res.get('predictions', [{}])[0].get('confidence') if isinstance(res.get('predictions'), list) and res.get('predictions') else 0.0)
                pred_c = str(top_c).strip().lower() if top_c else 'unknown'
                
                true_list.append(true_cls)
                pred_list.append(pred_c)
                conf_list.append(conf)
                latency_list.append(lat)
                records.append({
                    'image': item['filename'],
                    'true_class': true_cls,
                    'pred_class': pred_c,
                    'confidence': conf,
                    'latency_ms': round(lat, 2),
                    'correct': (true_cls == pred_c)
                })
                mark = "[OK]" if true_cls == pred_c else "[FAIL]"
                print(f"  {true_cls:<11} -> {pred_c:<11} (conf={conf:.3f}, {lat:.1f}ms) {mark}")
            except Exception as e:
                lat = (time.perf_counter() - t0) * 1000
                true_list.append(true_cls)
                pred_list.append('error')
                records.append({
                    'image': item['filename'],
                    'true_class': true_cls,
                    'pred_class': 'error',
                    'error': str(e),
                    'latency_ms': round(lat, 2),
                    'correct': False
                })
                print(f"  {true_cls:<11} -> ERROR: {str(e)[:40]}")

        metrics = compute_metrics(true_list, pred_list)
        metrics['latency_ms_mean'] = round(sum(latency_list) / len(latency_list), 2) if latency_list else 0.0
        metrics['latency_ms_min'] = round(min(latency_list), 2) if latency_list else 0.0
        metrics['latency_ms_max'] = round(max(latency_list), 2) if latency_list else 0.0
        metrics['detailed_records'] = records

        eval_results[model_id] = metrics

        print(f"\n--- Results for {model_id} ---")
        print(f"Accuracy:      {metrics['accuracy']*100:.1f}% ({metrics['correct']}/{metrics['total_evaluated']})")
        print(f"Macro-F1:      {metrics['macro_f1']:.4f}")
        print(f"Karma Recall:  {metrics['karma_recall']*100:.1f}%")
        print(f"Mean Latency:  {metrics['latency_ms_mean']} ms\n")

    # Winner selection based on class-level metrics and Karma recall
    axavj_f1 = eval_results['skin-type-axavj/1']['macro_f1']
    ng2uj_f1 = eval_results['skin-type-ng2uj/1']['macro_f1']
    axavj_karma = eval_results['skin-type-axavj/1']['karma_recall']
    ng2uj_karma = eval_results['skin-type-ng2uj/1']['karma_recall']

    recommended = 'skin-type-axavj/1' if (axavj_f1 >= ng2uj_f1 and axavj_karma >= ng2uj_karma) else ('skin-type-ng2uj/1' if ng2uj_f1 > axavj_f1 else 'skin-type-axavj/1')

    summary = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'dataset': {
            'name': 'facial-skin-analysis-and-type-classification (skin-18criteria-v1)',
            'license': 'Apache-2.0',
            'split': 'test (deduplicated by source image prefix)',
            'sample_count': len(sample_manifest),
            'samples_per_class': 5,
            'classes': CLASSES,
            'turkish_names': TURKISH_NAMES,
        },
        'comparison': eval_results,
        'selection': {
            'chosen_model_id': recommended,
            'rationale': f"Macro-F1: {eval_results[recommended]['macro_f1']} vs {eval_results['skin-type-ng2uj/1' if recommended == 'skin-type-axavj/1' else 'skin-type-axavj/1']['macro_f1']}; Karma Recall: {eval_results[recommended]['karma_recall']} vs {eval_results['skin-type-ng2uj/1' if recommended == 'skin-type-axavj/1' else 'skin-type-axavj/1']['karma_recall']}."
        }
    }

    out_file = Path('audit-results/skin-type-models-comparison.json')
    out_file.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(f"Comparison report saved to: {out_file.resolve()}")
    print(f"\nSELECTED MODEL: {recommended}")
    print(f"Rationale: {summary['selection']['rationale']}")

if __name__ == '__main__':
    run_comparison()
