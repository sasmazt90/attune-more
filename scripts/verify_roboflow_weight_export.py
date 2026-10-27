"""Verify actual local weight downloadability (.pt / .onnx) for all trained models in `tolgar-sasmaz`.
Follows security guardrails: never prints or logs API keys or signed URLs.
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


def scrub(s: str, key: str) -> str:
    if not isinstance(s, str):
        return str(s)
    out = s.replace(key, '[REDACTED]') if key else s
    out = re.sub(r'api_key=[^&\s"\']+', 'api_key=[REDACTED]', out)
    out = re.sub(r'token=[^&\s"\']+', 'token=[REDACTED]', out)
    out = re.sub(r'Signature=[^&\s"\']+', 'Signature=[REDACTED]', out)
    out = re.sub(r'https://storage\.googleapis\.com/[^\s"\']+', 'https://storage.googleapis.com/[REDACTED_SIGNED_URL]', out)
    return out


TRAINED_TARGETS = [
    ('attune-comedones-boxes-grouped-r1', 1, 'rfdetr-small'),
    ('attune-comedones-clean-train-r2', 1, 'rfdetr-nas'),
    ('attune-pores-masks-grouped-r1', 2, 'yolov11s-seg'),
    ('attune-skin-acne-marks-pigmentation', 1, 'rfdetr-nas'),
    ('attune-skin-findings-boxes-research', 1, 'rfdetr-nas'),
    ('attune-skin-regional-skin-map', 1, 'rfdetr-nas-seg'),
    ('lesion-detection-ruc40-qzwqz', 1, 'rfdetr-large'),
]


def main():
    key = load_key()
    if not key:
        print('NO_API_KEY_FOUND')
        return

    from roboflow import Roboflow
    rf = Roboflow(api_key=key)
    ws = rf.workspace('tolgar-sasmaz')

    results = []
    for pid, ver_num, mtype in TRAINED_TARGETS:
        entry = {
            'projectId': pid,
            'version': ver_num,
            'modelType': mtype,
            'restVersionTrainKeys': [],
            'restModelKeys': [],
            'weightsUrlInVersionJson': False,
            'sdkModelsDownloadAttempt': None,
            'restWeightsEndpointAttempt': None,
        }
        # 1. Check REST version JSON for any weight URLs (weights, onnx, pt, etc.)
        try:
            url = f'https://api.roboflow.com/tolgar-sasmaz/{pid}/{ver_num}?api_key={key}'
            req = urllib.request.Request(url, headers={'User-Agent': 'AttuneWeightAudit/1.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            v_obj = data.get('version', {})
            t_obj = v_obj.get('train') or {}
            m_obj = v_obj.get('model') or {}
            entry['restVersionTrainKeys'] = list(t_obj.keys())
            entry['restModelKeys'] = list(m_obj.keys())
            found_weight_keys = []
            for k_w in ('weights', 'onnx', 'pt', 'torchscript', 'tflite', 'coreml'):
                if t_obj.get(k_w):
                    found_weight_keys.append(f'train.{k_w}')
                if m_obj.get(k_w):
                    found_weight_keys.append(f'model.{k_w}')
            entry['weightsUrlInVersionJson'] = bool(found_weight_keys)
            entry['foundWeightKeys'] = found_weight_keys
        except Exception as e:
            entry['restVersionError'] = f'{type(e).__name__}: {scrub(str(e), key)}'

        # 2. Check REST /{workspace}/{project}/{version}/{format} or /weights endpoint
        for ep_suffix in ('weights', mtype, 'onnx'):
            try:
                url = f'https://api.roboflow.com/tolgar-sasmaz/{pid}/{ver_num}/{ep_suffix}?api_key={key}'
                req = urllib.request.Request(url, headers={'User-Agent': 'AttuneWeightAudit/1.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    ep_data = json.loads(resp.read().decode('utf-8'))
                entry[f'restEndpoint_{ep_suffix}'] = {
                    'httpStatus': 200,
                    'keys': list(ep_data.keys()),
                    'hasWeightsUrl': bool(ep_data.get('weights') or ep_data.get('model', {}).get('weights')),
                }
            except urllib.error.HTTPError as he:
                body = ''
                try:
                    body = he.read().decode('utf-8', errors='ignore')[:200]
                except Exception:
                    pass
                entry[f'restEndpoint_{ep_suffix}'] = {
                    'httpStatus': he.code,
                    'error': scrub(body, key),
                }
            except Exception as e:
                entry[f'restEndpoint_{ep_suffix}'] = {
                    'error': f'{type(e).__name__}: {scrub(str(e), key)}',
                }

        # 3. Check SDK model object methods
        try:
            ver_sdk = ws.project(pid).version(ver_num)
            m_list = ver_sdk.models() if hasattr(ver_sdk, 'models') and callable(ver_sdk.models) else []
            if m_list:
                m0 = m_list[0]
                m_attrs = [a for a in dir(m0) if not a.startswith('_')]
                has_dl = hasattr(m0, 'download')
                entry['sdkModelsDownloadAttempt'] = {
                    'modelCount': len(m_list),
                    'firstModelAttrs': m_attrs,
                    'hasDownloadMethod': has_dl,
                }
                if has_dl:
                    tmp_dir = Path(f'C:/Users/PC/Desktop/AI Workspace/TOGG/e2e-verification-20261024/tmp_weights_{pid}')
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    dl_res = m0.download(location=str(tmp_dir))
                    entry['sdkModelsDownloadAttempt']['downloadResult'] = scrub(str(dl_res), key)
            else:
                entry['sdkModelsDownloadAttempt'] = {'modelCount': 0, 'hasDownloadMethod': False}
        except Exception as e:
            entry['sdkModelsDownloadAttempt'] = {'error': f'{type(e).__name__}: {scrub(str(e), key)}'}

        results.append(entry)

    out_payload = {'workspace': 'tolgar-sasmaz', 'weightExportAudit': results}
    for out_path in (
        Path('docs/skin-research/roboflow-weight-export-audit-20261024.json'),
        Path('C:/Users/PC/Desktop/AI Workspace/TOGG/e2e-verification-20261024/roboflow-weight-export-audit-20261024.json'),
    ):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Saved weight export audit to {out_path.resolve()}')


if __name__ == '__main__':
    main()
