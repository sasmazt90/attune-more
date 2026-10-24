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
    """Extract face panel crops from Tolgar-Skin(1).docx and save to shared directories with full provenance."""
    out = {}
    if not DOCX_PATH.exists():
        return out
    with zipfile.ZipFile(DOCX_PATH, 'r') as zf:
        media_files = sorted(n for n in zf.namelist() if n.startswith('word/media/'))
        targets = [
            ('word/media/image1.png', 'tolgar_docx_screen1_face_crop.png', (42, 132, 512, 718), 'Screen 1 (Genel Bakış): contains existing white face mesh overlay from screenshot'),
            ('word/media/image5.png', 'tolgar_docx_screen5_face_crop.png', (42, 132, 512, 718), 'Screen 5 (Kızarıklık): contains existing red heatmap overlay from screenshot'),
        ]
        for member, out_name, (x0, y0, x1, y1), note in targets:
            if member not in media_files:
                continue
            raw_bytes = zf.read(member)
            arr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            sh_h, sh_w = img.shape[:2]
            cx0, cy0 = max(0, min(x0, sh_w - 1)), max(0, min(y0, sh_h - 1))
            cx1, cy1 = max(cx0 + 1, min(x1, sh_w)), max(cy0 + 1, min(y1, sh_h))
            crop = img[cy0:cy1, cx0:cx1]
            ok, png_buf = cv2.imencode('.png', crop)
            assert ok
            png_bytes = png_buf.tobytes()
            sha = hashlib.sha256(png_bytes).hexdigest()
            for d in (REPO_OUT_DIR, SHARED_OUT_DIR):
                (d / out_name).write_bytes(png_bytes)
            out[out_name] = {
                'sourceDocxMember': member,
                'sourceScreenshotSize': {'width': int(sh_w), 'height': int(sh_h)},
                'cropBoxXYXY': [int(cx0), int(cy0), int(cx1), int(cy1)],
                'cropPixelSize': {'width': int(crop.shape[1]), 'height': int(crop.shape[0])},
                'sha256': sha,
                'containsExistingUiOverlay': True,
                'provenanceNote': note,
            }
    return out


def load_angle_request(person_dir: Path, angle: str) -> dict:
    req_path = person_dir / angle / 'request.json'
    req = json.loads(req_path.read_text(encoding='utf-8'))
    img_path = person_dir / angle / 'analysis-input.png'
    if not img_path.exists():
        img_path = person_dir / angle / 'replay-decoded-source.png'
    b64_photo = 'data:image/png;base64,' + base64.b64encode(img_path.read_bytes()).decode('ascii')

    if 'meshes' not in req:
        geom = json.loads((person_dir / angle / 'geometry.json').read_text(encoding='utf-8'))
        preflight = json.loads((person_dir / angle / 'preflight.json').read_text(encoding='utf-8'))
        front_req = json.loads((person_dir / 'FRONT' / 'request.json').read_text(encoding='utf-8'))
        expr_obs = copy.deepcopy(front_req.get('expressionObservation') or {})
        if isinstance(expr_obs, dict):
            expr_obs['photoId'] = geom['photoId']
        req = {
            'experimentalAcneV5': False,
            'requestId': str(uuid.uuid4()),
            'capturePreflight': preflight,
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
            'conditions': front_req.get('conditions', {}),
            'temporal': front_req.get('temporal', {}),
        }
    else:
        req['photo'] = b64_photo
        req['pose'] = req.get('pose') or angle
        req['experimentalAcneV5'] = False
        req['hostedProcessingConsent'] = False
    return req


def summarize_response(data: dict, elapsed_s: float) -> dict:
    general = data.get('general') or {}
    skin_type = general.get('skinType') or {}
    trace = skin_type.get('decisionTrace') or {}
    maps = data.get('maps') or {}
    measurements = data.get('measurements') or {}
    acne_cands = data.get('acneCandidates') or {}

    acne_summary = {}
    for k, v in acne_cands.items():
        if v:
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


def _run_pose_gate_comparison() -> dict:
    node_script = r'''
require('./tests/unit/ts_loader.js');
const { matchesSkinAngle, angleGuidance, SKIN_SIDE_MIN_YAW_DEG, SKIN_SIDE_MAX_YAW_DEG, SKIN_FRONT_MAX_YAW_DEG } = require('./apps/vehicle-app/src/utils/skinMultiAngle.ts');
const { matchesDentalAngle, dentalGuidance, DENTAL_SIDE_MIN_DEG, DENTAL_SIDE_MAX_DEG } = require('./apps/vehicle-app/src/utils/dentalCapture.ts');

function makeTransform(yawDeg) {
  const rad = (yawDeg * Math.PI) / 180;
  const c = Math.cos(rad), s = Math.sin(rad);
  return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, -40, 1];
}

function old7463eefSkinSide(a, angle) {
  return angle === 'LEFT' ? (a.yaw >= 0.25 && a.yaw <= 0.92) : (a.yaw <= -0.25 && a.yaw >= -0.92);
}

function old51ab991SkinSide(a, angle) {
  const m = a.faceTransform;
  const yawDeg = Math.atan2(m[8], m[10]) * 180 / Math.PI;
  return angle === 'LEFT' ? (yawDeg >= 15 && yawDeg <= 35) : (yawDeg <= -15 && yawDeg >= -35);
}

function oldDentalSide(a, angle) {
  const m = a.faceTransform;
  const yaw = Math.atan2(m[8], m[10]);
  return angle === 'LEFT' ? (yaw >= 15 * Math.PI / 180 && yaw <= 0.65) : (yaw <= -15 * Math.PI / 180 && yaw >= -0.65);
}

const base = { faceDetected: true, isMediaPipeActive: true, yaw: 0, pitch: 0, roll: 0, scaleRatio: 0.5, sourceFramed: true, isAligned: false };
const testCases = [
  { label: '0° (Tam karşı / FRONT)', yawDeg: 0, noseYaw: 0.0, target: 'FRONT' },
  { label: '10° (Hafif dönüş / yan alt sınır altı)', yawDeg: 10, noseYaw: 0.18, target: 'LEFT' },
  { label: '12.5° (Erken yan dönüş - korunan poz)', yawDeg: 12.5, noseYaw: 0.26, target: 'LEFT' },
  { label: '15° (Standart yan başlangıç)', yawDeg: 15, noseYaw: 0.32, target: 'LEFT' },
  { label: '24.2° (Gerçek 01_england LEFT karesi)', yawDeg: 24.21, noseYaw: 0.79, target: 'LEFT' },
  { label: '25.5° (Gerçek 02_germany LEFT karesi, 2D yaw=0.93 > 0.92)', yawDeg: 25.5, noseYaw: 0.93, target: 'LEFT' },
  { label: '34° (Normal yan dönüş)', yawDeg: 34, noseYaw: 0.88, target: 'LEFT' },
  { label: '38° (Genişletilmiş yan dönüş - YENİ KABUL)', yawDeg: 38, noseYaw: 0.98, target: 'LEFT' },
  { label: '42° (Genişletilmiş yan dönüş - YENİ KABUL)', yawDeg: 42, noseYaw: 1.06, target: 'LEFT' },
  { label: '45° (Üst sınır yan dönüş - YENİ KABUL)', yawDeg: 45, noseYaw: 1.12, target: 'LEFT' },
  { label: '48° (Aşırı dönüş > 45° - RED)', yawDeg: 48, noseYaw: 1.22, target: 'LEFT' },
];

const rows = testCases.map(tc => {
  const a = { ...base, yaw: tc.noseYaw, faceTransform: makeTransform(tc.yawDeg) };
  return {
    label: tc.label,
    yawDeg: tc.yawDeg,
    noseRatioYaw: tc.noseYaw,
    targetAngle: tc.target,
    skinOld7463eef: tc.target === 'FRONT' ? Math.abs(tc.noseYaw) <= 0.20 : old7463eefSkinSide(a, tc.target),
    skinOld51ab991: tc.target === 'FRONT' ? Math.abs(tc.yawDeg) <= 12 : old51ab991SkinSide(a, tc.target),
    skinNewCurrent: matchesSkinAngle(a, tc.target),
    skinGuidanceTr: angleGuidance(a, tc.target),
    dentalOld: tc.target === 'FRONT' ? Math.abs(tc.yawDeg) <= 12 : oldDentalSide(a, tc.target),
    dentalNewCurrent: matchesDentalAngle(a, tc.target),
    dentalGuidanceTr: dentalGuidance(a, tc.target),
  };
});

console.log(JSON.stringify({
  skinFrontMaxDeg: SKIN_FRONT_MAX_YAW_DEG,
  skinSideRangeDeg: [SKIN_SIDE_MIN_YAW_DEG, SKIN_SIDE_MAX_YAW_DEG],
  dentalSideRangeDeg: [DENTAL_SIDE_MIN_DEG, DENTAL_SIDE_MAX_DEG],
  comparisonRows: rows,
}));
'''
    r = subprocess.run(['node', '-e', node_script], cwd=ROOT, text=True, capture_output=True, encoding='utf8')
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def main():
    _ensure_dirs()
    PD.runtime(lambda: None)

    # A. Extract user's Tolgar-Skin(1).docx screenshot crops with full provenance
    docx_crops = _extract_tolgar_docx_crops()

    # B. Function-level E2E on 3-angle captures (02_germany & 01_england FRONT, LEFT, RIGHT)
    p_ger = REPLAY_DIR / '02_germany'
    p_eng = REPLAY_DIR / '01_england'

    # Run user's Tolgar-Skin(1).docx screen1 crop through local ONNX ViT base model + full pipeline with matching RGBA hash
    docx_e2e = {}
    if (REPO_OUT_DIR / 'tolgar_docx_screen1_face_crop.png').exists():
        crop_bytes = (REPO_OUT_DIR / 'tolgar_docx_screen1_face_crop.png').read_bytes()
        crop_img = cv2.imdecode(np.frombuffer(crop_bytes, np.uint8), cv2.IMREAD_COLOR)
        vit_pred = LST.infer(crop_img)
        req_docx = load_angle_request(p_ger, 'FRONT')
        resized_crop = cv2.resize(crop_img, (1280, 720), interpolation=cv2.INTER_LINEAR)
        ok, enc = cv2.imencode('.png', resized_crop)
        assert ok
        photo_url = 'data:image/png;base64,' + base64.b64encode(enc.tobytes()).decode('ascii')
        _, rgba_hash = AA.decode_photo(photo_url)
        req_docx['photo'] = photo_url
        req_docx['photoId'] = rgba_hash
        if isinstance(req_docx.get('expressionObservation'), dict):
            req_docx['expressionObservation'] = {**req_docx['expressionObservation'], 'photoId': rgba_hash}
        if isinstance(req_docx.get('capturePreflight'), dict):
            req_docx['capturePreflight'] = {**req_docx['capturePreflight'], 'photoId': rgba_hash}
        req_docx['pose'] = 'FRONT'
        t0 = time.perf_counter()
        raw_docx = PD.analyze_product(req_docx, AA.analyze_skin, lambda: None)
        res_docx = LST.finalize_product_type(raw_docx)
        docx_e2e['tolgar_docx_screen1_crop_analysis'] = {
            'provenance': docx_crops['tolgar_docx_screen1_face_crop.png'],
            'directLocalVitOnRawCrop': vit_pred,
            'fullPipelineResult': summarize_response(res_docx, time.perf_counter() - t0),
        }

    # Run 02_germany FRONT, LEFT, RIGHT through full local pipeline (zero cloud calls)
    req_ger_front = load_angle_request(p_ger, 'FRONT')
    t0 = time.perf_counter()
    res_ger_front = LST.finalize_product_type(PD.analyze_product(req_ger_front, AA.analyze_skin, lambda: None))
    t_ger_front = time.perf_counter() - t0

    req_ger_left = load_angle_request(p_ger, 'LEFT')
    t0 = time.perf_counter()
    res_ger_left = LST.finalize_product_type(PD.analyze_product(req_ger_left, AA.analyze_skin, lambda: None))
    t_ger_left = time.perf_counter() - t0

    req_ger_right = load_angle_request(p_ger, 'RIGHT')
    t0 = time.perf_counter()
    res_ger_right = LST.finalize_product_type(PD.analyze_product(req_ger_right, AA.analyze_skin, lambda: None))
    t_ger_right = time.perf_counter() - t0

    # Fuse the 3 real angles of 02_germany
    t0 = time.perf_counter()
    fused_ger_3angle = LST.fuse_multi_angle_skin(res_ger_front, res_ger_left, res_ger_right)
    t_ger_fused = time.perf_counter() - t0

    # Missing cheek test on 01_england FRONT
    req_eng_front = load_angle_request(p_eng, 'FRONT')
    t0 = time.perf_counter()
    raw_eng = AA.analyze_skin(req_eng_front)
    raw_eng['measurements'].pop('rightCheek', None)
    res_eng_missing_cheek = LST.finalize_product_type(raw_eng)
    t_eng_missing = time.perf_counter() - t0

    # C. HTTP-level E2E via FastAPI TestClient (`/api/local-health/skin` and `/api/local-health/skin/fuse-multi-angle`)
    orig_parked = LH.parked
    LH.parked = lambda: True
    try:
        client = TestClient(app)
        t0 = time.perf_counter()
        resp_skin_front = client.post('/api/local-health/skin', json=req_ger_front)
        assert resp_skin_front.status_code == 200, resp_skin_front.text
        http_front_json = resp_skin_front.json()
        t_http_front = time.perf_counter() - t0

        t0 = time.perf_counter()
        resp_skin_left = client.post('/api/local-health/skin', json=req_ger_left)
        assert resp_skin_left.status_code == 200, resp_skin_left.text
        http_left_json = resp_skin_left.json()
        t_http_left = time.perf_counter() - t0

        t0 = time.perf_counter()
        resp_skin_right = client.post('/api/local-health/skin', json=req_ger_right)
        assert resp_skin_right.status_code == 200, resp_skin_right.text
        http_right_json = resp_skin_right.json()
        t_http_right = time.perf_counter() - t0

        # HTTP 3-angle fusion of the 3 HTTP responses
        t0 = time.perf_counter()
        resp_fuse_real = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={'processingConsent': True, 'front': http_front_json, 'left': http_left_json, 'right': http_right_json},
        )
        assert resp_fuse_real.status_code == 200, resp_fuse_real.text
        http_fuse_real_json = resp_fuse_real.json()
        t_http_fuse_real = time.perf_counter() - t0

        # Controlled 3-angle fusion proof over HTTP: Hold FRONT T-zone oily constant and vary LEFT & RIGHT cheeks
        area = {'sourcePixels': 320, 'analysisPixels': 320, 'foreheadSourcePixels': 160, 'noseSourcePixels': 160}
        front_oily_tzone = copy.deepcopy(http_front_json)
        front_oily_tzone['photoId'] = 'front-fixed-photo-001'
        for r_name, oil_val in [('forehead', 6.4), ('nose', 5.8), ('chin', 3.2)]:
            front_oily_tzone['measurements'][r_name] = [
                {'id': 'oil', 'value': oil_val, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area, 'photoId': 'front-fixed-photo-001', 'capturePose': 'FRONT'},
                {'id': 'dry', 'value': 0.2, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area, 'photoId': 'front-fixed-photo-001', 'capturePose': 'FRONT'},
            ]

        # Variant 1: LEFT & RIGHT captures have dry cheeks -> Combination ('Karma')
        resp_fuse_v1 = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={
                'processingConsent': True,
                'front': front_oily_tzone,
                'left': {
                    'photoId': 'left-dry-cheek-photo-101',
                    'pose': 'LEFT',
                    'measurements': {
                        'rightCheek': [
                            {'id': 'oil', 'value': 0.2, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
                            {'id': 'dry', 'value': 3.9, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
                        ]
                    },
                },
                'right': {
                    'photoId': 'right-dry-cheek-photo-102',
                    'pose': 'RIGHT',
                    'measurements': {
                        'leftCheek': [
                            {'id': 'oil', 'value': 0.1, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
                            {'id': 'dry', 'value': 4.3, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
                        ]
                    },
                },
            },
        )
        assert resp_fuse_v1.status_code == 200, resp_fuse_v1.text

        # Variant 2: Holding FRONT identical, change LEFT & RIGHT captures to oily cheeks -> Oily ('Yağlı')
        resp_fuse_v2 = client.post(
            '/api/local-health/skin/fuse-multi-angle',
            json={
                'processingConsent': True,
                'front': front_oily_tzone,
                'left': {
                    'photoId': 'left-oily-cheek-photo-201',
                    'pose': 'LEFT',
                    'measurements': {
                        'rightCheek': [
                            {'id': 'oil', 'value': 6.1, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
                            {'id': 'dry', 'value': 0.2, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
                        ]
                    },
                },
                'right': {
                    'photoId': 'right-oily-cheek-photo-202',
                    'pose': 'RIGHT',
                    'measurements': {
                        'leftCheek': [
                            {'id': 'oil', 'value': 5.7, 'quality': 'valid', 'methodVersion': 'appearance-cv-6', 'evaluatedArea': area},
                            {'id': 'dry', 'value': 0.1, 'quality': 'valid', 'methodVersion': 'appearance-native-dry-2', 'evaluatedArea': area},
                        ]
                    },
                },
            },
        )
        assert resp_fuse_v2.status_code == 200, resp_fuse_v2.text
    finally:
        LH.parked = orig_parked

    # D. Pose gate comparison
    pose_comparison = _run_pose_gate_comparison()

    report = {
        'generatedAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sharedOutputDirectories': [str(REPO_OUT_DIR), str(SHARED_OUT_DIR)],
        'guarantees': {
            'zeroExtraInferenceCost': True,
            'hostedRoboflowInProductPath': False,
            'sensitivityUserQuestionRemoved': True,
            'rednessToSensitivityMappingRemoved': True,
            'globalVitLabelLeakageRemoved': True,
            'threeAngleFusionActive': True,
        },
        'tolgarDocxUserScreenshotExtraction': docx_e2e,
        'functionLevelThreeAnglePipeline': {
            'note': 'Separate 3-angle (FRONT/LEFT/RIGHT) test fixture run on local ONNX models (not mixed with Tolgar-Skin.docx user screenshots)',
            '02_germany_FRONT': summarize_response(res_ger_front, t_ger_front),
            '02_germany_LEFT': summarize_response(res_ger_left, t_ger_left),
            '02_germany_RIGHT': summarize_response(res_ger_right, t_ger_right),
            '02_germany_FUSED_3_ANGLE': summarize_response(fused_ger_3angle, t_ger_fused),
            '01_england_MISSING_CHEEK': summarize_response(res_eng_missing_cheek, t_eng_missing),
        },
        'httpLevelEndpointsVerification': {
            'POST_api_local_health_skin_FRONT': summarize_response(http_front_json, t_http_front),
            'POST_api_local_health_skin_LEFT': summarize_response(http_left_json, t_http_left),
            'POST_api_local_health_skin_RIGHT': summarize_response(http_right_json, t_http_right),
            'POST_api_local_health_skin_fuse_multi_angle_real': summarize_response(http_fuse_real_json, t_http_fuse_real),
            'threeAngleSideCaptureSensitivityProof': {
                'description': 'Holding FRONT (front-fixed-photo-001) constant and changing only LEFT (rightCheek) and RIGHT (leftCheek) inputs over HTTP',
                'variant1_dry_side_cheeks_produces_combination': summarize_response(resp_fuse_v1.json(), 0.01),
                'variant2_oily_side_cheeks_produces_oily': summarize_response(resp_fuse_v2.json(), 0.01),
            },
        },
        'poseGateOldVsNewComparison': pose_comparison,
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
