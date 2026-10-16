"""Point-relabelling sheets (engineering review, not expert). Shows ONLY original pixels + a source-pixel grid:
no source boxes, no model points. Region = face-oval bounding box from the product MediaPipe landmarks (label-free).
Tiles: side T = 0.5 x face width (landmarks 234-454), 15% overlap; each tile rendered at 640 px with grid lines every
G source px (G = nice step near 0.05 x face width) and source-px tick labels; 4 tiles per sheet.
"""
import json, math, sys
from pathlib import Path
import numpy as np, cv2

OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
NICE = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100]


def face_geometry(rp, w, h):
    L = rp['landmarks']; P = np.array([[l['x'] * w, l['y'] * h] for l in L])
    fw = float(np.hypot(*(P[234] - P[454])))
    oval = P[OVAL]; x0, y0 = oval.min(0); x1, y1 = oval.max(0)
    return fw, P, [max(0, int(x0)), max(0, int(y0)), min(w, int(math.ceil(x1))), min(h, int(math.ceil(y1)))]


def tiles_for(box, T):
    x0, y0, x1, y1 = box; step = max(1, int(T * 0.85)); out = []
    ys = list(range(y0, max(y0 + 1, y1 - T + 1), step)) or [y0]; xs = list(range(x0, max(x0 + 1, x1 - T + 1), step)) or [x0]
    if ys[-1] + T < y1: ys.append(max(y0, y1 - T))
    if xs[-1] + T < x1: xs.append(max(x0, x1 - T))
    for y in ys:
        for x in xs: out.append([x, y, min(x + T, x1), min(y + T, y1)])
    return out


def render_tile(img, t, G, S=640):
    x0, y0, x1, y1 = t; c = img[y0:y1, x0:x1]; f = S / max(c.shape[:2])
    c = cv2.resize(c, (max(1, round(c.shape[1] * f)), max(1, round(c.shape[0] * f))), interpolation=cv2.INTER_CUBIC)
    M = 46; can = np.full((S + M, S + M, 3), 255, np.uint8); can[M:M + c.shape[0], M:M + c.shape[1]] = c
    gx = (x0 // G + 1) * G
    while gx < x1:
        X = M + int((gx - x0) * f); cv2.line(can, (X, M), (X, M + c.shape[0]), (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(can, str(gx), (X - 14, 30), cv2.FONT_HERSHEY_SIMPLEX, .38, (0, 0, 0), 1); gx += G
    gy = (y0 // G + 1) * G
    while gy < y1:
        Y = M + int((gy - y0) * f); cv2.line(can, (M, Y), (M + c.shape[1], Y), (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(can, str(gy), (1, Y + 4), cv2.FONT_HERSHEY_SIMPLEX, .38, (0, 0, 0), 1); gy += G
    return can


def main(pack, replay_files, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    man = json.loads((Path(pack) / 'manifest.json').read_text()); rp = {}
    for f in replay_files:
        for l in open(f): r = json.loads(l); rp[r['sha256']] = r
    index = []
    for it in man:
        if it['kind'] != 'positive-photo': continue
        img = cv2.imread(str(Path(pack) / it['file'])); h, w = img.shape[:2]
        fw, P, box = face_geometry(rp[it['sha256']], w, h); T = max(48, int(round(0.5 * fw)))
        G = min(NICE, key=lambda g: abs(g - 0.05 * fw)); tl = tiles_for(box, T); ph = it['sha256'][:12]
        sheets = []
        for s0 in range(0, len(tl), 4):
            cells = [render_tile(img, t, G) for t in tl[s0:s0 + 4]]
            while len(cells) < 4: cells.append(np.full_like(cells[0], 255))
            for k, t in enumerate(tl[s0:s0 + 4]):
                cv2.putText(cells[k], f'{ph} T{s0 + k + 1} [{t[0]},{t[1]}-{t[2]},{t[3]}]', (48, 12), cv2.FONT_HERSHEY_SIMPLEX, .38, (200, 0, 0), 1)
            sheet = np.vstack([np.hstack(cells[:2]), np.hstack(cells[2:])]); fn = f'{ph}-s{s0 // 4 + 1:02d}.jpg'
            cv2.imwrite(str(out / fn), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92]); sheets.append(fn)
        index.append(dict(sha256=it['sha256'], photo=ph, width=w, height=h, faceWidthPx=round(fw, 1), faceBox=box, tilePx=T, gridPx=G,
                          tiles=[dict(id=f'T{i + 1}', rect=t) for i, t in enumerate(tl)], sheets=sheets))
    (out / 'index.json').write_text(json.dumps(index, indent=1))
    print(sum(len(i['tiles']) for i in index), 'tiles', sum(len(i['sheets']) for i in index), 'sheets')


if __name__ == '__main__': main(sys.argv[1], sys.argv[2:4], sys.argv[4])
