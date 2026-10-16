"""Reviewed-skin masks for the unused-test labels (rule in labels.json, fixed before inference). Writes audit-results/acne-unused-test/masks/<ph>.png
and adds mask hashes to labels-frozen.json. No model output is read."""
import hashlib, json, sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; O = CODE / 'audit-results/acne-unused-test'
sys.path[:0] = [str(HERE / 'external_acne')]
from make_label_sheets import OVAL
EYE_L = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
EYE_R = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]
BROW_L = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
BROW_R = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]


def main():
    lab = json.loads((O / 'labels.json').read_text()); rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}
    (O / 'masks').mkdir(exist_ok=True)
    for ph, p in lab['photos'].items():
        img = cv2.imread(str(O / 'photos' / (p['sha256'][:16] + '.jpg'))); h, w = img.shape[:2]
        P = np.array([[l['x'] * w, l['y'] * h] for l in rp[p['sha256']]['landmarks']], np.float32)
        m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [np.round(P[OVAL]).astype(np.int32)], 255)
        cut = np.zeros_like(m)
        for g in (EYE_L, EYE_R, BROW_L, BROW_R): cv2.fillPoly(cut, [cv2.convexHull(np.round(P[g]).astype(np.int32))], 255)
        k = max(1, int(round(.03 * p['faceWidthPx']))); cut = cv2.dilate(cut, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
        cv2.fillPoly(cut, [cv2.convexHull(np.round(P[LIPS]).astype(np.int32))], 255); m[cut > 0] = 0
        for x0, y0, x1, y1 in p['coverage']['exclude']: m[max(0, y0):y1, max(0, x0):x1] = 0
        black = (img.max(2) < 12).astype(np.uint8); black = cv2.dilate(black, np.ones((7, 7), np.uint8)); m[black > 0] = 0
        cv2.imwrite(str(O / 'masks' / f'{ph}.png'), m)
        p['mask'] = dict(file=f'masks/{ph}.png', sha256=hashlib.sha256((O / 'masks' / f'{ph}.png').read_bytes()).hexdigest(), maskPx=int((m > 0).sum()))
    s = json.dumps(lab, indent=1); (O / 'labels-frozen.json').write_text(s); print(hashlib.sha256(s.encode()).hexdigest(), {ph: p['mask']['maskPx'] for ph, p in lab['photos'].items()})


if __name__ == '__main__': main()
