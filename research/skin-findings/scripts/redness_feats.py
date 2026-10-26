"""Light-corrected redness per region for every item (all tags): a* after removing the normal-based shading,
absolute and relative to the person's own face median, high-percentile and area above the face median."""
import json, sys, os, numpy as np, cv2, mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
sys.path.insert(0, f'{S}/rf'); import light
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/revbb/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
REG = {'forehead': 'forehead', 'nose': 'nose', 'cheek_imgL': 'cheek_imgL', 'cheek_imgR': 'cheek_imgR', 'chin': 'chin'}
out = {}
OUT = f'{S}/rf/redness_feats.json'
if os.path.exists(OUT): out = json.load(open(OUT))
for tag in ('_k5', '_k6', '_k8', '_k9', '_k10'):
    for it in json.load(open(f'{S}/rf/items{tag}.json')):
        key = str(it['id'])
        if key in out: continue
        img = cv2.imread(it['path'])
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        if not r.face_landmarks: continue
        try:
            R = light.analyze(img, r.face_landmarks[0])
        except Exception:
            continue
        L, a, b = light.lab(R['corr'][..., ::-1]); u = R['usable']; rm = light.region_masks(R)
        am = float(np.median(a[u])); f = {}
        for rg, m in rm.items():
            if m.sum() < 50: continue
            av = a[m]
            f[rg] = [float(np.median(av)), float(np.percentile(av, 90)), float(np.median(av) - am), float((av > am + 4).mean()), float((av > am + 8).mean()), float(np.median(b[m]))]
        out[key] = f
        if len(out) % 50 == 0: json.dump(out, open(OUT, 'w')); print('n', len(out), flush=True)
    json.dump(out, open(OUT, 'w')); print(tag, len(out), flush=True)
