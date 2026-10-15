"""Python MediaPipe FaceLandmarker replay with the product's own .task model.

Research-only replay of the product capture landmark step for still photos.
It is NOT the browser classic worker: decode path and runtime differ, so its
agreement with real browser preflight rows is measured separately and every
row it produces is labelled 'python-mediapipe-replay'. Reads images read-only;
writes one JSON-lines file under the given output path. No weights besides the
product face_landmarker.task (SHA pinned) are loaded.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

TASK_SHA256 = '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True); ap.add_argument('--items', required=True, help='JSON list of {sha256,path}')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    task = Path(a.task)
    if hashlib.sha256(task.read_bytes()).hexdigest() != TASK_SHA256: raise SystemExit('TASK_MODEL_HASH_MISMATCH')
    import cv2, numpy as np, mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision
    opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(task)), running_mode=vision.RunningMode.IMAGE,
                                        num_faces=2, output_face_blendshapes=True)
    items = json.loads(Path(a.items).read_text('utf8')); out = Path(a.out)
    done = set()
    if out.exists():
        done = {json.loads(l)['sha256'] for l in out.read_text('utf8').splitlines() if l.strip()}
    with vision.FaceLandmarker.create_from_options(opts) as lm, out.open('a', encoding='utf8') as f:
        for it in items:
            if it['sha256'] in done: continue
            data = Path(it['path']).read_bytes()
            if hashlib.sha256(data).hexdigest() != it['sha256']: raise SystemExit('SOURCE_HASH_MISMATCH:' + it['sha256'][:8])
            bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            # Product page/preflight: landmarks and quality run on an analysis
            # canvas scaled to width<=640 (browser drawImage; bilinear here).
            ratio = min(1., 640 / bgr.shape[1]); aw, ah = round(bgr.shape[1] * ratio), round(bgr.shape[0] * ratio)
            analysis = cv2.resize(bgr, (aw, ah), interpolation=cv2.INTER_LINEAR) if ratio < 1 else bgr
            rgb = cv2.cvtColor(analysis, cv2.COLOR_BGR2RGB)
            t = time.perf_counter(); res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
            row = dict(sha256=it['sha256'], width=int(bgr.shape[1]), height=int(bgr.shape[0]), analysisWidth=aw, analysisHeight=ah, faceCount=len(res.face_landmarks),
                       landmarks=[dict(x=float(p.x), y=float(p.y), z=float(p.z)) for p in res.face_landmarks[0]] if res.face_landmarks else [],
                       blendshapes={c.category_name: float(c.score) for c in res.face_blendshapes[0]} if res.face_blendshapes else {},
                       seconds=time.perf_counter() - t, replay='python-mediapipe-replay', mediapipe=mp.__version__)
            f.write(json.dumps(row) + '\n'); f.flush()


if __name__ == '__main__':
    main()
