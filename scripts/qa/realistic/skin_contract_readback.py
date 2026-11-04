#!/usr/bin/env python3
"""QA-31 runtime proof. Reads the Skin API responses a journey saved and compares model hashes with disk.

Shows what actually ran on this platform: method and model per criterion, the acne chain, skin type,
the findings models and their hashes. A hash is compared with the file the API process can read.
Says nothing about accuracy. Usage: skin_contract_readback.py <evidence folder> [--model-dir PATH]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

DEFAULT_MODEL_DIR = '/opt/attune/services/core-api/models/regional-skin-v3'


def walk_for(value, key, found=None):
    found = [] if found is None else found
    if isinstance(value, dict):
        for k, v in value.items():
            if k == key:
                found.append(v)
            walk_for(v, key, found)
    elif isinstance(value, list):
        for item in value:
            walk_for(item, key, found)
    return found


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder')
    parser.add_argument('--model-dir', default=os.environ.get('ATTUNE_REGIONAL_V3_DIR', DEFAULT_MODEL_DIR))
    args = parser.parse_args()
    report = json.loads((Path(args.folder) / 'report.json').read_text())
    bodies = report.get('apiBodies', [])
    skin = [b['body'] for b in bodies if b['path'].endswith('local-health/skin')]
    fuse = [b['body'] for b in bodies if b['path'].endswith('regional-fuse')]
    prepare = [b['body'] for b in bodies if b['path'].endswith('prepare')]
    out = {'platform': report.get('platform'), 'input': report.get('input'), 'photosAnalyzed': len(skin), 'fusions': len(fuse), 'prepareCalls': len(prepare)}
    front = skin[0] if skin else {}
    acne = front.get('acneRuntime') or {}
    out['acneChain'] = {k: acne.get(k) for k in ('methodVersion', 'status', 'reason', 'experimental', 'accepted', 'modelHash', 'step0SHA256', 'onnxSHA256', 'verifierSHA256', 'tileCount', 'detectorForwardCount', 'timing')}
    out['acneChain']['nonAcneUnchanged'] = (acne.get('nonAcnePreservation') or {}).get('equal')
    methods = (front.get('activeCriterionMethods') or {}).get('criteria') or {}
    out['criteria'] = {name: {region: {k: row.get(k) for k in ('methodVersion', 'modelVersion', 'modelHash', 'calibrationVersion', 'status', 'reason')} for region, row in regions.items() if region == 'overview' or len(regions) == 1} for name, regions in methods.items()}
    out['skinType'] = (front.get('general') or {}).get('skinType')
    out['modelInference'] = (front.get('general') or {}).get('modelInference')
    out['experimentalResearchModels'] = front.get('experimentalResearchModels')
    manifests = walk_for(fuse, 'models') + walk_for(skin, 'models') + walk_for(prepare, 'models')
    declared = {}
    for manifest in manifests:
        if isinstance(manifest, dict):
            for name, value in manifest.items():
                if isinstance(value, str) and len(value) == 64:
                    declared[name] = value
    disk = {}
    for name, value in sorted(declared.items()):
        path = Path(args.model_dir) / name
        disk[name] = {'runtimeSHA256': value, 'fileExists': path.exists(), 'matchesDisk': path.exists() and sha(path) == value}
    out['runtimeModels'] = disk
    out['allRuntimeHashesMatchDisk'] = bool(disk) and all(v['matchesDisk'] for v in disk.values())
    findings = walk_for(fuse, 'findings')
    rows = next((f for f in findings if isinstance(f, list) and f and isinstance(f[0], dict)), [])
    out['findings'] = [{k: f.get(k) for k in ('id', 'region', 'status', 'pose', 'score', 'threshold', 'count', 'countUnavailable', 'severity', 'areaPct', 'reason') if k in f} for f in rows]
    regional = walk_for(fuse, 'regions')
    states = next((r for r in regional if isinstance(r, dict) and r), {})
    out['regionalStates'] = {k: {'state': v.get('state'), 'sensitive': v.get('sensitive'), 'reason': v.get('reason')} for k, v in states.items() if isinstance(v, dict)}
    types = walk_for(fuse, 'skinType')
    out['fusedSkinType'] = types[0] if types else None
    uncertain = [k for k, v in out['regionalStates'].items() if v['state'] == 'unmeasured']
    out['unmeasuredRegions'] = uncertain
    target = Path(args.folder) / 'skin-contract-runtime.json'
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, ensure_ascii=False)[:6000])


if __name__ == '__main__':
    main()
