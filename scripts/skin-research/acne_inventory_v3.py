"""Acne v3 multi-source inventory (read-only on the dataset archives).

Phases (each resumable, time-bounded so it fits one shell call):
  hash   decode every image of every archive once, record size + dHash (+ mirrored dHash) and its annotations
  link   group images across/within archives (Roboflow family, exact decoded hash, dHash<=6 incl. mirror)
  agree  for cross-archive duplicates with acne labels on both sides, measure box agreement (label completeness)

No pixels are written; output is NDJSON/JSON with hashes, sizes and box coordinates only.
"""
import argparse, hashlib, io, json, os, re, sys, time, zipfile, collections
from pathlib import Path
import numpy as np, cv2

LICENCE = {  # from each archive's README (publisher declaration, not individual consent)
    'DC EB 2.v1i.coco.zip': 'CC BY 4.0', 'Find wrinkles- marks and dark circles.v2-roboflow-instant-1--eval-.coco.zip': 'Public Domain',
    'Skin Analysis.v11-augmentation_version.coco-segmentation.zip': 'CC BY 4.0', 'Skin care.v5i.coco.zip': 'CC BY 4.0',
    'Skin-Problem-Detection-Relabel-Clean3.v1-skin-disease-detection-.coco.zip': 'CC BY 4.0', 'Skin.v5i.coco.zip': 'CC BY 4.0',
    'Skin_Analysis.v1i.coco.zip': 'undefined', 'SmartSkinCare.v8i.coco.zip': 'CC BY 4.0', 'Wrinkles Detector.v2i.coco-segmentation.zip': 'CC BY 4.0',
    'ciltanalizi.v12i.coco.zip': 'CC BY 4.0', 'multi-class.v1i.multiclass.zip': 'CC BY 4.0', 'skin_concern_detection_model.v1i.coco.zip': 'CC BY 4.0',
    'skin_face_detection.v1i.coco.zip': 'CC BY 4.0', 'yolo arnold.v1i.coco.zip': 'CC BY 4.0'}
# inflammatory acne lesion classes (product "Sivilce görünümü"); comedones and scars are kept apart and never negative
ACNE = {'pimple', 'acne', 'akne'}
COMEDO = {'whiteheads', 'blackheads'}
SCAR_OR_MARK = {'post acne', 'marks'}


def norm(c): return c.strip().lower()


def role_of(cls):
    c = norm(cls)
    return 'acne' if c in ACNE else 'comedo' if c in COMEDO else 'scar_mark' if c in SCAR_OR_MARK else 'other'


def family_of(path):
    b = os.path.basename(path)
    m = re.match(r'(.+?)_(jpg|jpeg|png)\.rf\.', b, re.I)
    return m.group(1) if m else os.path.splitext(b)[0]


def dhash(gray, flip=False):
    g = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    if flip: g = g[:, ::-1]
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int(''.join('1' if b else '0' for b in bits), 2)


def hamming(a, b): return bin(a ^ b).count('1')


def coco_index(zf):
    out = {}
    for a in [n for n in zf.namelist() if n.endswith('_annotations.coco.json')]:
        d = json.loads(zf.read(a)); split = a.split('/')[0]
        cats = {c['id']: c['name'] for c in d.get('categories', [])}
        imgs = {i['id']: i for i in d['images']}
        anns = collections.defaultdict(list)
        for an in d.get('annotations', []):
            x, y, w, h = an['bbox']
            anns[an['image_id']].append(dict(id=an['id'], cls=cats.get(an['category_id'], '?'), box=[x, y, x + w, y + h],
                                             seg=bool(an.get('segmentation'))))
        for iid, im in imgs.items():
            out[split + '/' + im['file_name']] = dict(split=split, cocoW=im['width'], cocoH=im['height'], anns=anns.get(iid, []))
    return out


def phase_hash(root, out, budget):
    t0 = time.time(); (out / 'hash').mkdir(parents=True, exist_ok=True)
    for z in sorted(LICENCE):
        dst = out / 'hash' / (z + '.ndjson'); done_mark = out / 'hash' / (z + '.done')
        if done_mark.exists(): continue
        zf = zipfile.ZipFile(root / z); idx = coco_index(zf)
        names = sorted(n for n in zf.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png')))
        seen = set()
        if dst.exists():
            for line in dst.read_text().splitlines():
                try: seen.add(json.loads(line)['path'])
                except Exception: pass
        with dst.open('a') as f:
            for n in names:
                if n in seen: continue
                if time.time() - t0 > budget: print('budget', z, len(seen)); return False
                raw = zf.read(n); arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                rec = dict(archive=z, path=n, family=family_of(n), fileSha=hashlib.sha256(raw).hexdigest())
                if arr is None: rec.update(decodeError=True)
                else:
                    g = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
                    rec.update(w=arr.shape[1], h=arr.shape[0], pixSha=hashlib.sha256(arr.tobytes()).hexdigest()[:24],
                               dh=dhash(g), dhf=dhash(g, True), mean=round(float(g.mean()), 1))
                meta = idx.get(n)
                rec.update(split=meta['split'] if meta else n.split('/')[0], anns=meta['anns'] if meta else None)
                f.write(json.dumps(rec) + '\n'); seen.add(n)
        done_mark.write_text(str(len(seen))); print('done', z, len(seen))
    return True


class UF:
    def __init__(s): s.p = {}
    def find(s, a):
        s.p.setdefault(a, a)
        while s.p[a] != a: s.p[a] = s.p[s.p[a]]; a = s.p[a]
        return a
    def union(s, a, b): s.p[s.find(a)] = s.find(b)


def load(out):
    rows = []
    for p in sorted((out / 'hash').glob('*.ndjson')):
        rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return rows


def phase_thumb(root, out, budget):
    """32x32 gray thumbnails (local only, never in Git) to verify dHash candidate pairs by normalised correlation."""
    t0 = time.time(); dst = out / 'thumbs'; dst.mkdir(exist_ok=True)
    for z in sorted(LICENCE):
        f = dst / (z + '.npz')
        if f.exists(): continue
        part = dst / (z + '.part.npz'); have = dict(np.load(part)) if part.exists() else {}
        zf = zipfile.ZipFile(root / z)
        names = sorted(n for n in zf.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png')))
        for n in names:
            if n in have: continue
            if time.time() - t0 > budget: np.savez(part, **have); print('budget', z, len(have)); return False
            arr = cv2.imdecode(np.frombuffer(zf.read(n), np.uint8), cv2.IMREAD_GRAYSCALE)
            if arr is not None: have[n] = cv2.resize(arr, (32, 32), interpolation=cv2.INTER_AREA)
        np.savez(f, **have); part.unlink(missing_ok=True); print('done', z, len(have))
    return True


def ncc(a, b):
    a = a.astype(np.float32).ravel(); b = b.astype(np.float32).ravel(); a -= a.mean(); b -= b.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / d) if d > 0 else 0.


def phase_link(out, thr=6, min_ncc=.92):
    rows = [r for r in load(out) if not r.get('decodeError')]
    th = {}
    for f in (out / 'thumbs').glob('*.npz'):
        if f.name.endswith('.part.npz'): continue
        z = f.name[:-4]
        for k, v in np.load(f).items(): th[z + '::' + k] = v
    uf = UF(); key = lambda r: r['archive'] + '::' + r['path']
    for r in rows:
        uf.union(key(r), 'fam:' + r['archive'] + ':' + r['family']); uf.union(key(r), 'pix:' + r['pixSha'])
    # dHash neighbours via 4x16-bit band buckets (pigeonhole: <=3 differing bits guarantees a shared band; we then verify <=thr)
    buckets = collections.defaultdict(list)
    for i, r in enumerate(rows):
        for b in range(4): buckets[(b, (r['dh'] >> (16 * b)) & 0xFFFF)].append(i)
    pairs = set()
    for i, r in enumerate(rows):
        for h in (r['dh'], r['dhf']):
            for b in range(4):
                for j in buckets[(b, (h >> (16 * b)) & 0xFFFF)]:
                    if j <= i: continue
                    d = min(hamming(r['dh'], rows[j]['dh']), hamming(r['dhf'], rows[j]['dh']))
                    if d <= thr and abs(rows[i]['mean'] - rows[j]['mean']) < 25:
                        ta, tb = th[key(r)], th[key(rows[j])]
                        c = max(ncc(ta, tb), ncc(ta[:, ::-1], tb))  # mirrored copies count as the same photo
                        if c >= min_ncc: pairs.add((i, j, d))
    for i, j, d in pairs: uf.union(key(rows[i]), key(rows[j]))
    groups = collections.defaultdict(list)
    for r in rows: groups[uf.find(key(r))].append(r)
    gid = {}; summary = collections.Counter(); cross = []
    for n, (g, members) in enumerate(sorted(groups.items(), key=lambda kv: kv[0])):
        arch = sorted({m['archive'] for m in members})
        for m in members: gid[key(m)] = 'g%05d' % n
        summary['groups'] += 1; summary['multiArchiveGroups'] += len(arch) > 1
        if len(arch) > 1: cross.append(dict(group='g%05d' % n, archives=arch, members=[key(m) for m in members]))
    (out / 'groups.json').write_text(json.dumps(dict(threshold=thr, minNcc=min_ncc, pairs=len(pairs), summary=summary, groupOf=gid, cross=cross)))
    print(dict(images=len(rows), pairs=len(pairs), **summary))


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.


def phase_agree(out):
    """For cross-archive duplicate pairs (same pixels up to resize), compare acne boxes after scaling to a common frame."""
    rows = {r['archive'] + '::' + r['path']: r for r in load(out) if not r.get('decodeError')}
    g = json.loads((out / 'groups.json').read_text()); res = []
    for c in g['cross']:
        ms = [rows[k] for k in c['members'] if rows[k].get('anns') is not None]
        for a_i in range(len(ms)):
            for b_i in range(a_i + 1, len(ms)):
                A, B = ms[a_i], ms[b_i]
                if A['archive'] == B['archive']: continue
                if abs(A['w'] / A['h'] - B['w'] / B['h']) > .02: continue  # different crop -> boxes not comparable
                if hamming(A['dh'], B['dh']) > 6: continue  # mirrored/rotated copies skipped (frame differs)
                sa = [1 / A['w'], 1 / A['h']]; sb = [1 / B['w'], 1 / B['h']]
                na = lambda r, s: [[b['box'][0] * s[0], b['box'][1] * s[1], b['box'][2] * s[0], b['box'][3] * s[1]] for b in r['anns'] if role_of(b['cls']) == 'acne']
                ba, bb = na(A, sa), na(B, sb)
                if not ba and not bb: continue
                used = set(); m = 0
                for x in ba:
                    best = max(((iou(x, y), j) for j, y in enumerate(bb) if j not in used), default=(0, None))
                    if best[0] >= .3: used.add(best[1]); m += 1
                res.append(dict(a=A['archive'], b=B['archive'], aBoxes=len(ba), bBoxes=len(bb), matched=m, group=c['group']))
    by = collections.defaultdict(lambda: collections.Counter())
    for r in res:
        k = tuple(sorted([r['a'], r['b']])); flip = k[0] != r['a']
        by[k]['pairs'] += 1; by[k]['matched'] += r['matched']
        by[k]['boxes_' + k[0]] += r['bBoxes'] if flip else r['aBoxes']; by[k]['boxes_' + k[1]] += r['aBoxes'] if flip else r['bBoxes']
    summ = [dict(archives=list(k), **v) for k, v in by.items()]
    (out / 'agreement.json').write_text(json.dumps(dict(pairs=res, summary=summ), indent=1))
    for s in summ: print(s)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--root', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--budget', type=float, default=150)
    a = ap.parse_args(); root, out = Path(a.root), Path(a.out)
    if a.phase == 'hash': sys.exit(0 if phase_hash(root, out, a.budget) else 3)
    if a.phase == 'thumb': sys.exit(0 if phase_thumb(root, out, a.budget) else 3)
    if a.phase == 'link': phase_link(out)
    if a.phase == 'agree': phase_agree(out)
