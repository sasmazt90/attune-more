"""Acne v6 training manifest (no training here): the v5 reviewed core unchanged + the limited, reviewed TRAIN extension + the same
auxiliary TRAIN negative photos. DEV / DEV-EXT / RESERVED / held-out / 941-cohort / sealed-test photos are never included (asserted).

TRAIN extension rules (assistant engineering review, not human or expert verified; source records unchanged):
  * positive = source acne box KEPT in acne-v6/trainext/boxreview/box-review-decisions.json; every other source acne box -> IGNORE (reason)
  * explicit known-negative confounder box = confounder KEPT in the same file; other confounder boxes -> IGNORE (reason)
  * known-negative ROI = union of ACCEPTED candidate regions (acne-v6/trainext/roi/frozen.json), cleared within max(10 px, side) of any box
  * all other pixels stay UNKNOWN (ignored by the loss); photos with neither a kept positive nor an accepted ROI are left out (no signal)
"""
import hashlib, json, shutil
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; A = CODE / 'audit-results'
V5 = A / 'acne-v5-data'; X = A / 'acne-v6/trainext'; OUT = A / 'acne-v6-data'


def main():
    OUT.mkdir(exist_ok=True); (OUT / 'ext').mkdir(exist_ok=True)
    m5 = json.loads((V5 / 'manifest-v5.json').read_text()); photos = []
    for p in m5['photos']:                                  # v5 core + auxiliary negatives, unchanged
        q = dict(p)
        for k in ('file', 'mask'):
            if q.get(k):
                (OUT / q[k]).parent.mkdir(parents=True, exist_ok=True)
                if not (OUT / q[k]).exists(): shutil.copyfile(V5 / q[k], OUT / q[k])
        photos.append(q)
    key = json.loads((X / 'boxreview/box-review-key.json').read_text()); dec = json.loads((X / 'boxreview/box-review-decisions.json').read_text())
    kp = {(k['sha'], k['id']) for n, k in enumerate(key['positive'], 1) if n in set(dec['positiveKeep'])}
    kc = {(k['sha'], k['id']) for n, k in enumerate(key['confounder'], 1) if n in set(dec['confounderKeep'])}
    fz = {r['sha256']: r for r in json.loads((X / 'roi/frozen.json').read_text())['masks']}
    m4 = {p['sha256']: p for p in json.loads((A / 'acne-v4-data/manifest-v4.json').read_text())['photos']}
    sel = json.loads((X / 'selection.json').read_text())['selected']
    st = dict(extSelected=len(sel), extSourcePositive=0, extKeptPositive=0, extIgnoredPositive=0, extConfounderKept=0, extConfounderIgnored=0,
              extRoiPhotos=0, extRoiPixels=0, extLeftOutNoSignal=0)
    for r in sel:
        s = r['sha256']; p = m4[s]; assert p['role'] == 'TRAIN' and p['kind'] == 'positive-photo'
        raw = Path(r['file']).read_bytes(); assert hashlib.sha256(raw).hexdigest() == s
        pos, ign, neg = [], [dict(b) for b in p.get('ignore', [])], []
        for b in p['positive']:
            st['extSourcePositive'] += 1
            if (s, b['id']) in kp: pos.append(dict(b, review='kept: visible lesion (assistant engineering review)')); st['extKeptPositive'] += 1
            else: ign.append(dict(b, why='assistant review: no clearly visible lesion inside the box at native resolution (or texture/hair/eye/lip/blur)')); st['extIgnoredPositive'] += 1
        for b in p.get('negativeBoxes', []):
            if (s, b['id']) in kc: neg.append(dict(b, review='kept as explicit non-acne mark (assistant engineering review)')); st['extConfounderKept'] += 1
            else: ign.append(dict(b, why='assistant review: confounder box too large / ambiguous / possibly containing a lesion')); st['extConfounderIgnored'] += 1
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR); h, w = img.shape[:2]; mk = None; mpx = 0
        if s in fz:
            m = cv2.imread(str(X / 'roi' / fz[s]['mask']), cv2.IMREAD_GRAYSCALE) > 0
            for b in pos + ign + neg:
                bb = b['box']; g = max(10, max(bb[2] - bb[0], bb[3] - bb[1]))
                m[max(0, int(bb[1] - g)):int(bb[3] + g), max(0, int(bb[0] - g)):int(bb[2] + g)] = False
            if m.any(): mk = f'ext/{s[:16]}-negroi.png'; cv2.imwrite(str(OUT / mk), m.astype(np.uint8) * 255); mpx = int(m.sum()); st['extRoiPhotos'] += 1; st['extRoiPixels'] += mpx
        if not pos and mk is None: st['extLeftOutNoSignal'] += 1; continue
        rel = f'ext/{s[:16]}{Path(r["file"]).suffix}'; (OUT / rel).write_bytes(raw)
        photos.append(dict(sha256=s, kind='positive-photo', role='TRAIN', file=rel, width=w, height=h, sourceArchive=p['sourceArchive'], researchGroup=p['researchGroup'],
                           positive=pos, ignore=ign, negativeBoxes=neg, mask=mk, maskPixels=mpx, extension='v6-trainext',
                           reviewLevel='assistant engineering review (boxes and clean ROIs at native resolution); not human or expert verified',
                           rights=p.get('rights', 'publisher declaration only; no individual consent record'), personIdentity='unknown'))
    # leakage guards
    dev = {p['sha256'] for p in m4.values() if p['role'] == 'DEV'} | {p['sha256'] for p in json.loads((A / 'acne-v6/devext/manifest.json').read_text())['photos']}
    other941 = {r['sha256'] for r in json.loads((A / 'acne-v4-data/photoselection/manifest.json').read_text()) if r['cohort'] != 'acne'}
    failed = {r['sha256'] for r in map(json.loads, (A / 'acne-v3-20261015/evaluation-v3prod-step0.jsonl').read_text().splitlines())
              if r['set'] in ('development', 'unusedEval')}      # Scope B, controls, reviewed negatives, held-out 20 ('trainProbe' rows are TRAIN photos)
    S = {p['sha256'] for p in photos}
    assert not (S & dev) and not (S & other941) and not (S & failed), 'LEAK'
    groups = {p['researchGroup'] for p in photos}; devg = {p['researchGroup'] for p in m4.values() if p['role'] == 'DEV'} | {p['researchGroup'] for p in json.loads((A / 'acne-v6/devext/manifest.json').read_text())['photos']}
    assert not (groups & devg), 'GROUP LEAK'
    sides = sorted(float(max(b['box'][2] - b['box'][0], b['box'][3] - b['box'][1])) for p in m5['photos'] if p['kind'] == 'positive-photo' for b in p['positive'])
    pp = [p for p in photos if p['kind'] == 'positive-photo']
    st.update(positivePhotos=len(pp), negativePhotos=len(photos) - len(pp), keptPositiveTotal=sum(len(p['positive']) for p in pp),
              roiPhotosTotal=sum(1 for p in pp if p.get('mask')), roiPixelsTotal=int(sum(p.get('maskPixels', 0) for p in pp)))
    man = dict(version='acne-v6-1', photos=photos, targetSidePx=dict(source='v5 core kept positives, native SmartSkinCare resolution (unchanged from v5)', values=sides), stats=st,
               v5Stats=m5['stats'], rule=__doc__)
    (OUT / 'manifest-v6.json').write_text(json.dumps(man)); print(json.dumps(st))


if __name__ == '__main__': main()
