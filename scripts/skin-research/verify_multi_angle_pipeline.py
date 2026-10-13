#!/usr/bin/env python3
"""Run multi-angle product capture proof across 3 real validation images (FRONT, RIGHT, LEFT).

Demonstrates:
1. MediaPipe FaceLandmarker detection
2. Frontend execution via verify_product_angle_pipeline.cjs
3. Exact inspection of why RIGHT profile 55d380f7 passes and LEFT profile 5432a6e1 fails due to blur
"""

import os
import sys
import json
import base64
import subprocess
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

sys.path.append(str(LIVE_TEST / '.runtime/python-packages'))
import mediapipe as mp

DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
LANDMARKER_MODEL = ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'

test_targets = [
    ('FRONT', '695ed248'),
    ('RIGHT', '55d380f7'),
    ('LEFT', '5432a6e1')
]

def main():
    print("=== Preparing Multi-Angle Verification Payload ===")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(LANDMARKER_MODEL)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    payload = []
    for angle, prefix in test_targets:
        match_rows = [r for r in data['rows'] if r['sha256'].startswith(prefix) or r.get('fileName', '').startswith(prefix)]
        assert match_rows, f"No row found for {prefix}"
        r = match_rows[0]
        img_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'])
        assert img_path.exists(), f"File missing: {img_path}"

        bgr = cv2.imread(str(img_path))
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        pts = (
            [{'x': float(p.x), 'y': float(p.y), 'z': float(p.z)} for p in det.face_landmarks[0]]
            if det.face_landmarks and len(det.face_landmarks[0]) >= 468
            else []
        )
        assert pts, f"Landmarks missing for {prefix}"
        rgb_b64 = base64.b64encode(rgb.tobytes()).decode('ascii')

        payload.append({
            'targetAngle': angle,
            'sha256': r['sha256'],
            'fileName': r.get('fileName', r['sha256'][:8]),
            'width': w,
            'height': h,
            'landmarks': pts,
            'rgbBase64': rgb_b64
        })

    print(f"Passing {len(payload)} test images to verify_product_angle_pipeline.cjs...")
    node_path = f"{LIVE_TEST / 'node_modules'};{LIVE_TEST / 'apps/vehicle-app/node_modules'};{ROOT / 'node_modules'};{ROOT / 'apps/vehicle-app/node_modules'}"
    env = os.environ.copy()
    env['NODE_PATH'] = node_path
    cmd = ['node', str(ROOT / 'scripts/skin-research/verify_product_angle_pipeline.cjs')]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(json.dumps(payload).encode('utf-8'))
    if p.returncode != 0:
        print("STDERR:\n", err.decode('utf-8'))
        raise RuntimeError("verify_product_angle_pipeline.cjs failed")
    print(out.decode('utf-8'))

if __name__ == '__main__':
    main()
