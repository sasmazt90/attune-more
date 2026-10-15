"""Blind, calibrated visual review used in place of an unavailable dermatologist.

calib-build  writes numbered contact sheets of skin patches (local only, never in Git) plus a sealed key.
             Patch kinds: POS (a labeled acne lesion inside), HARD (a labeled mole/freckle/spot/pore, no acne label
             inside), RAND (unlabeled skin inside the labeled face area). Mixed and shuffled.
calib-score  scores the reviewer's answers against the key with the pre-registered gate.
The gate is fixed before any sheet is viewed: sensitivity(POS) >= .85 and specificity(HARD) >= .85.
RAND has no ground truth (unlabeled != clean); it is only reported.
"""
import argparse, json, random, zipfile, hashlib, sys, collections
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).resolve().parent))
import acne_inventory_v3 as inv

GATE = dict(minSensitivity=.85, minHardSpecificity=.85)  # round 1 (binary answers) - failed, kept for the record
# Round 2+ (three-way answers: acne / unsure / clean). What matters for negatives is how often a real lesion is called
# "clean"; "unsure" becomes UNKNOWN and is never used as a negative. Fixed before any round-2 sheet is viewed.
GATE3 = dict(maxPosCalledClean=.10, maxHardCalledAcne=.15, maxUnsureRate=.40)
HARD_CLASSES = {'mole', 'freckles', 'pigmentation', 'dark-spots', 'black spot', 'enlarged pores', 'englarged-pores', 'pores', 'gozenek'}
LESION_ARCHIVES = ['SmartSkinCare.v8i.coco.zip', 'Skin-Problem-Detection-Relabel-Clean3.v1-skin-disease-detection-.coco.zip',
                   'Skin Analysis.v11-augmentation_version.coco-segmentation.zip', 'ciltanalizi.v12i.coco.zip']
CELL, GRID = 224, 4


def patch_side(img_w, boxes):
    s = [max(b[2] - b[0], b[3] - b[1]) for b in boxes] or [img_w * .03]
    return int(np.clip(4 * np.median(s), 64, img_w / 3))


def inside(inner, outer): return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def overlaps(a, b): return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def candidates(rows, rng, kind_quota):
    out = collections.defaultdict(list)
    for r in rows:
        anns = r['anns'] or []
        acne = [b['box'] for b in anns if inv.role_of(b['cls']) == 'acne']
        if not acne: continue
        others = [b['box'] for b in anns if inv.role_of(b['cls']) != 'acne']
        hard = [b['box'] for b in anns if inv.norm(b['cls']) in HARD_CLASSES]
        s = patch_side(r['w'], acne); allb = [b['box'] for b in anns]
        x0, y0 = min(b[0] for b in allb), min(b[1] for b in allb); x1, y1 = max(b[2] for b in allb), max(b[3] for b in allb)
        def win(cx, cy):
            x = int(np.clip(cx - s / 2, 0, r['w'] - s)); y = int(np.clip(cy - s / 2, 0, r['h'] - s)); return [x, y, x + s, y + s]
        b = acne[rng.randrange(len(acne))]
        w = win((b[0] + b[2]) / 2 + rng.uniform(-.25, .25) * s, (b[1] + b[3]) / 2 + rng.uniform(-.25, .25) * s)
        if inside(b, w) and not any(overlaps(o, w) and not inside(o, w) for o in others): out['POS'].append((r, w))
        if hard:
            h = hard[rng.randrange(len(hard))]; w = win((h[0] + h[2]) / 2, (h[1] + h[3]) / 2)
            if inside(h, w) and not any(overlaps(a, w) for a in acne): out['HARD'].append((r, w))
        for _ in range(20):
            w = win(rng.uniform(x0, x1), rng.uniform(y0, y1))
            if not any(overlaps(a, w) for a in allb): out['RAND'].append((r, w)); break
    return {k: rng.sample(v, min(kind_quota[k], len(v))) for k, v in out.items()}


def build(root, out, seed, quota):
    rng = random.Random(seed)
    rows = [json.loads(l) for a in LESION_ARCHIVES for l in (out / 'hash' / (a + '.ndjson')).read_text().splitlines()]
    rows = [r for r in rows if not r.get('decodeError') and r.get('anns')]
    rng.shuffle(rows)
    picked = candidates(rows, rng, quota)
    items = [(k, r, w) for k, v in picked.items() for r, w in v]; rng.shuffle(items)
    zfs = {a: zipfile.ZipFile(root / a) for a in LESION_ARCHIVES}
    d = out / 'review' / ('calib-%d' % seed); d.mkdir(parents=True, exist_ok=True); key = []
    per = GRID * GRID
    for s in range(0, len(items), per):
        sheet = np.full((GRID * CELL, GRID * CELL, 3), 255, np.uint8)
        for i, (k, r, w) in enumerate(items[s:s + per]):
            img = cv2.imdecode(np.frombuffer(zfs[r['archive']].read(r['path']), np.uint8), cv2.IMREAD_COLOR)
            p = cv2.resize(img[w[1]:w[3], w[0]:w[2]], (CELL - 8, CELL - 8), interpolation=cv2.INTER_CUBIC)
            yy, xx = divmod(i, GRID); sheet[yy * CELL + 4:yy * CELL + CELL - 4, xx * CELL + 4:xx * CELL + CELL - 4] = p
            cv2.putText(sheet, str(i + 1), (xx * CELL + 8, yy * CELL + 26), cv2.FONT_HERSHEY_SIMPLEX, .8, (255, 255, 255), 3)
            cv2.putText(sheet, str(i + 1), (xx * CELL + 8, yy * CELL + 26), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 0, 0), 1)
            key.append(dict(sheet=s // per + 1, cell=i + 1, kind=k, archive=r['archive'], path=r['path'], window=w))
        cv2.imwrite(str(d / ('sheet_%02d.png' % (s // per + 1))), sheet)
    (d / 'key.sealed.json').write_text(json.dumps(dict(gate=GATE if seed == 1 else GATE3, answerMode='binary' if seed == 1 else 'three-way', seed=seed, items=key)))
    print('sheets', -(-len(items) // per), 'items', collections.Counter(k for k, _, _ in items),
          'keySha', hashlib.sha256((d / 'key.sealed.json').read_bytes()).hexdigest()[:16])


def score3(d, key, ans):
    c = collections.Counter(); wrong = []
    for it in key['items']:
        a = ans.get(str(it['sheet']), {}); v = 'acne' if it['cell'] in a.get('acne', []) else 'unsure' if it['cell'] in a.get('unsure', []) else 'clean'
        c[it['kind'] + '_' + v] += 1
        if (it['kind'] == 'POS' and v == 'clean') or (it['kind'] == 'HARD' and v == 'acne'): wrong.append(dict(sheet=it['sheet'], cell=it['cell'], kind=it['kind'], said=v))
    n = lambda k: sum(c[k + '_' + v] for v in ('acne', 'unsure', 'clean'))
    g = key['gate']; pos_clean = c['POS_clean'] / max(1, n('POS')); hard_acne = c['HARD_acne'] / max(1, n('HARD'))
    unsure = sum(c[k + '_unsure'] for k in ('POS', 'HARD', 'RAND')) / max(1, len(key['items']))
    res = dict(counts=c, posCalledClean=pos_clean, hardCalledAcne=hard_acne, unsureRate=unsure, gate=g,
               passed=pos_clean <= g['maxPosCalledClean'] and hard_acne <= g['maxHardCalledAcne'] and unsure <= g['maxUnsureRate'], disagreements=wrong)
    (d / 'score.json').write_text(json.dumps(res, indent=1)); print(json.dumps({k: v for k, v in res.items() if k != 'disagreements'}))


def score(out, seed, answers_path):
    d = out / 'review' / ('calib-%d' % seed); key = json.loads((d / 'key.sealed.json').read_text())
    if key.get('answerMode') == 'three-way': return score3(d, key, json.loads(Path(answers_path).read_text()))
    ans = json.loads(Path(answers_path).read_text())  # {"1":[cells with acne], "2":[...], ...}
    c = collections.Counter(); wrong = []
    for it in key['items']:
        said = it['cell'] in ans.get(str(it['sheet']), [])
        c[it['kind'] + ('_yes' if said else '_no')] += 1
        if (it['kind'] == 'POS') != said: wrong.append(dict(sheet=it['sheet'], cell=it['cell'], kind=it['kind']))
    sens = c['POS_yes'] / max(1, c['POS_yes'] + c['POS_no']); spec = c['HARD_no'] / max(1, c['HARD_yes'] + c['HARD_no'])
    res = dict(counts=c, sensitivity=sens, hardSpecificity=spec, randFlagged=c['RAND_yes'] / max(1, c['RAND_yes'] + c['RAND_no']),
               gate=key['gate'], passed=sens >= key['gate']['minSensitivity'] and spec >= key['gate']['minHardSpecificity'], disagreements=wrong)
    (d / 'score.json').write_text(json.dumps(res, indent=1)); print(json.dumps({k: v for k, v in res.items() if k != 'disagreements'}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('phase'); ap.add_argument('--root'); ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=1); ap.add_argument('--answers')
    a = ap.parse_args(); out = Path(a.out)
    if a.phase == 'calib-build': build(Path(a.root), out, a.seed, dict(POS=48, HARD=24, RAND=24))
    if a.phase == 'calib-score': score(out, a.seed, a.answers)
