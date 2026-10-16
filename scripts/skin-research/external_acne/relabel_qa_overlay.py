"""Layer-1 self-check overlay: only my own review points (no source labels, no model points). Colour = my review category."""
import json, sys, cv2
from pathlib import Path
COL = {'TARGET': (0, 0, 255), 'UNCERTAIN': (0, 200, 255), 'SCAR_PIGMENT': (255, 0, 255), 'BLACKHEAD': (0, 0, 0), 'PORE': (128, 128, 128), 'MOLE': (255, 0, 0), 'OTHER': (0, 255, 0)}
man = {m['sha256'][:12]: m for m in json.load(open('../pack/manifest.json')) if m['kind'] == 'positive-photo'}
for ph in sys.argv[1:]:
    L = json.load(open(f'labels/{ph}.json')); img = cv2.imread(f"../pack/{man[ph]['file']}"); fb = json.load(open('sheets/index.json'))
    box = next(i for i in fb if i['photo'] == ph)['faceBox']; r = max(4, int(0.03 * L['faceWidthPx']))
    for p in L['points']:
        cv2.circle(img, (int(p['x']), int(p['y'])), r, COL[p['cat']], max(1, r // 6)); cv2.putText(img, p['id'], (int(p['x']) + r, int(p['y'])), 0, max(.3, r / 30), COL[p['cat']], 1)
    c = img[box[1]:box[3], box[0]:box[2]]; s = 1300 / max(c.shape[:2]); c = cv2.resize(c, None, fx=s, fy=s)
    Path('qa').mkdir(exist_ok=True); cv2.imwrite(f'qa/{ph}.jpg', c, [cv2.IMWRITE_JPEG_QUALITY, 88])
