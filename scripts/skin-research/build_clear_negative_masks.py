"""Conservative known-negative skin masks for the 42 screened Kaggle Clear photos (source pixels, native 250x250).

Review level: 'assistant-engineering' (MediaPipe landmark geometry + colour exclusion + assistant visual check of overlays).
NOT human/dermatologist verified, NOT microlesion absence, NOT a whole-image negative.
Included: both cheeks, central forehead, nose bridge.  Excluded (UNKNOWN): eyes, brows, lips, nostrils, chin/perioral
(beard/stubble risk), hairline, background, and pixels far from the photo's own skin colour (hair, shadow, glare).
Roles are fixed by person group before any model output: sha256(group) % 10 < 7 -> TRAIN, else DEV.
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np, cv2
CODE = Path(__file__).resolve().parents[2]
D = CODE / 'audit-results/acne-v4-data'; OUT = D / 'clear-masks'
CHEEK_L = [116, 117, 118, 119, 100, 142, 203, 206, 216, 192, 213, 147, 123]
CHEEK_R = [345, 346, 347, 348, 329, 371, 423, 426, 436, 416, 433, 376, 352]
FOREHEAD = [67, 109, 10, 338, 297, 299, 337, 151, 108, 69]
BRIDGE = [168, 417, 351, 6, 122, 193]


def role_of(group): return 'TRAIN' if int(hashlib.sha256(group.encode()).hexdigest(), 16) % 10 < 7 else 'DEV'


def main(rejects=()):
    man = json.loads((D / 'clear/manifest.json').read_text())
    lms = {json.loads(l)['sha256']: json.loads(l) for l in (OUT / 'landmarks.jsonl').read_text().splitlines()}
    rows = []
    for r in man:
        raw = (D / 'clear' / r['photo']).read_bytes(); assert hashlib.sha256(raw).hexdigest() == r['sha256']
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR); h, w = img.shape[:2]
        L = lms[r['sha256']]; pts = np.array([[p['x'] * w, p['y'] * h] for p in L['landmarks']], np.float32)
        mask = np.zeros((h, w), np.uint8)
        for poly in (CHEEK_L, CHEEK_R, FOREHEAD, BRIDGE): cv2.fillPoly(mask, [pts[poly].round().astype(np.int32)], 255)
        mask = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=2)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        ref = np.median(lab[mask > 0], 0); dist = np.linalg.norm(lab - ref, axis=2)
        tol = max(12., 2.5 * np.median(dist[mask > 0]))
        keep = (mask > 0) & (dist <= tol) & (lab[..., 0] < 245)
        keep = cv2.morphologyEx(keep.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
        status = 'REJECTED_BY_VISUAL_CHECK' if r['sha256'][:8] in rejects else 'ENGINEERING_NEGATIVE_ROI'
        if status != 'ENGINEERING_NEGATIVE_ROI': keep[:] = False
        cv2.imwrite(str(OUT / f'{r["sha256"][:16]}-mask.png'), keep.astype(np.uint8) * 255)
        ov = img.copy(); ov[keep] = (.55 * ov[keep] + .45 * np.array([0, 210, 0])).astype(np.uint8)
        rows.append(dict(sha256=r['sha256'], photo=r['photo'], personGroup=r['filename_person_group'], role=role_of(r['filename_person_group']),
                         width=w, height=h, status=status, negativePixels=int(keep.sum()), maskFile=f'{r["sha256"][:16]}-mask.png',
                         reviewLevel='assistant-engineering (landmark geometry + colour exclusion + assistant overlay check); not human/expert verified',
                         excluded='eyes, brows, lips, nostrils, chin/perioral, hairline, background, off-skin-colour pixels', source=r['source_path'], rights=r['rights'],
                         nativeResolution='250x250; used at native scale with padding, never upsampled'))
        rows[-1]['_ov'] = ov
    sheets = []
    for s in range(0, len(rows), 21):
        chunk = rows[s:s + 21]; sheet = np.full((3 * 270, 7 * 260, 3), 255, np.uint8)
        for i, r in enumerate(chunk):
            y, x = divmod(i, 7); sheet[y * 270 + 18:y * 270 + 268, x * 260:x * 260 + 250] = r['_ov']
            cv2.putText(sheet, f'{s + i + 1}:{r["sha256"][:8]}', (x * 260 + 2, y * 270 + 14), cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 0, 0), 1)
        p = OUT / f'review-sheet-{s // 21 + 1}.png'; cv2.imwrite(str(p), sheet); sheets.append(p.name)
    for r in rows: r.pop('_ov')
    (OUT / 'clear-negative-masks.json').write_text(json.dumps(dict(version='clear-negative-masks-v1', rejectedAfterVisualCheck=sorted(rejects), sheets=sheets, rows=rows), indent=1))
    print({k: sum(1 for r in rows if r['role'] == k and r['status'] == 'ENGINEERING_NEGATIVE_ROI') for k in ('TRAIN', 'DEV')}, 'pixels median', int(np.median([r['negativePixels'] for r in rows])))


if __name__ == '__main__': main(tuple(sys.argv[1:]))
