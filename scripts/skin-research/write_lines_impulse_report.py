"""Computed lines-only regression receipt; no photos or private request bodies."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DATA=ROOT/'audit-results/lines-impulse-20261012'
def read(path):return json.loads(path.read_text('utf8'))
rows=read(DATA/'same-input-comparison.json');native=read(DATA/'native-only-comparison.json');response=read(DATA/'noise-filter-response.json');api=read(DATA/'normal-api-receipt.json');delivery=read(DATA/'delivery.json');browser=read(ROOT/'output/playwright/lines-impulse-20261012/proof.json')
def sample(prefix):return next(v for v in rows if v['sourceSHA256'].startswith(prefix))
def lines(prefix):return sample(prefix)['targets']['lines']
def retained(prefix):
 t=lines(prefix);return t['after']['value']>0 and t['after']['activeWithinKnownSourcePixels']>=t['before']['activeWithinKnownSourcePixels'] and t['after']['rawSupportWithinKnownSourcePixels']>=t['before']['rawSupportWithinKnownSourcePixels']
acceptance=dict(noiseRawZero=lines('5bd42346')['after']['value']==0,noiseKnownMapZero=lines('5bd42346')['after']['activeWithinKnownSourcePixels']==0,noiseKnownRawZero=lines('5bd42346')['after']['rawSupportWithinKnownSourcePixels']==0,noiseAllMapZero=lines('5bd42346')['after']['geometry']['activeAnalysisPixels']==0,finePositivePreserved=retained('a94f1646') and lines('a94f1646')['after']['value']==lines('a94f1646')['before']['value'],strongPositiveLocalSupportPreserved=retained('02386f86'),normalAPIEqualsSource=all(v['actualAPIEqualsOffline'] and v['actualAPIPhotoMatches'] for v in api),oldIsolatedRecordBytesPreserved=browser['historyBytesPreserved'],realBrowserScanAndAPI=browser['realMediaPipe'] and browser['actualAPISourceMatches'],labelsPreserved=browser['allKnownLabelsCorrect'],historyLinesScopeSplit=all(not v['comparable'] and v['deltaBlocked'] and v['seriesCount']==2 and v['sameNormalization'] for v in browser['samplingComparisonControls'] if v['criterion']=='lines'),historyBagScopeUnchanged=all(v['comparable'] and not v['deltaBlocked'] and v['seriesCount']==1 for v in browser['samplingComparisonControls'] if v['criterion']=='bags'),normalShortcut=delivery['normalShortcutMatch'] and delivery['normalSession'],servedJavaScriptMatch=all(v['matches'] for v in delivery['servedJavaScript'].values()),native200=browser['real200Accepted'])
assert all(acceptance.values()),acceptance
samples=[dict(sourceSHA256=v['sourceSHA256'],inputSHA256=v['inputSHA256'],sourceRelativePath=v['sourceRelativePath'],split=v['split'],lines=v['targets']['lines'],otherRegionalRowsAndMapsExact=v['nonTargetExactMatches']) for v in rows]
evidence=dict(schemaVersion=1,baselineCommit='677d696734267e6bef21dc36d2ded93517c920bc',baselineBuild='Lehkk49AObsF8QjoPR7GY',buildId=delivery['buildId'],samplingSupportVersion='native-impulse-one-cycle-lines-v1',photometricSamplingVersion='native-isolated-impulse-median-v1',lineSupportVersion='connected-local-one-coarsest-period-v1',gaborNormalizationUnchanged='outer-canthus-gabor-radiating-hair-excluded-v4',sourceHashes=read(DATA/'frozen-sampling-source-hashes.json'),filterResponses=response,nativeOnlyComparison=[dict(sourceSHA256=v['sourceSHA256'],lines=v['targets']['lines']) for v in native],finalComparison=samples,actualAPI=api,browser=browser,delivery=delivery,acceptance=acceptance,nonTargetExactPairs=sum(len(v['nonTargetExactMatches']) for v in rows),focusedRegressions=26,typecheck='PASS',productionBuild='PASS',scopeLimits=['One already transformed noisy development regression; no natural-photo general accuracy claim.','Partial positive polygons and criterion-specific reviewed negatives only; unlabeled pixels remain unknown.','Strong-positive source map drops short support outside its annotation; those unknown pixels are not declared false positives.','A coherent component must span one coarsest configured Gabor period in the visible target support. Short real isolated segments may also be below this versioned scope.','AG local four-class skin-type work is separate; no integration or external call.'],hostedCalls=browser['hostedConsentRequestCount'],userStorageTouched=False,newTraining=False)
evidence['delivery'].pop('frontendSources',None)
(ROOT/'docs/lines-impulse-evidence-20261013.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8')
table=[]
for row in rows:
 t=row['targets']['lines'];table.append(f"| {row['sourceSHA256'][:8]} | {t['before']['value']:.6f} → {t['after']['value']:.6f} | {t['before']['activeWithinKnownSourcePixels']} → {t['after']['activeWithinKnownSourcePixels']} | {t['before']['rawSupportWithinKnownSourcePixels']} → {t['after']['rawSupportWithinKnownSourcePixels']} | {t['labelScope']} |")
md=f'''# Lines noise regression — normal product delivery, 2026-10-13

Only lines sampling/support changes relative to `677d696734267e6bef21dc36d2ded93517c920bc` / `Lehkk49AObsF8QjoPR7GY`. No AG worktree/model change, training, download, hosted or paid request. Natural photo/color, original quality/hair/exclusion/brightness masks and every other criterion retain their original image input. Bag sampling v3 and the completed polygon-scope diagnosis remain untouched.

## Source pixels and filter responses

5bd42346 is an already transformed, impulse-corrupted regression source, not the primary natural-photo acceptance sample. The delivered lines v4 had raw0.507554/UI1, 77 active source pixels, including40 in its reviewed negative ROI. The noisy nearest source impulses at (483,243) gray241 vs local median127 and (470,253) gray246 vs median99 spread directional Gabor responses into source x476–481/y242–252. The receipt contains every active grid/source coordinate, radial/orthogonal magnitude, direction ratio/gate, strongest frequency/theta and nearby impulse pixel. This diagnoses quadrature response lobes and short corner/texture support; it does not invent full negative labels.

Existing narrow native impulse sampling alone preserves both named positives exactly, but only changes the noise raw0.507554 → 0.184245 and reviewed-negative map40 → 17 (raw support44 → 23). UI0 hides that residual, so this stage is not accepted as the fix.

The final additional rule tests connected **accepted visible local support**, after the original ROI/occlusion/relative-brightness checks. A component must span at least one coarsest configured Gabor period: ceil(1/0.13)=8 analysis cells. This follows the unchanged filter bank, not a photo ID, desired score, or parameter search. It rejects the remaining short spot components (3×3/5×5 and other spans below8); coherent fine lines retain their values. No global blur, output rescale, UI rounding change, band expansion or quality override. Both card and PNG gradient derive from this same retained field and the original area denominator.

Local visual layers: `audit-results/lines-impulse-20261012/5bd42346-source-gabor-responses.png`. The final stage has zero raw signal and zero active source/grid support, not merely UI0. Unknown pixels outside reviewed support are never labeled healthy.

## Same real browser payloads and normal API

| Source | Before → after raw index | Active map in known source support | Raw support in known source support | Label task |
|---|---:|---:|---:|---|
{chr(10).join(table)}

Fine positive retains its complete prior map and score0.568984. Pronounced positive changes2.512537 → 2.112975 while all34 previously captured annotated source pixels remain. Its total source map changes219 → 204: the removed short support is outside the partial annotation and therefore unknown, not established false positives. This version can exclude short real isolated segments; no claim of complete source-ROI recall/Dice or general accuracy is made.

Nine byte-pinned actual browser MediaPipe/crop/exclusion inputs were compared with frozen delivered code, then replayed through the normal shortcut API. All288 non-lines regional measurement/map pairs are exact, including bag sampling v3, dark, dryness and cheek/chin sag. API result equality excludes only model load/inference timing, retaining measurements, maps, contours, other general fields and hashes.

## Version and delivery

Gabor normalization remains `outer-canthus-gabor-radiating-hair-excluded-v4`; sampling is `native-impulse-one-cycle-lines-v1`, photometry `native-isolated-impulse-median-v1`, support `connected-local-one-coarsest-period-v1`. Existing history comparison keys resolve the sampling version in both regional and nested overview components. Actual own-profile old/new lines history splits into two series and blocks deltas; bag history remains one comparable v3 series. Old stored JSON bytes remain unchanged. User records were not opened/recomputed/rewritten.

26 focused regressions, typecheck and production build passed. Normal shortcut real scan/MediaPipe/API, new result/history source association, x/y and width/height×step, selected clip mask, criterion/region map clearing, all seven views/Turkish labels, narrow view and real browser200% passed. Natural source/colors, mesh/card/font design, integer bars and approved sounds are unchanged. Source receipt213 files, served JS18 chunks, backend source/index and the loaded accepted-model hash match. BUILD_ID `{delivery['buildId']}`. PR2 stays Draft, main unmerged.

Machine receipt: `docs/lines-impulse-evidence-20261013.json`; acceptance values are computed from actual evidence. No local skin-type/Karma candidate is included. Wait for AG's separately frozen delivery after this task.
'''
(ROOT/'docs/lines-impulse-followup-20261013.md').write_text(md,'utf8')
print(json.dumps({'acceptance':acceptance,'buildId':delivery['buildId'],'nonTargetPairs':evidence['nonTargetExactPairs']}))
