"""Assemble a LOCAL human-review package from existing sources and labels (no new labels, no downloads, no upload).

Selection (product-capture-like only):
  * SmartSkinCare photos whose replayed product gate passed (81 TRAIN + 20 held-out development; eyewear UNKNOWN)
  * the 15 CDC-reviewed TRAIN negative photos (reviewed clean masks)
The sealed cross-source test (every Skin care v5 group) is excluded and checked.
Per photo: byte-identical source copy, an overlay of EXISTING labels, and labels.json with the decisions a human must take.
Labelling itself is done with the existing tool scripts/skin-research/acne-appearance-capture.html (not a new tool).
Output lives under audit-results/ (Git-ignored)."""
import csv, glob, hashlib, json, shutil, sys, zipfile
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; CODE = HERE.parents[1]; TOGG = CODE.parent
sys.path[:0] = [str(HERE)]
import run_acne_v2_pilot as v2
v2.setup_paths(CODE, TOGG)
from acne_takeover_support import strict_clean_mask
from prepare_acne_data_v2 import map_windows
OUT = CODE / 'audit-results/acne-review-package-20261016'
DATASETS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
CONF = {'mole', 'freckles', 'pigmentation', 'enlarged pores', 'englarged-pores', 'pores', 'gozenek', 'dark-spots', 'black spot', 'hyperpigmentation'}
SCAR = {'post acne', 'marks'}; ACNE = {'pimple', 'acne', 'akne'}
COL = dict(pimple=(0, 112, 255), conflict=(255, 0, 255), confounder=(255, 200, 0), scar=(150, 150, 150), model=(0, 230, 255), crop=(255, 255, 255), otheracne=(0, 60, 200))


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.


def rect(img, b, c, t=2, label=None):
    p = [int(round(v)) for v in b]; cv2.rectangle(img, (p[0] - 2, p[1] - 2), (p[2] + 2, p[3] + 2), c, t)
    if label: cv2.putText(img, label, (p[0], max(10, p[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, .4, c, 1, cv2.LINE_AA)


def main():
    man = v2.read_json(CODE / 'docs/acne-data-v2-manifest-20261015.json')
    inv = v2.read_json(CODE / 'audit-results/acne-data-v2-20261015/inventory.json')
    plan = v2.read_json(CODE / 'audit-results/acne-v3-20261015/plan-v3.json')
    groups = v2.read_json(CODE / 'audit-results/acne-v3-20261015/groups.json')['groupOf']
    hashrows = {}
    for f in glob.glob(str(CODE / 'audit-results/acne-v3-20261015/hash/*.ndjson')):
        for l in open(f):
            r = json.loads(l); hashrows.setdefault(r['fileSha'], []).append(r)
    test_groups = {i['group'] for i in plan['items'] if i['role'] == 'TEST_CROSS_SOURCE'}
    in_test = lambda s: any(groups.get(r['archive'] + '::' + r['path']) in test_groups for r in hashrows.get(s, []))
    live = TOGG / 'attune-live-test' / v2.TAKEOVER
    ledger = {r['sha256']: r for r in v2.read_json(live / 'inputs/original-reviewed-detector-data.json')['rows']}
    # saved Step0 conf .30 final product boxes (only photos already evaluated)
    s0rows = [json.loads(l) for l in (CODE / 'audit-results/acne-v3-20261015/evaluation-v3prod-step0.jsonl').read_text().splitlines()]
    s0side = [json.loads(l) for l in (CODE / 'audit-results/acne-v3-20261015/v3prod-step0-boxes.jsonl').read_text().splitlines()]
    step0 = {}; k = 0
    for r in s0rows:
        if 'candidates' in r:
            if r['set'] in ('trainProbe', 'unusedEval'): step0[r['sha256']] = dict(boxes=s0side[k]['boxes'], matched={p[1] for p in r['pairs']})
            k += 1
    sel = [(p, 'TRAIN' if p['role'] == 'TRAIN_AUXILIARY' else 'DEV_HELDOUT20') for p in man['photos'] if (p.get('replay') or {}).get('gatePassedWithoutEyewear')]
    OUT.mkdir(parents=True, exist_ok=True); (OUT / 'photos').mkdir(exist_ok=True)
    smart = zipfile.ZipFile(DATASETS / 'SmartSkinCare.v8i.coco.zip'); index = []; excluded = []
    for p, role in sel:
        s = p['sha256']
        if in_test(s): excluded.append(dict(sha8=s[:8], role=role, reason='photo group overlaps the sealed Skin care v5 test')); continue
        raw = smart.read(p['path'])
        if hashlib.sha256(raw).hexdigest() != s: raise RuntimeError('SOURCE_HASH:' + s[:8])
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR); ov = img.copy()
        anns = next(r['anns'] for r in hashrows[s] if r['archive'].startswith('SmartSkinCare'))
        pos = {t['id']: t['box'] for t in p['targets']}; conf_ids = {c['id'] for c in p['conflicts']}
        conf, scar, other = [], [], []
        for a in anns:
            c = a['cls'].strip().lower()
            if a['id'] in pos: continue
            if a['id'] in conf_ids: continue
            (conf if c in CONF else scar if c in SCAR else other).append(dict(id=a['id'], cls=a['cls'], box=a['box']))
        cr = p['productCrop']; rect(ov, [cr['x'], cr['y'], cr['x'] + cr['width'], cr['y'] + cr['height']], COL['crop'], 1, 'urun crop')
        for b in scar: rect(ov, b['box'], COL['scar'], 1)
        for b in conf: rect(ov, b['box'], COL['confounder'], 1, b['cls'][:5])
        for i, b in pos.items(): rect(ov, b, COL['pimple'], 2, f'P{i}')
        for c in p['conflicts']: rect(ov, c['box'], COL['conflict'], 2, f'C{c["id"]}')
        model = []
        if s in step0:
            for j, b in enumerate(step0[s]['boxes']):
                if j not in step0[s]['matched']: model.append(dict(id=f'M{j}', box=[round(v, 1) for v in b])); rect(ov, b, COL['model'], 1, f'M{j}')
        near = [c for c in conf if any(iou(c['box'], b) > 0 for b in pos.values())]
        d = OUT / 'photos' / f'{role}-{s[:10]}'; d.mkdir(exist_ok=True)
        ext = Path(p['path']).suffix; (d / ('source' + ext)).write_bytes(raw); cv2.imwrite(str(d / 'overlay.jpg'), ov, [cv2.IMWRITE_JPEG_QUALITY, 90])
        decisions = dict(
            confirmEachPimpleBox=[f'P{i}' for i in pos],
            resolveConflicts=[dict(id=f'C{c["id"]}', withClasses=[w['cls'] for w in c['conflictWith']]) for c in p['conflicts']],
            confirmConfounderNotAcne=[f'{c["cls"]}#{c["id"]}' for c in near],
            reviewModelUnknownCandidates=[m['id'] for m in model],
            completeness='Are all visible pimples inside the product crop boxed? Draw each missing one as "Görünür aday kutusu".',
            cleanRegions='Draw at least the clearly clean skin areas as "İncelenmiş negatif alan"; leave the rest UNKNOWN.',
            unmeasurable='Mark glare, hair/beard, blur, shadow regions as "Ölçülemeyen alan".')
        rec = dict(sha256=s, role=role, source='SmartSkinCare.v8i (publisher CC BY 4.0; no individual consent record)', cocoPath=p['path'], width=p['width'], height=p['height'],
                   productGate=dict(replayPassedWithoutEyewear=True, eyewear='UNKNOWN'), productCrop=cr,
                   existing=dict(pimple=[dict(id=f'P{i}', box=b) for i, b in pos.items()], conflicts=p['conflicts'], confounders=conf, postAcneOrMarks=scar, other=other),
                   step0Conf30UnmatchedCandidates=dict(status='UNKNOWN - not acne, not negative', boxes=model) if s in step0 else 'not evaluated',
                   decisions=decisions, coordinateSpace='source pixels')
        (d / 'labels.json').write_text(json.dumps(rec, indent=1))
        index.append(dict(folder=d.name, role=role, pimpleBoxes=len(pos), conflicts=len(p['conflicts']), confoundersTouchingPimple=len(near), confounders=len(conf),
                          postAcneOrMarks=len(scar), step0UnknownCandidates=len(model) if s in step0 else '', reviewedCleanMask='', archiveAcneInsideCleanMask=''))
    for n in inv['negatives']:
        s = n['sha256']
        if in_test(s): excluded.append(dict(sha8=s[:8], role='REVIEWED_NEGATIVE', reason='photo group overlaps the sealed Skin care v5 test')); continue
        src = map_windows(n['absolutePath'], TOGG); raw = Path(src).read_bytes()
        if hashlib.sha256(raw).hexdigest() != s: raise RuntimeError('SOURCE_HASH:' + s[:8])
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR); ov = img.copy()
        sup = cv2.imread(str(live / 'train-clean-support' / (s + '.png')), cv2.IMREAD_GRAYSCALE)
        mask, _ = strict_clean_mask(ledger[s], img, reviewed_support=sup); m = mask > 0
        ov[m] = (.6 * ov[m] + .4 * np.array([0, 200, 0])).astype(np.uint8)
        arch = []
        for r in hashrows.get(s, []):
            for a in r['anns'] or []: arch.append(dict(archive=r['archive'], cls=a['cls'], box=a['box']))
        inside = []
        for a in arch:
            c = a['cls'].strip().lower(); col = COL['otheracne'] if c in ACNE else COL['confounder'] if c in CONF else COL['scar']
            if c in ACNE or c in CONF or c in SCAR:
                rect(ov, a['box'], col, 1, a['cls'][:5])
                cx, cy = int((a['box'][0] + a['box'][2]) / 2), int((a['box'][1] + a['box'][3]) / 2)
                if c in ACNE and 0 <= cy < m.shape[0] and 0 <= cx < m.shape[1] and m[cy, cx]: inside.append(a)
        d = OUT / 'photos' / f'REVIEWED_NEGATIVE-{s[:10]}'; d.mkdir(exist_ok=True)
        (d / ('source' + Path(str(src)).suffix)).write_bytes(raw); cv2.imwrite(str(d / 'overlay.jpg'), ov, [cv2.IMWRITE_JPEG_QUALITY, 90])
        rec = dict(sha256=s, role='REVIEWED_NEGATIVE (TRAIN)', source=f'{n["source"]} (CDC reviewed-negative ledger; licence as recorded there; no individual consent record)',
                   reviewedCleanPixels=int(m.sum()), reviewBasis=n.get('reviewBasis'), existingArchiveLabels=arch,
                   decisions=dict(confirmCleanMask='Is the green area really free of visible pimples? Any visible pimple inside it -> draw "Görünür aday kutusu" and report the mask as wrong.',
                                  resolveArchiveAcneInsideCleanMask=[f'{a["archive"][:20]}:{a["cls"]}@{[round(v) for v in a["box"]]}' for a in inside],
                                  unmeasurable='Mark glare, hair/beard, blur, shadow as "Ölçülemeyen alan".'), coordinateSpace='source pixels')
        (d / 'labels.json').write_text(json.dumps(rec, indent=1))
        index.append(dict(folder=d.name, role='REVIEWED_NEGATIVE', pimpleBoxes=0, conflicts=0, confoundersTouchingPimple=0, confounders=sum(1 for a in arch if a['cls'].strip().lower() in CONF),
                          postAcneOrMarks=sum(1 for a in arch if a['cls'].strip().lower() in SCAR), step0UnknownCandidates='', reviewedCleanMask=int(m.sum()), archiveAcneInsideCleanMask=len(inside)))
    with (OUT / 'index.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(index[0])); w.writeheader(); w.writerows(index)
    shutil.copyfile(HERE / 'acne-appearance-capture.html', OUT / 'acne-appearance-capture.html')
    tot = lambda k: sum(int(r[k] or 0) for r in index)
    summary = dict(photos=len(index), uniquePhotoSHA=len({json.loads((OUT / 'photos' / r['folder'] / 'labels.json').read_text())['sha256'] for r in index}),
                   byRole={r: sum(1 for x in index if x['role'] == r) for r in ('TRAIN', 'DEV_HELDOUT20', 'REVIEWED_NEGATIVE')},
                   pimpleBoxesToConfirm=tot('pimpleBoxes'), conflictsToResolve=tot('conflicts'), confoundersTouchingPimple=tot('confoundersTouchingPimple'),
                   step0UnknownCandidatesToReview=tot('step0UnknownCandidates'), archiveAcneInsideCleanMask=tot('archiveAcneInsideCleanMask'),
                   photosWithStep0Candidates=sum(1 for r in index if r['step0UnknownCandidates'] != ''), sealedTestExcludedAndChecked=True, excludedForSealedTest=excluded)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1)); print(json.dumps(summary, indent=1))


if __name__ == '__main__': main()
