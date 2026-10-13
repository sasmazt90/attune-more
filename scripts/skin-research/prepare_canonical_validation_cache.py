#!/usr/bin/env python3
"""Precompute and cache canonical validation image envelopes and masks for fast, zero-drift evaluation."""

import sys
import os
import json
import base64
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.append(str(LIVE_TEST / '.runtime/python-packages'))
import pickle
import cv2
import numpy as np
import mediapipe as mp

sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
from evaluate_all_checkpoints_side_by_side import MANIFEST_PATH, compute_masks_and_envelopes

CACHE_PATH = ROOT / 'audit-results/acne-detection-verification-20261013/canonical-validation-cache.pkl'


def build_and_save_cache():
    print("=== Precomputing Canonical Validation Images Cache ===", flush=True)
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    data_path = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    rows_by_sha = {r['sha256']: r for r in data['rows'] if r.get('split') == 'validation'}

    adapter_payload = []
    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    raw_images = {}
    for m_img in manifest['images']:
        sha = m_img['sha256']
        row = rows_by_sha[sha]
        img_path = Path(row['absolutePath']) if 'absolutePath' in row and Path(row['absolutePath']).exists() else (LIVE_TEST / row['path'])
        assert img_path.exists(), f"Image missing: {img_path}"
        bgr = cv2.imread(str(img_path))
        raw_images[sha] = bgr
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        points = (
            [{'x': float(p.x), 'y': float(p.y), 'z': float(p.z)} for p in det.face_landmarks[0]]
            if det.face_landmarks and len(det.face_landmarks[0]) >= 468
            else []
        )
        rgb_b64 = base64.b64encode(rgb.tobytes()).decode('ascii')
        adapter_payload.append({
            'sha256': sha,
            'width': w,
            'height': h,
            'landmarks': points,
            'rgbBase64': rgb_b64
        })

    node_path = f"{LIVE_TEST / 'node_modules'};{LIVE_TEST / 'apps/vehicle-app/node_modules'};{ROOT / 'node_modules'};{ROOT / 'apps/vehicle-app/node_modules'}"
    env = os.environ.copy()
    env['NODE_PATH'] = node_path
    cmd = ['node', str(ROOT / 'scripts/skin-research/product_skin_adapter.cjs')]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(json.dumps(adapter_payload).encode('utf-8'))
    if p.returncode != 0:
        raise RuntimeError(f"product_skin_adapter.cjs failed:\n{err.decode('utf-8')}")
    adapter_results = {res['sha256']: res for res in json.loads(out.decode('utf-8'))}

    images_data = []
    for m_img in manifest['images']:
        sha = m_img['sha256']
        bgr = raw_images[sha]
        ares = adapter_results[sha]
        points = ares.get('alignment') and ares['alignment'].get('box') and [item for item in adapter_payload if item['sha256'] == sha][0]['landmarks']
        meshes = ares.get('meshes', {})

        if points:
            envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = compute_masks_and_envelopes(
                bgr, points, meshes
            )
        else:
            envelopes, skin_support, hair, exclusion, scale, origin, face_support, face_pixels = [None]*8

        allowed_regions = ares.get('allowedRegions', [])
        truth_boxes = [a['box'] for a in m_img['annotations']]
        truth_categories = [a['scopeCategory'] for a in m_img['annotations']]

        images_data.append({
            'sha256': sha,
            'fileName': m_img['fileName'],
            'bgr': bgr,
            'width': m_img['width'],
            'height': m_img['height'],
            'landmarks': points,
            'productAngle': m_img['productAngle'],
            'isProductPose': m_img['isProductPose'],
            'capturable': m_img['capturable'],
            'isNegative': m_img['isNegative'],
            'truth': truth_boxes,
            'truthCategories': truth_categories,
            'envelopes': envelopes,
            'skin_support': skin_support,
            'hair': hair,
            'exclusion': exclusion,
            'scale': scale,
            'origin': origin,
            'face_support': face_support,
            'facePixels': face_pixels,
            'allowedRegions': allowed_regions
        })

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, 'wb') as f:
        pickle.dump(images_data, f)
    print(f"Precomputed canonical cache saved to: {CACHE_PATH} ({len(images_data)} images)")
    return images_data


def load_canonical_validation_cache():
    if not CACHE_PATH.exists():
        return build_and_save_cache()
    with open(CACHE_PATH, 'rb') as f:
        return pickle.load(f)


if __name__ == '__main__':
    build_and_save_cache()
