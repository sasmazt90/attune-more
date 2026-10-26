"""Builds the three-pose camera fixture for tests/e2e/current_skin_contract.py (Chrome --use-file-for-fake-video-capture).

usage: python tests/e2e/make_skin_y4m.py FRONT.png SIDE_A.png SIDE_B.png audit-fixtures/three-angle.y4m [hold_s=10] [face_ratio=0.34] [width=1920] [height=1080]

Each photo is scaled so the MediaPipe landmark width is `face_ratio` of the frame width (default 1920x1080, the app's
requested camera size), centred, and held `hold_s`
seconds at 5 fps (front, then the two sides; Chrome loops the file). Nothing about pose or quality is faked: the app's
own MediaPipe gates decide which frame becomes which pose. Photos are not part of the repository (privacy); the
handoff used synthetic characters of the research set (K-217, K-236).
"""
import sys
from pathlib import Path
import cv2, numpy as np, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

front, side_a, side_b, out = sys.argv[1:5]
hold = float(sys.argv[5]) if len(sys.argv) > 5 else 10
ratio = float(sys.argv[6]) if len(sys.argv) > 6 else 0.34
W = int(sys.argv[7]) if len(sys.argv) > 7 else 1920
H = int(sys.argv[8]) if len(sys.argv) > 8 else 1080
FPS = 5
task = Path(__file__).resolve().parents[2] / 'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(task)), num_faces=1))


def frame(path):
    img = cv2.imread(path); h, w = img.shape[:2]
    found = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))).face_landmarks
    assert found, f'no face in {path}'
    xs = np.array([p.x for p in found[0]]) * w; ys = np.array([p.y for p in found[0]]) * h
    k = ratio * W / (xs.max() - xs.min())
    img = cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    M = np.float32([[1, 0, W / 2 - (xs.max() + xs.min()) / 2 * k], [0, 1, H / 2 - (ys.max() + ys.min()) / 2 * k]])
    return cv2.cvtColor(cv2.warpAffine(img, M, (W, H), borderValue=(40, 40, 40)), cv2.COLOR_BGR2YUV_I420).tobytes()


Path(out).parent.mkdir(parents=True, exist_ok=True)
with open(out, 'wb') as f:
    f.write(f'YUV4MPEG2 W{W} H{H} F{FPS}:1 Ip A1:1 C420jpeg\n'.encode())
    for path in (front, side_a, side_b):
        data = frame(path)
        for _ in range(int(hold * FPS)):
            f.write(b'FRAME\n'); f.write(data)
print(out)
