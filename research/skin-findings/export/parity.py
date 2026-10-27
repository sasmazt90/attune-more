"""Embedding parity: production crop+DINOv2 recipe vs cached research embeddings (finding_angle4_emb.npz)."""
import sys, json, numpy as np, cv2, torch, mediapipe as mp
from PIL import Image
from mediapipe.tasks.python import vision, BaseOptions
from transformers import AutoImageProcessor, AutoModel
S = '/tmp/claude-0/-home-claude/6c3a640c-814a-5b9e-a7fb-dc8a45e4bc81/scratchpad'
_src = open(f'{S}/rf/finding_clf.py').read(); exec('CROPS = {' + _src.split('CROPS = {', 1)[1].split("NEW = ")[0])
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=f'{S}/repo/claude-skin/apps/vehicle-app/public/mediapipe/models/face_landmarker.task'), num_faces=1))
D = f'{S}/rv3model/dinov2-small'; proc = AutoImageProcessor.from_pretrained(D, local_files_only=True); dm = AutoModel.from_pretrained(D, local_files_only=True).eval()
z = np.load(f'{S}/rf/finding_angle4_emb.npz', allow_pickle=True); E = z['E']; M = z['meta']
SIDE_OK = {'pos': lambda n: not n.endswith('_R'), 'neg': lambda n: not n.endswith('_L'), 'front': lambda n: True}
for kid in sys.argv[1:]:
    for f, view, srcn in (('front', 'front', 'front'), ('side_1', 'pos', 's20'), ('side_2', 'neg', 's20')):
        img = cv2.imread(f'{S}/gen/approved/{kid}/{kid}-{f}.png'); h, w = img.shape[:2]
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        P = np.array([[q.x * w, q.y * h] for q in r.face_landmarks[0]]); fw = P[:, 0].max() - P[:, 0].min()
        names, ims = [], []
        for name, (idx, pad, _) in CROPS.items():
            if not SIDE_OK[view](name): continue
            x0, y0 = P[idx].min(0) - pad * fw; x1, y1 = P[idx].max(0) + pad * fw
            c = img[int(max(0, y0)):int(y1), int(max(0, x0)):int(x1)]
            names.append(name); ims.append(Image.fromarray(cv2.cvtColor(cv2.resize(c, (224, 224)), cv2.COLOR_BGR2RGB)))
        with torch.no_grad():
            o = dm(**proc(images=ims, return_tensors='pt')).last_hidden_state
        e = torch.cat([o[:, 0], o[:, 1:].mean(1)], 1).numpy()
        rows = [i for i, m in enumerate(M) if m['kid'] == kid and m['src'] == srcn]
        for n, v in zip(names, e):
            cand = [i for i in rows if M[i]['crop'] == n]
            d = min(np.abs(E[i] - v).max() for i in cand) if cand else None
            cos = max(float(E[i] @ v / np.linalg.norm(E[i]) / np.linalg.norm(v)) for i in cand) if cand else None
            print(kid, f, n, 'maxabs', None if d is None else round(float(d), 4), 'cos', None if cos is None else round(cos, 5))
