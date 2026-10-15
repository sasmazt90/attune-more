"""Acne training/evaluation input v2: original Pimple boxes on the product tile chain.

Research data preparation only; production acne stays accepted:false, file:null.
Sources are read-only: the publisher COCO archive (SmartSkinCare v8, CC BY 4.0
declared; individual consent not recorded), the frozen selected-source manifest,
the CDC takeover ledger, reviews and browser preflight. Outputs go to an
explicit output-root (pixels, overlays, caches) and to a pixel-free manifest.

Label rules (no silent relabelling):
  * POSITIVE: publisher COCO 'Pimple' box (annotation id kept), not in conflict.
  * CONFLICT: Pimple box that coincides with another publisher class box
    (IoU>=.30 or its centre inside a comparable-size other-class box): UNKNOWN.
  * OTHER_CLASS (Post acne, Mole, Pigmentation, Freckles, Enlarged pores): UNKNOWN
    for Pimple supervision; never clean skin, never their surroundings.
  * PSEUDO: the 401 engineering pseudo-positives: excluded, UNKNOWN.
  * NEGATIVE: only the existing explicit reviewed clean support masks (whole
    visible face review intersect product support) of reviewed negative photos.
  * Everything else is UNKNOWN (loss-masked), including unlabelled skin.
Product chain: source decode -> product photo_input crop from (replayed)
landmarks -> current native 384 tile grid (stride 288, pad 114, BGR uint8 ->
float 0..255, no normalisation) -> box minus tile origin -> model -> plus origin.
"""
import argparse, base64, hashlib, json, math, os, subprocess, sys, zipfile
from pathlib import Path

import numpy as np

VERSION = 'acne-data-v2'
SMART_ARCHIVE = 'SmartSkinCare.v8i.coco.zip'
SMART_ARCHIVE_SHA256 = None  # recorded at inventory time from the frozen selected-source manifest
TAKEOVER = 'audit-results/acne-takeover-20261015'
SELECTED = 'audit-results/skin-selected-20261011/manifest.json'
OTHER_CLASSES = ('Post acne', 'Mole', 'Pigmentation', 'Freckles', 'Enlarged pores', 'Skin-defects')
TILE, STRIDE, PAD_VALUE = 384, 288, 114


class PrepError(RuntimeError):
    pass


def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(Path(p).read_bytes())
def read_json(p): return json.loads(Path(p).read_text('utf8'))


def xywh_to_xyxy(b):
    x, y, w, h = map(float, b)
    return [x, y, x + w, y + h]


def iou(a, b):
    ix = max(0., min(a[2], b[2]) - max(a[0], b[0])); iy = max(0., min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.


def size_band(b):
    side = max(b[2] - b[0], b[3] - b[1])
    return 'micro' if side < 8 else 'small' if side < 16 else 'medium'


def classify_annotations(anns):
    """anns: [{id, cls, box(xyxy)}] -> (positives, conflicts, others). Pure."""
    pim = [a for a in anns if a['cls'] == 'Pimple']; oth = [a for a in anns if a['cls'] != 'Pimple']
    pos, conf = [], []
    for p in pim:
        b = p['box']; c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2); area = (b[2] - b[0]) * (b[3] - b[1])
        hits = [o for o in oth if iou(b, o['box']) >= .30 or
                (o['box'][0] <= c[0] <= o['box'][2] and o['box'][1] <= c[1] <= o['box'][3] and
                 (o['box'][2] - o['box'][0]) * (o['box'][3] - o['box'][1]) < 4 * area)]
        (conf if hits else pos).append({**p, 'conflictWith': [dict(id=o['id'], cls=o['cls']) for o in hits]} if hits else p)
    return pos, conf, oth


def tile_rects_for_crop(crop, shape):
    """Exactly acne_takeover_support.tile_rectangles given the photo_input crop."""
    h, w = shape
    x, y, ex, ey = crop['x'], crop['y'], crop['x'] + crop['width'], crop['y'] + crop['height']
    xs = sorted(set([*range(x, max(x + 1, ex - TILE + 1), STRIDE), max(x, ex - TILE)]))
    ys = sorted(set([*range(y, max(y + 1, ey - TILE + 1), STRIDE), max(y, ey - TILE)]))
    if len(xs) * len(ys) > 64: raise PrepError('NATIVE_TILE_BUDGET_EXCEEDED')
    return [[int(a), int(b), int(min(ex, a + TILE)), int(min(ey, b + TILE))] for a in xs for b in ys]


def tile_targets(rect, boxes, keep_fraction=.70):
    """Source boxes -> tile coordinates. Kept when >=70% of the box area is in
    the tile (prior contract); clipped-off remainders are returned as protected
    (UNKNOWN) so a cut lesion never becomes a negative."""
    a, b, c, d = rect; kept, protected = [], []
    for box in boxes:
        x, y, ex, ey = box['box']; cl = [max(x, a), max(y, b), min(ex, c), min(ey, d)]
        inside = cl[2] - cl[0] >= 2 and cl[3] - cl[1] >= 2
        if inside and (cl[2] - cl[0]) * (cl[3] - cl[1]) >= keep_fraction * (ex - x) * (ey - y):
            kept.append(dict(id=box['id'], tile=[cl[0] - a, cl[1] - b, cl[2] - a, cl[3] - b]))
        elif ex > a and x < c and ey > b and y < d:
            protected.append(dict(id=box['id'], tile=[x - a, y - b, ex - a, ey - b]))
    return kept, protected


def tile_tensor(bgr, rect):
    """Exactly the product infer_tiles input: 384x384, pad 114, BGR, float32 0..255, CHW."""
    a, b, c, d = rect; t = np.full((TILE, TILE, 3), PAD_VALUE, np.uint8); patch = bgr[b:d, a:c]
    t[:patch.shape[0], :patch.shape[1]] = patch
    return t.transpose(2, 0, 1).astype(np.float32)


def tile_to_source(box, rect):
    return [box[0] + rect[0], box[1] + rect[1], box[2] + rect[0], box[3] + rect[1]]


def dhash(gray, flip=False):
    import cv2
    g = cv2.resize(gray[:, ::-1] if flip else gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int(''.join('1' if v else '0' for v in bits), 2)


def hamming(a, b): return bin(a ^ b).count('1')


class UnionFind:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x: self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


def family_of(path):
    name = Path(str(path).replace('\\', '/')).name
    for sep in ('_jpg.rf.', '_jpeg.rf.', '_png.rf.', '.rf.'):
        if sep in name: return name.split(sep)[0]
    return Path(name).stem


# ------------------------------------------------------------------ inventory
def load_smart_coco(archive):
    z = zipfile.ZipFile(archive); out = {}
    for sp in ('train', 'valid', 'test'):
        d = json.loads(z.read(f'{sp}/_annotations.coco.json')); cat = {c['id']: c['name'] for c in d['categories']}
        ims = {im['id']: im for im in d['images']}
        for im in d['images']: out[f'{sp}/{im["file_name"]}'] = dict(cocoSplit=sp, imageId=im['id'], width=im['width'], height=im['height'], anns=[])
        for a in d['annotations']:
            out[f'{sp}/{ims[a["image_id"]]["file_name"]}']['anns'].append(dict(id=int(a['id']), cls=cat[a['category_id']], box=xywh_to_xyxy(a['bbox'])))
    return out


def inventory(input_root, datasets, out):
    """Role assignment from fixed, result-independent rules (see ROLE_RULES)."""
    import cv2
    sel = read_json(input_root / SELECTED)
    src = next(s for s in sel['sources'] if s['id'] == 'smart')
    archive = Path(datasets) / SMART_ARCHIVE
    if sha_file(archive) != src['archiveSHA256']: raise PrepError('SMART_ARCHIVE_CHANGED')
    coco = load_smart_coco(archive)
    rows = sel['rows']; idx = {i: r for i, r in enumerate(rows)}
    smart = {r['sha256']: (i, r) for i, r in enumerate(rows) if r['source'] == 'smart'}
    ledger = {r['sha256']: r for r in read_json(input_root / TAKEOVER / 'inputs/original-reviewed-detector-data.json')['rows']}
    cohort = read_json(input_root / TAKEOVER / 'inputs/controlled_train_cohort.json')
    scope = read_json(input_root / TAKEOVER / 'inputs/annotation-scope-manifest.json')
    preflight = {r['sha256'] for r in read_json(input_root / TAKEOVER / 'browser-preflight.json')['rows']}
    curated = read_json(input_root / TAKEOVER / 'inputs/train-data-engineering-reviewed-20261013.json')
    pseudo = [dict(sha256=r['sha256'], sourceId=a.get('sourceId'), box=a['box']) for r in curated['rows'] for a in r.get('annotations', []) if a.get('reviewStatus') == 'engineering_review']
    scope_b = {r['sha256'] for r in scope['images'] if r.get('inScopeTruthCount') or r.get('isNegative')}
    dev = set(cohort['pilotControlShas']) | (scope_b & preflight)
    prior_validation = {s for s, r in ledger.items() if r['split'] == 'validation'}
    clean = read_json(input_root / TAKEOVER / 'train-clean-support/manifest.json')
    # groups: export family, decoded hash, frozen perceptual quarantine pairs, flip-aware dHash
    uf = UnionFind(); decoded = {}
    for s, (i, r) in smart.items():
        uf.union(s, 'fam:' + family_of(r['path'])); uf.union(s, 'dec:' + r['decodedSHA256'])
    for a, b, _ in sel['perceptualQuarantinePairs']:
        ra, rb = idx[a], idx[b]
        if ra['source'] == 'smart' or rb['source'] == 'smart' or ra['sha256'] in dev or rb['sha256'] in dev:
            uf.union(ra['sha256'], rb['sha256'])
    for s, r in ledger.items():
        uf.union(s, 'fam:' + (r.get('family') or family_of(r['path']))); uf.union(s, 'dec:' + r['decodedSHA256'])
    hashes = {}
    paths = {s: r['absolutePath'] for s, (i, r) in smart.items()} | {s: r['absolutePath'] for s, r in ledger.items()}
    for s, p in paths.items():
        local = map_windows(p, input_root.parent)
        data = local.read_bytes()
        if sha_bytes(data) != s: raise PrepError('SOURCE_HASH:' + s[:8])
        g = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE); hashes[s] = (dhash(g), dhash(g, True))
    keys = list(hashes)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if min(hamming(hashes[a][0], hashes[b][0]), hamming(hashes[a][0], hashes[b][1])) <= 6: uf.union(a, b)
    groups = {s: uf.find(s) for s in paths}
    dev_groups = {groups[s] for s in dev if s in groups} | {groups[s] for s in prior_validation if s in groups}
    items = []
    for s, (i, r) in smart.items():
        key = r['path'].replace('\\', '/'); c = coco.get(key)
        if c is None: raise PrepError('COCO_ROW_MISSING:' + key)
        pos, conf, oth = classify_annotations(c['anns'])
        stock = r.get('rights') == 'excluded-known-stock-source-group'
        if s in dev: role = 'DEV_REGRESSION'
        elif s in prior_validation: role = 'DEV_PRIOR_VALIDATION'
        elif stock: role = 'EXCLUDED_STOCK'
        elif not pos: role = 'NO_ORIGINAL_PIMPLE'
        elif groups[s] in dev_groups: role = 'EXCLUDED_DEV_GROUP_LINK'
        elif r['split'] == 'train': role = 'TRAIN_AUXILIARY'
        elif r['split'] == 'test' and not r.get('groupExposed') and not r.get('reviewExposed') and s not in ledger: role = 'UNUSED_EVAL_CANDIDATE'
        else: role = 'HELD_NOT_SELECTED'
        items.append(dict(sha256=s, decodedSHA256=r['decodedSHA256'], path=key, absolutePath=r['absolutePath'], selectedSplit=r['split'],
                          cocoSplit=c['cocoSplit'], cocoImageId=c['imageId'], width=c['width'], height=c['height'], family=family_of(key),
                          group=groups[s], role=role, rights=r.get('rights'), priorLedger=s in ledger, priorPilotTrain=s in set(cohort['pilotTrainShas']),
                          positives=[dict(id=p['id'], box=p['box'], band=size_band(p['box'])) for p in pos],
                          conflicts=[dict(id=p['id'], box=p['box'], conflictWith=p['conflictWith']) for p in conf],
                          otherClass=[dict(id=o['id'], cls=o['cls'], box=o['box']) for o in oth]))
    # A train-group that also holds an unused-eval row is a leak: drop the eval row.
    train_groups = {it['group'] for it in items if it['role'] == 'TRAIN_AUXILIARY'}
    for it in items:
        if it['role'] == 'UNUSED_EVAL_CANDIDATE' and it['group'] in train_groups: it['role'] = 'EXCLUDED_TRAIN_GROUP_LINK'
    negatives = []
    for r in clean['rows']:
        lr = ledger[r['sha256']]
        negatives.append(dict(sha256=r['sha256'], group=groups.get(r['sha256']), path=lr['path'], absolutePath=lr['absolutePath'], source=lr['source'],
                              maskSHA256=r['maskSHA256'], knownPixels=r['knownPixels'], reason=r.get('reason'), role='TRAIN_REVIEWED_NEGATIVE',
                              reviewBasis=clean['version']))
    neg_groups = {n['group'] for n in negatives}
    for it in items:
        if it['role'] == 'UNUSED_EVAL_CANDIDATE' and it['group'] in neg_groups: it['role'] = 'EXCLUDED_TRAIN_GROUP_LINK'
    return dict(version=VERSION, archive=dict(name=SMART_ARCHIVE, sha256=src['archiveSHA256'], license=src.get('license'),
                                              individualConsent='not-recorded'),
                selectedManifestSHA256=sha_file(input_root / SELECTED), items=items, negatives=negatives,
                pseudoExcluded=pseudo, devShas=sorted(dev), priorValidationShas=sorted(prior_validation))


def map_windows(path, togg_root):
    text = str(path)
    prefix = 'C:\\Users\\PC\\Desktop\\AI Workspace\\TOGG'
    if text.startswith(prefix): return Path(togg_root) / text[len(prefix):].replace('\\', '/').lstrip('/')
    return Path(text)


ROLE_RULES = [
    'DEV_REGRESSION: Scope B browser-preflight photos and the 28 prior control photos (repeatedly inspected development/regression; never final test)',
    'DEV_PRIOR_VALIDATION: prior ledger validation rows used for earlier model selection',
    'EXCLUDED_STOCK: frozen manifest stock-source exclusion',
    'NO_ORIGINAL_PIMPLE: no non-conflicting publisher Pimple box',
    'EXCLUDED_DEV_GROUP_LINK: export family / decoded hash / frozen perceptual quarantine / flip-aware dHash<=6 link to a development row',
    'TRAIN_AUXILIARY: frozen selected-manifest split train; post-hoc product replay, not a real product capture',
    'UNUSED_EVAL_CANDIDATE: frozen selected-manifest split test, never exposed, not in any prior ledger, no group link to train/dev/negatives',
    'HELD_NOT_SELECTED: remaining rows (e.g. unexposed selected-manifest validation); not used',
]


# ------------------------------------------------------------------- replay
def run_replay(code_root, landmarks_path, items_by_sha, togg_root, out_path):
    """Feed analysis-canvas RGB + replayed landmarks to the frontend TS replay."""
    import cv2
    env = dict(os.environ, NODE_PATH=str(Path(togg_root) / 'attune-live-test/node_modules'))
    proc = subprocess.Popen(['node', 'scripts/skin-research/acne_product_replay.cjs'], cwd=code_root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True)
    done = set()
    if Path(out_path).exists(): done = {json.loads(l)['sha256'] for l in Path(out_path).read_text('utf8').splitlines() if l.strip()}
    with open(out_path, 'a', encoding='utf8') as f:
        for line in Path(landmarks_path).read_text('utf8').splitlines():
            r = json.loads(line)
            if r['sha256'] in done: continue
            bgr = cv2.imread(str(items_by_sha[r['sha256']]))
            if (r['analysisWidth'], r['analysisHeight']) != (bgr.shape[1], bgr.shape[0]):
                bgr = cv2.resize(bgr, (r['analysisWidth'], r['analysisHeight']), interpolation=cv2.INTER_LINEAR)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            proc.stdin.write(json.dumps({**r, 'rgbBase64': base64.b64encode(rgb.tobytes()).decode()}) + '\n'); proc.stdin.flush()
            out = json.loads(proc.stdout.readline()); out['landmarkReplay'] = r['replay']; out['landmarks'] = r['landmarks']
            out['analysisWidth'], out['analysisHeight'] = r['analysisWidth'], r['analysisHeight']
            f.write(json.dumps(out) + '\n'); f.flush()
    proc.stdin.close(); proc.wait()


# ----------------------------------------------------------- support / tiles
def product_support(code_root, bgr, landmarks, snapshot, quality_valid):
    """Current production acne support for one photo: frozen analyze_skin prelude
    with the replayed snapshot geometry. Returns native masks (source pixels)."""
    import cv2
    sys.path[:0] = [str(code_root / 'services/core-api'), str(code_root / 'scripts/skin-research')]
    from evaluate_acne_classical import production_context
    import audit_acne_measurement_scope as audit
    from acne_surface_support import acne_support_masks
    ok, png = cv2.imencode('.png', bgr)
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    payload = dict(photo='data:image/png;base64,' + base64.b64encode(png.tobytes()).decode(), photoId=sha_bytes(rgba.tobytes()),
                   landmarks=landmarks, meshes=snapshot['meshes'], exclusions=snapshot['exclusions'], qualityValid=quality_valid,
                   conditions=dict(yaw=0, pitch=0, roll=0, scaleRatio=0))
    ctx = production_context(payload); shape = bgr.shape[:2]; o, s = ctx['origin'], ctx['scale']
    env = np.logical_or.reduce([v for v in ctx['acne_envelopes'].values()]) if ctx['acne_envelopes'] else np.zeros(ctx['gray'].shape, bool)
    yolox = env & ctx['acne_skin']
    masks = acne_support_masks(ctx['masks'], ctx['gray'].shape, payload['meshes'], s, o)
    closed = np.logical_or.reduce([v for k, v in masks.items() if k in audit.REGIONS]) if any(k in masks for k in audit.REGIONS) else np.zeros(ctx['gray'].shape, bool)
    face = ctx['face_support'] > 0
    return dict(face=audit.to_native(face, o, s, shape), yoloxEnvelopeSupport=audit.to_native(yolox, o, s, shape),
                closedCellSupport=audit.to_native(closed & ctx['acne_skin'], o, s, shape), origin=list(o), scale=s)


def center_in(mask, box):
    cx, cy = int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2)
    if not (0 <= cy < mask.shape[0] and 0 <= cx < mask.shape[1]): return None
    return bool(mask[cy, cx])


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('phase', choices=['inventory', 'agreement', 'replay', 'build', 'verify'])
    ap.add_argument('--input-root', required=True); ap.add_argument('--datasets', required=True)
    ap.add_argument('--output-root', required=True); ap.add_argument('--manifest', help='pixel-free fixed manifest (build/verify)')
    ap.add_argument('--code-root', default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args(argv)
    input_root, out = Path(a.input_root).resolve(), Path(a.output_root).resolve(); code_root = Path(a.code_root).resolve()
    if out == input_root or input_root in out.parents: raise PrepError('OUTPUT_ROOT_INSIDE_INPUT_ROOT')
    out.mkdir(parents=True, exist_ok=True); togg = input_root.parent
    sys.path[:0] = [str(code_root / 'scripts/skin-research'), str(code_root / 'services/core-api')]
    if a.phase == 'inventory':
        inv = inventory(input_root, a.datasets, out); inv['roleRules'] = ROLE_RULES
        (out / 'inventory.json').write_text(json.dumps(inv) + '\n', 'utf8')
        need = [it for it in inv['items'] if it['role'] in ('TRAIN_AUXILIARY', 'UNUSED_EVAL_CANDIDATE', 'DEV_REGRESSION')] + inv['negatives']
        (out / 'landmark-items.json').write_text(json.dumps([dict(sha256=it['sha256'], path=str(map_windows(it['absolutePath'], togg))) for it in need]), 'utf8')
        from collections import Counter
        print(json.dumps(dict(roles=Counter(it['role'] for it in inv['items']), negatives=len(inv['negatives']), landmarkItems=len(need))))
        return
    if a.phase == 'agreement':
        agreement(input_root, code_root, out, togg); return
    inv = read_json(out / 'inventory.json')
    if a.phase == 'replay':
        paths = {it['sha256']: map_windows(it['absolutePath'], togg) for it in inv['items'] + inv['negatives']}
        run_replay(code_root, out / 'landmarks.jsonl', paths, togg, out / 'replay.jsonl'); return
    if a.phase == 'build':
        build(inv, input_root, code_root, out, togg, Path(a.manifest)); return
    if a.phase == 'verify':
        verify(input_root, code_root, out, togg, Path(a.manifest)); return


def agreement(input_root, code_root, out, togg):
    """Replay (python MediaPipe + TS functions) versus the real browser preflight
    on the 40 preflight photos: landmark error, quality/pose/snapshot/gate agreement."""
    pre = {r['sha256']: r for r in read_json(input_root / TAKEOVER / 'browser-preflight.json')['rows']}
    ev = {r['sha256']: r for r in read_json(input_root / TAKEOVER / 'evaluation-step0/summary.json')['rows']}
    items = {i['sha256']: Path(i['path']) for i in read_json(out / 'preflight-items.json')}
    target = out / 'preflight-replay.jsonl'
    if not target.exists(): run_replay(code_root, out / 'preflight-landmarks-a640.jsonl', items, togg, target)
    rows = []
    for line in target.read_text('utf8').splitlines():
        r = json.loads(line); b = pre[r['sha256']]; bl = b['alignment'].get('landmarks') or []
        err = None
        if bl and r.get('landmarks'):
            w, h = b['width'], b['height']
            d = np.array([[p['x'] * w, p['y'] * h] for p in r['landmarks'][:468]]) - np.array([[p['x'] * w, p['y'] * h] for p in bl[:468]])
            err = dict(meanPx=float(np.linalg.norm(d, axis=1).mean()), maxPx=float(np.abs(d).max()))
        rows.append(dict(sha256=r['sha256'], landmarkError=err, browserQuality=b['quality']['status'], replayQuality=r['quality']['status'],
                         browserAngle=b['matchedAngle'], replayAngle=r['matchedAngle'], browserGate=ev[r['sha256']]['fullStaticProductPass'],
                         replayGateWithoutEyewear=r['gatePassedWithoutEyewear'], browserEyewear=[(v or {}).get('status') for v in (ev[r['sha256']].get('eyewearFrontend'), ev[r['sha256']].get('eyewearBackend'))]))
    errs = [r['landmarkError']['meanPx'] for r in rows if r['landmarkError']]
    summary = dict(photos=len(rows), qualityAgree=sum(r['browserQuality'] == r['replayQuality'] for r in rows), angleAgree=sum(r['browserAngle'] == r['replayAngle'] for r in rows),
                   gateAgree=sum(r['browserGate'] == r['replayGateWithoutEyewear'] for r in rows),
                   gateDisagreeExplainedByEyewear=sum(r['browserGate'] != r['replayGateWithoutEyewear'] and 'EYEWEAR_PRESENT' in r['browserEyewear'] for r in rows),
                   landmarkMeanPxMedian=float(np.median(errs)), landmarkMeanPxMax=float(np.max(errs)))
    (out / 'agreement.json').write_text(json.dumps(dict(summary=summary, rows=rows), indent=1), 'utf8'); print(json.dumps(summary))


def build(inv, input_root, code_root, out, togg, manifest_path):
    """Fixed pixel-free manifest: per photo product crop/tiles/support, per target
    tile mapping and support flags, negatives, pilot tile order, prior-prep diff."""
    import cv2, random
    from skin_models import photo_input
    if manifest_path.exists(): raise PrepError('MANIFEST_ALREADY_FROZEN')
    replay = {json.loads(l)['sha256']: json.loads(l) for l in (out / 'replay.jsonl').read_text('utf8').splitlines() if l.strip()}
    photos, tiles = [], []
    for it in inv['items']:
        if it['role'] not in ('TRAIN_AUXILIARY', 'UNUSED_EVAL_CANDIDATE'): continue
        rp = replay.get(it['sha256']); rec = dict(sha256=it['sha256'], role=it['role'], group=it['group'], family=it['family'], cocoSplit=it['cocoSplit'],
                                                  cocoImageId=it['cocoImageId'], path=it['path'], width=it['width'], height=it['height'],
                                                  rights=it['rights'], individualConsent='not-recorded', priorLedger=it['priorLedger'], priorPilotTrain=it['priorPilotTrain'],
                                                  conflicts=it['conflicts'], otherClassCount=len(it['otherClass']),
                                                  otherClassByType={c: sum(o['cls'] == c for o in it['otherClass']) for c in sorted({o['cls'] for o in it['otherClass']})})
        rec['replay'] = dict(landmarks=rp['landmarkReplay'] if rp and rp.get('landmarks') else None, faceDetected=bool(rp and rp['faceDetected']),
                             quality=rp['quality']['status'] if rp else None, angle=rp['matchedAngle'] if rp else None,
                             gatePassedWithoutEyewear=bool(rp and rp['gatePassedWithoutEyewear']), reasons=rp['reasons'] if rp else ['NO_REPLAY'],
                             eyewear='NOT_REPLAYED')
        bgr = cv2.imread(str(map_windows(it['absolutePath'], togg)))
        if bgr.shape[1] != it['width'] or bgr.shape[0] != it['height']: raise PrepError('COCO_SIZE_MISMATCH:' + it['sha256'][:8])
        targets = [dict(id=p['id'], box=p['box'], band=p['band']) for p in it['positives']]
        if rp and len(rp.get('landmarks') or []) >= 468:
            _, crop = photo_input(bgr, rp['landmarks']); rec['productCrop'] = {k: crop[k] for k in ('x', 'y', 'width', 'height')}
            rects = tile_rects_for_crop(crop, bgr.shape[:2])
            support = product_support(code_root, bgr, rp['landmarks'], rp['snapshot'], rp['quality']['isValid']) if rp.get('snapshot') else None
            for t in targets:
                b = t['box']; c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                t['centerInProductCrop'] = bool(crop['x'] <= c[0] < crop['x'] + crop['width'] and crop['y'] <= c[1] < crop['y'] + crop['height'])
                t['centerInFaceOval'] = center_in(support['face'], b) if support else None
                t['centerInYoloxEnvelopeSupport'] = center_in(support['yoloxEnvelopeSupport'], b) if support else None
                t['centerInClosedCellSupport'] = center_in(support['closedCellSupport'], b) if support else None
            covered = set()
            for k, r in enumerate(rects):
                kept, prot = tile_targets(r, it['positives'] and [dict(id=p['id'], box=p['box']) for p in it['positives']])
                cprot = tile_targets(r, [dict(id=p['id'], box=p['box']) for p in it['conflicts']], keep_fraction=2.)[1]
                covered |= {v['id'] for v in kept}
                tiles.append(dict(sha256=it['sha256'], role=it['role'], tile=k, rect=r, boxes=kept, protected=prot + cprot, kind='positive' if kept else 'no-positive'))
            for t in targets: t['inATrainingTile'] = t['id'] in covered
        else:
            rec['productCrop'] = None
            for t in targets: t.update(centerInProductCrop=None, centerInFaceOval=None, centerInYoloxEnvelopeSupport=None, centerInClosedCellSupport=None, inATrainingTile=False)
        rec['targets'] = targets; photos.append(rec)
    negatives = []
    from acne_takeover_support import strict_clean_mask
    ledger = {r['sha256']: r for r in read_json(input_root / TAKEOVER / 'inputs/original-reviewed-detector-data.json')['rows']}
    for n in inv['negatives']:
        row = ledger[n['sha256']]; bgr = cv2.imread(str(map_windows(n['absolutePath'], togg)))
        sup_path = input_root / TAKEOVER / 'train-clean-support' / (n['sha256'] + '.png')
        if sha_file(sup_path) != n['maskSHA256']: raise PrepError('CLEAN_SUPPORT_CHANGED')
        mask, _ = strict_clean_mask(row, bgr, reviewed_support=cv2.imread(str(sup_path), cv2.IMREAD_GRAYSCALE))
        rp = replay.get(n['sha256']); rec = dict(sha256=n['sha256'], group=n['group'], source=n['source'], knownCleanPixels=int((mask > 0).sum()),
                                                 reviewBasis=n['reviewBasis'], maskSHA256=n['maskSHA256'], productCrop=None, tiles=[])
        pts = row.get('landmarks') or (rp or {}).get('landmarks')
        if pts and len(pts) >= 468 and rec['knownCleanPixels']:
            _, crop = photo_input(bgr, pts); rec['productCrop'] = {k: crop[k] for k in ('x', 'y', 'width', 'height')}
            rec['landmarkSource'] = 'ledger-browser' if row.get('landmarks') else 'python-mediapipe-replay'
            for k, r in enumerate(tile_rects_for_crop(crop, bgr.shape[:2])):
                a_, b_, c_, d_ = r; known = int((mask[b_:d_, a_:c_] > 0).sum())
                if known: tiles.append(dict(sha256=n['sha256'], role='TRAIN_REVIEWED_NEGATIVE', tile=k, rect=r, boxes=[], protected=[], kind='negative', knownCleanPixels=known))
        negatives.append(rec)
    rng = random.Random(20261015)
    pos_tiles = [i for i, t in enumerate(tiles) if t['role'] == 'TRAIN_AUXILIARY' and t['kind'] == 'positive']
    neg_tiles = [i for i, t in enumerate(tiles) if t['kind'] == 'negative']
    rng.shuffle(pos_tiles); rng.shuffle(neg_tiles)
    order, pi, ni = [], 0, 0
    for i in range(600):
        if i % 10 == 9 and neg_tiles: order.append(neg_tiles[ni % len(neg_tiles)]); ni += 1
        else: order.append(pos_tiles[pi % len(pos_tiles)]); pi += 1
    manifest = dict(version=VERSION, kind='fixed training/evaluation input; research only; production acne accepted:false, file:null',
                    archive=inv['archive'], selectedManifestSHA256=inv['selectedManifestSHA256'], inventorySHA256=sha_file(out / 'inventory.json'),
                    landmarksSHA256=sha_file(out / 'landmarks.jsonl'), replaySHA256=sha_file(out / 'replay.jsonl'),
                    roleRules=inv['roleRules'], labelRules=__doc__.split('Label rules')[1].split('Product chain')[0].strip(),
                    productChain=dict(contract='photo_input camera-crop-v1 -> native 384 tiles stride 288 pad 114 -> BGR uint8 -> float 0..255 CHW -> box - tile origin -> model -> + tile origin',
                                      landmarks='python MediaPipe 0.10.21 with product face_landmarker.task on the <=640 analysis canvas (bilinear); browser agreement measured on 40 preflight rows',
                                      gates='frontend TS alignment/quality/pose/snapshot replay in node; eyewear ONNX gate NOT replayed (UNKNOWN)',
                                      auxiliary='every TRAIN/UNUSED row is a post-hoc replay of a stretched publisher export; it is not proof of a real product capture'),
                    devShas=inv['devShas'], priorValidationShas=inv['priorValidationShas'], pseudoExcluded=len(inv['pseudoExcluded']),
                    photos=photos, negatives=negatives, tiles=tiles, pilotOrder=order,
                    pilotOrderSHA256=sha_bytes(json.dumps([[tiles[i]['sha256'], tiles[i]['rect']] for i in order]).encode()),
                    personIdentity='unknown for every row; source/family/hash grouping is not person independence')
    manifest_path.write_text(json.dumps(manifest, separators=(',', ':')) + '\n', 'utf8')
    print(json.dumps(dict(manifest=str(manifest_path), sha256=sha_file(manifest_path), photos=len(photos), tiles=len(tiles), negatives=len(negatives))))


def verify(input_root, code_root, out, togg, manifest_path):
    """Chain check on real pixels: every training-tile box round-trips to the
    source box exactly; the tile tensor equals the product infer_tiles input;
    overlays of real tiles with their boxes are written for visual inspection."""
    import cv2, random
    man = read_json(manifest_path); inv = read_json(out / 'inventory.json')
    items = {i['sha256']: i for i in inv['items']} | {n['sha256']: n for n in inv['negatives']}
    pos = {p['sha256']: {t['id']: t['box'] for t in p['targets']} | {c['id']: c['box'] for c in p['conflicts']} for p in man['photos']}
    checked = mismatches = 0; per = {}
    for t in man['tiles']:
        for b in t['boxes']:
            src = pos[t['sha256']][b['id']]; back = tile_to_source(b['tile'], t['rect']); checked += 1
            cl = [max(src[0], t['rect'][0]), max(src[1], t['rect'][1]), min(src[2], t['rect'][2]), min(src[3], t['rect'][3])]
            if any(abs(u - v) > 1e-9 for u, v in zip(back, cl)): mismatches += 1
        per.setdefault(t['sha256'], []).append(t)
    rng = random.Random(7); sample = rng.sample([t for t in man['tiles'] if t['boxes']], 16)
    sheet = []
    for t in sample:
        bgr = cv2.imread(str(map_windows(items[t['sha256']]['absolutePath'], togg)))
        x = tile_tensor(bgr, t['rect']); img = x.transpose(1, 2, 0).astype(np.uint8).copy()
        # identical to acne_takeover_support.infer_tiles construction
        ref = np.full((TILE, TILE, 3), PAD_VALUE, np.uint8); a_, b_, c_, d_ = t['rect']; patch = bgr[b_:d_, a_:c_]; ref[:patch.shape[0], :patch.shape[1]] = patch
        if not np.array_equal(ref, img): raise PrepError('TILE_TENSOR_MISMATCH')
        for b in t['boxes']: cv2.rectangle(img, (int(b['tile'][0]), int(b['tile'][1])), (int(math.ceil(b['tile'][2])), int(math.ceil(b['tile'][3]))), (0, 255, 0), 1)
        for b in t['protected']: cv2.rectangle(img, (int(b['tile'][0]), int(b['tile'][1])), (int(math.ceil(b['tile'][2])), int(math.ceil(b['tile'][3]))), (0, 200, 255), 1)
        cv2.putText(img, f"{t['sha256'][:8]} {t['rect']}", (3, 12), cv2.FONT_HERSHEY_SIMPLEX, .35, (255, 255, 255), 1, cv2.LINE_AA)
        sheet.append(img)
    rows = [np.hstack(sheet[i:i + 4]) for i in range(0, 16, 4)]
    (out / 'overlays').mkdir(exist_ok=True); cv2.imwrite(str(out / 'overlays' / 'training-tiles-sample.png'), np.vstack(rows))
    # Prior pilot input versus this input, on the same source photos.
    cohort = read_json(input_root / TAKEOVER / 'inputs/controlled_train_cohort.json')
    crops = {p['sha256']: p['productCrop'] for p in man['photos'] if p.get('productCrop')}
    prior_tiles = cohort['pilotTrainTiles']; inside_area = []; prior_boxes_outside = 0; prior_boxes = 0
    for t in prior_tiles:
        c = crops.get(t['imageSha256'])
        if not c: continue
        a_, b_, c_, d_ = t['rect']; ix = max(0, min(c_, c['x'] + c['width']) - max(a_, c['x'])); iy = max(0, min(d_, c['y'] + c['height']) - max(b_, c['y']))
        inside_area.append(ix * iy / max(1, (c_ - a_) * (d_ - b_)))
        for bx in t.get('boxes', []):
            prior_boxes += 1; cx, cy = a_ + (bx[0] + bx[2]) / 2, b_ + (bx[1] + bx[3]) / 2
            prior_boxes_outside += not (c['x'] <= cx < c['x'] + c['width'] and c['y'] <= cy < c['y'] + c['height'])
    grid_aligned = sum(1 for t in prior_tiles if t['imageSha256'] in crops and (t['rect'][0] - crops[t['imageSha256']]['x']) % STRIDE == 0
                       and (t['rect'][1] - crops[t['imageSha256']]['y']) % STRIDE == 0)
    prior_train = set(cohort['pilotTrainShas']); new_train = {p['sha256'] for p in man['photos'] if p['role'] == 'TRAIN_AUXILIARY'}
    ledger = read_json(input_root / TAKEOVER / 'inputs/original-reviewed-detector-data.json')['rows']
    prior_pos = sum(len(r.get('annotations', [])) for r in ledger if r['sha256'] in prior_train)
    diff = dict(priorPilotTrainPhotos=len(prior_train), priorPilotOriginalPimpleBoxes=prior_pos, priorEngineeringPseudoPositivesInBaseTrainingData=man['pseudoExcluded'],
                newTrainPhotos=len(new_train), newTrainOriginalPimpleBoxes=sum(len(p['targets']) for p in man['photos'] if p['role'] == 'TRAIN_AUXILIARY'),
                overlapPhotos=len(prior_train & new_train), priorTilesWithReplayCrop=len(inside_area),
                priorTileAreaInsideProductCropMean=float(np.mean(inside_area)) if inside_area else None,
                priorTilesFullyInsideProductCrop=sum(v >= .999 for v in inside_area), priorTilesOnProductTileGrid=grid_aligned,
                priorTileBoxesWithCentreOutsideProductCrop=prior_boxes_outside, priorTileBoxesChecked=prior_boxes)
    result = dict(manifestSHA256=sha_file(manifest_path), boxesChecked=checked, roundTripMismatches=mismatches, tileTensorsChecked=len(sample),
                  tileTensorEqualsProductConstruction=True, priorVersusNew=diff, sampleTiles=[[t['sha256'], t['rect']] for t in sample])
    (out / 'chain-verification.json').write_text(json.dumps(result, indent=1), 'utf8'); print(json.dumps({k: v for k, v in result.items() if k != 'sampleTiles'}))


if __name__ == '__main__':
    main()
