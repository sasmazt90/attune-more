"""Verify downloaded third-party acne detectors on the frozen label-independent DEV pack (no training, no threshold sweep).

Modes (input decided from pixels / product tile plan only; labels used only for scoring):
  full    whole photo, ultralytics letterbox at the model's training imgsz
  crop    product face crop (union of the product tile rectangles), same imgsz
  tiles   the product native tiles (<=384x288 source px each) at imgsz 384, merged with class-agnostic NMS .30
  app     (Dewiin only) the published BlemishBot pipeline: face crop -> no-acne gate model -> acne model conf .01 agnostic NMS
Confidence: ultralytics default .25 (app mode: .01 as published). Acne classes only count as candidates.
Scoring: one-to-one IoU .50 / .30 against source boxes; small < 16 px; unlabeled = unmatched at .30; false candidates = candidate
centre inside frozen reviewed clean ROI (positive photos) or reviewed Clear mask (negative photos).
"""
import json, sys, time, statistics as st
from pathlib import Path
import numpy as np, cv2, torch, torchvision
from ultralytics import YOLO

P = Path('pack'); man = json.loads((P / 'manifest.json').read_text())
MODELS = {'dewiin-acne': ('dewiin-acne.pt', 320, {'Papules', 'Pustule', 'Whitehead', 'Nodule'}),
          'dewiin-anyacne': ('dewiin-no_acne_model.pt', 320, {'Acne'}),
          'unzelanoor': ('unzelanoor-best.pt', 640, {'acne'})}


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i; return i / u if u > 0 else 0.


def o2o(T, F, thr):
    pr = sorted(((iou(t, p), i, j) for i, t in enumerate(T) for j, p in enumerate(F)), reverse=True); ut, up, m = set(), set(), []
    for v, i, j in pr:
        if v < thr: break
        if i in ut or j in up: continue
        ut.add(i); up.add(j); m.append((i, j))
    return m


def predict(model, img, imgsz, keep, conf=.25, agnostic=False):
    r = model.predict(img, imgsz=imgsz, conf=conf, verbose=False, agnostic_nms=agnostic)[0]
    out = []
    for b, c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        if model.names[int(c)] in keep: out.append(b + [s])
    return out


def nms(boxes, thr=.30):
    if not boxes: return []
    t = torch.tensor(boxes); k = torchvision.ops.nms(t[:, :4], t[:, 4], thr); return [boxes[i] for i in k.tolist()]


def run(name, mode):
    f, imgsz, keep = MODELS[name]; model = YOLO(f); gate = YOLO('dewiin-no_acne_model.pt') if mode == 'app' else None
    rows = []
    for it in man:
        img = cv2.imread(str(P / it['file'])); R = it['rects']; t0 = time.perf_counter()
        x0, y0 = min(r[0] for r in R), min(r[1] for r in R); x1, y1 = max(r[2] for r in R), max(r[3] for r in R)
        if mode == 'full': F = predict(model, img, imgsz, keep)
        elif mode == 'crop':
            F = [[b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0, b[4]] for b in predict(model, img[y0:y1, x0:x1], imgsz, keep)]
        elif mode == 'tiles':
            F = nms([[b[0] + a, b[1] + c, b[2] + a, b[3] + c, b[4]] for (a, c, e, d) in R for b in predict(model, img[c:d, a:e], 384, keep)])
        elif mode == 'app':
            crop = img[y0:y1, x0:x1]
            F = [] if not predict(gate, crop, 320, {'Acne'}) else \
                [[b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0, b[4]] for b in predict(model, crop, imgsz, keep, conf=.01, agnostic=True)]
        rows.append(dict(sha=it['sha256'], kind=it['kind'], set=it['set'], final=F, sec=time.perf_counter() - t0))
    return rows


def score(rows):
    by = {i['sha256']: i for i in man}; tot = dict(targets=0, hit50=0, hit30=0, small=0, smallHit50=0, smallHit30=0, final=0, unlabeled=0, roiFP=0, clearFP=0)
    ar, roiper, clearper = [], [], []
    for r in rows:
        it = by[r['sha']]; F = [b[:4] for b in r['final']]
        def centre_in(maskfile):
            m = cv2.imread(str(P / maskfile), cv2.IMREAD_GRAYSCALE) > 0; c = 0
            for b in F:
                cx, cy = int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2)
                if 0 <= cy < m.shape[0] and 0 <= cx < m.shape[1] and m[cy, cx]: c += 1
            return c
        if r['kind'] == 'negative-photo':
            c = centre_in(it['negMask']); tot['clearFP'] += c; clearper.append(c); continue
        T = it['positive']; m50 = o2o(T, F, .5); m30 = o2o(T, F, .3); h50 = {i for i, _ in m50}; h30 = {i for i, _ in m30}
        tot['targets'] += len(T); tot['hit50'] += len(m50); tot['hit30'] += len(m30); tot['final'] += len(F); tot['unlabeled'] += len(F) - len(m30)
        for i, t in enumerate(T):
            if max(t[2] - t[0], t[3] - t[1]) < 16: tot['small'] += 1; tot['smallHit50'] += i in h50; tot['smallHit30'] += i in h30
        ar += [((F[j][2] - F[j][0]) * (F[j][3] - F[j][1])) / max(1e-6, (T[i][2] - T[i][0]) * (T[i][3] - T[i][1])) for i, j in m30]
        if 'roiMask' in it: c = centre_in(it['roiMask']); tot['roiFP'] += c; roiper.append(c)
    tot['medianAreaRatio'] = round(st.median(ar), 2) if ar else None; tot['roiFPperPhoto'] = roiper; tot['clearFPperPhoto'] = clearper
    tot['medianSec'] = round(st.median(r['sec'] for r in rows), 3)
    return tot


if __name__ == '__main__':
    res = {}
    for name, mode in [('dewiin-acne', 'full'), ('dewiin-acne', 'crop'), ('dewiin-acne', 'tiles'), ('dewiin-acne', 'app'),
                       ('dewiin-anyacne', 'full'), ('dewiin-anyacne', 'crop'), ('dewiin-anyacne', 'tiles'),
                       ('unzelanoor', 'full'), ('unzelanoor', 'crop'), ('unzelanoor', 'tiles')]:
        rows = run(name, mode); s = score(rows); res[f'{name}/{mode}'] = dict(score=s, rows=rows)
        print(name, mode, json.dumps({k: v for k, v in s.items() if not k.endswith('PerPhoto')}), 'roi', s['roiFPperPhoto'], 'clear', s['clearFPperPhoto'], flush=True)
    json.dump(res, open('external-results.json', 'w'))
