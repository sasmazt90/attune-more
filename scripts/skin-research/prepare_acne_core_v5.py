"""Acne v5 reviewed TRAIN core (no training): 65 v3-TRAIN photos of the review package with
  * source boxes kept unchanged in `sourceBoxes`; review decisions stored separately in `review`
  * positives = Pimple boxes the assistant engineering review kept; reviewed-doubtful Pimple boxes -> IGNORE (reason recorded)
  * known-negative ROI = union of accepted candidate regions (assistant engineering review); everything else UNKNOWN
  * confounder boxes as in v4 (explicit negative), other classes IGNORE
Auxiliary negative photos: v4 TRAIN Clear (engineering) and CDC reviewed negatives. No DEV/RESERVED/held-out/941/Skin care v5 photo."""
import glob, hashlib, json, shutil, sys
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]
sys.path[:0] = [str(HERE)]
import prepare_acne_data_v4 as v4
C = CODE / 'audit-results/acne-v5-core'; D4 = CODE / 'audit-results/acne-v4-data'; OUT = CODE / 'audit-results/acne-v5-data'


def main():
    OUT.mkdir(exist_ok=True); (OUT / 'core').mkdir(exist_ok=True)
    keys = json.loads((C / 'box-review-key.json').read_text()); dec = json.loads((C / 'box-review-decisions.json').read_text())
    ign_idx = set(dec['ignore']); norm = lambda i: str(i)[1:] if str(i).startswith('P') else str(i)
    doubtful = {(k['sha'], norm(k['id'])) for n, k in enumerate(keys, 1) if n in ign_idx}; reviewed = {(k['sha'], norm(k['id'])) for k in keys}
    rois = json.loads((C / 'roi-candidates.json').read_text()); rd = json.loads((C / 'roi-review-decisions.json').read_text())
    acc = set(rd['accept']); flagged = set(rd['possibleUnlabeledLesionInside'])
    hashrows = {}
    for f in glob.glob(str(CODE / 'audit-results/acne-v3-20261015/hash/*.ndjson')):
        for l in open(f):
            r = json.loads(l)
            if r['archive'].startswith('SmartSkinCare'): hashrows[r['fileSha']] = r
    plan = json.loads((CODE / 'audit-results/acne-v3-20261015/plan-v3.json').read_text()); role = {}; grp = {}
    for i in plan['items']: role.setdefault(i['fileSha'], set()).add(i['role']); grp[i['fileSha']] = i['group']
    v4man = json.loads((D4 / 'manifest-v4.json').read_text()); other941 = set()
    A = json.loads((D4 / 'photoselection/manifest.json').read_text()); other941 = {r['sha256'] for r in A if r['cohort'] != 'acne'}
    photos = []; stats = dict(sourcePimple=0, keptPositive=0, ignoredReviewed=0, acceptedRoi=0, roiPixels=0)
    for folder in sorted(glob.glob(str(CODE / 'audit-results/acne-review-package-20261016/photos/TRAIN-*'))):
        L = json.loads((Path(folder) / 'labels.json').read_text()); s = L['sha256']
        if role.get(s) != {'TRAIN'}: continue
        assert s not in other941
        src = sorted(Path(folder).glob('source.*'))[0]; raw = src.read_bytes(); assert hashlib.sha256(raw).hexdigest() == s
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR); h, w = img.shape[:2]
        pos, ign, neg = v4.split_boxes(hashrows[s]['anns'], w)
        kept = []
        for b in pos:
            if (s, str(b['id'])) not in reviewed: ign.append(dict(b, why='not in the reviewed box set: kept out of the core')); stats['notReviewed'] = stats.get('notReviewed', 0) + 1
            elif (s, str(b['id'])) in doubtful: ign.append(dict(b, why='assistant review: no clearly visible lesion inside the box at native resolution')); stats['ignoredReviewed'] += 1
            else: kept.append(dict(b, review='kept: visible lesion (assistant engineering review)'))
        stats['sourcePimple'] += len(pos); stats['keptPositive'] += len(kept)
        m = np.zeros((h, w), bool); regions = []
        for it in rois:
            if it['sha'] != s or it.get('reviewIndex') is None: continue
            a = it['reviewIndex'] in acc
            regions.append(dict(region=it['region'], reviewIndex=it['reviewIndex'], accepted=a, possibleUnlabeledLesion=it['reviewIndex'] in flagged, pixels=it['pixels']))
            if a: m |= cv2.imread(str(C / it['file']), cv2.IMREAD_GRAYSCALE) > 0; stats['acceptedRoi'] += 1
        for b in kept + [x for x in ign]:   # safety: never negative over/near any lesion or ignore box
            bb = b['box']; g = max(10, max(bb[2] - bb[0], bb[3] - bb[1])); m[max(0, int(bb[1] - g)):int(bb[3] + g), max(0, int(bb[0] - g)):int(bb[2] + g)] = False
        stats['roiPixels'] += int(m.sum())
        rel = f'core/{s[:16]}{src.suffix}'; (OUT / rel).write_bytes(raw)
        mk = None
        if m.any(): mk = f'core/{s[:16]}-negroi.png'; cv2.imwrite(str(OUT / mk), m.astype(np.uint8) * 255)
        photos.append(dict(sha256=s, kind='positive-photo', role='TRAIN', file=rel, width=w, height=h, sourceArchive='SmartSkinCare.v8i.coco.zip', researchGroup=grp[s],
                           positive=kept, ignore=ign, negativeBoxes=neg, mask=mk, maskPixels=int(m.sum()), roiReview=regions,
                           sourceBoxes=dict(pimple=len(pos), note='publisher boxes unchanged in the source archive / review package labels.json'),
                           reviewLevel='assistant engineering review (boxes and clean ROIs at native resolution); not human or expert verified',
                           rights='publisher CC BY 4.0 declaration only; no individual consent record', personIdentity='unknown'))
    for p in v4man['photos']:
        if p['kind'] == 'negative-photo' and p['role'] == 'TRAIN':
            q = dict(p); q['file'] = 'v4/' + p['file']; q['mask'] = 'v4/' + p['mask']
            for k in ('file', 'mask'): (OUT / q[k]).parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(D4 / p[k], OUT / q[k])
            photos.append(q)
    groups = {}
    for p in photos: groups.setdefault(p['researchGroup'], set()).add(p['role'])
    sides = sorted(float(max(b['box'][2] - b['box'][0], b['box'][3] - b['box'][1])) for p in photos if p['kind'] == 'positive-photo' for b in p['positive'])
    man = dict(version='acne-v5-core-1', photos=photos, targetSidePx=dict(source='kept core positives, native SmartSkinCare resolution', values=sides), stats=stats,
               boxReview=str(C / 'box-review-decisions.json'), roiReview=str(C / 'roi-review-decisions.json'))
    (OUT / 'manifest-v5.json').write_text(json.dumps(man)); print(json.dumps(stats), 'photos', len(photos), 'median side', np.median(sides))


if __name__ == '__main__': main()
