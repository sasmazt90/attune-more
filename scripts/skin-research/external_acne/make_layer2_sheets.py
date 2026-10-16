"""Layer 2 (post-hoc, model/source-assisted) review sheets. Scope fixed before any sheet is viewed:
  A) every 'false point on reviewed skin' of Step0, Dewiin no-acne model/tiles and tristan-gray/tiles at r = 0.03 fw,
     clustered per photo within r (one item per physical spot; which model(s) made it is hidden on the sheet);
  B) every source box that contains no layer-1 point and whose centre lies in the reviewed mask (source box drawn).
Each cell: left = zoom (A: +-0.06 fw around the point, crosshair with an open centre; B: box + margin), right = context
(+-0.2 fw, small ring/box). Items are shuffled with a fixed seed across photos. Layer 1 is not changed by this review."""
import json, random, sys
from pathlib import Path
import numpy as np, cv2


def crop(img, cx, cy, half, S):
    h, w = img.shape[:2]; x0, y0 = int(round(cx - half)), int(round(cy - half)); n = int(round(2 * half))
    can = np.zeros((n, n, 3), np.uint8)
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(w, x0 + n), min(h, y0 + n)
    if sx1 > sx0 and sy1 > sy0: can[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = img[sy0:sy1, sx0:sx1]
    f = S / n; return cv2.resize(can, (S, S), interpolation=cv2.INTER_CUBIC), (x0, y0, f)


def cell(img, it, fw, S=210):
    if it['kind'] == 'A':
        cx, cy = it['x'], it['y']; z, (x0, y0, f) = crop(img, cx, cy, max(8., .06 * fw), S); c = S // 2; g = 9; L = 22
        for a, b in (((c - g - L, c), (c - g, c)), ((c + g, c), (c + g + L, c)), ((c, c - g - L), (c, c - g)), ((c, c + g), (c, c + g + L))):
            cv2.line(z, a, b, (0, 255, 255), 2)
        k, (kx, ky, kf) = crop(img, cx, cy, .2 * fw, S); cv2.circle(k, (S // 2, S // 2), 12, (0, 255, 255), 2)
    else:
        b = it['box']; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; half = max(.75 * max(b[2] - b[0], b[3] - b[1]), .06 * fw)
        z, (x0, y0, f) = crop(img, cx, cy, half, S)
        cv2.rectangle(z, (int((b[0] - x0) * f), int((b[1] - y0) * f)), (int((b[2] - x0) * f), int((b[3] - y0) * f)), (255, 0, 255), 1)
        k, (kx, ky, kf) = crop(img, cx, cy, max(.2 * fw, 1.5 * half), S)
        cv2.rectangle(k, (int((b[0] - kx) * kf), int((b[1] - ky) * kf)), (int((b[2] - kx) * kf), int((b[3] - ky) * kf)), (255, 0, 255), 1)
    out = np.full((S + 22, 2 * S + 6, 3), 255, np.uint8); out[22:, :S] = z; out[22:, S + 6:] = k
    cv2.putText(out, it['id'], (3, 16), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 1); return out


def main(W, scope_out, sheet_dir):
    W = Path(W); scope = json.load(open(scope_out)); man = {m['sha256'][:12]: m for m in json.load(open(W / 'pack/manifest.json'))}
    L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']; out = Path(sheet_dir); out.mkdir(parents=True, exist_ok=True)
    cache = {}; cells = []
    for it in scope['items']:
        ph = it['photo']
        if ph not in cache: cache[ph] = cv2.imread(str(W / 'pack' / man[ph]['file']))
        cells.append(cell(cache[ph], it, L1[ph]['faceWidthPx']))
    per = 16
    for s in range(0, len(cells), per):
        cs = cells[s:s + per]
        while len(cs) < per: cs.append(np.full_like(cells[0], 255))
        rows = [np.hstack(cs[i:i + 4]) for i in range(0, per, 4)]
        cv2.imwrite(str(out / f'l2-{s // per + 1:02d}.jpg'), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(len(cells), 'cells')


if __name__ == '__main__': main(*sys.argv[1:4])
