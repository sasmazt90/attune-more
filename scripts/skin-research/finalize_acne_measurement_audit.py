"""Write the pixel-free evidence receipt for the acne measurement-scope audit.

Reads the completed audit results (output-root) and the read-only input-root;
writes one JSON with no photos, overlays, base64 or raw pixel arrays.
VISUAL_REVIEW below is a post-hoc, NON-blind Claude engineering review of the
source overlays of every target whose centre was lost at a mask stage. It is
not dermatologist/human adjudication and does not create labels.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_acne_measurement_scope import sha_file, read_json, check_roots, VERSION

VISIBLE = 'VISIBLE_SKIN_NO_OCCLUDER_SEEN'
VISUAL_REVIEW = {
    # FRONT, presentation-mesh cell gap inside the region envelope
    'f2ed24a9#2': (VISIBLE, 'glabella skin between brow exclusion and nose mesh'),
    'f2ed24a9#11': (VISIBLE, 'lower-cheek skin in the same lesion cluster as eligible triangles'),
    'f2ed24a9#14': (VISIBLE, 'chin/cheek skin; adjacent triangle is eligible'),
    'f2ed24a9#15': (VISIBLE, 'chin/cheek skin; adjacent triangle is eligible'),
    'f2ed24a9#16': (VISIBLE, 'chin/cheek skin; 36% of box on eligible triangles'),
    'f2ed24a9#17': (VISIBLE, 'cheek skin between mesh triangles'),
    '695ed248#1': (VISIBLE, 'skin below the lower lip; lip itself is outside the box'),
    '4a1762ee#0': (VISIBLE, 'cheek skin; glare is nearby but not over the target'),
    # FRONT, outside every exported region envelope (perioral / upper lip / brow margin)
    'f2ed24a9#4': (VISIBLE, 'upper-lip skin beside the nostril; strong warm cast'),
    'f2ed24a9#5': (VISIBLE, 'upper-lip skin beside the nostril; strong warm cast'),
    'f2ed24a9#6': (VISIBLE, 'forehead skin above the brow margin'),
    'f2ed24a9#10': (VISIBLE, 'upper-lip skin'),
    'f2ed24a9#12': (VISIBLE, 'lower cheek/jaw skin outside the chin and cheek envelopes'),
    'f2ed24a9#18': (VISIBLE, 'upper-lip skin'),
    'f2ed24a9#20': (VISIBLE, 'upper-lip skin'),
    '695ed248#2': (VISIBLE, 'upper-lip / nasolabial skin'),
    '695ed248#3': (VISIBLE, 'alar-cheek junction skin beside the nasal crease'),
    '26ebdde4#2': ('UNKNOWN', 'box straddles the lip vermilion border; lips are excluded by design'),
    # Side pose: only one cheek mesh exported by the product snapshot
    '2ed3716e#0': (VISIBLE, 'forehead skin; LEFT pose exports rightCheek only'),
    '2ed3716e#1': (VISIBLE, 'forehead skin above the brow; LEFT pose exports rightCheek only'),
    '2ed3716e#2': (VISIBLE, 'forehead skin; LEFT pose exports rightCheek only'),
    '2ed3716e#3': (VISIBLE, 'forehead skin above the brow; LEFT pose exports rightCheek only'),
    '2ed3716e#4': (VISIBLE, 'forehead skin above the brow; LEFT pose exports rightCheek only'),
    '55d380f7#0': (VISIBLE, 'chin skin; RIGHT pose exports leftCheek only'),
    '55d380f7#1': (VISIBLE, 'nasal ala skin above the nostril shadow; RIGHT pose exports leftCheek only'),
    '55d380f7#2': (VISIBLE, 'nasal ala skin above the nostril shadow; RIGHT pose exports leftCheek only'),
    '55d380f7#3': (VISIBLE, 'nasal ala skin; RIGHT pose exports leftCheek only'),
    '55d380f7#4': (VISIBLE, 'nasal ala skin; RIGHT pose exports leftCheek only'),
    '55d380f7#6': (VISIBLE, 'chin skin; RIGHT pose exports leftCheek only'),
}


def compact_target(t):
    m = t['masks']
    return dict(targetId=t['targetId'], cohort=t['cohort'], sourceSHA256=t['sha256'], annotationIndex=t['annotationIndex'],
                sourceBox=t['sourceBox'], sourceCenter=t['sourceCenter'], sourceResolution=t['sourceResolution'],
                analysisResolution=t['analysisResolution'], origin=t['origin'], scale=t['scale'], analysisBox=t['analysisBox'],
                photoInputCrop={k: t['photoInputCrop'][k] for k in ('x', 'y', 'width', 'height')}, scaleBand=t['scaleBand'],
                targetAreaSourcePixels=t['targetArea'],
                centerFirstLoss=m['centerFirstLoss'], areaFullLossStage=m['areaFullLossStage'],
                boxFractionEligible=m['boxFractionEligible'],
                independentCenterRejected={k: v['centerRejected'] for k, v in m['independent'].items()},
                independentBoxFractionPassing={k: v['boxFractionPassing'] for k, v in m['independent'].items()},
                sequentialBoxFractionRemaining={v['stage']: v['boxFractionRemaining'] for v in m['sequential']},
                partsCenter=t['partsCenter'], regionDetail=t['regionDetail'],
                methods={k: {f: v[f] for f in ('primaryOutcome', 'areaOutcome', 'replayVerified', 'rawResponseInBox',
                                                'rawResponseInEligibleBox', 'rawComponentsTouchingBox', 'frozenCandidatesOverlapping',
                                                'frozenCandidateCentersInsideBox', 'bestIoU', 'reachableMaxIoUGivenMethodGeometry',
                                                'methodCandidateBoxAreaRangeNative')} for k, v in t['methods'].items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-root', required=True); ap.add_argument('--output-root', required=True)
    ap.add_argument('--manifest', required=True); ap.add_argument('--first-run-results')
    ap.add_argument('--evidence', required=True)
    a = ap.parse_args()
    input_root, output_root = check_roots(a.input_root, a.output_root)
    res_path = output_root / 'audit-results.json'; res = read_json(res_path); man = read_json(a.manifest)
    if res['manifestSHA256'] != sha_file(a.manifest):
        raise RuntimeError('RESULTS_NOT_FROM_THIS_MANIFEST')
    details = {t['targetId']: t for t in res['targetDetails']}
    lost = [k for k, t in details.items() if t['masks']['centerFirstLoss']]
    if sorted(lost) != sorted(VISUAL_REVIEW):
        raise RuntimeError('VISUAL_REVIEW_MUST_COVER_EXACTLY_THE_MASK_LOST_TARGETS')
    review = []
    for k in sorted(VISUAL_REVIEW):
        overlay = output_root / 'overlays' / (k.replace('#', '-t') + '.png')
        review.append(dict(targetId=k, verdict=VISUAL_REVIEW[k][0], note=VISUAL_REVIEW[k][1],
                           regionCategory=details[k]['regionDetail']['category'], overlaySHA256=sha_file(overlay)))
    counts = {}
    for r in review:
        counts.setdefault(r['regionCategory'], {}).setdefault(r['verdict'], 0)
        counts[r['regionCategory']][r['verdict']] += 1
    build = input_root / 'apps/vehicle-app/.next/BUILD_ID'
    acne = read_json(input_root / 'services/core-api/models/skin-focused.json')['models']['acne']
    evidence = dict(
        version=VERSION, kind=man['kind'], productDecisionChanged=False,
        productionAcneAtInputRoot=dict(accepted=acne.get('accepted'), file=acne.get('file')),
        buildIdAtInputRoot=build.read_text('utf8').strip() if build.exists() else None,
        frozenCommit=man['frozenCommit'], frozenManifestSHA256=man['frozenManifestSHA256'],
        auditManifest=dict(path=Path(a.manifest).name, sha256=sha_file(a.manifest), amends=man.get('amends')),
        firstRunResultsSHA256=sha_file(a.first_run_results) if a.first_run_results else None,
        resultsSHA256=sha_file(res_path), codeIdentities=man['code'], inputIdentities=man['inputs'],
        expectedCounts=man['expectedCounts'], summary=res['summary'],
        photos=[{k: v for k, v in p.items()} for p in res['photos']],
        targetsGateRejected=[t for t in res['targets'] if not t['gatePassed']],
        targetsMeasured=[compact_target(details[t['targetId']]) for t in res['targets'] if t['gatePassed']],
        visualReview=dict(reviewer='Claude (this session), post-hoc source-overlay engineering review', blinded=False,
                          clinicalOrHumanAdjudication=False, performedAfterResults=True, labelsCreated=False,
                          rule='UNKNOWN unless the structure is visible; no error label for unseen structure',
                          counts=counts, rows=review),
        resource=res['resource'], elapsedSeconds=res['elapsedSeconds'], environment=res['environment'],
        torchImported=res['torchImported'], onnxruntimeImported=res['onnxruntimeImported'],
        excludedFromGit='photos, overlays, maps, base64 and raw pixel arrays stay in the local output-root only')
    text = json.dumps(evidence, indent=1, ensure_ascii=False, allow_nan=False)
    if 'base64' in text.replace('base64 and raw', '') or 'data:image' in text:
        raise RuntimeError('PIXEL_PAYLOAD_IN_EVIDENCE')
    Path(a.evidence).write_text(text + '\n', 'utf8')
    print(json.dumps(dict(evidence=a.evidence, sha256=sha_file(a.evidence), reviewed=len(review), counts=counts)))


if __name__ == '__main__':
    main()
