"""Legend figures for the common-scope comparison (photo pixels: not committed). Colours encode STATUS only:
ring green/red = in-scope layer-1 TARGET found/missed by this row; small grey ring = UNCERTAIN; dashed? no: purple ring = TARGET outside the
common scope (not counted); blue dot = matched prediction; open blue circle = duplicate; red X = false point on reviewed skin;
grey dot = on UNCERTAIN/other/out-of-scope target; yellow dot = unreviewed or non-skin; cyan line = reviewed-skin mask."""
import json, sys
from pathlib import Path
import numpy as np, cv2
W = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
o = json.load(open(W / 'common-scope-results.json')); L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']
man = {m['sha256'][:12]: m for m in json.load(open(W / 'pack/manifest.json'))}; rows = json.load(open(W / 'regen/all-rows.json')); step0 = {}
for f in ('step0/dev.jsonl', 'step0/devext.jsonl'):
    for l in open(W / f): r = json.loads(l); step0[r['sha256'][:12]] = r['final']
def preds(k, ph):
    if k == 'step0-final': return step0[ph]
    if k == 'step0-before-filter': return json.load(open(W / 'trace/acne-step0-trace' / f'{ph}.json'))['nms']
    return [r for r in rows[k] if r['sha'][:12] == ph][0]['final']
LEG = ['ring green = in-scope TARGET found by this row   ring red = in-scope TARGET missed   purple ring = TARGET outside common scope (not counted)   small grey ring = UNCERTAIN',
       'blue dot = matched prediction (<= 0.03 face width)   open blue circle = duplicate   red X = false point on reviewed skin   grey dot = on UNCERTAIN/other/out-of-scope target',
       'yellow dot = unreviewed area or non-skin (outside face oval)   cyan line = reviewed-skin mask (same for every row)']
KEYS = ['step0-final', 'step0-before-filter', 'dewiin-anyacne/tiles', 'tristan-gray/tiles', 'carsten12/tiles']
for ph in sys.argv[3].split(','):
    img0 = cv2.imread(str(W / 'pack' / man[ph]['file'])); mask = cv2.imread(str(W / 'layer1/masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE)
    ys, xs = np.where(mask > 0); L = L1[ph]
    x0, x1 = max(0, xs.min() - 30), min(img0.shape[1], xs.max() + 30); y0, y1 = max(0, ys.min() - 30), min(img0.shape[0], ys.max() + 30)
    P = 560; f = P / (x1 - x0); panels = []
    for k in KEYS:
        c = cv2.resize(img0[y0:y1, x0:x1], (P, int((y1 - y0) * f)), interpolation=cv2.INTER_AREA); T = lambda x, y: (int((x - x0) * f), int((y - y0) * f))
        mm = cv2.resize((mask[y0:y1, x0:x1] > 0).astype(np.uint8), (c.shape[1], c.shape[0]), interpolation=cv2.INTER_NEAREST)
        cnt, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(c, cnt, -1, (255, 255, 0), 1)
        R = o['perPhotoClasses'][k][ph]; rad = max(6, int(0.03 * L['faceWidthPx'] * f)); hits = set(R['hitIds'])
        for p in L['points']:
            q = T(p['x'], p['y'])
            if p['cat'] == 'TARGET':
                col = (180, 0, 180) if p['id'] in R['outOfScope'] else ((0, 200, 0) if p['id'] in hits else (0, 0, 255)); cv2.circle(c, q, rad, col, 2)
            elif p['cat'] == 'UNCERTAIN': cv2.circle(c, q, max(3, rad // 2), (150, 150, 150), 1)
        for b, cl in zip(preds(k, ph), R['classes']):
            q = T((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            if cl == 'matched': cv2.circle(c, q, 4, (255, 80, 0), -1)
            elif cl == 'duplicate': cv2.circle(c, q, 5, (255, 80, 0), 1)
            elif cl == 'false': cv2.drawMarker(c, q, (0, 0, 255), cv2.MARKER_TILTED_CROSS, 11, 2)
            elif cl in ('onUncertain', 'onOther', 'nearOutOfScopeTarget'): cv2.circle(c, q, 3, (120, 120, 120), -1)
            elif 0 <= q[0] < c.shape[1] and 0 <= q[1] < c.shape[0]: cv2.circle(c, q, 3, (0, 220, 255), -1)
        t = o['table'][k]['perPhoto'][ph]; hd = np.full((30, P, 3), 255, np.uint8)
        cv2.putText(hd, f"{k}: found {t['found']}/{t['targets']}  false {t['false']}  dup {t['duplicate']}", (4, 21), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1)
        panels.append(np.vstack([hd, c]))
    h = max(p.shape[0] for p in panels); panels = [np.vstack([p, np.full((h - p.shape[0], P, 3), 255, np.uint8)]) for p in panels]
    top = np.hstack(panels); leg = np.full((72, top.shape[1], 3), 255, np.uint8)
    for i, s in enumerate(LEG): cv2.putText(leg, s, (6, 20 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1)
    cv2.putText(leg, ph, (top.shape[1] - 160, 20), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1)
    cv2.imwrite(str(out / f'common-{ph}.jpg'), np.vstack([top, leg]), [cv2.IMWRITE_JPEG_QUALITY, 86])
