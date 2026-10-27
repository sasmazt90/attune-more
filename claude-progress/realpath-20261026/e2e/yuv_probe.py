"""Inference-only: findings.pt evidence on the camera-fixture frames after YUV 4:2:0 decoding (ffmpeg, as the browser
receives them) vs the same frames before encoding. No training."""
import os, sys, json, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR'] = f'{S}/rv3model'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R, regional_attach as RA
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
kid = sys.argv[1]; maps = {}
for pose, i in (('FRONT', 1), ('LEFT', 2), ('RIGHT', 3)):
    bgr = cv2.imread(f'{S}/e2e/probe/{kid}-{i}.png')
    L = [{'x': q.x, 'y': q.y} for q in lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))).face_landmarks[0]]
    maps[pose] = R.analyze_photo(bgr, L, pose=pose)
fz = RA.fuse_regional(maps)
res = {'seen': [(f['id'], f['region']) for f in fz['findings']['findings'] if f['status'] == 'seen'],
       'rosacea_max': {p: {r: e['findings_Rozasea_max'] for r, e in m['findingEvidence'].items() if e['usable']} for p, m in maps.items()}}
print('yuv420-decoded', json.dumps(res))
json.dump(res, open(f'{S}/e2e/yuv_probe_{kid}.json', 'w'), indent=1)
