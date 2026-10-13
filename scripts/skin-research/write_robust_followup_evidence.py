"""Generate bounded follow-up evidence from immutable inputs and actual script receipts."""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'services/core-api')]
import evaluate_periorbital_and_acne_comparative as audit
OUT=ROOT/'audit-results/dry-sag-robust-followup-20261013';PREV=ROOT/'audit-results/dry-sag-native-followup-20261013'
def read(path):return json.loads(path.read_text('utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
selection=read(PREV/'source-selection.json')
if isinstance(selection,dict):selection=selection.get('sources',selection.get('rows',[]))
categories={r['sha256'][:8]:r.get('imageCategory',r.get('category')) for r in selection}
experiments=[]
for name,path in [('robust-DoG',OUT/'robust-trial.json'),('robust-plate',OUT/'plate/robust-trial.json')]:
    receipt=read(path);rows=[]
    for row in receipt['sources']:
        prefix=row['source'];file=Path(row['path']);assert sha(file)==row['sha256']
        baseline_file=PREV/(prefix+'-normal-api.json');before=read(baseline_file) if baseline_file.exists() else None
        old=None
        if before and 'general' in before:
            v=next(v for v in before['general']['measurements'] if v['id']=='dry')
            alpha=audit.project_map_alpha(before['maps'].get('overview:dry'),cv2.imread(str(file)).shape)
            old=dict(value=v['value'],activeSourcePixels=int((alpha>0).sum()),reviewedNegativePixels=int((alpha[750:1050,750:1200]>0).sum()) if prefix=='e1646fda' else None)
        current=next((v for v in row['product'] or [] if v['region']=='overview'),None)
        rows.append(dict(source=prefix,sha256=row['sha256'],category=categories.get(prefix) or row['category'],partialBoxCandidateSupport=row['boxes'],productionV3Before=old,trialOverview=current))
    negative=next(r for r in rows if r['source']=='0642d4ab')
    partial=next(r for r in rows if r['source']=='594aadd0')
    negative_preserved=negative['trialOverview']['sourcePixels']<=negative['productionV3Before']['activeSourcePixels']
    partial_preserved=all(b['nativeAfter']>=b['nativeBefore'] for b in partial['partialBoxCandidateSupport'])
    accept=negative_preserved and partial_preserved
    # These trials were explicitly not integrated. Failures must remain visible.
    assert not accept,'An accepted hypothesis needs separate product integration and verification'
    experiments.append(dict(name=name,hypothesis=receipt['hypothesis'],seconds=receipt['seconds'],processCPUSeconds=receipt['processCPUSeconds'],sampledPeakRSSBytes=receipt['sampledPeakRSSBytes'],naturalNegativeSupportPreserved=negative_preserved,allPartialBoxNativeSupportPreserved=partial_preserved,eligibleForDelivery=accept,thresholdSearch=receipt['thresholdSearch'],productionChanged=receipt['productionChanged'],sources=rows,receiptSHA256=sha(path)))
camera_path=ROOT/'output/playwright'/OUT.name/'camera-receipt.json';camera=read(camera_path)
for source in ('0642d4ab','e1646fda'):
    row=next(r for r in read(OUT/'plate/robust-trial.json')['sources'] if r['source']==source)
    image=cv2.imread(row['path']);response=read(OUT/'plate'/(source+'-robust.json'))
    alpha=audit.project_map_alpha(response['maps'].get('overview:dry'),image.shape)>0
    overlay=image.copy();overlay[alpha]=(overlay[alpha]*.3+np.array([0,0,255])*.7).astype('uint8')
    cv2.imwrite(str(OUT/(source+'-rejected-product-plate.png')),overlay)
additional=[]
for row in read(OUT/'additional-sag-selection.json'):
    p=read(OUT/(row['sha256'][:8]+'-probe.json'))
    additional.append(dict(sourceSHA256=row['sha256'],path=row['absolutePath'],category='natural-photo-with-visible-smile; not neutral sag acceptance',quality=p['quality'],conditions=p['conditions'],angles=p['supportedAngles'],utilityPoseCaptureCompleted=p['poseCaptureCompleted'],snapshotFailure=p['snapshotFailure'],mouthOpening=p['mouthOpening']))
delivery=read(OUT/'delivery.json')
stage=ROOT/'.runtime/skin-dry-sag-robust-check-20261013'
stage_sources=read(stage/'source-receipt.json')
stage_matches={p:sha(ROOT/p)==digest for p,digest in stage_sources.items()};assert all(stage_matches.values())
stage_build=(stage/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip();assert stage_build
build_validation=dict(stagedBuildId=stage_build,deliveredBuildId=delivery['buildId'],frontendSourceMatches=stage_matches,stagedBuildPromoted=False,reason='Production frontend and backend are unchanged; protected normal build is retained')
evidence=dict(generatedUTC=datetime.now(timezone.utc).isoformat(),sourceBaseline='1f93e33289aed3ef3061adfe72597f5989d1bde0',productionBehaviorChanged=any(e['productionChanged'] for e in experiments),experiments=experiments,additionalSources=additional,actualAutomaticCamera=camera,delivery=delivery,buildValidation=build_validation,limitations=['No qualified natural neutral sag positive or complete-face peeling positive accepted.','Box support is not pixel truth, Dice, clinical severity or general accuracy.','Partial peeling, processed sources, natural reviewed negative ROI and transformed noise remain distinct.','No training, AG mutation, hosted call, source photo transformation for pose, or user record rewrite.'],previousEvidenceSHA256=sha(ROOT/'docs/dry-sag-native-evidence-20261013.json'))
(ROOT/'docs/dry-sag-robust-evidence-20261013.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),'utf8')
first,second=experiments
def product(e,s):return next(r for r in e['sources'] if r['source']==s)
p1=product(first,'e1646fda');p2=product(second,'0642d4ab');broad=product(second,'387e1700')['partialBoxCandidateSupport'][0];partial=product(first,'594aadd0')['partialBoxCandidateSupport'][1]
doc=f'''# Bounded robust dry/sag follow-up, 2026-10-13

Current baseline is `1f93e33289aed3ef3061adfe72597f5989d1bde0`; the attachment's older db3 baseline is not treated as current. **No further production algorithm is shipped.** Chin/overview sag v8, cheek v7 and dry v3 remain exact; other analysis sources, frontend, model and config hashes match the protected delivery.

Two new fixed hypotheses ran on the already selected local sources. This does not repeat the six previous failed trials or expand archives. No threshold search, training, model integration or hosted call. Selection adds only two previously visually inspected sag photos, closed before the 45-minute limit; both visibly smile and are not neutral acceptance positives.

| Hypothesis | Relevant positive support | Negative / regression | Decision / resources |
|---|---|---|---|
| Native DoG + robust median/MAD background | Natural partial 594aadd0 box at (194,326): {partial['nativeBefore']} → {partial['nativeAfter']} native candidate pixels | e1646fda reviewed forehead: {p1['productionV3Before']['reviewedNegativePixels']} → {p1['trialOverview']['reviewedNegativePixels']} product pixels | Reject: loses partial positive support; {first['seconds']:.2f}s, sampled peak RSS {first['sampledPeakRSSBytes']/2**20:.1f} MiB |
| Native bright plate + robust background, extreme 1/2-pixel impulses removed | Processed 387e1700 first box: {broad['nativeBefore']} → {broad['nativeAfter']} candidates | Natural 0642d4ab product: {p2['productionV3Before']['activeSourcePixels']} → {p2['trialOverview']['sourcePixels']} pixels | Reject: creates reviewed-negative support; {second['seconds']:.2f}s, sampled peak RSS {second['sampledPeakRSSBytes']/2**20:.1f} MiB |

Box counts are candidates in partial/weak annotation boxes, not labelled true-positive pixel counts or full ROI Dice. Exterior is unknown. Native before counts compare the old local native detector, whereas product before counts use the pinned normal v3 API output. These scopes are explicitly different. 387e1700 is processed with hand/cosmetic confounders; 594aadd0 is naturally photographed visible peeling with incomplete head and invalid product ROI. Neither becomes a complete-face acceptance example. c31892d1's earlier stage-by-stage loss diagnosis and source-coordinate layers remain preserved in the previous evidence; product v3 remains 0.066794 / 36 pixels.

The new robust trials identify the remaining failure more narrowly: thresholding fine DoG peaks still loses broad low-contrast peeling; replacing DoG with local bright prominence recovers broad fragments but accepts ordinary skin/reflection support. Native resolution and a robust background alone do not establish flake specificity. The rejected product overlays retain the exact false source pixels. No score floor, UI rounding change, copied raw candidates, or photo-specific rule is used.

## Actual normal automatic camera and history

Natural 55ec00b8 completed real browser MediaPipe → quality/FRONT pose → automatic camera capture → native crop → normal API → result → same-record history. Native YUV420 camera encoding preserves source dimensions without spatial/pose transforms; source file, camera bytes and captured pixel SHA are recorded separately. Request count {camera['requestCount']}, response count {camera['responseCount']}, hosted calls {camera['hostedCalls']}.

The visible smile/opening is a confounder, not a neutral sag positive. Chin/cheeks/overview return `null / EXPRESSION_OPEN_MOUTH_OR_SMILE`, show “—” and have no fabricated local map. This validates the full unavailable-result path, not sag detection success. 55ec00b8 utility mouth opening is just above 0.10; no guard was relaxed. e0da1a64 has unsupported FRONT yaw and visible smile. Existing a72ce06c fails the expression guard, b482028c complete-head framing, 3c472c6f unsupported side yaw; 515cc548 remains an API-only engineering replay with FRONT rejected. A neutral natural lower-fold positive across valid angles remains concretely open.

All seven new-result and history views use correct central Turkish labels. Raw dry values remain raw (overview {next(v['value'] for v in camera['targets'] if v['region']=='overview' and v['id']=='dry'):.6f}, UI ordinary 0%). Map x/y/step/photo associations and criterion/region clearing were checked; unavailable sag maps stay absent. Narrow and native Chrome 200% controls were reachable; history bytes unchanged. No old/new normalization or sampling contract changed, so previous v7/v8 separation remains. User records and the normal profile are not used by the isolated test profile.

Focused dry/sag/overview/reference regressions: 27 passed; typecheck passed. A separate production build validates the identical frontend sources; the functioning delivered build remains `{delivery['buildId']}`. Normal shortcut ownership, {sum(delivery['frontendSources'].values())} frontend source hashes, {len(delivery['servedJavaScript'])} served JavaScript hashes and {len(delivery['backendSources'])} loaded-after-write backend source hashes passed. Both model/config hashes remain identical. PR #2 stays Draft; no main merge.

Machine evidence: `docs/dry-sag-robust-evidence-20261013.json`. Local full receipts/overlays: `audit-results/dry-sag-robust-followup-20261013`; browser evidence: `output/playwright/dry-sag-robust-followup-20261013`.
'''
(ROOT/'docs/dry-sag-robust-followup-20261013.md').write_text(doc,'utf8')
print(json.dumps(dict(experiments=len(experiments),eligibleForDelivery=sum(e['eligibleForDelivery'] for e in experiments),productionBehaviorChanged=evidence['productionBehaviorChanged'],automaticScan=camera['automaticScanCompleted'])))
