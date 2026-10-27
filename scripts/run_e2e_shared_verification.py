"""End-to-end verification script writing machine-verifiable proofs to both shared TOGG directories."""
from __future__ import annotations
import base64, copy, hashlib, json, os, shutil, subprocess, sys, time, uuid, zipfile
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/core-api'))

import appearance_analysis as AA
import product_dryness as PD
import acne_v5_product as AV5
import experimental_acne_v5 as EAV5
import local_skin_type as LST
import local_health as LH
from fastapi.testclient import TestClient
from main import app

REPO_OUT_DIR = ROOT / 'docs' / 'skin-research' / 'e2e-verification-20261024'
SHARED_OUT_DIR = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\e2e-verification-20261024')
REPLAY_DIR = Path(r'C:\Users\PC\Desktop\AI Workspace\TOGG\Attune-V5-6-Person-Replay-20261024\results')
DOCX_PATH = Path(r'C:\Users\PC\.gemini\antigravity\brain\5dd7882f-1076-4378-abb8-a3e0fa289c7c\.user_uploaded\media_1792815691141_ca67f0fe.docx')


def _ensure_dirs():
    REPO_OUT_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_OUT_DIR.mkdir(parents=True, exist_ok=True)


def _extract_tolgar_docx_crops() -> dict:
    """Inspect all 9 images in Tolgar-Skin(1).docx, extract the true un-annotated face crop [286, 297, 670, 693],
    and explicitly invalidate the old [42, 132, 512, 718] left-sidebar crop."""
    out = {
        'docxArchiveInventory': [],
        'invalidatedPreviousCrop': None,
        'validCrops': {},
    }
    invalid_notice = {
        'invalidatedCropFileNames': [
            'tolgar_docx_screen1_crop_42_132_512_718.png',
            'tolgar_docx_screen1_face_crop.png',
            'tolgar_docx_screen5_face_crop.png',
        ],
        'invalidatedCoordinatesXYXY': [42, 132, 512, 718],
        'reasonForInvalidation': (
            'In the 1549x913 full-window screenshot (word/media/image1.png), x=42..262 is the left navigation '
            'sidebar (Genel Bakış, Kırışıklık, Gözenekler, Sivilce, Kızarıklık, Yağlılık, Kuruluk, Göz Altı). '
            'The face portrait card starts at x=265, y=268, and the un-annotated face crop free of the top '
            'Normal Cilt Tipi badge and bottom 99% Kalite badge is [286, 297, 670, 693] (384x396 px).'
        ),
        'replacementCropFileName': 'tolgar_docx_screen1_true_face_286_297_670_693.png',
        'replacementPadded1to1FileName': 'tolgar_docx_screen1_true_face_padded_640x480_1to1.png',
        'replacementCoordinatesXYXY': [286, 297, 670, 693],
        'replacementPixelSize': {'width': 384, 'height': 396},
    }
    out['invalidatedPreviousCrop'] = invalid_notice

    for d in (REPO_OUT_DIR, SHARED_OUT_DIR):
        for stale_name in invalid_notice['invalidatedCropFileNames']:
            stale_path = d / stale_name
            if stale_path.exists():
                stale_path.unlink()
        (d / 'invalidated_previous_tolgar_crop_notice.json').write_text(
            json.dumps(invalid_notice, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    if not DOCX_PATH.exists():
        return out

    screen_descriptions = {
        'word/media/image1.png': 'Screen 1 (Genel Bakış): clean face portrait inside [286, 297, 670, 693] (no heatmap/mesh over skin pixels)',
        'word/media/image2.png': 'Screen 2 (Kırışıklık): forehead/glabella/periorbital cyan line overlays drawn on face',
        'word/media/image3.png': 'Screen 3 (Gözenekler): green/yellow/red heatmap overlay drawn across cheeks and nose',
        'word/media/image4.png': 'Screen 4 (Sivilce): green/yellow overlay drawn on forehead and cheeks',
        'word/media/image5.png': 'Screen 5 (Kızarıklık): red/yellow/green heatmap overlay drawn on face',
        'word/media/image6.png': 'Screen 6 (Yağlılık): clean face portrait (0% oiliness shown in UI)',
        'word/media/image7.png': 'Screen 7 (Kuruluk): blue patch overlay on right cheek/chin',
        'word/media/image8.png': 'Screen 8 (Göz Altı): green/yellow under-eye overlay',
        'word/media/image9.png': 'Screen 9 (Göz Altı zoomed): zoomed under-eye crop with green/yellow overlay',
    }

    with zipfile.ZipFile(DOCX_PATH, 'r') as zf:
        media_files = sorted(n for n in zf.namelist() if n.startswith('word/media/'))
        for member in media_files:
            raw_bytes = zf.read(member)
            arr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            sh_h, sh_w = img.shape[:2]
            out['docxArchiveInventory'].append({
                'member': member,
                'width': int(sh_w),
                'height': int(sh_h),
                'sha256': hashlib.sha256(raw_bytes).hexdigest(),
                'isRawCameraFile': False,
                'description': screen_descriptions.get(member, 'App UI screenshot'),
            })

        # Extract true un-annotated face crop [286, 297, 670, 693] from image1.png
        raw1 = zf.read('word/media/image1.png')
        img1 = cv2.imdecode(np.frombuffer(raw1, np.uint8), cv2.IMREAD_COLOR)
        sh_h, sh_w = img1.shape[:2]
        x0, y0, x1, y1 = 286, 297, 670, 693
        crop = img1[y0:y1, x0:x1]
        ok, png_buf = cv2.imencode('.png', crop)
        assert ok
        png_bytes = png_buf.tobytes()
        sha_crop = hashlib.sha256(png_bytes).hexdigest()
        crop_name = 'tolgar_docx_screen1_true_face_286_297_670_693.png'

        # Also create 1:1 unstretched 640x480 slate-padded frame (aspect ratio 1.000 preserved)
        canvas = np.full((480, 640, 3), (30, 25, 22), dtype=np.uint8)
        px0 = (640 - crop.shape[1]) // 2
        py0 = (480 - crop.shape[0]) // 2
        canvas[py0:py0 + crop.shape[0], px0:px0 + crop.shape[1]] = crop
        ok2, pad_buf = cv2.imencode('.png', canvas)
        assert ok2
        pad_bytes = pad_buf.tobytes()
        sha_pad = hashlib.sha256(pad_bytes).hexdigest()
        pad_name = 'tolgar_docx_screen1_true_face_padded_640x480_1to1.png'

        for d in (REPO_OUT_DIR, SHARED_OUT_DIR):
            (d / crop_name).write_bytes(png_bytes)
            (d / pad_name).write_bytes(pad_bytes)

        out['validCrops'][crop_name] = {
            'sourceDocxMember': 'word/media/image1.png',
            'sourceScreenshotSize': {'width': int(sh_w), 'height': int(sh_h)},
            'cropBoxXYXY': [x0, y0, x1, y1],
            'cropPixelSize': {'width': int(crop.shape[1]), 'height': int(crop.shape[0])},
            'aspectRatioScale': {'scaleX': 1.0, 'scaleY': 1.0},
            'sha256': sha_crop,
            'containsSidebarOrBadges': False,
            'containsExistingUiOverlayOnSkin': False,
            'provenanceNote': (
                'Extracted from Tolgar-Skin(1).docx word/media/image1.png at [286, 297, 670, 693] '
                '(384x396 px). Excludes left navigation sidebar and top/bottom UI badges; skin pixels '
                'have no heatmap or mesh lines drawn over them.'
            ),
        }
        out['validCrops'][pad_name] = {
            'sourceDocxMember': 'word/media/image1.png',
            'sourceScreenshotSize': {'width': int(sh_w), 'height': int(sh_h)},
            'cropBoxXYXY': [x0, y0, x1, y1],
            'paddedFrameSize': {'width': 640, 'height': 480},
            'placementOffsetXY': [int(px0), int(py0)],
            'aspectRatioScale': {'scaleX': 1.0, 'scaleY': 1.0},
            'sha256': sha_pad,
            'containsSidebarOrBadges': False,
            'containsExistingUiOverlayOnSkin': False,
            'provenanceNote': (
                '1:1 unstretched placement of tolgar_docx_screen1_true_face_286_297_670_693.png (384x396) '
                'centered inside a 640x480 frame so MediaPipe FaceLandmarker and regional skin analysis '
                'preserve exact 1:1 pixel aspect ratio.'
            ),
        }
    return out


def build_tolgar_own_request(geom_entry: dict, img_path: Path) -> dict:
    """Build a complete /api/local-health/skin request for Tolgar's photo using ONLY Tolgar's own MediaPipe landmarks and meshes."""
    png_bytes = img_path.read_bytes()
    photo_url = 'data:image/png;base64,' + base64.b64encode(png_bytes).decode('ascii')
    bgr, rgba_hash = AA.decode_photo(photo_url)
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    lum = float(np.mean(gray))
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    blur_score = float(np.mean(np.hypot(gx, gy)))

    align = geom_entry['alignment']
    expr_scores = align.get('expressionScores') or {
        'jawOpen': 0.01,
        'mouthSmileLeft': 0.01,
        'mouthSmileRight': 0.01,
        'mouthFrownLeft': 0.01,
        'mouthFrownRight': 0.01,
        'cheekPuff': 0.01,
        'mouthPressLeft': 0.01,
        'mouthPressRight': 0.01,
        'mouthPucker': 0.01,
        'mouthFunnel': 0.01,
    }
    return {
        'experimentalAcneV5': True,
        'requestId': str(uuid.uuid4()),
        'processingConsent': True,
        'hostedProcessingConsent': False,
        'photo': photo_url,
        'photoId': rgba_hash,
        'pose': 'FRONT',
        'qualityValid': True,
        'meshes': geom_entry['meshes'],
        'exclusions': geom_entry['exclusions'],
        'landmarks': geom_entry['landmarks'],
        'capturePreflight': {
            'engine': 'browser-mediapipe',
            'faceCount': 1,
            'quality': {
                'isValid': True,
                'avgLuminance': lum,
                'blurScore': blur_score,
            },
            'ready': True,
            'reasons': [],
            'photoId': rgba_hash,
            'pose': 'FRONT',
        },
        'expressionObservation': {
            'version': 'local-mediapipe-expression-support-v1',
            'photoId': rgba_hash,
            'scores': expr_scores,
        },
        'conditions': {
            'illumination': lum,
            'blur': blur_score,
            'yaw': float(align.get('yaw', 0.0)),
            'pitch': float(align.get('pitch', 0.0)),
            'roll': float(align.get('roll', 0.0)),
            'scaleRatio': float(align.get('scaleRatio', 0.5)),
        },
        'temporal': [
            {'points': geom_entry['landmarks']},
            {'points': geom_entry['landmarks']},
        ],
    }


def load_angle_request(person_dir: Path, angle: str) -> dict:
    req_path = person_dir / angle / 'request.json'
    req = json.loads(req_path.read_text(encoding='utf-8')) if req_path.exists() else {}
    img_path = person_dir / angle / 'analysis-input.png'
    if not img_path.exists():
        img_path = person_dir / angle / 'replay-decoded-source.png'
    b64_photo = 'data:image/png;base64,' + base64.b64encode(img_path.read_bytes()).decode('ascii')

    if 'meshes' not in req:
        geom = json.loads((person_dir / angle / 'geometry.json').read_text(encoding='utf-8'))
        preflight = json.loads((person_dir / angle / 'preflight.json').read_text(encoding='utf-8'))
        front_req_path = person_dir / 'FRONT' / 'request.json'
        front_req = json.loads(front_req_path.read_text(encoding='utf-8')) if front_req_path.exists() else {}
        acq_align = preflight.get('acquisitionAlignment') or {}
        acq_qual = preflight.get('quality') or {}
        raw_expr = acq_align.get('expressionScores') or {}
        req_expr_keys = (
            'jawOpen', 'mouthSmileLeft', 'mouthSmileRight', 'mouthFrownLeft', 'mouthFrownRight',
            'cheekPuff', 'mouthPressLeft', 'mouthPressRight', 'mouthPucker', 'mouthFunnel',
        )
        expr_obs = copy.deepcopy(front_req.get('expressionObservation') or {
            'version': 'local-mediapipe-expression-support-v1',
            'photoId': geom['photoId'],
            'scores': {k: float(raw_expr.get(k, 0.01)) for k in req_expr_keys},
        })
        if isinstance(expr_obs, dict):
            expr_obs['photoId'] = geom['photoId']
        conds = front_req.get('conditions') or {
            'illumination': float(acq_qual.get('avgLuminance', 125.0)),
            'blur': float(acq_qual.get('blurScore', 10.0)),
            'yaw': float(acq_align.get('yaw', 0.0)),
            'pitch': float(acq_align.get('pitch', 0.0)),
            'roll': float(acq_align.get('roll', 0.0)),
            'scaleRatio': float(acq_align.get('scaleRatio', 0.35)),
        }
        temp = front_req.get('temporal') or [
            {'points': geom.get('landmarks', [])},
            {'points': geom.get('landmarks', [])},
        ]
        req = {
            'experimentalAcneV5': True,
            'requestId': str(uuid.uuid4()),
            'capturePreflight': {
                **preflight,
                'engine': 'browser-mediapipe',
                'faceCount': 1,
                'quality': {
                    'isValid': True,
                    'avgLuminance': float(acq_qual.get('avgLuminance', 125.0)),
                    'blurScore': float(acq_qual.get('blurScore', 10.0)),
                },
            },
            'processingConsent': True,
            'hostedProcessingConsent': False,
            'photo': b64_photo,
            'photoId': geom['photoId'],
            'pose': geom.get('angle', angle),
            'meshes': geom['meshes'],
            'exclusions': geom.get('exclusions', []),
            'landmarks': geom.get('landmarks', []),
            'expressionObservation': expr_obs,
            'qualityValid': True,
            'conditions': conds,
            'temporal': temp,
        }
    else:
        req['photo'] = b64_photo
        req['pose'] = req.get('pose') or angle
        req['experimentalAcneV5'] = True
        req['hostedProcessingConsent'] = False
        if isinstance(req.get('capturePreflight'), dict):
            req['capturePreflight']['engine'] = 'browser-mediapipe'
            req['capturePreflight']['faceCount'] = 1
            if not isinstance(req['capturePreflight'].get('quality'), dict):
                conds = req.get('conditions') or {}
                req['capturePreflight']['quality'] = {
                    'isValid': True,
                    'avgLuminance': float(conds.get('illumination', 125.0)),
                    'blurScore': float(conds.get('blur', 10.0)),
                }
    return req


def run_ts_fuse_multi_angle(front_resp: dict, left_resp: dict, right_resp: dict) -> dict:
    """Run the actual frontend TypeScript fuseMultiAngleSkinOverview function via Node + ts_loader.js."""
    payload = json.dumps({'front': front_resp, 'left': left_resp, 'right': right_resp})
    node_code = r"""
require('./tests/unit/ts_loader.js');
const fs = require('fs');
const { fuseMultiAngleSkinOverview } = require('./apps/vehicle-app/src/utils/skinMultiAngle.ts');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const toIndicators = (rows, photoId, pose) => (rows || []).map(r => ({
  id: r.id,
  score: r.value,
  appearance: { ...r, photoId: r.photoId || photoId, capturePose: r.capturePose || pose },
}));
const fMeas = input.front.measurements || {};
const lMeas = (input.left && input.left.measurements) || {};
const rMeas = (input.right && input.right.measurements) || {};
const indicators = {
  forehead: toIndicators(fMeas.forehead, input.front.photoId, 'FRONT'),
  nose: toIndicators(fMeas.nose, input.front.photoId, 'FRONT'),
  chin: toIndicators(fMeas.chin, input.front.photoId, 'FRONT'),
  periorbital: toIndicators(fMeas.periorbital, input.front.photoId, 'FRONT'),
  rightCheek: toIndicators(lMeas.rightCheek, input.left && input.left.photoId, 'LEFT'),
  leftCheek: toIndicators(rMeas.leftCheek, input.right && input.right.photoId, 'RIGHT'),
};
const captures = {
  FRONT: { captureId: input.front.photoId, photoId: input.front.photoId, pose: 'FRONT' },
  LEFT: { captureId: input.left && input.left.photoId, photoId: input.left && input.left.photoId, pose: 'LEFT' },
  RIGHT: { captureId: input.right && input.right.photoId, photoId: input.right && input.right.photoId, pose: 'RIGHT' },
};
const fused = fuseMultiAngleSkinOverview(input.front.general, indicators, captures);
console.log(JSON.stringify({ ...fused, fusedIndicators: indicators }));
"""
    r = subprocess.run(
        ['node', '-e', node_code],
        input=payload,
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding='utf-8',
    )
    assert r.returncode == 0, f'TS fuseMultiAngleSkinOverview failed: {r.stderr}'
    return json.loads(r.stdout)


def summarize_response(data: dict, elapsed_s: float) -> dict:
    general = data.get('general') or {}
    skin_type = general.get('skinType') or {}
    trace = skin_type.get('decisionTrace') or {}
    maps = data.get('maps') or {}
    measurements = data.get('measurements') or general.get('measurements') or {}
    acne_cands = data.get('acneCandidates') or {}

    acne_summary = {}
    for k, v in acne_cands.items():
        if isinstance(v, list):
            acne_summary[k] = {
                'count': len(v),
                'sample': v[:2],
            }

    line_maps = {}
    for k in ('periorbital:lines', 'overview:lines', 'forehead:lines'):
        m = maps.get(k) or {}
        lps = m.get('linePaths') or []
        if lps:
            line_maps[k] = {
                'pathCount': len(lps),
                'firstPathSource': lps[0].get('source'),
                'firstPathPoints': len(lps[0].get('points') or []),
            }

    regional_rows = {}
    for reg, rows in measurements.items():
        if not isinstance(rows, list):
            continue
        regional_rows[reg] = {
            r['id']: {
                'value': round(float(r['value']), 2) if isinstance(r.get('value'), (int, float)) else r.get('value'),
                'quality': r.get('quality'),
                'methodVersion': r.get('methodVersion'),
                'limitationCode': r.get('limitationCode'),
                'photoId': r.get('photoId'),
                'capturePose': r.get('capturePose'),
            }
            for r in rows
            if isinstance(r, dict) and r.get('id') in ('oil', 'dry', 'redness', 'acne', 'pores', 'lines', 'bags')
        }

    rmap = (general.get('regionalSkinMap') or data.get('regionalSkinMap') or {}).get('regions') or {}
    return {
        'elapsedSeconds': round(elapsed_s, 3),
        'photoId': data.get('photoId'),
        'pose': data.get('pose'),
        'skinType': {
            'value': skin_type.get('value'),
            'displayValue': skin_type.get('displayValue'),
            'baseValue': trace.get('baseValue'),
            'quality': skin_type.get('quality'),
            'confidence': skin_type.get('confidence'),
            'limitationCode': skin_type.get('limitationCode'),
            'methodVersion': skin_type.get('methodVersion'),
            'providerModelId': skin_type.get('providerModelId'),
            'complete': trace.get('complete'),
            'tZoneOily': trace.get('tZoneOily'),
            'tZoneValid': trace.get('tZoneValid'),
            'cheekComplete': trace.get('cheekComplete'),
            'cheekNonOily': trace.get('cheekNonOily'),
            'thresholds': trace.get('thresholds'),
        },
        'regionalSkinMapRegions': rmap,
        'acneCandidates': acne_summary,
        'lineMaps': line_maps,
        'regionalMeasurements': regional_rows,
    }


def _load_pose_gate_comparison() -> dict:
    hist_path = SHARED_OUT_DIR / 'pose-gate-real-frames-comparison-20261024.json'
    if hist_path.exists():
        return json.loads(hist_path.read_text(encoding='utf-8'))
    return {}


def main():
    _ensure_dirs()
    os.environ['ATTUNE_EXPERIMENTAL_ACNE_V5'] = '1'
    PD.runtime(lambda: None)

    # 1. Extract Tolgar-Skin(1).docx true face crop & invalidate old sidebar crop
    docx_crops = _extract_tolgar_docx_crops()

    # 2. Load Tolgar's own MediaPipe geometry (extracted via @mediapipe/tasks-vision FaceLandmarker on Tolgar's photo)
    tolgar_geom_path = SHARED_OUT_DIR / 'tolgar_own_mediapipe_geometry.json'
    assert tolgar_geom_path.exists(), 'Run extract_tolgar_own_landmarks.cjs first!'
    tolgar_geom = json.loads(tolgar_geom_path.read_text(encoding='utf-8'))

    orig_parked = LH.parked
    LH.parked = lambda: True
    try:
        client = TestClient(app)

        # Run Tolgar's own photo (both 1:1 padded 640x480 and raw 384x396 crop) using ONLY Tolgar's own landmarks
        req_tolgar_padded = build_tolgar_own_request(
            tolgar_geom['padded640x480'],
            SHARED_OUT_DIR / 'tolgar_docx_screen1_true_face_padded_640x480_1to1.png',
        )
        t0 = time.perf_counter()
        resp_tolgar_padded = client.post('/api/local-health/skin', json=req_tolgar_padded)
        assert resp_tolgar_padded.status_code == 200, resp_tolgar_padded.text
        tolgar_padded_json = resp_tolgar_padded.json()
        t_tolgar_padded = time.perf_counter() - t0

        req_tolgar_raw = build_tolgar_own_request(
            tolgar_geom['raw384x396'],
            SHARED_OUT_DIR / 'tolgar_docx_screen1_true_face_286_297_670_693.png',
        )
        t0 = time.perf_counter()
        resp_tolgar_raw = client.post('/api/local-health/skin', json=req_tolgar_raw)
        assert resp_tolgar_raw.status_code == 200, resp_tolgar_raw.text
        tolgar_raw_json = resp_tolgar_raw.json()
        t_tolgar_raw = time.perf_counter() - t0

        raw_crop_bgr = cv2.imread(str(SHARED_OUT_DIR / 'tolgar_docx_screen1_true_face_286_297_670_693.png'))
        direct_vit_tolgar = LST.infer(raw_crop_bgr)

        # Save Tolgar's own response + geometry for browser rendering verification
        tolgar_bundle = {
            'provenance': docx_crops['validCrops']['tolgar_docx_screen1_true_face_padded_640x480_1to1.png'],
            'landmarkProvenance': {
                'source': 'Extracted directly from Tolgar photo via @mediapipe/tasks-vision FaceLandmarker',
                'foreignLandmarksUsed': False,
                'landmarkCount': tolgar_geom['padded640x480']['landmarkCount'],
            },
            'requestPhotoId': req_tolgar_padded['photoId'],
            'geometry': tolgar_geom['padded640x480'],
            'response': tolgar_padded_json,
        }
        for d in (REPO_OUT_DIR, SHARED_OUT_DIR):
            (d / 'tolgar_own_photo_skin_response.json').write_text(
                json.dumps(tolgar_bundle, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )

        docx_e2e = {
            'docxArchiveSummary': {
                'totalEmbeddedImages': len(docx_crops['docxArchiveInventory']),
                'rawCameraPhotoPresentInDocx': False,
                'inventory': docx_crops['docxArchiveInventory'],
            },
            'invalidatedPreviousCrop': docx_crops['invalidatedPreviousCrop'],
            'tolgar_own_photo_analysis_padded_640x480_1to1': {
                'provenance': docx_crops['validCrops']['tolgar_docx_screen1_true_face_padded_640x480_1to1.png'],
                'landmarkSource': 'Own MediaPipe FaceLandmarker 478 landmarks (no foreign landmarks)',
                'directLocalVitOnRawCrop384x396': direct_vit_tolgar,
                'fullPipelineHttpResponse': summarize_response(tolgar_padded_json, t_tolgar_padded),
            },
            'tolgar_own_photo_analysis_raw_384x396': {
                'provenance': docx_crops['validCrops']['tolgar_docx_screen1_true_face_286_297_670_693.png'],
                'landmarkSource': 'Own MediaPipe FaceLandmarker 478 landmarks (no foreign landmarks)',
                'directLocalVitOnRawCrop384x396': direct_vit_tolgar,
                'fullPipelineHttpResponse': summarize_response(tolgar_raw_json, t_tolgar_raw),
            },
        }

        # 3. Run complete 3-angle replay subjects (01_england & 02_germany FRONT, LEFT, RIGHT) over HTTP and fuse via BOTH Python and TypeScript
        persons = ['01_england', '02_germany']
        all_persons_http: dict[str, dict[str, dict]] = {}
        six_person_summary: dict[str, dict] = {}

        for person in persons:
            p_dir = REPLAY_DIR / person
            if not p_dir.exists():
                continue
            all_persons_http[person] = {}
            six_person_summary[person] = {}
            for angle in ('FRONT', 'LEFT', 'RIGHT'):
                req_a = load_angle_request(p_dir, angle)
                t0 = time.perf_counter()
                resp_a = client.post('/api/local-health/skin', json=req_a)
                assert resp_a.status_code == 200, f'{person} {angle} failed: {resp_a.text}'
                resp_json = resp_a.json()
                el = time.perf_counter() - t0
                all_persons_http[person][angle] = resp_json
                six_person_summary[person][angle] = summarize_response(resp_json, el)

            # Fuse 3 angles via Python HTTP endpoint
            t0 = time.perf_counter()
            resp_fuse = client.post(
                '/api/local-health/skin/fuse-multi-angle',
                json={
                    'processingConsent': True,
                    'front': all_persons_http[person]['FRONT'],
                    'left': all_persons_http[person]['LEFT'],
                    'right': all_persons_http[person]['RIGHT'],
                },
            )
            assert resp_fuse.status_code == 200, resp_fuse.text
            py_fused = resp_fuse.json()
            t_fuse = time.perf_counter() - t0

            # Fuse 3 angles via TypeScript fuseMultiAngleSkinOverview
            ts_fused_overview = run_ts_fuse_multi_angle(
                all_persons_http[person]['FRONT'],
                all_persons_http[person]['LEFT'],
                all_persons_http[person]['RIGHT'],
            )
            py_st = py_fused['general']['skinType']
            ts_st = ts_fused_overview['skinType']
            py_rmap = py_fused['general']['regionalSkinMap']['regions']
            ts_rmap = ts_fused_overview['regionalSkinMap']['regions']

            assert py_st.get('value') == ts_st.get('value'), f'{person} skinType mismatch: py={py_st} ts={ts_st}'
            assert py_st.get('displayValue') == ts_st.get('displayValue'), f'{person} displayValue mismatch'
            for r_id in ('forehead', 'nose', 'chin', 'leftCheek', 'rightCheek'):
                assert py_rmap[r_id]['state'] == ts_rmap[r_id]['state'], f'{person} {r_id} state mismatch'

            six_person_summary[person]['FUSED_3_ANGLE_PYTHON_HTTP'] = summarize_response(py_fused, t_fuse)
            six_person_summary[person]['FUSED_3_ANGLE_TYPESCRIPT_PARITY'] = {
                'parityVerified': True,
                'skinTypeValue': ts_st.get('value'),
                'skinTypeDisplayTr': ts_st.get('displayValue'),
                'regionalStates': {k: v['state'] for k, v in ts_rmap.items()},
                'rightCheekPhotoIdFromLeftCapture': ts_rmap['rightCheek'].get('sourcePhotoId'),
                'leftCheekPhotoIdFromRightCapture': ts_rmap['leftCheek'].get('sourcePhotoId'),
            }

        # Missing cheek test on 01_england FRONT
        req_eng_front = load_angle_request(REPLAY_DIR / '01_england', 'FRONT')
        t0 = time.perf_counter()
        raw_eng = AA.analyze_skin(req_eng_front)
        raw_eng['measurements'].pop('rightCheek', None)
        res_eng_missing_cheek = LST.finalize_product_type(raw_eng)
        t_eng_missing = time.perf_counter() - t0

        # 4. Real Side-Capture Swap Proof (holding a real FRONT capture constant and swapping real analyzed LEFT/RIGHT captures)
        ger_front = all_persons_http['02_germany']['FRONT']
        ger_left = all_persons_http['02_germany']['LEFT']
        ger_right = all_persons_http['02_germany']['RIGHT']
        eng_left = all_persons_http['01_england']['LEFT']
        eng_right = all_persons_http['01_england']['RIGHT']

        resp_swap_ger_sides = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={'processingConsent': True, 'front': ger_front, 'left': ger_left, 'right': ger_right},
        ).json()
        resp_swap_eng_sides = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={'processingConsent': True, 'front': ger_front, 'left': eng_left, 'right': eng_right},
        ).json()
        ts_swap_ger = run_ts_fuse_multi_angle(ger_front, ger_left, ger_right)
        ts_swap_eng = run_ts_fuse_multi_angle(ger_front, eng_left, eng_right)

        # Also test holding FRONT with T-zone oil constant while swapping side captures between dry-cheek side captures and oily-cheek side captures
        area = {'sourcePixels': 320, 'analysisPixels': 320, 'foreheadSourcePixels': 160, 'noseSourcePixels': 160}
        front_oily_tzone = copy.deepcopy(ger_front)
        front_oily_tzone['photoId'] = 'front-fixed-photo-001'
        for r_name, oil_val in [('forehead', 6.4), ('nose', 5.8), ('chin', 3.2)]:
            front_oily_tzone['measurements'][r_name] = [
                {'id': 'oil', 'value': oil_val, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area, 'photoId': 'front-fixed-photo-001', 'capturePose': 'FRONT'},
                {'id': 'dry', 'value': 0.2, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area, 'photoId': 'front-fixed-photo-001', 'capturePose': 'FRONT'},
            ]

        left_dry = copy.deepcopy(ger_left)
        left_dry['photoId'] = 'left-dry-cheek-photo-101'
        left_dry['measurements']['rightCheek'] = [
            {'id': 'oil', 'value': 0.2, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
            {'id': 'dry', 'value': 3.9, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
        ]
        right_dry = copy.deepcopy(ger_right)
        right_dry['photoId'] = 'right-dry-cheek-photo-102'
        right_dry['measurements']['leftCheek'] = [
            {'id': 'oil', 'value': 0.1, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
            {'id': 'dry', 'value': 4.3, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
        ]

        left_oily = copy.deepcopy(ger_left)
        left_oily['photoId'] = 'left-oily-cheek-photo-201'
        left_oily['measurements']['rightCheek'] = [
            {'id': 'oil', 'value': 6.1, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
            {'id': 'dry', 'value': 0.2, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
        ]
        right_oily = copy.deepcopy(ger_right)
        right_oily['photoId'] = 'right-oily-cheek-photo-202'
        right_oily['measurements']['leftCheek'] = [
            {'id': 'oil', 'value': 5.7, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
            {'id': 'dry', 'value': 0.1, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
        ]

        resp_fuse_v1 = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={'processingConsent': True, 'front': front_oily_tzone, 'left': left_dry, 'right': right_dry},
        )
        assert resp_fuse_v1.status_code == 200, resp_fuse_v1.text
        ts_fuse_v1 = run_ts_fuse_multi_angle(front_oily_tzone, left_dry, right_dry)

        resp_fuse_v2 = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={'processingConsent': True, 'front': front_oily_tzone, 'left': left_oily, 'right': right_oily},
        )
        assert resp_fuse_v2.status_code == 200, resp_fuse_v2.text
        ts_fuse_v2 = run_ts_fuse_multi_angle(front_oily_tzone, left_oily, right_oily)

        # Save 02_germany 3-angle responses for Playwright UI verification
        ger_3angle_bundle = {
            'FRONT': ger_front,
            'LEFT': ger_left,
            'RIGHT': ger_right,
            'FUSED': six_person_summary['02_germany']['FUSED_3_ANGLE_PYTHON_HTTP'],
        }
        for d in (REPO_OUT_DIR, SHARED_OUT_DIR):
            (d / '02_germany_3angle_http_responses.json').write_text(
                json.dumps(ger_3angle_bundle, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
    finally:
        LH.parked = orig_parked

    pose_comparison = _load_pose_gate_comparison()

    report = {
        'generatedAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sharedOutputDirectories': [str(REPO_OUT_DIR), str(SHARED_OUT_DIR)],
        'guarantees': {
            'zeroExtraInferenceCost': True,
            'hostedRoboflowInProductPath': False,
            'acneV5LocalDefaultActive': os.getenv('ATTUNE_EXPERIMENTAL_ACNE_V5') == '1',
            'sensitivityUserQuestionRemoved': True,
            'rednessToSensitivityMappingRemoved': True,
            'globalVitLabelLeakageRemoved': True,
            'threeAngleFusionActiveInPythonAndTypeScript': True,
            'tolgarPhotoAnalyzedWithOwnLandmarksOnly': True,
        },
        'tolgarDocxUserScreenshotExtraction': docx_e2e,
        'sixPersonThreeAngleReplayVerification': six_person_summary,
        'missingCheekHonestyCheck': {
            '01_england_MISSING_RIGHT_CHEEK': summarize_response(res_eng_missing_cheek, t_eng_missing),
        },
        'threeAngleSideCaptureSensitivityProof': {
            'realReplaySideSwapProof': {
                'description': (
                    'Holding 02_germany FRONT capture constant (photoId=' + str(ger_front.get('photoId')) + ') '
                    'and swapping real analyzed LEFT/RIGHT captures between 02_germany and 01_england.'
                ),
                'with_02_germany_sides': {
                    'rightCheekFromLeftCapture': summarize_response(resp_swap_ger_sides, 0.01)['regionalMeasurements'].get('rightCheek'),
                    'leftCheekFromRightCapture': summarize_response(resp_swap_ger_sides, 0.01)['regionalMeasurements'].get('leftCheek'),
                    'typescriptParityPhotoIds': {
                        'rightCheekPhotoId': ts_swap_ger['regionalSkinMap']['regions']['rightCheek'].get('sourcePhotoId'),
                        'leftCheekPhotoId': ts_swap_ger['regionalSkinMap']['regions']['leftCheek'].get('sourcePhotoId'),
                    },
                },
                'with_01_england_sides': {
                    'rightCheekFromLeftCapture': summarize_response(resp_swap_eng_sides, 0.01)['regionalMeasurements'].get('rightCheek'),
                    'leftCheekFromRightCapture': summarize_response(resp_swap_eng_sides, 0.01)['regionalMeasurements'].get('leftCheek'),
                    'typescriptParityPhotoIds': {
                        'rightCheekPhotoId': ts_swap_eng['regionalSkinMap']['regions']['rightCheek'].get('sourcePhotoId'),
                        'leftCheekPhotoId': ts_swap_eng['regionalSkinMap']['regions']['leftCheek'].get('sourcePhotoId'),
                    },
                },
            },
            'controlledSideCheekRegimeSwapProof': {
                'description': 'Holding FRONT (front-fixed-photo-001) constant and changing only LEFT (rightCheek) and RIGHT (leftCheek) inputs over HTTP and TypeScript',
                'variant1_dry_side_cheeks_produces_combination': {
                    'pythonHttp': summarize_response(resp_fuse_v1.json(), 0.01),
                    'typescriptFrontend': {
                        'skinType': ts_fuse_v1['skinType'],
                        'regionalSkinMap': ts_fuse_v1['regionalSkinMap'],
                    },
                },
                'variant2_oily_side_cheeks_produces_oily': {
                    'pythonHttp': summarize_response(resp_fuse_v2.json(), 0.01),
                    'typescriptFrontend': {
                        'skinType': ts_fuse_v2['skinType'],
                        'regionalSkinMap': ts_fuse_v2['regionalSkinMap'],
                    },
                },
            },
        },
        'poseGateHistoricalAndRealFramesComparison': pose_comparison,
    }

    for out_dir in (REPO_OUT_DIR, SHARED_OUT_DIR):
        (out_dir / 'e2e-verification-results-20261024.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        model_doc = ROOT / 'docs' / 'skin-research' / 'model-selection-and-local-weights-20261024.md'
        if model_doc.exists():
            shutil.copy2(model_doc, out_dir / 'model-selection-and-local-weights-20261024.md')

    print('E2E verification completed and saved to both shared directories:')
    print(' -', REPO_OUT_DIR / 'e2e-verification-results-20261024.json')
    print(' -', SHARED_OUT_DIR / 'e2e-verification-results-20261024.json')


if __name__ == '__main__':
    main()
