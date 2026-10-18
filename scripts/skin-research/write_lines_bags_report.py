"""Publish bounded computed receipts; no photos, request bodies or credentials."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/lines-bags-followup-20261012'
def read(path):return json.loads(path.read_text('utf8'))
rows=read(DATA/'same-input-comparison.json');scope=read(DATA/'bag-target-scope.json')
noise=read(DATA/'noise-proximity.json');ablation=read(DATA/'noise-ablation.json');api=read(DATA/'normal-api-receipt.json')
browser=read(ROOT/'output/playwright/lines-bags-followup-20261012/proof.json');delivery=read(DATA/'delivery.json')
def sample(prefix):return next(v for v in rows if v['sourceSHA256'].startswith(prefix))
def bags(prefix):return sample(prefix)['targets']['bags']
acceptance={
 'fineLinesLocalPositiveRestored':sample('a94f1646')['targets']['lines']['after']['value']>0 and sample('a94f1646')['targets']['lines']['after']['activeWithinKnownSourcePixels']>0,
 'deepLinesLocalPositivePreserved':sample('02386f86')['targets']['lines']['after']['value']>0 and sample('02386f86')['targets']['lines']['after']['activeWithinKnownSourcePixels']>0,
 'twoBagPositivesValuesPreserved':all(bags(p)['before']['value']==bags(p)['after']['value'] for p in ('20031f35','36e4010b')),
 'reviewedNaturalBagControlsRemainZero':all(bags(p)['after']['value']==0 and bags(p)['after']['activeWithinKnownSourcePixels']==0 for p in ('e0ee9f0c','beda0290','4b13b16a')),
 'transformedBagImpulseRegressionRemoved':bags('5bd42346')['after']['value']==0 and bags('5bd42346')['after']['geometry']['activeAnalysisPixels']==0,
 'allActualAPIsEqualOffline':all(v['actualAPIEqualsOffline'] and v['actualAPIPhotoMatches'] for v in api),
 'allAnalysisMapsInsideTrueBandAndSelectedSupport':all(t['after']['geometry']['outsideEyeBandAnalysisPixels']==0 and t['after']['geometry']['outsideSelectedRegionAnalysisPixels']==0 for row in rows for t in row['targets'].values()),
 'bothHistoryScopesSplitBothNewVersions':len(browser['samplingComparisonControls'])==4 and all(not v['comparable'] and v['deltaBlocked'] and v['seriesCount']==2 for v in browser['samplingComparisonControls']),
 'oldIsolatedHistoryBytesPreserved':browser['historyBytesPreserved'],
 'allSevenViewsLabelsPreserved':browser['allKnownLabelsCorrect'] and all(len(v['views'])==7 for v in browser['views']),
 'actualCameraMediaPipeAndAPI':browser['realMediaPipe'] and browser['actualAPISourceMatches'],
 'normalShortcutAndServedHashes':delivery['normalShortcutMatch'] and delivery['normalSession'] and delivery['actualAPIEqualsCaptured'] and all(v['matches'] for v in delivery['servedJavaScript'].values()),
 'native200Accepted':browser['real200Accepted'],
}
assert all(acceptance.values()),acceptance
evidence=dict(schemaVersion=1,baselineCommit='ab475ff9a93d55d4ec960e36276768bb71aae17e',frozenAGCommit='de82971813af181e791a0d495c929dd239d23584',selectedAGRange='ff0b161bd807fe81d2ba5ee6283d4f5b26f6a102..de82971813af181e791a0d495c929dd239d23584',buildId=delivery['buildId'],frozenFiles=read(ROOT/'.runtime/lines-v4-frozen-20261012/receipt.json'),samples=rows,bagTargetScope=scope,noiseProximity=noise,noiseAblation=ablation,actualAPI=api,historyAndBrowser=browser,delivery=delivery,acceptance=acceptance,nonTargetExactPairCount=sum(len(v['nonTargetExactMatches']) for v in rows),checks={'focusedRegressions':23,'typecheck':'PASS','productionBuild':'PASS'},limitations=['Source labels are partial polygons and engineering-reviewed target-specific support, not full-ROI disease severity or general accuracy.','01955323 and 4b13b16a lack criterion-specific lines pixel-negative labels in the current ledger; exploratory visual controls only.','20031f35 annotation and lower-fold target differ; source polygon overlap remains zero.','Transformed 5bd42346 still has lines v4 residual, raw 0.507554 / UI1 and known-negative support; bag correction does not fix lines noise.','AG local skin-type/Karma work is not delivered here.'],hostedCalls=0,newTraining=False,privateUserStorageTouched=False)
evidence['delivery'].pop('frontendSources',None)
evidence['mediapipeModelSHA256']=hashlib.sha256((ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task').read_bytes()).hexdigest()
evidence['browserUtilitySourceHashes']=read(ROOT/'.runtime/periorbital-v5-browser-support/source-hashes.json')
dest=ROOT/'docs/lines-bags-product-evidence-20261012.json';dest.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8')
table=[]
for row in rows:
 p=row['sourceSHA256'][:8];t=row['targets']['lines'];table.append(f"| {p} | {t['before']['value']} → {t['after']['value']} | {t['after']['ui']} | {t['after'].get('rawAcceptedAnalysisPixels',0)} | {t['after']['geometry']['activeSourcePixels']} | {t['after']['activeWithinKnownSourcePixels']} / {t['knownSourcePixels']} | {t['labelScope']} |")
text=f'''# Lines v4 and bag scope/noise: normal-product receipt, 2026-10-12

The delivered `ab475ff9` product is the baseline. Only the frozen AG range's lines band, multi-scale Gabor/orientation selectivity and relative brightness support were transferred. AG moving files, skin_models.py, skin-focused.json and local skin-type weights were not copied. Our closed eye cells, Turkish label adapter, dark v4, shared dryness and cheek/chin sag remain.

## Same actual product inputs

The two named lines positives and 01955323 were captured using real browser MediaPipe and the existing snapshot/crop/exclusion/quality utilities. The other six inputs are byte-pinned prior real browser captures with the delivered closed-cell mesh. Both methods run the identical source/payload, not AG's reference scores. Every current result was then reproduced by the normal shortcut API. Model runtime timings alone are excluded from result equality; numeric rows, maps, contours, hashes and the remaining general result match.

| Source SHA prefix | v3 → v4 raw lines index | UI | Raw accepted grid cells | Active source map cells | Active in known label / known source pixels | Label task |
|---|---:|---:|---:|---:|---:|---|
{chr(10).join(table)}

PNG alpha is quantized 0..100; raw support is recorded independently. UI0 does not mean no signal. Known positives only measure local capture, not complete ROI recall/Dice. The reviewed lines negatives beda0290 and e0ee9f0c have no active/raw support inside their known-negative areas. e0ee9f0c retains raw 0.006457 outside that known area; 4b13b16a retains 0.105812 with no lines-specific pixel-negative ledger. The transformed noise source has raw 0.507554/UI1 and 40 active known-negative lines pixels: this remains open. Unlabeled areas are unknown.

All current active grid cells are inside the real v4 band and selected triangle union. Source-grid projection records origin/scale/step and boundary rasterization separately; source edges can differ by a pixel from re-rasterizing continuous source polygons. The browser's real image x/y and width/height×step and actual clip triangles match, for both new result and the same history record.

## Bag annotation target scope

20031f35's source `dc` class is `eyebag`, with a single partial polygon along the upper lower-lid/bag margin. The dataset provides no authoritative whole-bag-versus-fold ontology; the semantic finding is grounded in the actual polygon/image, not a newly invented class definition. V5 excludes the lid margin and measures supported lower folds. The three-panel local overlay is `audit-results/lines-bags-followup-20261012/20031f35-target-scope.png`.

Of {scope['sourcePixels']} annotated source pixels, {scope['sourcePixelsInsideBand']} enter the projected v5 band and {scope['sourcePixelsOutsideBand']} are outside. The {scope['activeSourcePixels']} active source-map pixels overlap the annotation at {scope['activeWithinAnnotatedSourcePixels']} pixels. This is a target-scope mismatch, not demonstrated full-bag detection accuracy. Coordinates, band and selected closed cells were checked; no additional coordinate error was found. No band expansion, fixed score, quality override or threshold reduction was applied. Same-input bag positives remain **9.359850** and **0.976358**; the partial polygon is not claimed captured for 20031f35.

## Transformed noise regression

5bd42346 is an already transformed/rotated, impulse-corrupted source, not natural-photo accuracy evidence. Native residual >0.35 against a 3×3 median, limited to connected components of one/two pixels, identifies sparse extreme impulses. Its strongest paired-edge centers lie beside such impulses. In a same-geometry ablation, replacing only these native impulses removes the bag 0.509856/UI1 signal. Production now uses that photometric sample only for periorbital folds, before resizing. Source display, anatomy, quality/exposure masks and other criteria use the original image. Coherent fine lines and ordinary skin texture are not blurred; a focused regression verifies this and source immutability.

Bag formula remains `contour-fold-local-support-v5`; sampling is `tracked-center-closed-cells-impulse-v3`, photometry `native-isolated-impulse-median-v1`. The closed-cell support is retained. Noise bag becomes **0, zero active map**, both natural bag positives remain exactly unchanged, and e0ee9f0c/beda0290/4b13b16a remain zero. Quality rejection remains null with no map. This bag-specific fix does not solve the lines noise residual.

## History and normal delivery

Lines v3/v4 normalization and bag sampling v2/v3 form separate actual overview and regional series; comparisons/deltas are blocked. Old own-profile JSON bytes remain unchanged. No user records/photos were recalculated, rewritten or removed. All seven views were inspected in new result and history, including correct and corrupted old-label fixtures ({sum(len(view['labels']) for case in browser['views'] for view in case['views'])} label checks). Criterion/region switches clear the old map. Normal shortcut new scan uses real 478-point MediaPipe and the same API; natural photo/background, selected meshes, cards and typography remain. Camera YUV scan is a distinct source from the pinned PNG, not a claimed identical score comparison.

Focused regressions **23 passed**; typecheck and production build passed. Existing unrelated lint warnings remain. Real desktop, narrow view and native browser200% were checked; CSS zoom remains1, DPR{browser['real200Percent']['dpr']}, inner width{browser['real200Percent']['innerWidth']}, no horizontal overflow. Every one of {evidence['nonTargetExactPairCount']} non-target regional measurement/map pairs is exact on the nine pinned inputs.

BUILD_ID `{delivery['buildId']}`. The normal owned shortcut/API, {len(delivery['servedJavaScript'])} served JS chunks, staged frontend source receipt, backend files and loaded accepted-model SHA match. Hosted consent/config, approved sounds, production models, launcher and private user storage were preserved. No new training, hosted request, paid service or rejected neural activation. PR2 remains Draft; main is not merged. AG's local skin-type/Karma work remains separate and incomplete here.

Machine receipt: `docs/lines-bags-product-evidence-20261012.json`. Its acceptance fields derive from actual comparisons; failures and scope limits are recorded separately.
'''
(ROOT/'docs/lines-bags-product-followup-20261012.md').write_text(text,'utf8')
print(json.dumps({'build':delivery['buildId'],'acceptance':acceptance,'nonTargetPairs':evidence['nonTargetExactPairCount']}))
