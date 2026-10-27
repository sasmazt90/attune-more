"""Inference-only: the exact photos the app sent, analysed with (a) the browser's landmarks, (b) Python MediaPipe landmarks;
plus the pixel difference to the fixture frame. No training."""
import os, sys, json, cv2, numpy as np, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR'] = f'{S}/rv3model'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
O = f'{S}/e2e/out-K-217'
for pose in ('FRONT', 'LEFT', 'RIGHT'):
    bgr = cv2.imread(f'{O}/sent-{pose}.png'); Lb = json.load(open(f'{O}/sent-{pose}-landmarks.json'))
    Lp = [{'x': q.x, 'y': q.y} for q in lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))).face_landmarks[0]]
    d = np.mean([abs(a['x'] - b['x']) * bgr.shape[1] + abs(a['y'] - b['y']) * bgr.shape[0] for a, b in zip(Lb, Lp)])
    eb = R.analyze_photo(bgr, Lb, pose=pose)['findingEvidence']; ep = R.analyze_photo(bgr, Lp, pose=pose)['findingEvidence']
    print(pose, bgr.shape, 'mean landmark L1 px', round(d, 1), 'n', len(Lb), len(Lp))
    print('  browser lm', {r: e['findings_Rozasea_max'] for r, e in eb.items()})
    print('  python  lm', {r: e['findings_Rozasea_max'] for r, e in ep.items()})
