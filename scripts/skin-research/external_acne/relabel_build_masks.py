"""Layer-1 reviewed-coverage masks (protocol acne-point-relabel-protocol-1, review.coverage).
mask = face-oval polygon - (eyes, brows dilated 0.03 fw) - lips, ∩ tiles not marked not_reviewable, - exclusion rectangles.
Declared before opening source labels / model points: photos flagged collage / closeup_not_full_face get an EMPTY mask
(the landmark face oval does not describe the reviewed skin there), so no negative claims are made on them; their TARGET
points still count as targets. Writes relabel/masks/<photo>.png (0/255) and relabel/masks/stats.json.
"""
import json, sys
from pathlib import Path
import numpy as np, cv2

R = Path(__file__).parent
sys.path.insert(0, str(R)); from make_label_sheets import OVAL
EYE_L = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
EYE_R = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]
BROW_L = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
BROW_R = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
LIPS = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
NO_NEG = {'collage', 'closeup_not_full_face'}


def landmarks(replay_files):
    rp = {}
    for f in replay_files:
        for l in open(f): r = json.loads(l); rp[r['sha256']] = r
    return rp


def build(label, idx, rp, w, h):
    m = np.zeros((h, w), np.uint8); flags = set(label['coverage'].get('flags', []))
    L = rp[label['sha256']]['landmarks']; P = np.array([[l['x'] * w, l['y'] * h] for l in L], np.float32); fw = label['faceWidthPx']
    if flags & NO_NEG: return m, 'empty: ' + ','.join(sorted(flags & NO_NEG))
    cv2.fillPoly(m, [np.round(P[OVAL]).astype(np.int32)], 255)
    cut = np.zeros_like(m)
    for g in (EYE_L, EYE_R, BROW_L, BROW_R): cv2.fillPoly(cut, [cv2.convexHull(np.round(P[g]).astype(np.int32))], 255)
    k = max(1, int(round(0.03 * fw))); cut = cv2.dilate(cut, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    cv2.fillPoly(cut, [cv2.convexHull(np.round(P[LIPS]).astype(np.int32))], 255); m[cut > 0] = 0
    tiles = {t['id']: t['rect'] for t in idx['tiles']}; status = label['coverage'].get('tiles', {})
    rev = np.zeros_like(m)
    for tid, (x0, y0, x1, y1) in tiles.items():
        if status.get(tid) != 'not_reviewable': rev[y0:y1, x0:x1] = 255
    m[rev == 0] = 0
    for x0, y0, x1, y1 in label['coverage'].get('exclude', []): m[max(0, y0):y1, max(0, x0):x1] = 0
    return m, 'face-oval minus eyes/brows/lips, reviewable tiles, minus exclusions'


if __name__ == '__main__':
    pack = Path(sys.argv[1]); rp = landmarks(sys.argv[2:4]); out = R / 'masks'; out.mkdir(exist_ok=True)
    man = {m['sha256']: m for m in json.load(open(pack / 'manifest.json'))}; IDX = {i['photo']: i for i in json.load(open(R / 'sheets/index.json'))}
    stats = {}
    for f in sorted((R / 'labels').glob('*.json')):
        lab = json.load(open(f)); ph = lab['photo']; it = man[lab['sha256']]; w, h = IDX[ph]['width'], IDX[ph]['height']
        m, how = build(lab, IDX[ph], rp, w, h); cv2.imwrite(str(out / f'{ph}.png'), m)
        inside = sum(1 for p in lab['points'] if p['cat'] == 'TARGET' and 0 <= int(p['y']) < h and 0 <= int(p['x']) < w and m[int(p['y']), int(p['x'])])
        stats[ph] = dict(maskPx=int((m > 0).sum()), maskFracOfImage=round(float((m > 0).mean()), 4), rule=how,
                         targets=sum(p['cat'] == 'TARGET' for p in lab['points']), targetsInsideMask=inside, flags=lab['coverage'].get('flags', []))
        print(ph, stats[ph])
    (out / 'stats.json').write_text(json.dumps(stats, indent=1))
