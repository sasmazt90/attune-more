"""Audit Roboflow workspace (`tolgar-sasmaz`) models, trainings, metrics, and local weight exportability.
Follows security guardrails: reads ROBOFLOW_API_KEY / ATTUNE_ROBOFLOW_API_KEY from environment/.env.local
and never prints or writes any API key or signed token to output files.
"""
import json
import os
import re
import urllib.request
from pathlib import Path


def load_key():
    for k in ('ROBOFLOW_API_KEY', 'ATTUNE_ROBOFLOW_API_KEY'):
        v = os.environ.get(k, '').strip()
        if v:
            return v
    for p in (
        Path('.env.local'),
        Path('C:/Users/PC/Desktop/AI Workspace/TOGG/.env.local'),
        Path('C:/Users/PC/Desktop/AI Workspace/TOGG/attune-antigravity-skin/.env.local'),
    ):
        if p.is_file():
            for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, val = line.partition('=')
                    if k.strip() in ('ROBOFLOW_API_KEY', 'ATTUNE_ROBOFLOW_API_KEY'):
                        val = val.strip().strip('"').strip("'")
                        if val:
                            return val
    return ''


def scrub(obj, key):
    if isinstance(obj, str):
        s = obj.replace(key, '[REDACTED]') if key else obj
        s = re.sub(r'api_key=[^&\s"\']+', 'api_key=[REDACTED]', s)
        s = re.sub(r'token=[^&\s"\']+', 'token=[REDACTED]', s)
        s = re.sub(r'Signature=[^&\s"\']+', 'Signature=[REDACTED]', s)
        return s
    if isinstance(obj, dict):
        return {k: scrub(v, key) for k, v in obj.items() if k not in ('key', 'api_key')}
    if isinstance(obj, list):
        return [scrub(x, key) for x in obj]
    return obj


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': 'AttuneInventoryAudit/1.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main():
    key = load_key()
    if not key:
        print('NO_API_KEY_FOUND')
        return

    from roboflow import Roboflow
    rf = Roboflow(api_key=key)
    ws = rf.workspace('tolgar-sasmaz')
    ws_data = fetch_json(f'https://api.roboflow.com/tolgar-sasmaz?api_key={key}')
    projects_raw = ws_data.get('workspace', {}).get('projects', [])

    inventory = []
    for p_meta in projects_raw:
        pid = p_meta.get('id', '').split('/')[-1]
        p_detail = fetch_json(f'https://api.roboflow.com/tolgar-sasmaz/{pid}?api_key={key}')
        proj_obj = p_detail.get('project', {})
        versions_raw = p_detail.get('versions', [])
        proj_sdk = ws.project(pid)

        ver_entries = []
        for v_raw in versions_raw:
            v_num = str(v_raw.get('id', '')).split('/')[-1]
            v_detail = fetch_json(f'https://api.roboflow.com/tolgar-sasmaz/{pid}/{v_num}?api_key={key}')
            v_obj = v_detail.get('version', v_raw)
            train_obj = v_obj.get('train') or {}
            model_obj = v_obj.get('model') or {}

            sdk_models_info = []
            sdk_trainings_info = []
            weight_download_check = {'attempted': False, 'exportableLocalWeights': False, 'reason': 'no-trained-model'}
            try:
                ver_sdk = proj_sdk.version(int(v_num))
                if hasattr(ver_sdk, 'models') and callable(ver_sdk.models):
                    m_list = ver_sdk.models()
                    sdk_models_info = [str(m) for m in (m_list or [])]
                if hasattr(ver_sdk, 'trainings') and callable(ver_sdk.trainings):
                    t_list = ver_sdk.trainings()
                    for t in (t_list or []):
                        t_dict = getattr(t, '__dict__', {})
                        sdk_trainings_info.append({
                            k: scrub(v, key)
                            for k, v in t_dict.items()
                            if not k.startswith('_') and k in ('id', 'status', 'model_type', 'metrics', 'created', 'endpoint', 'weights')
                        })
            except Exception as e:
                sdk_models_info = [f'sdk_err:{type(e).__name__}:{scrub(str(e), key)}']

            # Check if weights URL or ONNX/PT weight export exists in version detail
            weights_fields = {}
            for k_w in ('weights', 'onnx', 'tfjs', 'coreml', 'tflite', 'OpenVINO'):
                if k_w in model_obj:
                    val = model_obj[k_w]
                    weights_fields[k_w] = bool(val) if not isinstance(val, dict) else list(val.keys())
                if k_w in train_obj:
                    val = train_obj[k_w]
                    weights_fields[f'train_{k_w}'] = bool(val) if not isinstance(val, dict) else list(val.keys())

            if train_obj or model_obj or sdk_trainings_info:
                has_weights_url = bool(weights_fields)
                weight_download_check = {
                    'attempted': True,
                    'exportableLocalWeights': has_weights_url,
                    'weightsFieldsPresent': weights_fields,
                    'trainStatus': train_obj.get('status'),
                    'modelType': train_obj.get('modelType') or model_obj.get('modelType') or model_obj.get('type'),
                    'endpoint': model_obj.get('endpoint') or train_obj.get('endpoint'),
                }

            ver_entries.append({
                'version': v_num,
                'id': v_obj.get('id'),
                'name': v_obj.get('name'),
                'images': v_obj.get('images'),
                'splits': v_obj.get('splits'),
                'preprocessing': v_obj.get('preprocessing'),
                'augmentation': v_obj.get('augmentation'),
                'exports': v_obj.get('exports'),
                'modelId': model_obj.get('id'),
                'modelEndpoint': model_obj.get('endpoint'),
                'modelType': model_obj.get('type') or train_obj.get('modelType'),
                'modelMap': model_obj.get('map'),
                'modelPrecision': model_obj.get('precision'),
                'modelRecall': model_obj.get('recall'),
                'trainStatus': train_obj.get('status'),
                'trainResults': train_obj.get('results'),
                'trainMetrics': train_obj.get('metrics'),
                'sdkModels': sdk_models_info,
                'sdkTrainings': sdk_trainings_info,
                'weightCheck': weight_download_check,
                'rawModelKeys': list(model_obj.keys()),
                'rawTrainKeys': list(train_obj.keys()),
            })

        inventory.append({
            'projectId': pid,
            'name': proj_obj.get('name'),
            'type': proj_obj.get('type'),
            'classes': proj_obj.get('classes'),
            'images': proj_obj.get('images'),
            'versions': ver_entries,
        })

    out = scrub({'workspace': 'tolgar-sasmaz', 'projectCount': len(inventory), 'projects': inventory}, key)
    for out_path in (
        Path('docs/skin-research/roboflow-workspace-inventory-20261024.json'),
        Path('C:/Users/PC/Desktop/AI Workspace/TOGG/e2e-verification-20261024/roboflow-workspace-inventory-20261024.json'),
    ):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Saved workspace inventory ({len(inventory)} projects) to {out_path.resolve()}')


if __name__ == '__main__':
    main()
