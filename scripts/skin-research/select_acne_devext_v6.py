"""Acne v6 additional DEV group from the existing v3 VALIDATION role (evaluation only, never trained on).

Candidates: plan-v3 items whose ONLY role is VALIDATION, whose research group has no other role, with >= 1 source acne box, not already in
v4 DEV, not in the 941 UNKNOWN cohort, not a failed-product-evaluation photo, not from the sealed Skin care v5 archive. Leakage check:
64-bit dHash against every v6 training photo (core 65 + TRAIN extension + TRAIN negatives) and against v4 DEV; distance <= 10 -> excluded.
The source bytes are read from the publisher archive and hash-checked. Product gates are NOT relaxed: the evaluator later decides per photo
(replay-pass with eyewear UNKNOWN, or a recorded failure status). No model output is read here.

  python select_acne_devext_v6.py
"""
import collections, hashlib, json, zipfile
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; A = CODE / 'audit-results'; OUT = A / 'acne-v6/devext'
DATASETS = CODE.parents[1] / 'Datasets'


def dhash(img):
    g = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA).astype(int)
    return int(''.join('1' if b else '0' for b in (g[:, 1:] > g[:, :-1]).ravel()), 2)


def main():
    (OUT / 'photos').mkdir(parents=True, exist_ok=True)
    plan = json.loads((A / 'acne-v3-20261015/plan-v3.json').read_text()); role, g2r = {}, collections.defaultdict(set)
    for i in plan['items']: role.setdefault(i['fileSha'], set()).add(i['role']); g2r[i['group']].add(i['role'])
    v4 = json.loads((A / 'acne-v4-data/manifest-v4.json').read_text())['photos']; dev4 = {p['sha256'] for p in v4 if p['role'] == 'DEV'}
    other941 = {r['sha256'] for r in json.loads((A / 'acne-v4-data/photoselection/manifest.json').read_text()) if r['cohort'] != 'acne'}
    failed = {json.loads(l)['sha256'] for l in (A / 'acne-v3-20261015/evaluation-v3prod-step0.jsonl').read_text().splitlines()}
    why = collections.Counter(); cand = []; seen = set()
    for i in plan['items']:
        s = i['fileSha']
        if i['role'] != 'VALIDATION' or s in seen: continue
        seen.add(s)
        if role[s] != {'VALIDATION'}: why['sha has another role'] += 1; continue
        if g2r[i['group']] != {'VALIDATION'}: why['group has another role'] += 1; continue
        if not i['pos']: why['no source acne box'] += 1; continue
        if s in dev4: why['already v4 DEV'] += 1; continue
        if s in other941: why['941 cohort'] += 1; continue
        if s in failed: why['failed product evaluation photo'] += 1; continue
        if i['archive'] == plan['testArchive']: why['sealed test archive'] += 1; continue
        cand.append(i)
    # training / DEV reference hashes
    ref = {}
    m6 = json.loads((A / 'acne-v5-data/manifest-v5.json').read_text())['photos']
    for p in m6: ref[p['sha256']] = A / 'acne-v5-data' / p['file']
    for r in json.loads((A / 'acne-v6/trainext/selection.json').read_text())['selected']: ref[r['sha256']] = Path(r['file'])
    for p in v4:
        if p['role'] == 'DEV': ref[p['sha256']] = A / 'acne-v4-data' / p['file']
    refh = {s: dhash(cv2.imread(str(f))) for s, f in ref.items()}
    zips = {}; photos = []
    for i in sorted(cand, key=lambda x: x['fileSha']):
        z = zips.setdefault(i['archive'], zipfile.ZipFile(DATASETS / i['archive']))
        raw = z.read(i['path']); assert hashlib.sha256(raw).hexdigest() == i['fileSha']
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR); h = dhash(img)
        near = [s for s, rh in refh.items() if bin(h ^ rh).count('1') <= 10]
        if near: why['near-duplicate of a v6 TRAIN or v4 DEV photo'] += 1; continue
        f = OUT / 'photos' / f'{i["fileSha"][:16]}{Path(i["path"]).suffix}'; f.write_bytes(raw)
        photos.append(dict(sha256=i['fileSha'], kind='positive-photo', role='DEV-EXT (v3 VALIDATION)', file=str(f.resolve()), width=img.shape[1], height=img.shape[0],
                           sourceArchive=i['archive'], researchGroup=i['group'], positive=[dict(box=b) for b in i['pos']], ignore=[dict(box=b) for b in i['ign']],
                           negativeBoxes=[dict(box=b) for b in i['neg']], reviewLevel='publisher boxes (not reviewed); clean-skin ROIs reviewed separately',
                           rights='publisher declaration only; no individual consent record', personIdentity='unknown'))
    man = dict(version='acne-v6-devext-1', rule=__doc__, exclusions=dict(why), candidates=len(cand), photos=photos,
               bySource=dict(collections.Counter(p['sourceArchive'] for p in photos)))
    (OUT / 'manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(dict(exclusions=dict(why), kept=len(photos), bySource=man['bySource'])))


if __name__ == '__main__': main()
