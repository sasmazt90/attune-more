"""Focused, bounded access probe for 4-class skin type models on Roboflow Serverless API.
Max 8 requests: 1 photo per class (normal, dry, oily, combination) x 2 candidate models.
Uses official inference-sdk with api_key_transport='header'.
NEVER prints, logs or records private API keys.
"""
import os, sys, time, json
from pathlib import Path

# Load local env if requested
env_file = Path('.env.local')
if os.getenv('ATTUNE_LOAD_LOCAL_ENV') == '1' and env_file.is_file():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            k, sep, v = line.partition('=')
            if sep and k.strip() in ('ATTUNE_ROBOFLOW_API_KEY', 'ROBOFLOW_API_KEY', 'ATTUNE_SKIN_TYPE_MODEL'):
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

api_key = os.getenv('ATTUNE_ROBOFLOW_API_KEY') or os.getenv('ROBOFLOW_API_KEY')
if not api_key:
    print("ERROR: ATTUNE_ROBOFLOW_API_KEY not found in environment or .env.local", file=sys.stderr)
    sys.exit(1)

from inference_sdk import InferenceConfiguration, InferenceHTTPClient
from inference_sdk.http.errors import HTTPCallErrorError, HTTPClientError

MODELS = [
    'skin-type-axavj/1',
    'skin-type-ng2uj/1',
]

CLASSES = ['normal', 'dry', 'oily', 'combination']

DATASET_ROOT = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-live-test\audit-results\focused-skin-20261010\sources\skin-18criteria-v1\skin_type_classification_dataset\test')

# Pick 1 representative test photo per class
TEST_SAMPLES = {
    'normal': DATASET_ROOT / 'normal' / 'normal_037d2ca54ba52d645ffd_jpg.rf.016f29e4a2114b6ad3b15a0d0b356850.jpg',
    'dry': DATASET_ROOT / 'dry' / 'dry_00f1189752d6631b2b22_jpg.rf.7baa779a64867cadde0a202baeeed00f.jpg',
    'oily': DATASET_ROOT / 'oily' / 'oily_021e826dd8fd78c2e8f5-Copy_jpg.rf.233c9ee4e5e1910fd22e32bc70475f9d.jpg',
    'combination': DATASET_ROOT / 'combination' / 'combination_-_0bc5ca1194a13cfd7b9a_jpg.rf.0c21ccb4c6c58bf8aacd4d27c5042db9.jpg',
}

def scrub(val):
    if not isinstance(val, str):
        return val
    if api_key and api_key in val:
        return val.replace(api_key, "[REDACTED_API_KEY]")
    return val

def run_probe():
    client = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=api_key
    )
    client.configure(InferenceConfiguration(api_key_transport="header"))

    results = []
    print(f"=== ROBOFLOW SERVERLESS 4-CLASS ACCESS PROBE (MAX {len(MODELS) * len(TEST_SAMPLES)} REQUESTS) ===")
    
    for model_id in MODELS:
        print(f"\n--- Testing Model: {model_id} ---")
        for true_class, img_path in TEST_SAMPLES.items():
            if not img_path.is_file():
                print(f"  [SKIP] Image not found: {img_path.name}")
                continue
            
            entry = {
                'model_id': model_id,
                'true_class': true_class,
                'image_name': img_path.name,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            }
            start_t = time.perf_counter()
            try:
                res = client.infer(str(img_path), model_id=model_id)
                elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                entry['success'] = True
                entry['status_code'] = 200
                entry['latency_ms'] = elapsed_ms
                entry['raw_response'] = res
                
                # Check top prediction
                top_pred = res.get('top') or (res.get('predictions', [{}])[0].get('class') if isinstance(res.get('predictions'), list) and res.get('predictions') else None)
                conf = res.get('confidence') or (res.get('predictions', [{}])[0].get('confidence') if isinstance(res.get('predictions'), list) and res.get('predictions') else None)
                entry['predicted_class'] = top_pred
                entry['confidence'] = conf
                
                print(f"  True: {true_class:<11} -> Pred: {str(top_pred):<11} Conf: {conf} ({elapsed_ms}ms) [OK]")
            except HTTPCallErrorError as e:
                elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                entry['success'] = False
                entry['status_code'] = e.status_code
                entry['latency_ms'] = elapsed_ms
                entry['error_message'] = scrub(str(e.api_message or e.description))
                print(f"  True: {true_class:<11} -> HTTP {e.status_code}: {scrub(str(e.api_message or e.description))} ({elapsed_ms}ms) [FAIL]")
            except Exception as e:
                elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
                entry['success'] = False
                entry['status_code'] = getattr(e, 'status_code', None) or 'CLIENT_ERROR'
                entry['latency_ms'] = elapsed_ms
                entry['error_message'] = scrub(str(e))
                print(f"  True: {true_class:<11} -> ERROR: {scrub(str(e))} ({elapsed_ms}ms) [FAIL]")
            
            results.append(entry)

    out_file = Path('audit-results/skin-type-access-probe.json')
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f"\nProbe evidence saved to: {out_file.resolve()}")

if __name__ == '__main__':
    run_probe()
