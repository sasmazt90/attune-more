"""Convert layer-1 review marks (sheet display px) to source px. Each mark: [sheetNo, sx, sy, CAT, note].
Sheet layout: 2x2 cells of 686 px (46 px margin + 640 px tile). Tile k on sheet s = (s-1)*4 + row*2 + col.
Coverage per photo: {"tiles": {"T3": "partial"|"not_reviewable"}, "exclude": [[x0,y0,x1,y1],...] (source px), "flags": [...]}.
Merge: same category within 0.015 x face width -> one point (mean)."""
import json, sys
from pathlib import Path

CATS = {'TARGET', 'BLACKHEAD', 'SCAR_PIGMENT', 'PORE', 'MOLE', 'OTHER', 'UNCERTAIN'}
IDX = {i['photo']: i for i in json.load(open(Path(__file__).parent / 'sheets/index.json'))}


def to_src(photo, s, sx, sy):
    it = IDX[photo]; col, row = int(sx // 686), int(sy // 686); k = (s - 1) * 4 + row * 2 + col
    t = it['tiles'][k]['rect']; f = 640 / max(t[2] - t[0], t[3] - t[1])
    lx, ly = sx - col * 686 - 46, sy - row * 686 - 46
    assert -2 <= lx <= 642 and -2 <= ly <= 642, (photo, s, sx, sy)
    x, y = t[0] + lx / f, t[1] + ly / f
    assert t[0] - 2 <= x <= t[2] + 2 and t[1] - 2 <= y <= t[3] + 2, (photo, s, sx, sy, t)
    return round(x, 1), round(y, 1), it['tiles'][k]['id']


def build(photo, marks, cov):
    # mark sheet number 0 = point read directly in source px from a label-free zoom/overview grid (zoom.py)
    it = IDX[photo]; r = 0.015 * it['faceWidthPx']; pts = []
    for m in marks:
        s, sx, sy, c = m[:4]; assert c in CATS, c
        x, y, tid = (float(sx), float(sy), 'Z') if s == 0 else to_src(photo, s, sx, sy); pts.append(dict(x=x, y=y, cat=c, tiles=[tid], note=m[4] if len(m) > 4 else ''))
    merged = []
    for p in pts:
        q = next((q for q in merged if q['cat'] == p['cat'] and ((q['x'] - p['x']) ** 2 + (q['y'] - p['y']) ** 2) ** .5 <= r), None)
        if q is None: merged.append(dict(p, n=1)); continue
        n = q['n']; q['x'] = round((q['x'] * n + p['x']) / (n + 1), 1); q['y'] = round((q['y'] * n + p['y']) / (n + 1), 1); q['n'] = n + 1; q['tiles'] += p['tiles']
        q['note'] = q['note'] or p['note']
    return dict(photo=photo, sha256=it['sha256'], faceWidthPx=it['faceWidthPx'], mergeRadiusPx=round(r, 1), coverage=cov,
                points=[dict(id=f'P{i + 1}', **{k: v for k, v in p.items()}) for i, p in enumerate(merged)], rawMarks=marks)


if __name__ == '__main__':
    raw = json.load(open(sys.argv[1])); out = Path(sys.argv[2]); out.mkdir(exist_ok=True)
    for ph, d in raw.items():
        L = build(ph, d['marks'], d['coverage']); (out / f'{ph}.json').write_text(json.dumps(L, indent=1))
        from collections import Counter
        print(ph, dict(Counter(p['cat'] for p in L['points'])))
