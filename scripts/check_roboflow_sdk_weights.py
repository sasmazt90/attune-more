"""Test official Roboflow Python SDK model weights download method (Method B in docs):
https://docs.roboflow.com/models/model-weights/download-roboflow-model-weights
Tests whether current authorized key has workspace permission to download classification weights.
NEVER prints, logs or records private API keys.
"""
import os, sys, json
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
    print("ERROR: ATTUNE_ROBOFLOW_API_KEY not found", file=sys.stderr)
    sys.exit(1)

def scrub(val):
    if not isinstance(val, str):
        return val
    if api_key and api_key in val:
        return val.replace(api_key, "[REDACTED_API_KEY]")
    return val

from roboflow import Roboflow

print("=== CHECKING OFFICIAL ROBOFLOW PYTHON SDK WEIGHTS ACCESS ===")
rf = Roboflow(api_key=api_key)

MODELS = [
    ('face-detection-beautysense', 'skin-type-axavj', 1),
    ('fyp-symvg', 'skin-type-ng2uj', 1),
]

sdk_results = {}

for workspace_id, project_id, version_num in MODELS:
    slug = f"{workspace_id}/{project_id}/{version_num}"
    print(f"\n--- Checking {slug} via Roboflow SDK ---")
    result_entry = {
        'workspace': workspace_id,
        'project': project_id,
        'version': version_num,
    }
    
    try:
        # Access workspace
        ws = rf.workspace(workspace_id)
        print(f"  Workspace '{workspace_id}' access: OK")
        
        # Access project
        project = ws.project(project_id)
        print(f"  Project '{project_id}' type: {getattr(project, 'type', 'unknown')}")
        
        # Access version
        ver = project.version(version_num)
        print(f"  Version {version_num}: OK")
        
        # Check models on version
        models_list = getattr(ver, 'models', None)
        if callable(models_list):
            models_list = models_list()
        print(f"  Models on version: {models_list}")
        
        # Try downloading weights
        target_dir = Path(f'models/download_test_{project_id}')
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if version has model or download
        model_obj = ver.model if hasattr(ver, 'model') else (models_list[0] if models_list else None)
        if model_obj and hasattr(model_obj, 'download'):
            print("  Attempting model_obj.download()...")
            dl_res = model_obj.download(location=str(target_dir))
            print(f"  Download succeeded: {dl_res}")
            result_entry['status'] = 'DOWNLOAD_SUCCESS'
            result_entry['download_result'] = str(dl_res)
        else:
            print("  No model_obj.download method found on version object")
            result_entry['status'] = 'NO_DOWNLOAD_METHOD'
            result_entry['detail'] = f"ver attributes: {[a for a in dir(ver) if not a.startswith('_')]}"
            
    except Exception as e:
        err_msg = scrub(str(e))
        print(f"  SDK Exception: {err_msg}")
        result_entry['status'] = 'ACCESS_ERROR'
        result_entry['error_class'] = e.__class__.__name__
        result_entry['error_message'] = err_msg

    sdk_results[slug] = result_entry

out_file = Path('audit-results/skin-type-sdk-weights-check.json')
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(json.dumps(sdk_results, indent=2), encoding='utf-8')
print(f"\nSDK Weights verification saved to: {out_file.resolve()}")
