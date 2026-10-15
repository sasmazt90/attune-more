"""Pixel-free receipt for the closed-cell support comparison.

Adds (1) per-target before/after outcome stages using the frozen-code replays
on the NEW support (used only when the replay reproduces the NEW candidate
list exactly) and (2) a post-hoc, NON-blind Claude visual review of every new
candidate that falls inside the existing explicit negative-face label scope.
No labels are created; hair/beard/border stays UNKNOWN.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_acne_measurement_scope as audit
import compare_acne_closed_support as compare
from audit_acne_measurement_scope import sha_file, read_json, check_roots, TAKEOVER, COMPARISON, REGIONS

SKIN, UNK = 'reviewed-non-pimple-visible-skin-support', 'UNKNOWN-hair-or-border-support'
# (photo prefix, method, NEW-support candidate index) -> (verdict, note)
NEW_NEGATIVE_REVIEW = {
    **{('0560bfd8', 'A', i): (SKIN, 'visible facial skin texture/wrinkle; no hair over box') for i in (7, 8, 9, 10, 11)},
    **{('0560bfd8', 'B', i): (SKIN, 'visible facial skin texture/wrinkle; no hair over box') for i in
       (4, 8, 12, 22, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 35, 37, 39, 40, 41, 43, 44, 46, 47, 48, 50, 51, 52)},
    **{('02386f86', 'B', i): (SKIN, 'visible cheek skin') for i in (0, 2, 3, 5)},
    ('02413bf9', 'B', 3): (UNK, 'box touches the eyebrow edge'),
    **{('02413bf9', 'B', i): (UNK, 'beard over or around the box') for i in (6, 7, 8)},
    ('0597e811', 'A', 0): (SKIN, 'visible cheek skin'), ('0597e811', 'B', 0): (SKIN, 'visible cheek skin'),
    ('0597e811', 'B', 1): (SKIN, 'visible cheek skin'), ('0597e811', 'B', 2): (UNK, 'grey textured patch; hair/shadow cannot be excluded'),
    ('33da7a52', 'B', 1): (SKIN, 'bright nasal-bridge skin, not clipped, no hair'),
    ('36e4010b', 'A', 1): (SKIN, 'visible nose skin'), ('36e4010b', 'B', 0): (UNK, 'blond fringe over forehead'),
    ('36e4010b', 'B', 14): (SKIN, 'visible cheek skin'),
}


def new_outcomes(entry, photo, targets, new_candidates):
    """Per-target stage on NEW support with frozen-code replays (no new candidates)."""
    from evaluate_acne_classical import production_context
    from skin_models import photo_input
    image, payload = audit.production_payload(photo, entry); ctx = production_context(payload)
    masks = compare.support(ctx, 'new'); overall, regions, eligible = compare.scoped(ctx, masks)
    ctx2 = dict(ctx, masks=masks, overall=overall); shape = image.shape[:2]; origin, scale = ctx['origin'], ctx['scale']
    _, crop = photo_input(image, entry['alignment']['landmarks'])
    stages, _, _ = audit.stage_masks_for(ctx2, entry['snapshot']['exclusions'], crop, shape)
    final = np.logical_and.reduce([v[1] for v in stages])
    native_regions = {k: audit.to_native(v, origin, scale, shape) for k, v in regions.items()}
    ra = audit.replay_a(ctx2, eligible); rb = audit.replay_b(image, final, crop, ctx['face_pixels'], native_regions)
    import cv2
    ra['rawNative'] = audit.to_native(ra['raw'], origin, scale, shape)
    ra['labelsNative'] = cv2.warpAffine(ra['labels'].astype(np.float32), audit.analysis_to_source_matrix(origin, scale), (shape[1], shape[0]), flags=cv2.INTER_NEAREST).astype(np.int32)
    rb['rawNative'], rb['labelsNative'] = rb['raw'], rb['labels']
    accepted = {'A': sum(c['reason'] == 'ACCEPTED' for c in ra['components']), 'B': sum(c['reason'] == 'ACCEPTED' for c in rb['components'])}
    verified = {m: accepted[m] == len(new_candidates[m]) for m in 'AB'}
    preds = {m: compare.boxes(new_candidates[m]) for m in 'AB'}
    out = []
    for t in targets:
        b = t['box']; masks_attr, cumulative = audit.attribute_masks(stages, b); w = audit.box_window(b, shape); row = dict(targetId=t['targetId'])
        for m, rp in (('A', ra), ('B', rb)):
            raw = None; reasons = []
            if w is not None:
                patch = rp['rawNative'][w[0]:w[1], w[2]:w[3]]; raw = bool((patch & cumulative[w[0]:w[1], w[2]:w[3]]).any())
                labels = set(np.unique(rp['labelsNative'][w[0]:w[1], w[2]:w[3]])) - {0}
                reasons = sorted({c['reason'] for c in rp['components'] if c['label'] in labels})
            ious = [audit.iou(b, p) for p in preds[m]]; best = max(ious) if ious else None
            row[m] = dict(outcome=audit.classify(dict(passed=True), masks_attr, verified[m], raw, any(v > 0 for v in ious), best),
                          bestIoU=best, componentReasonsTouchingBox=reasons)
        out.append(row)
    return out, verified


def main():
    ap = argparse.ArgumentParser()
    for k in ('--input-root', '--output-root', '--manifest', '--evidence', '--prior-evidence'): ap.add_argument(k, required=True)
    a = ap.parse_args()
    input_root, output_root = check_roots(a.input_root, a.output_root)
    cmp = read_json(output_root / 'comparison.json'); man = read_json(a.manifest); prior = read_json(a.prior_evidence)
    if cmp['manifestSHA256'] != sha_file(a.manifest): raise RuntimeError('RESULTS_NOT_FROM_THIS_MANIFEST')
    pre = {r['sha256']: r for r in read_json(input_root / TAKEOVER / 'browser-preflight.json')['rows']}
    by_photo = {}
    for t in man['targets']: by_photo.setdefault(t['sha256'], []).append(t)
    prior_t = {t['targetId']: t for t in prior['targetsMeasured']}
    from heavy_job_lease import HeavyJobLease
    targets, replay = [], {}
    with HeavyJobLease('CLAUDE-acne-closed-support-finalize', peak_mib=700, minimum_available_mib=1200, memory_metric='private') as lease:
        for p in cmp['photos']:
            ts = by_photo.get(p['sha256'], [])
            if not ts: continue
            lease.check()
            photo = (input_root / TAKEOVER / 'product-inputs' / p['sha256'] / 'snapshot.png').read_bytes()
            rows, verified = new_outcomes(pre[p['sha256']], photo, ts, {m: p['kinds']['new']['methods'][m]['candidates'] for m in 'AB'})
            replay[p['sha256'][:8]] = verified
            cmp_t = {t['targetId']: t for t in p['targets']}
            for r in rows:
                old, c = prior_t[r['targetId']], cmp_t[r['targetId']]
                targets.append(dict(targetId=r['targetId'], cohort=c['cohort'], scaleBand=c['scaleBand'], sourceBox=c['sourceBox'],
                                    regionCategoryBefore=old['regionDetail']['category'],
                                    before=dict(centerFirstLoss=old['centerFirstLoss'], boxFractionEligible=old['boxFractionEligible'],
                                                **{m: dict(outcome=old['methods'][m]['primaryOutcome'], bestIoU=old['methods'][m]['bestIoU'],
                                                           iou050Hit=c['kinds']['old']['methods'][m]['iou050Hit'], centerHit=c['kinds']['old']['methods'][m]['centerHit']) for m in 'AB'}),
                                    after=dict(centerFirstLoss=c['kinds']['new']['centerFirstLoss'], boxFractionEligible=c['kinds']['new']['boxFractionEligible'],
                                               **{m: dict(outcome=r[m]['outcome'], bestIoU=r[m]['bestIoU'], componentReasonsTouchingBox=r[m]['componentReasonsTouchingBox'],
                                                          iou050Hit=c['kinds']['new']['methods'][m]['iou050Hit'], centerHit=c['kinds']['new']['methods'][m]['centerHit']) for m in 'AB'})))
        receipt = lease.receipt()
    review, counts = [], {}
    for p in cmp['photos']:
        if not p.get('negative'): continue
        for m in 'AB':
            for r in p['negative'][m]:
                if r['support'] != 'new' or r['status'] != 'NEW_IN_NEGATIVE_LABEL_SCOPE': continue
                key = (p['sha256'][:8], m, r['candidate'])
                if key not in NEW_NEGATIVE_REVIEW: raise RuntimeError('UNREVIEWED_NEW_NEGATIVE_CANDIDATE:%s' % (key,))
                v, note = NEW_NEGATIVE_REVIEW[key]
                review.append(dict(sha256=p['sha256'], method=m, newCandidateIndex=r['candidate'], sourceBox=r['sourceBox'], verdict=v, note=note))
    if len(review) != len(NEW_NEGATIVE_REVIEW): raise RuntimeError('REVIEW_TABLE_HAS_EXTRA_ROWS')
    neg = {}
    for m in 'AB':
        old_rows = [r for p in cmp['photos'] if p.get('negative') for r in p['negative'][m] if r['support'] == 'old']
        new_rows = [r for p in cmp['photos'] if p.get('negative') for r in p['negative'][m] if r['support'] == 'new']
        old_skin = sum(r['status'] == 'PRIOR:' + SKIN for r in old_rows); old_unk = sum(r['status'] == 'PRIOR:' + UNK for r in old_rows)
        new_skin = sum(r['status'] == 'PRIOR:' + SKIN for r in new_rows) + sum(v['method'] == m and v['verdict'] == SKIN for v in review)
        new_unk = sum(r['status'] == 'PRIOR:' + UNK for r in new_rows) + sum(v['method'] == m and v['verdict'] == UNK for v in review)
        neg[m] = dict(photos=7, before=dict(candidates=len(old_rows), automaticProjection=sum(r['automaticProjection'] for r in old_rows),
                                            reviewedVisibleSkin=old_skin, unknown=old_unk, reviewedPerPhoto=old_skin / 7),
                      after=dict(candidates=len(new_rows), automaticProjection=sum(r['automaticProjection'] for r in new_rows),
                                 reviewedVisibleSkin=new_skin, unknown=new_unk, reviewedPerPhoto=new_skin / 7,
                                 outsideNegativeLabelScope=sum(r['status'] == 'OUTSIDE_NEGATIVE_LABEL_SCOPE' for r in new_rows)))
    def tally(cohort, when, m):
        return audit._count([t[when][m]['outcome'] for t in targets if t['cohort'] == cohort])
    stage = {c: {w: {m: tally(c, w, m) for m in 'AB'} for w in ('before', 'after')} for c in ('scope-B-development', 'heldout-train')}
    def bsum(k):
        tot = {}
        for p in cmp['photos']:
            for r, v in (p['bFilterRejections'][k] or {}).items(): tot[r] = tot.get(r, 0) + v
        return tot
    photos = [{k: v for k, v in p.items() if k not in ('targets', 'negative', 'kinds')} | dict(
        cohort=p['cohort'], kinds={k: dict(eligiblePixels=p['kinds'][k]['eligiblePixels'], methods={m: {f: p['kinds'][k]['methods'][m][f] for f in ('candidateCount', 'seconds', 'repeatSeconds', 'staticRepeatIdentical', 'diagnostics')} for m in 'AB'}) for k in ('old', 'new')})
        for p in cmp['photos']]
    evidence = dict(version=compare.VERSION, kind=man['kind'], productDecisionChanged=False,
                    productionAcneAtInputRoot={k: read_json(input_root / 'services/core-api/models/skin-focused.json')['models']['acne'].get(k) for k in ('accepted', 'file')},
                    manifest=dict(path=Path(a.manifest).name, sha256=sha_file(a.manifest)), comparisonSHA256=sha_file(output_root / 'comparison.json'),
                    codeIdentities=man['code'], inputIdentities=man['inputs'], priorAudit=man['priorAudit'],
                    summary=cmp['summary'], outcomeStages=stage, bFilterRejectionTotals=dict(old=bsum('old'), new=bsum('new')),
                    newSupportReplayVerified=replay, targets=targets, negatives=neg,
                    newNegativeCandidateReview=dict(reviewer='Claude (this session), post-hoc overlay review', blinded=False, clinicalOrHumanAdjudication=False,
                                                    rule='prior negative-face label scope only; hair/beard/brow/ambiguous stays UNKNOWN', rows=review),
                    photos=photos, resource=dict(comparison=cmp['resource'], finalize=receipt), elapsedSeconds=cmp['elapsedSeconds'], environment=cmp['environment'],
                    excludedFromGit='photos, overlays, maps and pixel arrays stay in the local output-root only')
    text = json.dumps(evidence, indent=1, ensure_ascii=False, allow_nan=False)
    if 'data:image' in text: raise RuntimeError('PIXEL_PAYLOAD_IN_EVIDENCE')
    Path(a.evidence).write_text(text + '\n', 'utf8')
    print(json.dumps(dict(evidence=a.evidence, sha256=sha_file(a.evidence), stage=stage, negatives=neg, replay=replay)))


if __name__ == '__main__':
    main()
