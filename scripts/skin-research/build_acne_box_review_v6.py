"""Acne v6 box review sheets for the TRAIN extension (assistant engineering review at native resolution).

For every source acne box (positive) and every explicit confounder box (mole / pigmentation / pores - used as KNOWN_NEG by the trainer)
of the selected photos: a square crop of the ORIGINAL pixels around the box (context max(4x box side, 64 px)), the box outline drawn
1 px outside the box, resized for display only. Writes box-review-key.json (index -> photo SHA, source id, class, box) and sheets of
64 cells. Source labels are never modified; decisions are written by the reviewer to a separate JSON. No model output is read.

  python build_acne_box_review_v6.py --selection audit-results/acne-v6/trainext/selection.json --out audit-results/acne-v6/trainext/boxreview
"""
import argparse, json
from pathlib import Path
import numpy as np, cv2
CODE = Path(__file__).resolve().parents[2]


def main(sel, out):
    out.mkdir(parents=True, exist_ok=True)
    S = [r['sha256'] for r in json.loads(Path(sel).read_text())['selected']]
    man = {p['sha256']: p for p in json.loads((CODE / 'audit-results/acne-v4-data/manifest-v4.json').read_text())['photos']}
    key = {'positive': [], 'confounder': []}
    for s in S:
        p = man[s]
        for b in p['positive']: key['positive'].append(dict(sha=s, id=b['id'], cls=b['cls'], box=b['box'], file=str(CODE / 'audit-results/acne-v4-data' / p['file'])))
        for b in p.get('negativeBoxes', []): key['confounder'].append(dict(sha=s, id=b['id'], cls=b['cls'], box=b['box'], file=str(CODE / 'audit-results/acne-v4-data' / p['file'])))
    cache = {}; CELL = 200; per = 64
    for kind, col in (('positive', (0, 255, 255)), ('confounder', (255, 255, 0))):
        K = key[kind]
        for s0 in range(0, len(K), per):
            sheet = np.full((8 * CELL, 8 * CELL, 3), 255, np.uint8)
            for k, it in enumerate(K[s0:s0 + per]):
                if it['file'] not in cache: cache.clear(); cache[it['file']] = cv2.imread(it['file'])
                img = cache[it['file']]; h, w = img.shape[:2]; b = it['box']
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; side = max(b[2] - b[0], b[3] - b[1]); half = max(4 * side, 64) / 2
                x0, y0 = int(max(0, cx - half)), int(max(0, cy - half)); x1, y1 = int(min(w, cx + half)), int(min(h, cy + half))
                crop = img[y0:y1, x0:x1].copy(); f = (CELL - 4) / max(crop.shape[:2])
                crop = cv2.resize(crop, (max(1, round(crop.shape[1] * f)), max(1, round(crop.shape[0] * f))), interpolation=cv2.INTER_CUBIC)
                bx = [round((b[0] - x0) * f) - 1, round((b[1] - y0) * f) - 1, round((b[2] - x0) * f) + 1, round((b[3] - y0) * f) + 1]
                cv2.rectangle(crop, (bx[0], bx[1]), (bx[2], bx[3]), col, 1)
                yy, xx = divmod(k, 8); sheet[yy * CELL + 2:yy * CELL + 2 + crop.shape[0], xx * CELL + 2:xx * CELL + 2 + crop.shape[1]] = crop
                lab = str(s0 + k + 1)
                for c, th in (((255, 255, 255), 2), ((0, 0, 0), 1)): cv2.putText(sheet, lab, (xx * CELL + 4, yy * CELL + 16), cv2.FONT_HERSHEY_SIMPLEX, .5, c, th)
                it['reviewIndex'] = s0 + k + 1; it['sheet'] = f'{kind}-sheet-{s0 // per + 1:02d}.jpg'
            cv2.imwrite(str(out / f'{kind}-sheet-{s0 // per + 1:02d}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    for K in key.values():
        for it in K: it.pop('file')
    (out / 'box-review-key.json').write_text(json.dumps(key))
    print({k: len(v) for k, v in key.items()}, 'sheets', {k: -(-len(v) // per) for k, v in key.items()})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--selection', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args(); main(a.selection, Path(a.out))
