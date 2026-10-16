"""Legend images (local only, not in Git): for each evaluated photo with >= 1 Step0 candidate, the same photo with the reviewed mask
outline and every Step0 point marked by what v1 and v3 decided, plus label points. Reads frozen labels and cached inference only."""
import json
from pathlib import Path
import numpy as np, cv2

CODE = Path(__file__).resolve().parents[2]; O = CODE / 'audit-results/acne-unused-test'
COL = {('keep', 'keep'): (0, 200, 0), ('keep', 'drop'): (0, 140, 255), ('drop', 'keep'): (255, 0, 255), ('drop', 'drop'): (0, 0, 255)}
TXT = {('keep', 'keep'): 'kept by v1 and v3', ('keep', 'drop'): 'kept by v1, removed by v3', ('drop', 'keep'): 'removed by v1, kept by v3', ('drop', 'drop'): 'removed by v1 and v3'}


def main():
    lab = json.loads((O / 'labels-frozen.json').read_text()); res = json.loads((CODE / 'docs/acne-unused-test-results-20261016.json').read_text())
    (O / 'figures').mkdir(exist_ok=True)
    for ph, L in lab['photos'].items():
        rec = json.loads((O / 'infer' / f'{ph}.json').read_text())
        if not rec['final']: continue
        img = cv2.imread(str(O / 'photos' / (L['sha256'][:16] + '.jpg'))); S = 2; img = cv2.resize(img, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
        m = cv2.imread(str(O / 'masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE); m = cv2.resize(m, None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)
        cs, _ = cv2.findContours((m > 0).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(img, cs, -1, (255, 255, 0), 1)
        for p in L['points']: cv2.drawMarker(img, (int(p['x'] * S), int(p['y'] * S)), (255, 255, 255), cv2.MARKER_DIAMOND, 14, 1)
        cl = dict(zip(range(len(rec['final'])), res['perPhoto'][ph] and [None] * len(rec['final'])))
        for i, b in enumerate(rec['final']):
            k = ('keep' if rec['verifiers']['v1']['keep'][i] else 'drop', 'keep' if rec['verifiers']['v3']['keep'][i] else 'drop')
            c = (int((b[0] + b[2]) / 2 * S), int((b[1] + b[3]) / 2 * S)); cv2.circle(img, c, 10, COL[k], 2)
            cv2.putText(img, f"v1 {rec['verifiers']['v1']['proba'][i]:.2f} / v3 {rec['verifiers']['v3']['proba'][i]:.2f}", (c[0] + 12, c[1] + 4), 0, .45, COL[k], 1)
        h = np.full((26 * 7, img.shape[1], 3), 255, np.uint8); y = 20
        for k, t in TXT.items(): cv2.circle(h, (14, y - 5), 7, COL[k], 2); cv2.putText(h, 'Step0 point ' + t, (30, y), 0, .5, (0, 0, 0), 1); y += 26
        cv2.drawMarker(h, (14, y - 5), (120, 120, 120), cv2.MARKER_DIAMOND, 14, 1); cv2.putText(h, 'review label (uncertain / mole / pigment / other); no TARGET in this set', (30, y), 0, .5, (0, 0, 0), 1); y += 26
        cv2.line(h, (6, y - 5), (22, y - 5), (255, 200, 0), 2); cv2.putText(h, 'reviewed skin mask outline; numbers = verifier probabilities. Research only.', (30, y), 0, .5, (0, 0, 0), 1)
        cv2.imwrite(str(O / 'figures' / f'{ph}-step0-v1-v3.jpg'), np.vstack([img, h]), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(sorted(p.name for p in (O / 'figures').glob('*.jpg')))


if __name__ == '__main__': main()
