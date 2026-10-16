"""Per-target stage records for Step0 on the frozen layer-1 TARGET points (protocol acne-point-relabel-protocol-1, r = 0.03 fw).

Uses only the observed Step0 trace (audit-results/acne-step0-trace, final boxes verified equal to the stored rows) and the
frozen layer-1 JSON/masks. A box is 'near' a target when its CENTRE is within r (source px). Nearness is used only to follow a
target between stages; whether a target is found stays the frozen one-to-one result.

Stages per target (in chain order):
  S1 source/reviewed : inside image; inside the layer-1 reviewed mask
  S2 product crop    : inside the photo_input crop and inside a native tile rect (tile id, tile-local px, not in padding)
  S3 analysis raster : inside the product analysis raster (visible-region meshes + pad; origin/scale) and which visible
                       region envelope / acne_skin / hair / exclusion it falls on (masks mapped with (src - origin) * scale)
  S4 raw head        : best raw candidate (obj*cls >= .01) centre within r: score, tile
  S5 confidence      : a >= .30 candidate centre within r
  S6 NMS             : an NMS-selected box centre within r; else the suppressing box (higher score, IoU > .30 with the best near candidate)
  S7 filter          : near NMS boxes assigned / rejected (reasons)
  S8 final           : a final box centre within r; frozen one-to-one match (found / not found)
First loss = first stage that fails; every failing condition is listed in `causes`.
"""
import json, sys
from pathlib import Path
import numpy as np


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i; return i / u if u > 0 else 0.


def ctr(b): return ((b[0] + b[2]) / 2., (b[1] + b[3]) / 2.)


def near(boxes, p, r):
    return [b for b in boxes if np.hypot(ctr(b)[0] - p[0], ctr(b)[1] - p[1]) <= r]


def mask_at(M, key, p, tr):
    if key not in M: return None
    sx, sy = tr['scale'], tr['origin']; x = int((p[0] - sy[0]) * sx); y = int((p[1] - sy[1]) * sx)
    m = M[key]
    return bool(m[y, x]) if 0 <= y < m.shape[0] and 0 <= x < m.shape[1] else None


def trace_photo(tr, M, lab, l1mask, hit_ids, r):
    out = []
    for p in lab['points']:
        if p['cat'] != 'TARGET': continue
        q = (p['x'], p['y']); rec = dict(target=f"{tr['photo']}#{p['id']}", x=p['x'], y=p['y'], rPx=round(r, 1), found=p['id'] in hit_ids)
        rec['S1'] = dict(inImage=0 <= q[0] < tr['width'] and 0 <= q[1] < tr['height'],
                         inReviewedMask=bool(l1mask[int(q[1]), int(q[0])]) if l1mask is not None and l1mask.any() else None)
        c = tr['crop']; inside_rects = [i for i, t in enumerate(tr['rects']) if t[0] <= q[0] < t[2] and t[1] <= q[1] < t[3]]
        rec['S2'] = dict(inCrop=c['x'] <= q[0] < c['x'] + c['width'] and c['y'] <= q[1] < c['y'] + c['height'], tiles=inside_rects,
                         tileLocal=[[round(q[0] - tr['rects'][i][0], 1), round(q[1] - tr['rects'][i][1], 1)] for i in inside_rects],
                         inPadding=False if inside_rects else None)
        h, w = tr['maskShape']; x = (q[0] - tr['origin'][0]) * tr['scale']; y = (q[1] - tr['origin'][1]) * tr['scale']
        regs = [k[4:] for k in M if k.startswith('env_') and mask_at(M, k, q, tr)]
        rec['S3'] = dict(inRaster=0 <= x < w and 0 <= y < h, visibleRegions=tr['visibleRegions'], envelopes=regs,
                         acneSkin=mask_at(M, 'acne_skin', q, tr), hair=mask_at(M, 'hair', q, tr), exclusion=mask_at(M, 'acne_exclusion', q, tr),
                         faceSupport=mask_at(M, 'face_support', q, tr))
        raw = near(tr['raw'], q, r); best = max(raw, key=lambda b: b[6]) if raw else None
        rec['S4'] = dict(nearRaw=len(raw), bestScore=round(best[6], 4) if best else None, bestTile=best[7] if best else None)
        conf = near(tr['conf'], q, r); rec['S5'] = dict(nearConf=len(conf), bestScore=round(max(b[4] for b in conf), 4) if conf else None)
        nms = near(tr['nms'], q, r); sup = None
        if conf and not nms:
            bc = max(conf, key=lambda b: b[4])
            s = [b for b in tr['nms'] if b[4] >= bc[4] and iou(b, bc) > .30]
            if s:
                sb = max(s, key=lambda b: iou(b, bc)); d = np.hypot(ctr(sb)[0] - q[0], ctr(sb)[1] - q[1])
                sup = dict(box=[round(v, 1) for v in sb[:4]], score=round(sb[4], 4), iou=round(iou(sb, bc), 3), centreDistOverR=round(d / r, 2), sidePx=round(max(sb[2] - sb[0], sb[3] - sb[1]), 1))
        rec['S6'] = dict(nearNms=len(nms), suppressedBy=sup)
        rk = lambda b: tuple(round(v, 3) for v in b[:4])
        asg = {rk([a['x'], a['y'], a['x'] + a['width'], a['y'] + a['height']]): a for a in tr['assigned']}
        rej = {rk(j['box']): j for j in tr['rejected']}
        rec['S7'] = dict(assigned=[asg[rk(b)]['region'] + ':' + asg[rk(b)]['assignmentReason'] for b in nms if rk(b) in asg],
                         rejected=[rej[rk(b)]['reason'] for b in nms if rk(b) in rej])
        fin = near(tr['final'], q, r); rec['S8'] = dict(nearFinal=len(fin), found=rec['found'])
        causes = []
        if not rec['S2']['inCrop'] or not inside_rects: causes.append('outside product crop/tiles')
        if not rec['S3']['inRaster']: causes.append('outside product analysis raster (not a visible region of the matched angle)')
        elif not regs: causes.append('outside every visible region envelope')
        if rec['S3']['inRaster'] and rec['S3']['acneSkin'] is False: causes.append('not acne_skin at target (hair/exclusion/face edge/clipping)')
        if inside_rects and not raw: causes.append('model: no raw candidate (score >= .01) within r')
        elif raw and not conf: causes.append('model: best nearby score below .30')
        if conf and not nms: causes.append('NMS: suppressed' + (' by a box centred > r away' if sup and sup['centreDistOverR'] > 1 else ''))
        if nms and not fin: causes.append('filter: ' + ','.join(sorted(set(rec['S7']['rejected']))))
        if fin and not rec['found']: causes.append('final box near but one-to-one assigned to another target')
        order = ['outside product crop/tiles', 'outside product analysis raster', 'outside every visible region envelope', 'model:', 'NMS:', 'filter:', 'final box near']
        first = None
        if not rec['found']:
            if not rec['S2']['inCrop'] or not inside_rects: first = 'S2 product crop/tiles'
            elif not raw: first = 'S4 model raw (no candidate)'
            elif not conf: first = 'S5 model confidence (< .30)'
            elif not nms: first = 'S6 NMS'
            elif not fin: first = 'S7 filter'
            else: first = 'S8 matching (near final taken by another target)'
        rec['causes'] = causes; rec['firstLoss'] = first; out.append(rec)
    return out


def main(W):
    W = Path(W); L1 = json.load(open(W / 'acne-point-relabel-layer1-20261016.json'))['photos']; R = json.load(open(W / 'relabel-results.json'))
    import cv2
    rows = []
    for ph, lab in sorted(L1.items()):
        tr = json.load(open(W / 'trace/acne-step0-trace' / f'{ph}.json')); M = dict(np.load(W / 'trace/acne-step0-trace' / f'{ph}-masks.npz'))
        assert tr['finalEqualsStored']
        l1m = cv2.imread(str(W / 'layer1/masks' / f'{ph}.png'), cv2.IMREAD_GRAYSCALE) > 0
        hits = set(R['perPhotoDetail']['step0/product-chain'][ph]['hitIds'])
        rows += trace_photo(tr, M, lab, l1m, hits, 0.03 * lab['faceWidthPx'])
    json.dump(rows, open(W / 'step0-target-trace.json', 'w'), indent=1)
    return rows


if __name__ == '__main__':
    rows = main(sys.argv[1]); import collections
    miss = [r for r in rows if not r['found']]
    print(len(rows), 'targets', len(miss), 'missed'); print(collections.Counter(r['firstLoss'] for r in miss))
    print(collections.Counter(c for r in miss for c in r['causes']))
