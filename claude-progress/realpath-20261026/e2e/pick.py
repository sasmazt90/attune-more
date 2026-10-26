"""Inference-only screen: findings.pt evidence on original synthetic photos (3 poses) for a few labelled persons."""
import os, sys, json, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR'] = f'{S}/rv3model'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R, regional_attach as RA, skin_findings_v1 as SF
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
for kid in sys.argv[1:]:
    maps = {}
    for pose, f in (('FRONT', 'front'), ('LEFT', 'side_1'), ('RIGHT', 'side_2')):
        bgr = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{f}.png')
        L = [{'x': q.x, 'y': q.y} for q in lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))).face_landmarks[0]]
        maps[pose] = R.analyze_photo(bgr, L, pose=pose)
    best = {fid: max((e[d['key']] for m in maps.values() for r, e in m['findingEvidence'].items() if e['usable'] and r in d['regions']), default=0) - d['threshold'] for fid, d in SF.DETECTOR_FINDINGS.items()}
    print(kid, {k: round(v, 3) for k, v in best.items()}, flush=True)
