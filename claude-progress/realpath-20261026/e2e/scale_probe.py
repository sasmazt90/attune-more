"""Inference-only probe: same person, original photo vs the camera-fixture frame (1920x1080, face 34%) vs 1280x720 (30%).
Prints the findings.pt rosacea/mole/melasma evidence per region and pose. No training."""
import os, sys, json, cv2, numpy as np, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
os.environ['ATTUNE_REGIONAL_V3_DIR'] = f'{S}/rv3model'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api')
import regional_skin_v3 as R, regional_attach as RA
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
def frame(img, W, H, ratio):
    h, w = img.shape[:2]; L = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))).face_landmarks[0]
    xs = np.array([p.x for p in L]) * w; ys = np.array([p.y for p in L]) * h; k = ratio * W / (xs.max() - xs.min())
    img = cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    M = np.float32([[1, 0, W / 2 - (xs.max() + xs.min()) / 2 * k], [0, 1, H / 2 - (ys.max() + ys.min()) / 2 * k]])
    return cv2.warpAffine(img, M, (W, H), borderValue=(40, 40, 40))
kid = sys.argv[1]; out = {}
for name, conv in (('original', lambda im: im), ('1920x1080@0.34', lambda im: frame(im, 1920, 1080, .34)), ('1280x720@0.30', lambda im: frame(im, 1280, 720, .30))):
    maps = {}
    for pose, f in (('FRONT', 'front'), ('LEFT', 'side_1'), ('RIGHT', 'side_2')):
        bgr = conv(cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{f}.png'))
        L = [{'x': q.x, 'y': q.y} for q in lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))).face_landmarks[0]]
        maps[pose] = R.analyze_photo(bgr, L, pose=pose)
    fz = RA.fuse_regional(maps)
    out[name] = {'seen': [(f['id'], f['region']) for f in fz['findings']['findings'] if f['status'] == 'seen'],
                 'rosacea_max': {p: {r: e['findings_Rozasea_max'] for r, e in m['findingEvidence'].items() if e['usable']} for p, m in maps.items()}}
    print(name, json.dumps(out[name]))
json.dump(out, open(f'{S}/e2e/scale_probe_{kid}.json', 'w'), indent=1)
