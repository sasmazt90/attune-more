"""Triangulation check on all 140 front photos (+ 20° side photos): skin_findings_eye._delaunay vs scipy Delaunay."""
import sys, json, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
from scipy.spatial import Delaunay
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/repo/claude-skin/services/core-api'); import skin_findings_eye as SE
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
same = diff = 0; bad = []
for i in range(181, 321):
    kid = f'K-{i}'
    img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-front.png'); h, w = img.shape[:2]
    r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    P = np.array([[q.x * w, q.y * h] for q in r.face_landmarks[0][:468]]); fw = P[:, 0].max() - P[:, 0].min(); sc = 400 / fw
    P2 = (P - [P[:, 0].min() - .15 * fw, P[:, 1].min() - .15 * fw]) * sc
    a = {tuple(sorted(t)) for t in SE._delaunay(P2, 0, 0).tolist()}; b = {tuple(sorted(t)) for t in Delaunay(P2).simplices.tolist()}
    if a == b: same += 1
    else: diff += 1; bad.append((kid, len(a - b), len(b - a)))
print(json.dumps(dict(identical=same, different=diff, cases=bad)))
