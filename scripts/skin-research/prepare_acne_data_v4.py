"""Acne v4 data preparation (no training).

Positives: photos of the 2026-10-16 photo-selection package (cohort 'acne') whose groups already carry the v3 role TRAIN
(-> TRAIN) or VALIDATION (-> DEV). RESERVED_V2_EVAL, the sealed Skin care v5 test groups and photos outside the v3 plan are not used.
The 941 'other' (acne status UNKNOWN) photos are never used. Annotations come ONLY from the selected photo's own source
record (no blind merge of duplicate-group annotations).
Box states per photo (source pixels):
  positive  : Pimple / Acne / akne / acne / Whiteheads (pale-white appearance kept in scope), lesion-sized (<=15% width), no other-class twin
  ignore    : Blackheads, Post acne/marks, region-type classes, oversize acne boxes, conflicting twins, every other unlabeled pixel (UNKNOWN)
  negative  : explicit confounder boxes (Mole, Freckles, Pigmentation, (En)larged pores, gozenek, Dark-Spots) <=8% width not touching acne
Negative photos: 42 Clear (assistant-engineering ROI masks; TRAIN/DEV fixed by person group) and the 15 CDC reviewed TRAIN negatives
(CDC strict clean masks). Review levels are kept in separate fields.
"""
import csv, glob, hashlib, json, sys
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
sys.path[:0] = [str(HERE)]
import acne_inventory_v3 as inv
D = CODE / 'audit-results/acne-v4-data'; V3 = CODE / 'audit-results/acne-v3-20261015'
POS = {'pimple', 'acne', 'akne', 'whiteheads'}
CONF = {'mole', 'freckles', 'pigmentation', 'enlarged pores', 'englarged-pores', 'gozenek', 'dark-spots'}


def overlaps(a, b): return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def split_boxes(anns, w):
    pos, ign, neg = [], [], []
    acne = [a for a in anns if inv.norm(a['cls']) in POS]; rest = [a for a in anns if inv.norm(a['cls']) not in POS]
    for a in acne:
        b = a['box']; why = None
        if b[2] - b[0] > .15 * w: why = 'oversize-acne-box'
        elif any(inv.iou(b, o['box']) >= .5 for o in rest): why = 'conflicting-class-twin'
        (ign if why else pos).append(dict(id=a['id'], cls=a['cls'], box=b, **({'why': why} if why else {})))
    for o in rest:
        c = inv.norm(o['cls']); b = o['box']
        if c in CONF and b[2] - b[0] <= .08 * w and not any(overlaps(b, a["box"]) for a in acne): neg.append(dict(id=o['id'], cls=o['cls'], box=b))
        else: ign.append(dict(id=o['id'], cls=o['cls'], box=b, why='non-acne class: UNKNOWN for acne'))
    return pos, ign, neg


def main():
    plan = json.loads((V3 / 'plan-v3.json').read_text()); groups = json.loads((V3 / 'groups.json').read_text())['groupOf']
    prole = {}
    for i in plan['items']: prole.setdefault(i['fileSha'], set()).add(i['role'])
    hrows = {}
    for f in glob.glob(str(V3 / 'hash/*.ndjson')):
        for l in open(f):
            r = json.loads(l); hrows[(r['archive'], r['path'])] = r
    A = json.loads((D / 'photoselection/manifest.json').read_text())
    other_shas = {r['sha256'] for r in A if r['cohort'] != 'acne'}
    photos, skipped = [], {}
    for r in A:
        if r['cohort'] != 'acne': continue
        roles = prole.get(r['sha256'], set())
        role = 'TRAIN' if roles == {'TRAIN'} else 'DEV' if roles == {'VALIDATION'} else None
        if role is None: skipped[r['sha256'][:12]] = sorted(roles) or ['NOT_IN_V3_PLAN']; continue
        raw = (D / 'photoselection' / r['photo']).read_bytes(); assert hashlib.sha256(raw).hexdigest() == r['sha256']
        h = hrows[(r['source_archive'], r['source_path'])]; assert h['fileSha'] == r['sha256']
        pos, ign, neg = split_boxes(h['anns'] or [], r['width'])
        photos.append(dict(sha256=r['sha256'], kind='positive-photo', role=role, file='photoselection/' + r['photo'], width=r['width'], height=r['height'],
                           sourceArchive=r['source_archive'], sourcePath=r['source_path'], researchGroup=groups[r['source_archive'] + '::' + r['source_path']],
                           packageGroup=r['group'], positive=pos, ignore=ign, negativeBoxes=[n for n in neg], unlabeledSkin='UNKNOWN (ignore)',
                           reviewLevel='publisher boxes; photo framing screened by assistant (188px previews); lesion labels not verified',
                           rights=r['rights'], personIdentity='unknown'))
    # group consistency: no research group or package group in two roles
    for key in ('researchGroup', 'packageGroup'):
        g = {}
        for p in photos: g.setdefault(p[key], set()).add(p['role'])
        bad = [k for k, v in g.items() if len(v) > 1]
        assert not bad, (key, bad[:5])
    C = json.loads((D / 'clear-masks/clear-negative-masks.json').read_text())
    for r in C['rows']:
        if r['status'] != 'ENGINEERING_NEGATIVE_ROI': continue
        photos.append(dict(sha256=r['sha256'], kind='negative-photo', role=r['role'], file='clear/' + r['photo'], width=r['width'], height=r['height'],
                           sourceArchive='kaggle:xtvgie/face-datasets v1 (Clear)', sourcePath=r['source'], researchGroup='clear:' + r['personGroup'],
                           mask='clear-masks/' + r['maskFile'], maskPixels=r['negativePixels'], negativeSource='clear-engineering', reviewLevel=r['reviewLevel'],
                           rights=r['rights'], personIdentity='filename-derived group only', nativeResolution=r['nativeResolution']))
    # CDC reviewed TRAIN negatives (strict clean masks), copied with their source bytes
    sys.path[:0] = [str(HERE)]
    import run_acne_v2_pilot as v2
    v2.setup_paths(CODE, TOGG)
    from acne_takeover_support import strict_clean_mask
    from prepare_acne_data_v2 import map_windows
    live = TOGG / 'attune-live-test' / v2.TAKEOVER
    ledger = {r['sha256']: r for r in v2.read_json(live / 'inputs/original-reviewed-detector-data.json')['rows']}
    invj = json.loads((CODE / 'audit-results/acne-data-v2-20261015/inventory.json').read_text())
    (D / 'cdc-negatives').mkdir(exist_ok=True)
    excluded_cdc = []
    for n in invj['negatives']:
        if n['sha256'] in other_shas: excluded_cdc.append(n['sha256'][:12]); continue   # in the 941 UNKNOWN cohort: not used in this experiment
        s = n['sha256']; src = Path(map_windows(n['absolutePath'], TOGG)); raw = src.read_bytes(); assert hashlib.sha256(raw).hexdigest() == s
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        sup = cv2.imread(str(live / 'train-clean-support' / (s + '.png')), cv2.IMREAD_GRAYSCALE)
        m, _ = strict_clean_mask(ledger[s], img, reviewed_support=sup)
        (D / 'cdc-negatives' / (s[:16] + src.suffix)).write_bytes(raw); cv2.imwrite(str(D / 'cdc-negatives' / (s[:16] + '-mask.png')), ((m > 0) * 255).astype(np.uint8))
        photos.append(dict(sha256=s, kind='negative-photo', role='TRAIN', file='cdc-negatives/' + s[:16] + src.suffix, width=img.shape[1], height=img.shape[0],
                           sourceArchive=n['source'], researchGroup=n.get('group') or 'cdc:' + s[:12], mask='cdc-negatives/' + s[:16] + '-mask.png', maskPixels=int((m > 0).sum()),
                           negativeSource='cdc-reviewed', reviewLevel='CDC reviewed negative ROI (' + str(n.get('reviewBasis')) + ')', rights='as recorded in the CDC ledger; no individual consent record'))
    used = {p['sha256'] for p in photos}
    assert not (used & other_shas), 'UNKNOWN-cohort photo used'
    # scale target: per-box sides of SmartSkinCare TRAIN positives at native resolution (no upscaling elsewhere)
    sides = sorted(float(max(b['box'][2] - b['box'][0], b['box'][3] - b['box'][1])) for p in photos if p['kind'] == 'positive-photo' and p['role'] == 'TRAIN'
                   and p['sourceArchive'].startswith('SmartSkinCare') for b in p['positive'])
    man = dict(version='acne-v4-data-1', photos=photos, targetSidePx=dict(source='per-box side of SmartSkinCare TRAIN positives at native resolution', values=sides),
               unusedUnknownCohort=dict(count=len(other_shas), usedOverlap=0), skippedAcneCohort=skipped, cdcNegativesExcludedBecauseIn941=excluded_cdc,
               classMap=dict(positive=sorted(POS), negativeBox=sorted(CONF), ignore='Blackheads, Post acne/marks, all other classes, oversize/conflicting acne boxes, unlabeled skin'))
    (D / 'manifest-v4.json').write_text(json.dumps(man))
    from collections import Counter
    c = Counter((p['kind'], p['role']) for p in photos)
    print(dict(c)); print('positive boxes', {r: sum(len(p['positive']) for p in photos if p['kind'] == 'positive-photo' and p['role'] == r) for r in ('TRAIN', 'DEV')},
          'negative boxes', {r: sum(len(p.get('negativeBoxes', [])) for p in photos if p['role'] == r) for r in ('TRAIN', 'DEV')})
    print('neg ROI px', {k: sum(p.get('maskPixels', 0) for p in photos if p['kind'] == 'negative-photo' and (p['role'], p['negativeSource']) == k) for k in set((p['role'], p.get('negativeSource')) for p in photos if p['kind'] == 'negative-photo')})
    print('groups', {r: len({p['researchGroup'] for p in photos if p['role'] == r}) for r in ('TRAIN', 'DEV')}, 'skipped', Counter(tuple(v) for v in skipped.values()))
    print('cdc excluded (941 cohort)', excluded_cdc); print('target side median', np.median(sides), 'p25', np.percentile(sides, 25), 'p75', np.percentile(sides, 75), 'n', len(sides))


if __name__ == '__main__': main()
