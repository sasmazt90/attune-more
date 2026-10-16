"""Split the 30 frozen TARGETs of the positive supplement into inside / outside the current product analysis scope, from existing
records only (replay rows + photos -> product photo_input tiles and current_product_masks; no detector, no verifier, no label change).
Point test (source px -> analysis raster via (src - origin) * scale): in a product tile, inside a visible-region envelope, on acne_skin,
not on hair / acne_exclusion. Approximation: the old box filter also uses the box extent; a point inside this scope can still be
rejected for box-level reasons, so 'in scope' here means 'the product would analyse this location', not 'a box there is accepted'."""
import base64, hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
sys.path[:0] = [str(HERE)]
O = CODE / 'audit-results/acne-pos-supplement'; POS = TOGG / 'photo-eval-packs-20261016/01_positive_supplement'


def main():
    import eval_acne_v5_independent as v5; v5.setup(); import cv2
    from acne_takeover_support import current_product_masks
    lab = json.loads((O / 'labels-frozen.json').read_text()); res = json.loads((O / 'results.json').read_text())
    rp = {json.loads(l)['sha256']: json.loads(l) for l in open(O / 'replay.jsonl')}; out = {}
    for pid, L in lab['photos'].items():
        r = rp[L['sha256']]; bgr = cv2.imread(str(POS / L['file'])); pl = v5.plan(bgr, r); snap = r['snapshot']
        ok, png = cv2.imencode('.png', bgr); pidh = hashlib.sha256(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
        m = current_product_masks(dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=pidh, landmarks=r['landmarks'], meshes=snap['meshes'],
                                       exclusions=snap['exclusions'], qualityValid=r['quality']['isValid'], conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0)))
        sk, hair, exc = (np.asarray(m[k]) > 0 for k in ('acne_skin', 'hair', 'acne_exclusion')); env = {k: np.asarray(v) > 0 for k, v in m['acne_envelopes'].items()}
        sc, (ox, oy) = float(m['scale']), [float(v) for v in m['origin']]; H, W = sk.shape
        hits = {n: set(res['perPhoto'][pid][n]['hitIds']) for n in ('Step0', 'v1', 'v3')}; rows = []
        for q in L['points']:
            if q['cat'] != 'TARGET': continue
            x, y = int((q['x'] - ox) * sc), int((q['y'] - oy) * sc); inR = 0 <= x < W and 0 <= y < H
            tiles = [i for i, t in enumerate(pl['rects']) if t[0] <= q['x'] < t[2] and t[1] <= q['y'] < t[3]]
            regs = [k for k, e in env.items() if inR and e[y, x]]
            why = []
            if not tiles: why.append('outside product crop/tiles')
            if not inR: why.append('outside analysis raster')
            elif not regs: why.append('outside every visible-region envelope (side capture analyses the exposed cheek only)' if r['matchedAngle'] != 'FRONT' else 'outside every visible-region envelope')
            else:
                if not sk[y, x]: why.append('not on acne_skin')
                if hair[y, x]: why.append('on hair mask')
                if exc[y, x]: why.append('on acne exclusion')
            rows.append(dict(id=q['id'], note=q['note'], inProductScope=not why, reasons=why, regions=regs, foundBy={n: q['id'] in hits[n] for n in hits}))
        out[pid] = dict(pose=r['matchedAngle'], visibleRegions=list(snap['meshes']), targets=rows)
    tot = lambda f: sum(1 for p in out.values() for t in p['targets'] if f(t))
    summ = dict(targets=tot(lambda t: True), inScope=tot(lambda t: t['inProductScope']), outOfScope=tot(lambda t: not t['inProductScope']),
                **{f'{n}FoundInScope': tot(lambda t, n=n: t['inProductScope'] and t['foundBy'][n]) for n in ('Step0', 'v1', 'v3')},
                **{f'{n}FoundOutOfScope': tot(lambda t, n=n: (not t['inProductScope']) and t['foundBy'][n]) for n in ('Step0', 'v1', 'v3')},
                perPhoto={k: dict(pose=v['pose'], inScope=sum(t['inProductScope'] for t in v['targets']), outOfScope=sum(not t['inProductScope'] for t in v['targets']),
                                  **{n: sum(t['inProductScope'] and t['foundBy'][n] for t in v['targets']) for n in ('Step0', 'v1', 'v3')}) for k, v in out.items()})
    rec = dict(rule=__doc__, summary=summ, photos=out)
    (O / 'product-scope.json').write_text(json.dumps(rec, indent=1)); print(json.dumps(summ, indent=1))
    for k, v in out.items():
        for t in v['targets']:
            if not t['inProductScope']: print(k, t['id'], t['note'], t['reasons'], t['foundBy'])


if __name__ == '__main__': main()
