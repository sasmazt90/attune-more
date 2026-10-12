"""Check Roboflow API project metadata and weight download availability.
NEVER prints, logs or records private API keys.
"""
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

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

def scrub(val):
    if not isinstance(val, str):
        return val
    if api_key and api_key in val:
        return val.replace(api_key, "[REDACTED_API_KEY]")
    return val

headers = {'Authorization': f'Bearer {api_key}'}

MODELS = [
    ('face-detection-beautysense', 'skin-type-axavj', '1'),
    ('fyp-symvg', 'skin-type-ng2uj', '1'),
]

results = {}

for workspace, project, version in MODELS:
    slug = f"{workspace}/{project}/{version}"
    print(f"=== Checking {slug} ===")
    
    # 1. Project level metadata
    proj_url = f"https://api.roboflow.com/{workspace}/{project}"
    try:
        req = urllib.request.Request(proj_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            proj_data = json.loads(resp.read().decode('utf-8'))
            print(f"  Project {project}: OK (type={proj_data.get('project', {}).get('type')}, license={proj_data.get('project', {}).get('license')})")
    except urllib.error.HTTPError as e:
        print(f"  Project {project}: HTTP {e.code} - {scrub(e.reason)}")
    except Exception as e:
        print(f"  Project {project}: {scrub(str(e))}")

    # 2. Version level metadata
    ver_url = f"https://api.roboflow.com/{workspace}/{project}/{version}"
    ver_data = {}
    try:
        req = urllib.request.Request(ver_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            ver_data = json.loads(resp.read().decode('utf-8'))
            v_info = ver_data.get('version', {})
            exports = v_info.get('exports', [])
            weights = v_info.get('weights') or v_info.get('model', {}).get('weights')
            print(f"  Version {version}: OK")
            print(f"    exports: {exports}")
            print(f"    weights: {weights}")
    except urllib.error.HTTPError as e:
        print(f"  Version {version}: HTTP {e.code} - {scrub(e.reason)}")
    except Exception as e:
        print(f"  Version {version}: {scrub(str(e))}")

    # 3. Model weights endpoint (documented in roboflow weights download API)
    # https://docs.roboflow.com/models/model-weights/download-roboflow-model-weights
    weights_urls = [
        f"https://api.roboflow.com/{workspace}/{project}/{version}/weights",
        f"https://api.roboflow.com/{workspace}/{project}/{version}/weights/onnx",
        f"https://api.roboflow.com/{workspace}/{project}/{version}/model",
    ]
    for w_url in weights_urls:
        endpoint_name = w_url.split(f"/{version}/")[-1]
        try:
            req = urllib.request.Request(w_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                print(f"    Endpoint '{endpoint_name}': HTTP 200 -> keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        except urllib.error.HTTPError as e:
            err_body = scrub(e.read().decode('utf-8', errors='ignore'))
            print(f"    Endpoint '{endpoint_name}': HTTP {e.code} ({scrub(e.reason)}): {err_body[:100]}")
        except Exception as e:
            print(f"    Endpoint '{endpoint_name}': {scrub(str(e))}")

    results[slug] = {
        'workspace': workspace,
        'project': project,
        'version': version,
        'version_metadata': {
            'exports': ver_data.get('version', {}).get('exports'),
            'weights': ver_data.get('version', {}).get('weights') or ver_data.get('version', {}).get('model', {}).get('weights'),
        }
    }

out_file = Path('audit-results/skin-type-weights-availability.json')
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(json.dumps(results, indent=2), encoding='utf-8')
print(f"\nSaved weights availability report to {out_file.resolve()}")
