"""Candidate conservative clean-skin ROIs on the 65 reviewed TRAIN core photos (source pixels), for assistant engineering review.
Regions: left cheek, right cheek, central forehead (MediaPipe landmarks from the v2 replay). Removed before review: every source
annotation box of ANY class (dilated by max(10 px, 1x box side)), off-skin-colour pixels (hair, shadow, glare), eyes/brows/lips/nose
outside the polygons. Accepted regions become KNOWN_NEG; rejected regions stay UNKNOWN (reason recorded)."""
import glob, json, sys
from pathlib import Path
import numpy as np, cv2
CODE = Path(__file__).resolve().parents[2]; OUT = CODE / 'audit-results/acne-v5-core'
REG = dict(cheekL=[116, 117, 118, 119, 100, 142, 203, 206, 216, 192, 213, 147, 123], cheekR=[345, 346, 347, 348, 329, 371, 423, 426, 436, 416, 433, 376, 352],
           forehead=[67, 109, 10, 338, 297, 299, 337, 151, 108, 69])


def core():
    P = json.loads((CODE / 'audit-results/acne-v3-20261015/plan-v3.json').read_text()); role = {}
    for i in P['items']: role.setdefault(i['fileSha'], set()).add(i['role'])
    out = []
    for d in sorted(glob.glob(str(CODE / 'audit-results/acne-review-package-20261016/photos/TRAIN-*/labels.json'))):
        L = json.loads(Path(d).read_text())
        if role.get(L['sha256']) == {'TRAIN'}: out.append((Path(d).parent, L))
    return out


def main(phase):
    rp = {json.loads(l)['sha256']: json.loads(l) for l in (CODE / 'audit-results/acne-data-v2-20261015/replay.jsonl').read_text().splitlines()}
    hashrows = {}
    for f in glob.glob(str(CODE / 'audit-results/acne-v3-20261015/hash/*.ndjson')):
        for l in open(f):
            r = json.loads(l)
            if r['archive'].startswith('SmartSkinCare'): hashrows[r['fileSha']] = r
    items = []
    for folder, L in core():
        s = L['sha256']; src = sorted(folder.glob('source.*'))[0]; img = cv2.imread(str(src)); h, w = img.shape[:2]
        pts = np.array([[p['x'] * w, p['y'] * h] for p in rp[s]['landmarks']], np.float32)
        allbox = np.zeros((h, w), np.uint8)
        for a in hashrows[s]['anns']:
            b = a['box']; g = max(10, max(b[2] - b[0], b[3] - b[1]))
            cv2.rectangle(allbox, (int(b[0] - g), int(b[1] - g)), (int(b[2] + g), int(b[3] + g)), 255, -1)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        for name, poly in REG.items():
            m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [pts[poly].round().astype(np.int32)], 255); m = cv2.erode(m, np.ones((5, 5), np.uint8), iterations=2)
            m = (m > 0) & (allbox == 0)
            if m.sum() < 200: items.append(dict(sha=s, region=name, pixels=int(m.sum()), status='too-small')); continue
            ref = np.median(lab[m], 0); dist = np.linalg.norm(lab - ref, axis=2); tol = max(12., 2.5 * np.median(dist[m]))
            m = m & (dist <= tol) & (lab[..., 0] < 245)
            m = cv2.morphologyEx(m.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
            cv2.imwrite(str(OUT / f'roi-{s[:12]}-{name}.png'), m.astype(np.uint8) * 255)
            items.append(dict(sha=s, region=name, pixels=int(m.sum()), status='candidate', file=f'roi-{s[:12]}-{name}.png', src=str(src)))
    (OUT / 'roi-candidates.json').write_text(json.dumps(items, indent=0))
    C = [i for i in items if i['status'] == 'candidate' and i['pixels'] >= 200]; CELL = 300; per = 25
    for s0 in range(0, len(C), per):
        sheet = np.full((5 * CELL, 5 * CELL, 3), 255, np.uint8)
        for k, it in enumerate(C[s0:s0 + per]):
            img = cv2.imread(it['src']); m = cv2.imread(str(OUT / it['file']), cv2.IMREAD_GRAYSCALE) > 0
            ys, xs = np.nonzero(m); x0, x1, y0, y1 = max(0, xs.min() - 10), xs.max() + 10, max(0, ys.min() - 10), ys.max() + 10
            crop = img[y0:y1, x0:x1].copy(); mm = m[y0:y1, x0:x1].astype(np.uint8)
            cnt, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(crop, cnt, -1, (0, 255, 0), 1)
            f = (CELL - 8) / max(crop.shape[:2]); crop = cv2.resize(crop, (max(1, int(crop.shape[1] * f)), max(1, int(crop.shape[0] * f))), interpolation=cv2.INTER_CUBIC)
            yy, xx = divmod(k, 5); sheet[yy * CELL + 4:yy * CELL + 4 + crop.shape[0], xx * CELL + 4:xx * CELL + 4 + crop.shape[1]] = crop
            cv2.putText(sheet, str(s0 + k + 1), (xx * CELL + 6, yy * CELL + 20), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 2); cv2.putText(sheet, str(s0 + k + 1), (xx * CELL + 6, yy * CELL + 20), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 0), 1)
            it['reviewIndex'] = s0 + k + 1
        cv2.imwrite(str(OUT / f'roi-sheet-{s0 // per + 1}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
    (OUT / 'roi-candidates.json').write_text(json.dumps(items, indent=0))
    print('candidates', len(C), 'too small', sum(1 for i in items if i['status'] == 'too-small'), 'sheets', -(-len(C) // per))


if __name__ == '__main__': main(sys.argv[1] if len(sys.argv) > 1 else 'build')
