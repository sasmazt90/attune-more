"""Fixed-legend figures (not committed: contain photo pixels). Per photo: one panel per model.
Shapes/colours: layer-1 TARGET = ring (green if matched by this model, red if missed); UNCERTAIN = small grey ring;
other layer-1 categories = blue square; predictions = box centres: blue dot matched, red X false on reviewed skin,
open blue circle duplicate, grey dot on uncertain/other category, yellow dot unreviewed or outside face oval.
Reviewed-skin mask = cyan contour. Colours therefore encode STATUS (layer-1 class or match result), never model class."""
import json, sys
from pathlib import Path
import numpy as np, cv2

def panel(img, mask, L, preds, classes, hits, title, W=760):
    m = (mask > 0).astype(np.uint8); ys, xs = np.where(m) if m.any() else (np.array([0, img.shape[0]-1]), np.array([0, img.shape[1]-1]))
    pts = np.array([[p['x'], p['y']] for p in L['points']] + [[(b[0]+b[2])/2, (b[1]+b[3])/2] for b in preds] or [[0, 0]])
    x0 = int(max(0, min(xs.min(), pts[:, 0].min()) - 20)); x1 = int(min(img.shape[1], max(xs.max(), pts[:, 0].max()) + 20))
    y0 = int(max(0, min(ys.min(), pts[:, 1].min()) - 20)); y1 = int(min(img.shape[0], max(ys.max(), pts[:, 1].max()) + 20))
    c = img[y0:y1, x0:x1].copy(); f = W / c.shape[1]; c = cv2.resize(c, (W, int(c.shape[0] * f)), interpolation=cv2.INTER_AREA)
    T = lambda x, y: (int((x - x0) * f), int((y - y0) * f))
    mm = cv2.resize(m[y0:y1, x0:x1], (c.shape[1], c.shape[0]), interpolation=cv2.INTER_NEAREST)
    cnt, _ = cv2.findContours(mm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(c, cnt, -1, (255, 255, 0), 1)
    R = max(7, int(0.03 * L['faceWidthPx'] * f))
    for p in L['points']:
        q = T(p['x'], p['y'])
        if p['cat'] == 'TARGET': cv2.circle(c, q, R, (0, 200, 0) if p['id'] in hits else (0, 0, 255), 2)
        elif p['cat'] == 'UNCERTAIN': cv2.circle(c, q, max(4, R // 2), (150, 150, 150), 1)
        else: cv2.rectangle(c, (q[0]-5, q[1]-5), (q[0]+5, q[1]+5), (255, 0, 0), 1)
    for b, k in zip(preds, classes):
        q = T((b[0]+b[2])/2, (b[1]+b[3])/2)
        if k == 'matched': cv2.circle(c, q, 4, (255, 80, 0), -1)
        elif k == 'falseReviewed': cv2.drawMarker(c, q, (0, 0, 255), cv2.MARKER_TILTED_CROSS, 12, 2)
        elif k == 'duplicate': cv2.circle(c, q, 5, (255, 80, 0), 1)
        elif k == 'onUncertain' or k.startswith('onOther'): cv2.circle(c, q, 3, (120, 120, 120), -1)
        else: cv2.circle(c, q, 3, (0, 220, 255), -1)
    out = np.full((c.shape[0] + 34, W, 3), 255, np.uint8); out[34:] = c
    cv2.putText(out, title, (4, 23), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1); return out

LEGEND = ['ring green = layer-1 TARGET found by this model   ring red = layer-1 TARGET missed   small grey ring = layer-1 UNCERTAIN   blue square = other layer-1 category',
          'blue dot = prediction matched (<= 0.03 face width)   open blue circle = duplicate   red X = false point on reviewed skin',
          'grey dot = prediction on UNCERTAIN/other category   yellow dot = prediction outside reviewed skin (unreviewed / outside face oval)   cyan line = reviewed-skin mask']

def main(W, out, photos, models):
    W = Path(W); R = json.load(open(W / 'relabel-results.json')); L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']
    man = {m['sha256'][:12]: m for m in json.load(open(W / 'pack/manifest.json'))}; rows = json.load(open(W / 'regen/all-rows.json')); step0 = {}
    for f in ('step0/dev.jsonl', 'step0/devext.jsonl'):
        for l in open(W / f): r = json.loads(l); step0[r['sha256'][:12]] = r['final']
    Path(out).mkdir(parents=True, exist_ok=True)
    for ph in photos.split(','):
        img = cv2.imread(str(W / 'pack' / man[ph]['file'])); mask = cv2.imread(str(W / 'layer1/masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE)
        ps = []
        for k in models.split(','):
            preds = step0[ph] if k.startswith('step0') else [r for r in rows[k] if r['sha'][:12] == ph][0]['final']
            d = R['perPhotoDetail'][k][ph]
            ps.append(panel(img, mask, L1[ph], [b[:4] for b in preds], d['classes'], set(d['hitIds']), f"{k} | {ph} | found {d['hits']}/{d['targets']} | false {d['classes'].count('falseReviewed')}"))
        h = max(p.shape[0] for p in ps); ps = [np.vstack([p, np.full((h - p.shape[0], p.shape[1], 3), 255, np.uint8)]) for p in ps]
        top = np.hstack(ps); leg = np.full((70, top.shape[1], 3), 255, np.uint8)
        for i, t in enumerate(LEGEND): cv2.putText(leg, t, (6, 20 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1)
        cv2.imwrite(str(Path(out) / f'relabel-{ph}.jpg'), np.vstack([top, leg]), [cv2.IMWRITE_JPEG_QUALITY, 88])

if __name__ == '__main__': main(*sys.argv[1:5])
