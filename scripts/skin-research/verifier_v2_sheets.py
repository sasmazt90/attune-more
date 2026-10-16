"""Blind review sheets for the fixed v2 review list (local only; photos never go to Git).
Per candidate: review id, tight crop (+-max(10 px, .05 face width)), near context (+-.15 fw), face context (+-.6 fw), each 200 px,
marker = 4 ticks around the candidate centre (centre left visible). No pool, v1 label, box or score is drawn."""
import json, sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import verifier_extract as X

S = 200; PER = 10


def view(img, c, half, ticks):
    x0, y0 = int(round(c[0] - half)), int(round(c[1] - half)); n = max(2, int(round(2 * half))); can = np.zeros((n, n, 3), np.uint8)
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(img.shape[1], x0 + n), min(img.shape[0], y0 + n)
    if sx1 > sx0 and sy1 > sy0: can[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = img[sy0:sy1, sx0:sx1]
    can = cv2.resize(can, (S, S), interpolation=cv2.INTER_CUBIC if n < S else cv2.INTER_AREA); m = S // 2; g, l = ticks
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cv2.line(can, (m + dx * g, m + dy * g), (m + dx * (g + l), m + dy * (g + l)), (0, 255, 255), 2)
    return can


def main(sub='acne-verifier-v2'):
    """sub: audit-results/<sub> holding review-list.json (v2 default; v3: acne-verifier-v3)."""
    o = CODE / 'audit-results' / sub; L = json.loads((o / 'review-list.json').read_text())['items']
    files = {s[:12]: f for s, k, f, rp, _ in X.items('train')}; (o / 'sheets').mkdir(exist_ok=True); cache = {}
    for sh in range(0, len(L), PER):
        blocks = []
        for it in L[sh:sh + PER]:
            if it['photo'] not in cache: cache = {it['photo']: cv2.imread(files[it['photo']])}
            img = cache[it['photo']]; b = it['box']; c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2); fw = it['fwPx']
            tiles = [view(img, c, max(10., .05 * fw), (34, 22)), view(img, c, .15 * fw, (22, 16)), view(img, c, .6 * fw, (8, 12))]
            head = np.full((26, 3 * S + 8, 3), 255, np.uint8); cv2.putText(head, it['rid'], (4, 20), 0, .7, (0, 0, 0), 2)
            row = np.hstack([tiles[0], np.full((S, 4, 3), 255, np.uint8), tiles[1], np.full((S, 4, 3), 255, np.uint8), tiles[2]])
            blocks.append(np.vstack([head, row]))
        while len(blocks) % 2: blocks.append(np.full_like(blocks[0], 255))
        rows = [np.hstack([blocks[i], np.full((blocks[i].shape[0], 20, 3), 255, np.uint8), blocks[i + 1]]) for i in range(0, len(blocks), 2)]
        sheet = np.vstack([np.vstack([r, np.full((10, r.shape[1], 3), 255, np.uint8)]) for r in rows])
        cv2.imwrite(str(o / 'sheets' / f'sheet-{sh // PER + 1:02d}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(len(L), 'items', (len(L) + PER - 1) // PER, 'sheets')


if __name__ == '__main__': main(*sys.argv[1:2])
