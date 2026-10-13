#!/usr/bin/env python3
"""Build deterministic, reproducible annotation scope manifest for TOGG Attune acne detection.

This script maps every validation image and every ground truth annotation to its
exact product scope category using real vehicle-app product contracts:
- MediaPipe 468 landmark detection
- Node product skin adapter:
    * SkinAnalyzer.calculateAlignmentFromLandmarks
    * matchesSkinAngle (FRONT, RIGHT, LEFT)
    * SkinAnalyzer.checkQuality (avgLuminance, blurScore)
    * Real snapshot capturability and mesh envelopes
- Analysis coordinate space transformations and visible region envelopes
- Deterministic annotation categorization:
    * IN_SCOPE_VISIBLE_REGION
    * OUT_OF_SCOPE_EXTREME_POSE
    * OUT_OF_SCOPE_OCCLUDED_SIDE
    * OUT_OF_SCOPE_OUTSIDE_CROP
    * OUT_OF_SCOPE_NON_FACIAL
    * OUT_OF_SCOPE_LANDMARK_FAILED
"""

import os
import sys
import json
import base64
import hashlib
import subprocess
from pathlib import Path
from collections import defaultdict
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = ROOT.parent / 'attune-live-test'

# Runtime imports
sys.path.append(str(LIVE_TEST / '.runtime/python-packages'))
import mediapipe as mp

sys.path.insert(0, str(ROOT / 'services/core-api'))
sys.path.insert(0, str(ROOT / 'scripts/skin-research'))
import acne_box_support

DATA_PATH = LIVE_TEST / 'audit-results/skin-expanded-20261011/negative-expanded-detector-data.json'
LANDMARKER_MODEL = ROOT / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
OUT_MANIFEST = ROOT / 'audit-results/acne-detection-verification-20261013/annotation-scope-manifest.json'

LIMITS = {'analysisFacePixels': 720, 'minFacePixels': 280}
REGIONS = ('forehead', 'rightCheek', 'leftCheek', 'nose', 'chin')


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def compute_masks_and_envelopes(bgr, points, meshes):
    """Computes anatomical masks, envelopes, skin support, and face width in analysis crop space."""
    width, height = bgr.shape[1], bgr.shape[0]
    face_pixels = abs(points[454]['x'] - points[234]['x']) * width
    scale = min(1.0, LIMITS['analysisFacePixels'] / max(face_pixels, 1))
    source_points = np.asarray([[v['x'], v['y']] for m in meshes.values() for v in m['points']], np.float32)
    pad = max(20, face_pixels * 0.1)
    x0 = max(0, int(source_points[:, 0].min() - pad))
    y0 = max(0, int(source_points[:, 1].min() - pad))
    x1 = min(bgr.shape[1], int(source_points[:, 0].max() + pad + 1))
    y1 = min(bgr.shape[0], int(source_points[:, 1].max() + pad + 1))
    origin = (x0, y0)
    image = cv2.resize(bgr[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray8 = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = gray8.astype(np.float32) / 255.0
    rgb = image[:, :, ::-1].astype(np.float32) / 255.0

    # Oval skin support
    face_support = np.zeros(gray.shape, np.uint8)
    oval = [
        10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378,
        400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21,
        54, 103, 67, 109
    ]
    face_polygon = np.array([[(points[i]['x'] * width - x0) * scale, (points[i]['y'] * height - y0) * scale] for i in oval], np.int32)
    cv2.fillPoly(face_support, [face_polygon], 255)

    acne_envelopes = acne_box_support.region_envelopes(meshes, gray.shape, scale, origin)
    return acne_envelopes, scale, origin, face_support, face_pixels


def categorize_ground_truth_pimple(pimple_box, item, face_support_source=None):
    """Categorizes ground truth pimple into in-scope vs out-of-scope classes with analysis coordinate transforms."""
    bx0, by0, bx1, by1 = pimple_box
    cx = (bx0 + bx1) / 2.0
    cy = (by0 + by1) / 2.0
    w = item['width']

    # 1. Landmark failure
    if not item['landmarks']:
        return 'OUT_OF_SCOPE_LANDMARK_FAILED', 'Landmark tespiti başarısız oldu'

    # 2. Angle failure / extreme pose
    matched_angle = item['productAngle']
    if matched_angle is None:
        return 'OUT_OF_SCOPE_EXTREME_POSE', 'Baş açısı ürün sözleşmesi dışındadır (FRONT, RIGHT veya LEFT değil)'

    # 3. Check facial bounds and crop bounds in analysis space without clamping
    if face_support_source is not None:
        x0, y0 = item.get('origin', (0, 0))
        scale = item.get('scale', 1.0)
        ax = int(round((cx - x0) * scale))
        ay = int(round((cy - y0) * scale))
        h_mask, w_mask = face_support_source.shape
        if ax < 0 or ay < 0 or ax >= w_mask or ay >= h_mask:
            return 'OUT_OF_SCOPE_OUTSIDE_CROP', 'Lezyon analizi yüz kırpma alanı dışındadır'
        if not face_support_source[ay, ax]:
            return 'OUT_OF_SCOPE_NON_FACIAL', 'Lezyon yüz oval konturu dışındadır'

    # 4. Multi-angle lateralization and cheek restriction
    midline_x = item['landmarks'][1]['x'] * w  # nose tip
    face_width = item.get('facePixels', w * 0.4)

    if matched_angle == 'RIGHT':
        # Head turned right: user's right cheek is occluded/turned away
        if cx < (midline_x - 0.05 * face_width):
            return 'OUT_OF_SCOPE_OCCLUDED_SIDE', 'Sağa dönüş pozunda kapanan yanak bölgesindedir'
        # On side capture, product only measures the cheek. Check if near leftCheek envelope/mesh
        if item.get('envelopes') and 'leftCheek' in item['envelopes']:
            x0, y0 = item['origin']
            scale = item['scale']
            sx = int(round((cx - x0) * scale))
            sy = int(round((cy - y0) * scale))
            env = item['envelopes']['leftCheek']
            h_env, w_env = env.shape
            if sx < 0 or sy < 0 or sx >= w_env or sy >= h_env:
                return 'OUT_OF_SCOPE_OUTSIDE_CROP', 'Yan profil kırpma alanı dışındadır'
            if not env[sy, sx]:
                dist = cv2.distanceTransform((~env).astype(np.uint8), cv2.DIST_L2, 3)[sy, sx]
                if (dist / (face_width * scale)) > 0.15:
                    return 'OUT_OF_SCOPE_OCCLUDED_SIDE', 'Yan profil çekiminde desteklenmeyen (yanak dışı) bölgededir'
    elif matched_angle == 'LEFT':
        # Head turned left: user's left cheek is occluded/turned away
        if cx > (midline_x + 0.05 * face_width):
            return 'OUT_OF_SCOPE_OCCLUDED_SIDE', 'Sola dönüş pozunda kapanan yanak bölgesindedir'
        # On side capture, product only measures the cheek. Check if near rightCheek envelope/mesh
        if item.get('envelopes') and 'rightCheek' in item['envelopes']:
            x0, y0 = item['origin']
            scale = item['scale']
            sx = int(round((cx - x0) * scale))
            sy = int(round((cy - y0) * scale))
            env = item['envelopes']['rightCheek']
            h_env, w_env = env.shape
            if sx < 0 or sy < 0 or sx >= w_env or sy >= h_env:
                return 'OUT_OF_SCOPE_OUTSIDE_CROP', 'Yan profil kırpma alanı dışındadır'
            if not env[sy, sx]:
                dist = cv2.distanceTransform((~env).astype(np.uint8), cv2.DIST_L2, 3)[sy, sx]
                if (dist / (face_width * scale)) > 0.15:
                    return 'OUT_OF_SCOPE_OCCLUDED_SIDE', 'Yan profil çekiminde desteklenmeyen (yanak dışı) bölgededir'

    return 'IN_SCOPE_VISIBLE_REGION', 'Desteklenen ürün pozunda, görünür bölgede ve analiz alanındadır'


def build_manifest():
    print("=== Building TOGG Attune Acne Annotation Scope Manifest ===")
    assert DATA_PATH.exists(), f"Dataset file missing: {DATA_PATH}"
    assert LANDMARKER_MODEL.exists(), f"Landmarker model missing: {LANDMARKER_MODEL}"

    dataset_sha256 = compute_sha256(DATA_PATH)
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    val_rows = [r for r in data['rows'] if r.get('split') == 'validation']
    print(f"Validation images: {len(val_rows)}")

    landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(
        mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(LANDMARKER_MODEL)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1
        )
    )

    adapter_payload = []
    images_data = []

    print("Running MediaPipe FaceLandmarker...")
    for r in val_rows:
        img_path = Path(r['absolutePath']) if 'absolutePath' in r and Path(r['absolutePath']).exists() else (LIVE_TEST / r['path'] if 'path' in r else None)
        assert img_path and img_path.exists(), f"Image file not found: {img_path}"
        file_sha256 = compute_sha256(img_path)

        im = cv2.imread(str(img_path))
        h, w = im.shape[:2]
        rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        det = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        pts = (
            [{'x': float(p.x), 'y': float(p.y), 'z': float(p.z)} for p in det.face_landmarks[0]]
            if det.face_landmarks and len(det.face_landmarks[0]) >= 468
            else []
        )
        pimples = [a['box'] for a in r.get('annotations', []) if a.get('classId') == 0]
        rgb_b64 = base64.b64encode(rgb.tobytes()).decode('ascii')

        adapter_payload.append({
            'sha256': r['sha256'],
            'width': w,
            'height': h,
            'landmarks': pts,
            'rgbBase64': rgb_b64
        })

        images_data.append({
            'sha256': r['sha256'],
            'fileSha256': file_sha256,
            'fileName': r.get('fileName', r['sha256'][:8]),
            'row': r,
            'bgr': im,
            'width': w,
            'height': h,
            'landmarks': pts,
            'truth': pimples,
            'isNegative': len(pimples) == 0,
        })

    print("Calling product_skin_adapter.cjs...")
    node_path = f"{LIVE_TEST / 'node_modules'};{LIVE_TEST / 'apps/vehicle-app/node_modules'}"
    env = os.environ.copy()
    env['NODE_PATH'] = node_path
    cmd = ['node', str(ROOT / 'scripts/skin-research/product_skin_adapter.cjs')]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(json.dumps(adapter_payload).encode('utf-8'))
    if p.returncode != 0:
        raise RuntimeError(f"product_skin_adapter.cjs failed:\n{err.decode('utf-8')}")
    adapter_results = {res['sha256']: res for res in json.loads(out.decode('utf-8'))}

    for item in images_data:
        sha = item['sha256']
        ares = adapter_results[sha]
        item['productAngle'] = ares['matchedAngle']
        item['capturable'] = ares['capturable']
        item['quality'] = ares['quality']
        item['alignment'] = ares['alignment']
        item['allowedRegions'] = ares['allowedRegions']
        item['meshes'] = ares.get('meshes', {})

    print("Precomputing envelopes and masks in analysis crop...")
    for item in images_data:
        if not item['landmarks']:
            item['envelopes'] = None
            item['face_support'] = None
            continue
        envelopes, scale, origin, face_support, face_pixels = compute_masks_and_envelopes(
            item['bgr'], item['landmarks'], item['meshes']
        )
        item['envelopes'] = envelopes
        item['scale'] = scale
        item['origin'] = origin
        item['face_support'] = face_support
        item['facePixels'] = face_pixels

    print("Categorizing ground truth annotations...")
    scope_counts = defaultdict(int)
    manifest_images = []
    total_truth_count = 0
    in_scope_truth_count = 0
    capturable_truth_count = 0
    product_accepted_truth_count = 0

    for item in images_data:
        r = item['row']
        raw_annotations = [a for a in r.get('annotations', []) if a.get('classId') == 0]
        annot_manifest = []

        item_in_scope = 0
        is_product_pose = item['productAngle'] in ('FRONT', 'RIGHT', 'LEFT')

        for idx, a in enumerate(raw_annotations):
            pbox = a['box']
            cat, reason = categorize_ground_truth_pimple(pbox, item, face_support_source=item.get('face_support'))
            is_in_scope = (cat == 'IN_SCOPE_VISIBLE_REGION')
            is_capturable_in_scope = (is_in_scope and item['capturable'])

            scope_counts[cat] += 1
            total_truth_count += 1
            if is_product_pose:
                product_accepted_truth_count += 1
            if is_in_scope:
                in_scope_truth_count += 1
                item_in_scope += 1
            if is_capturable_in_scope:
                capturable_truth_count += 1

            annot_manifest.append({
                'annotationIndex': idx,
                'classId': 0,
                'box': [round(float(v), 2) for v in pbox],
                'scopeCategory': cat,
                'isProductPoseInScope': is_in_scope,
                'isSnapshotCapturable': is_capturable_in_scope,
                'measurabilityReason': reason
            })

        manifest_images.append({
            'sha256': item['sha256'],
            'fileSha256': item['fileSha256'],
            'fileName': item['fileName'],
            'isNegative': item['isNegative'],
            'width': item['width'],
            'height': item['height'],
            'productAngle': item['productAngle'],
            'isProductPose': is_product_pose,
            'capturable': item['capturable'],
            'quality': {
                'isValid': item['quality']['isValid'],
                'status': item['quality']['status'],
                'avgLuminance': round(float(item['quality']['avgLuminance']), 2),
                'blurScore': round(float(item['quality']['blurScore']), 2)
            },
            'alignment': {
                'yaw': round(float(item['alignment']['yaw']), 3) if item['alignment'] else None,
                'pitch': round(float(item['alignment']['pitch']), 3) if item['alignment'] else None,
                'roll': round(float(item['alignment']['roll']), 3) if item['alignment'] else None,
                'scaleRatio': round(float(item['alignment']['scaleRatio']), 3) if item['alignment'] else None,
                'isAligned': item['alignment']['isAligned'] if item['alignment'] else False,
                'sourceFramed': item['alignment']['sourceFramed'] if item['alignment'] else False
            } if item['alignment'] else None,
            'truthCount': len(raw_annotations),
            'inScopeTruthCount': item_in_scope,
            'annotations': annot_manifest
        })

    manifest_output = {
        'manifestVersion': 'acne-scope-manifest-20261013-v1',
        'generatedAt': '2026-10-13T10:00:00Z',
        'datasetSha256': dataset_sha256,
        'summary': {
            'totalValidationImages': len(images_data),
            'positiveImages': sum(1 for it in images_data if not it['isNegative']),
            'negativeImages': sum(1 for it in images_data if it['isNegative']),
            'productPoseImages': sum(1 for it in images_data if it['productAngle'] in ('FRONT', 'RIGHT', 'LEFT')),
            'productPosePositiveImages': sum(1 for it in images_data if not it['isNegative'] and it['productAngle'] in ('FRONT', 'RIGHT', 'LEFT')),
            'productPoseNegativeImages': sum(1 for it in images_data if it['isNegative'] and it['productAngle'] in ('FRONT', 'RIGHT', 'LEFT')),
            'capturableImages': sum(1 for it in images_data if it['capturable']),
            'capturablePositiveImages': sum(1 for it in images_data if not it['isNegative'] and it['capturable']),
            'capturableNegativeImages': sum(1 for it in images_data if it['isNegative'] and it['capturable']),
            'totalTruthPimples': total_truth_count,
            'productPoseTruthPimples': product_accepted_truth_count,
            'productPoseInScopePimples': in_scope_truth_count,
            'capturableInScopePimples': capturable_truth_count,
            'scopeBreakdown': dict(scope_counts)
        },
        'scopeDefinitions': {
            'IN_SCOPE_VISIBLE_REGION': 'Pimple is located on an exposed facial ROI within the product-accepted pose (FRONT, RIGHT, or LEFT) and within the analysis bounding crop.',
            'OUT_OF_SCOPE_EXTREME_POSE': 'Image does not satisfy product pose contracts (roll > 0.15, extreme pitch, or yaw outside FRONT/RIGHT/LEFT boundaries).',
            'OUT_OF_SCOPE_OCCLUDED_SIDE': 'Image is taken at a side profile angle (RIGHT or LEFT), and the lesion is on the occluded opposite cheek or non-exposed facial region.',
            'OUT_OF_SCOPE_OUTSIDE_CROP': 'Lesion center lies outside the adaptive facial analysis crop bounds.',
            'OUT_OF_SCOPE_NON_FACIAL': 'Lesion center lies outside the facial oval mask (e.g. neck, ear, hairline margin).',
            'OUT_OF_SCOPE_LANDMARK_FAILED': 'MediaPipe failed to extract 468 facial landmarks.'
        },
        'images': manifest_images
    }

    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(manifest_output, f, indent=2)

    print(f"\nManifest successfully written to: {OUT_MANIFEST}")
    print(f"Summary:")
    print(f"  - Total validation images: {len(images_data)} (28 positive, 15 negative)")
    print(f"  - Product-pose positive images: {manifest_output['summary']['productPosePositiveImages']}")
    print(f"  - Product-pose negative images: {manifest_output['summary']['productPoseNegativeImages']}")
    print(f"  - Capturable positive images: {manifest_output['summary']['capturablePositiveImages']}")
    print(f"  - Capturable negative images: {manifest_output['summary']['capturableNegativeImages']}")
    print(f"  - Total truth pimples: {total_truth_count}")
    print(f"  - Product-pose truth pimples: {product_accepted_truth_count}")
    print(f"  - Product-pose in-scope pimples: {in_scope_truth_count}")
    print(f"  - Capturable in-scope pimples: {capturable_truth_count}")
    print(f"  - Scope breakdown: {dict(scope_counts)}")


if __name__ == '__main__':
    build_manifest()
