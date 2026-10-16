"""Acne v6: candidate conservative clean-skin ROIs for assistant engineering review (same rule as build_acne_core_roi_v5.py).

Input: an items JSON list of {sha256, image (path), replay (path to a replay.jsonl with product MediaPipe landmarks), boxes (ALL
source annotation boxes of ANY class, source px)}. For each photo: left cheek, right cheek and central forehead polygons from the
landmarks, minus every source box dilated by max(10 px, 1x box side), minus off-skin-colour pixels (hair, shadow, glare), opened.
Candidates are written as binary masks plus review sheets (contour on the original pixels). Only regions a reviewer ACCEPTS become
known negatives; everything else stays UNKNOWN. Model predictions are never read here.

  python build_acne_roi_v6.py --items ITEMS.json --out DIR [--sheet-prefix roi-sheet]
  python build_acne_roi_v6.py freeze --out DIR --decisions DECISIONS.json   (writes frozen accepted masks + SHA-256 list)
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np, cv2

REG = dict(cheekL=[116, 117, 118, 119, 100, 142, 203, 206, 216, 192, 213, 147, 123], cheekR=[345, 346, 347, 348, 329, 371, 423, 426, 436, 416, 433, 376, 352],
           forehead=[67, 109, 10, 338, 297, 299, 337, 151, 108, 69])


def candidate_masks(img, landmarks, boxes):
    """Pure function: pixels + landmarks + source boxes -> {region: bool mask or None}."""
    h, w = img.shape[:2]
    pts = np.array([[p['x'] * w, p['y'] * h] for p in landmarks], np.float32)
    allbox = np.zeros((h, w), np.uint8)
    for b in boxes:
        g = max(10, max(b[2] - b[0], b[3] - b[1]))
        cv2.rectangle(allbox, (int(b[0] - g), int(b[1] - g)), (int(b[2] + g), int(b[3] + g)), 255, -1)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32); out = {}
    for name, poly in REG.items():
        m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [pts[poly].round().astype(np.int32)], 255); m = cv2.erode(m, np.ones((5, 5), np.uint8), iterations=2)
        m = (m > 0) & (allbox == 0)
        if m.sum() < 200: out[name] = None; continue
        ref = np.median(lab[m], 0); dist = np.linalg.norm(lab - ref, axis=2); tol = max(12., 2.5 * np.median(dist[m]))
        m = m & (dist <= tol) & (lab[..., 0] < 245)
        m = cv2.morphologyEx(m.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
        out[name] = m if m.sum() >= 200 else None
    return out


def build(items_path, out, prefix):
    out.mkdir(parents=True, exist_ok=True); (out / 'masks').mkdir(exist_ok=True)
    items = json.loads(Path(items_path).read_text()); rps = {}; cand = []
    for it in items:
        rp_path = it['replay']
        if rp_path not in rps: rps[rp_path] = {json.loads(l)['sha256']: json.loads(l) for l in Path(rp_path).read_text().splitlines()}
        rp = rps[rp_path][it['sha256']]; img = cv2.imread(it['image']); assert img is not None, it['image']
        for name, m in candidate_masks(img, rp['landmarks'], it['boxes']).items():
            if m is None: cand.append(dict(sha=it['sha256'], region=name, status='too-small')); continue
            f = f'masks/roi-{it["sha256"][:12]}-{name}.png'; cv2.imwrite(str(out / f), m.astype(np.uint8) * 255)
            cand.append(dict(sha=it['sha256'], region=name, pixels=int(m.sum()), status='candidate', file=f, src=it['image']))
    C = [c for c in cand if c['status'] == 'candidate']; CELL = 300; per = 25
    for s0 in range(0, len(C), per):
        sheet = np.full((5 * CELL, 5 * CELL, 3), 255, np.uint8)
        for k, it in enumerate(C[s0:s0 + per]):
            img = cv2.imread(it['src']); m = cv2.imread(str(out / it['file']), cv2.IMREAD_GRAYSCALE) > 0
            ys, xs = np.nonzero(m); x0, x1, y0, y1 = max(0, xs.min() - 10), xs.max() + 10, max(0, ys.min() - 10), ys.max() + 10
            crop = img[y0:y1, x0:x1].copy(); mm = m[y0:y1, x0:x1].astype(np.uint8)
            cnt, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(crop, cnt, -1, (0, 255, 0), 1)
            f = (CELL - 8) / max(crop.shape[:2]); crop = cv2.resize(crop, (max(1, int(crop.shape[1] * f)), max(1, int(crop.shape[0] * f))), interpolation=cv2.INTER_CUBIC)
            yy, xx = divmod(k, 5); sheet[yy * CELL + 4:yy * CELL + 4 + crop.shape[0], xx * CELL + 4:xx * CELL + 4 + crop.shape[1]] = crop
            for col, th in (((255, 255, 255), 2), ((0, 0, 0), 1)): cv2.putText(sheet, str(s0 + k + 1), (xx * CELL + 6, yy * CELL + 20), cv2.FONT_HERSHEY_SIMPLEX, .6, col, th)
            it['reviewIndex'] = s0 + k + 1
        cv2.imwrite(str(out / f'{prefix}-{s0 // per + 1}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
    (out / 'roi-candidates.json').write_text(json.dumps(cand, indent=0))
    print('photos', len(items), 'candidates', len(C), 'too small', len(cand) - len(C), 'sheets', -(-len(C) // per))


def freeze(out, decisions):
    """Union of ACCEPTED candidates per photo -> frozen mask; SHA-256 of every frozen mask and of the decisions file."""
    cand = json.loads((out / 'roi-candidates.json').read_text()); dec = json.loads(Path(decisions).read_text()); acc = set(dec['accept'])
    (out / 'frozen').mkdir(exist_ok=True); per = {}
    for c in cand:
        if c.get('reviewIndex') in acc:
            m = cv2.imread(str(out / c['file']), cv2.IMREAD_GRAYSCALE) > 0
            per[c['sha']] = per.get(c['sha'], np.zeros_like(m)) | m
    rows = []
    for s, m in sorted(per.items()):
        f = out / 'frozen' / f'{s[:16]}-cleanroi.png'; cv2.imwrite(str(f), m.astype(np.uint8) * 255)
        rows.append(dict(sha256=s, mask=f'frozen/{f.name}', pixels=int(m.sum()), maskSHA256=hashlib.sha256(f.read_bytes()).hexdigest()))
    fz = dict(decisionsSHA256=hashlib.sha256(Path(decisions).read_bytes()).hexdigest(), candidatesSHA256=hashlib.sha256((out / 'roi-candidates.json').read_bytes()).hexdigest(),
              photosWithRoi=len(rows), pixels=sum(r['pixels'] for r in rows), masks=rows)
    (out / 'frozen.json').write_text(json.dumps(fz, indent=1)); print(json.dumps({k: v for k, v in fz.items() if k != 'masks'}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase', nargs='?', default='build'); ap.add_argument('--items'); ap.add_argument('--out', required=True)
    ap.add_argument('--sheet-prefix', default='roi-sheet'); ap.add_argument('--decisions')
    a = ap.parse_args(); o = Path(a.out)
    if a.phase == 'build': build(a.items, o, a.sheet_prefix)
    elif a.phase == 'freeze': freeze(o, a.decisions)
