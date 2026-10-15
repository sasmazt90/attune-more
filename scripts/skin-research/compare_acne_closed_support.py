"""Frozen classical A/B on OLD (triangle-union) vs NEW (closed-cell) acne support.

The only changed element is the acne analysis support (five region masks and,
through them, the eligible scope, ownership and A's blemish baseline masks).
A/B colour operations, size/shape/boundary filters, thresholds and matching
rules are the frozen ones. OLD must reproduce the frozen candidate lists before
NEW is reported. No training, new method, threshold search or activation;
production acne stays accepted:false, file:null. Coverage gained is reported
separately from detection; outside-label areas are never auto-scored.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_acne_measurement_scope as audit
from audit_acne_measurement_scope import (AuditError, sha_file, read_json, normalized_text_sha, check_roots, map_path,
                                          TAKEOVER, COMPARISON, REGIONS, FROZEN_COMMIT, FROZEN_MANIFEST_SHA256)

VERSION = 'acne-closed-support-ab-v1'
AUDIT_REFERENCE = 'fe7042ef26f1504f75658ac6218517e1bd61a32c'
PRIOR = ('docs/acne-measurement-audit-evidence-20261015.json', 'docs/acne-measurement-audit-manifest-20261015-amendment1.json')
CODE_FILES = audit.CODE_FILES + ('services/core-api/acne_surface_support.py',
                                 'scripts/skin-research/compare_acne_closed_support.py',
                                 'scripts/skin-research/source_skin_support.py')
INPUT_FILES = audit.INPUT_FILES


# ------------------------------------------------------------ support + methods
def support(ctx, kind):
    """Region masks for 'old' (frozen triangle-union) or 'new' (closed cells)."""
    if kind == 'old':
        return dict(ctx['masks'])
    from acne_surface_support import acne_support_masks
    return acne_support_masks(ctx['masks'], ctx['gray'].shape, ctx['payload']['meshes'], ctx['scale'], ctx['origin'])


def scoped(ctx, masks):
    """Frozen shared scope recomputed from given region masks; every other
    exclusion term is the frozen one (exclusion, hair, clipping, gray, acne_skin)."""
    allmesh = np.logical_or.reduce(list(masks.values()))
    overall = allmesh & (ctx['exclusion'] == 0) & ~ctx['hair'] & ~ctx['clipping'] & (ctx['gray'] > .12)
    regions = {k: v for k, v in masks.items() if k in REGIONS}
    eligible = overall & ctx['acne_skin'] & np.logical_or.reduce(list(regions.values()))
    return overall, regions, eligible


def run_method(entry, photo, kind, method):
    """One full analysis: decode -> production preprocessing/geometry -> support
    -> frozen method -> component map -> JSON. Mirrors evaluate_acne_classical.run."""
    import cv2
    from evaluate_acne_classical import production_context
    from acne_lab_dog import detect, candidate_result
    from skin_models import photo_input
    t0 = time.perf_counter()
    image, payload = audit.production_payload(photo, entry)
    ctx = production_context(payload); t1 = time.perf_counter()
    masks = support(ctx, kind); overall, regions, eligible = scoped(ctx, masks)
    origin, scale, shape = ctx['origin'], ctx['scale'], image.shape[:2]
    native_eligible = audit.to_native(eligible, origin, scale, shape)
    _, crop = photo_input(image, entry['alignment']['landmarks']); x, y, w, h = (crop[k] for k in ('x', 'y', 'width', 'height'))
    scope = np.zeros(shape, bool); scope[y:y + h, x:x + w] = True; native_eligible &= scope
    if method == 'A':
        from appearance_analysis import acne_candidates
        from skin_scan_baseline.blemishes import blemish_map
        baseline = blemish_map(ctx['image'], {k: (v * 255).astype(np.uint8) for k, v in masks.items()})
        frozen, _ = acne_candidates(ctx['red'], ctx['gray'], ctx['saturation'], ctx['high'], ctx['local_contrast'], baseline, overall)
        objects, rejected = [], 0
        for bx, by, bw, bh, count, blob in frozen:
            owners = [k for k in REGIONS if k in regions and regions[k][blob].mean() >= .65]
            if not owners or not eligible[blob].all(): rejected += 1; continue
            objects.append(dict(x=bx, y=by, width=bw, height=bh, areaPixels=count, region=owners[0], pixels=np.column_stack(np.where(blob))[:, ::-1]))
        result, mask = candidate_result(objects, eligible.shape, origin, scale)
        native_map = audit.to_native(mask, origin, scale, shape)
        diag = dict(valid=True, originalComponents=len(frozen), sharedScopeRejected=rejected)
    else:
        objects, _, diag = detect(image[y:y + h, x:x + w], native_eligible[y:y + h, x:x + w], ctx['face_pixels'])
        native_regions = {k: audit.to_native(v, origin, scale, shape) for k, v in regions.items()}
        accepted = []
        for obj in objects:
            obj = {**obj, 'x': obj['x'] + x, 'y': obj['y'] + y, 'pixels': obj['pixels'] + [x, y]}; px = obj['pixels']
            owners = [k for k in REGIONS if k in native_regions and native_regions[k][px[:, 1], px[:, 0]].mean() >= .65]
            if owners: obj['region'] = owners[0]; accepted.append(obj)
        result, native_map = candidate_result(accepted, shape)
        diag = {k: v for k, v in diag.items() if k not in ('sigmas',)}
    native_map &= native_eligible
    result.update(method=method, support=kind, diagnostics=diag, activeSourcePixels=int(native_map.sum()))
    json.dumps(result, allow_nan=False); t2 = time.perf_counter()
    result['seconds'] = dict(preprocessing=t1 - t0, detectionMapSerialization=t2 - t1, full=t2 - t0)
    return result, native_map, native_eligible, ctx, masks, crop


def strip(rows):
    keys = ('x', 'y', 'width', 'height', 'areaPixels', 'region')
    return [{k: v for k, v in r.items() if k in keys} for r in rows]


def boxes(rows):
    return [[c['x'], c['y'], c['x'] + c['width'], c['y'] + c['height']] for c in rows]


def cell_counts(meshes):
    """Number of closed 4-edge convex cells per exported acne region (for receipts)."""
    import itertools, cv2
    out = {}
    for k in REGIONS:
        if k not in meshes: continue
        m = meshes[k]; edges = {tuple(sorted(e)) for e in m['edges']}; nb = {i: set() for i in range(len(m['points']))}
        for a, b in edges: nb[a].add(b); nb[b].add(a)
        pts = np.asarray([[p['x'], p['y']] for p in m['points']], np.float32); cells = set()
        for a, b in itertools.combinations(nb, 2):
            if (a, b) in edges: continue
            for c, d in itertools.combinations(sorted(nb[a] & nb[b]), 2):
                if tuple(sorted((c, d))) in edges: continue
                if cv2.isContourConvex(pts[[a, c, b, d]]): cells.add(tuple(sorted((a, b, c, d))))
        out[k] = len(cells)
    return out


# --------------------------------------------------------------- per photo
def photo_compare(s, input_root, entry, targets, frozen, orig_row, adjud, lease):
    import cv2
    from acne_lab_dog import match_boxes
    photo = (Path(input_root) / TAKEOVER / 'product-inputs' / s / 'snapshot.png').read_bytes()
    out = dict(sha256=s, kinds={}); maps = {}
    for kind in ('old', 'new'):
        per = {}
        for m in 'AB':
            r1, map1, el1, ctx, masks, crop = run_method(entry, photo, kind, m); lease.check()
            r2, map2, el2, *_ = run_method(entry, photo, kind, m); lease.check()
            stable = r1['candidates'] == r2['candidates'] and np.array_equal(map1, map2) and np.array_equal(el1, el2)
            if not stable: raise AuditError('NON_DETERMINISTIC:' + s[:8] + kind + m)
            per[m] = dict(result=r1, repeatSeconds=r2['seconds'], map=map1, eligible=el1)
        if kind == 'old':
            if per['A']['result']['candidates'] != frozen['A']['candidates'] or strip(per['B']['result']['candidates']) != strip(frozen['B']['candidates']):
                raise AuditError('OLD_SUPPORT_DOES_NOT_REPRODUCE_FROZEN:' + s[:8])
        if not np.array_equal(per['A']['eligible'], per['B']['eligible']):
            raise AuditError('A_B_SUPPORT_DIFFERS:' + s[:8] + kind)
        maps[kind] = dict(eligible=per['A']['eligible'], ctx=ctx, masks=masks, crop=crop, preds={m: boxes(per[m]['result']['candidates']) for m in 'AB'})
        out['kinds'][kind] = dict(eligiblePixels=int(per['A']['eligible'].sum()),
                                  methods={m: dict(candidateCount=per[m]['result']['candidateCount'], candidates=per[m]['result']['candidates'],
                                                   diagnostics=per[m]['result']['diagnostics'], seconds=per[m]['result']['seconds'],
                                                   repeatSeconds=per[m]['repeatSeconds'], staticRepeatIdentical=True) for m in 'AB'})
    ctx = maps['old']['ctx']; shape = maps['old']['eligible'].shape; crop = maps['old']['crop']
    out['closedCellsPerRegion'] = cell_counts(ctx['payload']['meshes'])
    added = maps['new']['eligible'] & ~maps['old']['eligible']; lost = maps['old']['eligible'] & ~maps['new']['eligible']
    if lost.any(): raise AuditError('NEW_SUPPORT_DROPS_OLD_PIXELS:' + s[:8])
    out['addedEligiblePixels'] = int(added.sum())
    # Other exclusions preserved: no added pixel may be in any frozen exclusion term.
    stages_new, native_new, canvas = audit.stage_masks_for(dict(ctx, masks=maps['new']['masks']), entry['snapshot']['exclusions'], crop, shape)
    for name in ('autoRectangles', 'frameEdge', 'landmarkHoles', 'ocularMargin', 'browHull', 'hair', 'valueClipping', 'allChannelClipping', 'grayAtOrBelow012'):
        if (added & native_new[name]).any(): raise AuditError('ADDED_SUPPORT_VIOLATES_EXCLUSION:' + name)
    if not (added & ~native_new['faceOval']).sum() == 0: raise AuditError('ADDED_SUPPORT_OUTSIDE_FACE_OVAL')
    final_new = np.logical_and.reduce([v[1] for v in stages_new])
    if not np.array_equal(final_new, maps['new']['eligible']): raise AuditError('NEW_STAGE_RECOMPOSITION_MISMATCH')
    stages_old, _, _ = audit.stage_masks_for(ctx, entry['snapshot']['exclusions'], crop, shape)
    env = audit.region_detail(ctx, entry.get('matchedAngle'), shape)[1]['envelope5']
    out['addedPixelsOutsideRegionEnvelopes'] = int((added & ~env).sum())
    # B filter behaviour on each support (counts only; filters are not tuned).
    out['bFilterRejections'] = {k: out['kinds'][k]['methods']['B']['diagnostics'].get('rejections') for k in ('old', 'new')}
    out['aSharedScopeRejected'] = {k: out['kinds'][k]['methods']['A']['diagnostics'].get('sharedScopeRejected') for k in ('old', 'new')}
    truth = [t['box'] for t in targets]
    out['matching'] = {k: {m: dict(iou050=match_boxes(truth, maps[k]['preds'][m]), centerHits=audit.center_hits(truth, maps[k]['preds'][m]))
                           for m in 'AB'} for k in ('old', 'new')}
    rows = []
    for t in targets:
        b = t['box']; r = dict(targetId=t['targetId'], cohort=t['cohort'], scaleBand=t['scaleBand'], sourceBox=b, kinds={})
        for k, st in (('old', stages_old), ('new', stages_new)):
            masks_attr, _ = audit.attribute_masks(st, b)
            mr = {}
            for m in 'AB':
                preds = maps[k]['preds'][m]; ious = [audit.iou(b, p) for p in preds]
                best = max(ious) if ious else None
                hit = any(p[0] == t['index'] for p in out['matching'][k][m]['iou050'])
                center = any(p[0] == t['index'] for p in out['matching'][k][m]['centerHits'])
                mr[m] = dict(bestIoU=best, iou050Hit=hit, centerHit=center, overlappingCandidates=sum(v > 0 for v in ious))
            r['kinds'][k] = dict(centerFirstLoss=masks_attr['centerFirstLoss'], centerInSupport=masks_attr['centerEligible'],
                                 boxFractionEligible=masks_attr['boxFractionEligible'], methods=mr)
        r['centerInRegionEnvelope'] = audit.center_value(env, b)
        rows.append(r)
    out['targets'] = rows
    # Reviewed negatives: same explicit negative-face scope; outside-label areas are not scored.
    out['negative'] = None
    if orig_row.get('negativeROI') and not orig_row.get('annotations'):
        from source_skin_support import known_skin_scope
        image = cv2.imdecode(np.frombuffer(photo, np.uint8), cv2.IMREAD_COLOR)
        clean = known_skin_scope({**orig_row, 'landmarks': entry['alignment']['landmarks']}, image) > 0
        neg = {}
        for m in 'AB':
            old_boxes = maps['old']['preds'][m]; rows_m = []
            for k in ('old', 'new'):
                for i, p in enumerate(maps[k]['preds'][m]):
                    cx, cy = audit.box_center(p); in_scope = bool(clean[cy, cx]) if 0 <= cy < clean.shape[0] and 0 <= cx < clean.shape[1] else None
                    prior = None
                    if p in old_boxes:
                        prior = adjud.get((m, s, old_boxes.index(p)))
                    status = ('PRIOR:' + prior) if prior else ('NEW_IN_NEGATIVE_LABEL_SCOPE' if in_scope else 'OUTSIDE_NEGATIVE_LABEL_SCOPE')
                    rows_m.append(dict(support=k, candidate=i, sourceBox=p, centerInNegativeLabelScope=in_scope,
                                       automaticProjection=bool(in_scope and maps[k]['eligible'][cy, cx]), status=status,
                                       newVersusOld=p not in old_boxes))
            neg[m] = rows_m
        out['negative'] = neg
        maps['clean'] = clean
    return out, maps


# -------------------------------------------------------------------- overlays
def render(s, maps, result, targets, out_dir):
    import cv2
    ctx = maps['old']['ctx']; image = ctx['bgr'].copy(); old, new = maps['old']['eligible'], maps['new']['eligible']
    tint = (image * .35).astype(np.uint8)
    tint[old] = image[old]
    tint[new & ~old] = (image[new & ~old] * .5 + np.array([0, 200, 0]) * .5).astype(np.uint8)
    for t in targets:
        b = t['box']; cv2.rectangle(tint, (int(b[0]) - 3, int(b[1]) - 3), (int(np.ceil(b[2])) + 3, int(np.ceil(b[3])) + 3), (0, 255, 255), 2)
        cv2.putText(tint, str(t['index']), (int(b[2]) + 4, int(b[1])), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
    for m, col in (('A', (0, 120, 255)), ('B', (255, 255, 0))):
        for p in maps['new']['preds'][m]:
            cv2.rectangle(tint, (int(p[0]), int(p[1])), (int(np.ceil(p[2])), int(np.ceil(p[3]))), col, 1)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = min(1., 1100 / max(tint.shape[:2]))
    cv2.imwrite(str(out_dir / f'{s[:8]}-support-old-new.png'), cv2.resize(tint, None, fx=f, fy=f, interpolation=cv2.INTER_AREA))
    tiles = []
    neg = result.get('negative') or {}
    for m in 'AB':
        for r in neg.get(m, []):
            if r['support'] != 'new' or r['status'] != 'NEW_IN_NEGATIVE_LABEL_SCOPE': continue
            p = r['sourceBox']; cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2; half = max(24., 4 * max(p[2] - p[0], p[3] - p[1]))
            x0, y0 = int(max(0, cx - half)), int(max(0, cy - half)); x1, y1 = int(min(image.shape[1], cx + half)), int(min(image.shape[0], cy + half))
            raw = cv2.resize(image[y0:y1, x0:x1], (200, 200), interpolation=cv2.INTER_NEAREST)
            ov = cv2.resize(tint[y0:y1, x0:x1], (200, 200), interpolation=cv2.INTER_NEAREST)
            fx, fy = 200 / max(1, x1 - x0), 200 / max(1, y1 - y0)
            for pane in (raw, ov):
                cv2.rectangle(pane, (int((p[0] - x0) * fx), int((p[1] - y0) * fy)), (int((p[2] - x0) * fx), int((p[3] - y0) * fy)), (0, 0, 255), 1)
            tile = cv2.copyMakeBorder(np.hstack([raw, ov]), 18, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(tile, f'{s[:8]} {m}{r["candidate"]}', (3, 13), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(tile)
    if tiles:
        cols = 4; rows = [np.hstack(tiles[i:i + cols] + [np.full_like(tiles[0], 255)] * (cols - len(tiles[i:i + cols]))) for i in range(0, len(tiles), cols)]
        cv2.imwrite(str(out_dir / f'{s[:8]}-new-negative-candidates.png'), np.vstack(rows))


# ------------------------------------------------------------------ summary
def summarize(photos):
    rows = [t for p in photos for t in p.get('targets', [])]
    res = {}
    for name, cohort in (('scopeB', 'scope-B-development'), ('controlsMeasured', 'heldout-train')):
        sub = [r for r in rows if r['cohort'] == cohort]
        c = dict(targets=len(sub))
        for k in ('old', 'new'):
            c[k] = dict(centerInSupport=sum(bool(r['kinds'][k]['centerInSupport']) for r in sub),
                        anyBoxAreaInSupport=sum((r['kinds'][k]['boxFractionEligible'] or 0) > 0 for r in sub),
                        firstLoss=audit._count([r['kinds'][k]['centerFirstLoss'] or 'IN_SUPPORT' for r in sub]),
                        **{m: dict(iou050=sum(r['kinds'][k]['methods'][m]['iou050Hit'] for r in sub),
                                   center=sum(r['kinds'][k]['methods'][m]['centerHit'] for r in sub),
                                   anyOverlap=sum(r['kinds'][k]['methods'][m]['overlappingCandidates'] > 0 for r in sub)) for m in 'AB'})
        c['recoveredIntoSupport'] = [r['targetId'] for r in sub if not r['kinds']['old']['centerInSupport'] and r['kinds']['new']['centerInSupport']]
        c['stillOutsideSupport'] = [r['targetId'] for r in sub if not r['kinds']['new']['centerInSupport']]
        res[name] = c
    neg = {}
    for m in 'AB':
        for k in ('old', 'new'):
            rs = [r for p in photos if p.get('negative') for r in p['negative'][m] if r['support'] == k]
            neg[f'{m}-{k}'] = dict(photos=sum(1 for p in photos if p.get('negative')), candidates=len(rs),
                                    automaticProjection=sum(r['automaticProjection'] for r in rs), status=audit._count([r['status'] for r in rs]))
    res['negatives'] = neg
    return res


def build_manifest(code_root, input_root):
    prior_manifest = read_json(Path(code_root) / PRIOR[1])
    return dict(version=VERSION, kind='geometry-only comparison of frozen classical A/B; post-hoc development data; NOT product acceptance',
                productDecisionChanged=False, productionAcne=dict(accepted=False, file=None), auditReference=AUDIT_REFERENCE,
                frozenCommit=FROZEN_COMMIT, frozenManifestSHA256=FROZEN_MANIFEST_SHA256,
                priorAudit={p: normalized_text_sha(Path(code_root) / p) for p in PRIOR},
                code={p: dict(normalizedSHA256=normalized_text_sha(Path(code_root) / p)) for p in CODE_FILES},
                inputs={p: dict(sha256=sha_file(Path(input_root) / p)) for p in INPUT_FILES},
                photos=prior_manifest['photos'], targets=prior_manifest['targets'],
                changedElement='acne analysis support only: five acne region masks polygon_mask -> closed_surface_mask (acne_surface_support.acne_support_masks); this also feeds A blemish_map region masks, shared eligible scope and region ownership',
                unchanged=['A/B colour operations', 'size/shape/fill/boundary/dark filters', 'thresholds and MAD config', 'IoU>=.50 greedy and centre matching',
                           'exclusions, hair, glare, gray, face oval, photo_input crop', 'other criteria masks and display mesh', 'fixed 14 + 29 target denominators'],
                order='OLD support must reproduce the frozen A/B candidate lists before NEW is reported',
                report=['before/after per target first loss', 'centre-in-support counts', 'recovered-from-cell-gap targets',
                        'still-outside region/pose targets', 'IoU>=.50 one-to-one primary; centre secondary', 'reviewed-negative FP with prior adjudication and new-candidate visual review',
                        'timing and static repeat'],
                negativeRule='prior adjudication carries over only for identical candidate boxes; new candidates outside the explicit negative label scope are not scored; new ones inside it are reviewed visually and stay UNKNOWN when hair/border is involved',
                computeBudget=dict(process='single, one photo at a time', runs='13 photos x 2 supports x 2 methods x 2 repeats',
                                   lease='HeavyJobLease 700 MiB private / 1200 MiB available (unchanged)', wallClockLimitSeconds=900))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('phase', choices=['manifest', 'run'])
    ap.add_argument('--input-root', required=True); ap.add_argument('--output-root', required=True)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--code-root', default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args(argv)
    input_root, output_root = check_roots(a.input_root, a.output_root); code_root = Path(a.code_root).resolve()
    sys.path[:0] = [str(code_root / 'scripts/skin-research'), str(code_root / 'services/core-api')]
    mp = Path(a.manifest)
    if a.phase == 'manifest':
        if mp.exists(): raise AuditError('MANIFEST_ALREADY_FROZEN')
        mp.write_text(json.dumps(build_manifest(code_root, input_root), indent=1, ensure_ascii=False) + '\n', 'utf8')
        print(json.dumps(dict(manifest=str(mp), sha256=sha_file(mp)))); return
    man = read_json(mp)
    for p, v in man['code'].items():
        if normalized_text_sha(code_root / p) != v['normalizedSHA256']: raise AuditError('CODE_IDENTITY_CHANGED:' + p)
    for p, v in man['inputs'].items():
        if sha_file(input_root / p) != v['sha256']: raise AuditError('INPUT_IDENTITY_CHANGED:' + p)
    output_root.mkdir(parents=True, exist_ok=True)
    if (output_root / 'comparison.json').exists(): raise AuditError('COMPLETED_COMPARISON_NOT_REPEATED')
    pre, orig, scope, ev, frozen_man, res = audit.load_frozen(input_root)
    adj = read_json(input_root / COMPARISON / 'negative-visibility-adjudication.json')
    adjud = {(r['method'], r['sha256'], r['candidateIndex']): r['status'] for r in adj['rows']}
    by_photo = {}
    for t in man['targets']: by_photo.setdefault(t['sha256'], []).append(t)
    from heavy_job_lease import HeavyJobLease
    import cv2
    started = time.monotonic(); photos = []
    with HeavyJobLease('CLAUDE-acne-closed-support-ab', peak_mib=700, minimum_available_mib=1200, memory_metric='private') as lease:
        cv2.setNumThreads(2)
        for p in man['photos']:
            if not p['staticProductPass']: continue
            lease.check(); s = p['sha256']
            if time.monotonic() - started > man['computeBudget']['wallClockLimitSeconds']: raise AuditError('COMPUTE_BUDGET_EXCEEDED')
            if sha_file(input_root / TAKEOVER / 'product-inputs' / s / 'snapshot.png') != p['snapshotSHA256']: raise AuditError('SNAPSHOT_CHANGED')
            result, maps = photo_compare(s, input_root, pre[s], by_photo.get(s, []), {m: res[m][s] for m in 'AB'}, orig[s], adjud, lease)
            render(s, maps, result, by_photo.get(s, []), output_root / 'overlays'); del maps
            result['cohort'] = p['cohort']; photos.append(result)
            print(json.dumps(dict(sha=s[:8], added=result['addedEligiblePixels'], cands={k: {m: result['kinds'][k]['methods'][m]['candidateCount'] for m in 'AB'} for k in ('old', 'new')})), flush=True)
        receipt = lease.receipt()
    receipt['scopeNote'] = 'process/RAM census ran inside the desktop Linux VM; it cannot see Windows-host processes'
    report = dict(version=VERSION, manifestSHA256=sha_file(mp), summary=summarize(photos), photos=photos, resource=receipt,
                  elapsedSeconds=time.monotonic() - started,
                  environment=dict(python=sys.version.split()[0], numpy=np.__version__, opencv=cv2.__version__, skimage=__import__('skimage').__version__),
                  torchImported='torch' in sys.modules, onnxruntimeImported='onnxruntime' in sys.modules)
    (output_root / 'comparison.json').write_text(json.dumps(report, indent=1, allow_nan=False) + '\n', 'utf8')
    print(json.dumps(dict(results=str(output_root / 'comparison.json'), elapsed=report['elapsedSeconds'])))


if __name__ == '__main__':
    main()
