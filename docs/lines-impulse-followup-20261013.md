# Lines noise regression — normal product delivery, 2026-10-13

Only lines sampling/support changes relative to `677d696734267e6bef21dc36d2ded93517c920bc` / `Lehkk49AObsF8QjoPR7GY`. No AG worktree/model change, training, download, hosted or paid request. Natural photo/color, original quality/hair/exclusion/brightness masks and every other criterion retain their original image input. Bag sampling v3 and the completed polygon-scope diagnosis remain untouched.

## Source pixels and filter responses

5bd42346 is an already transformed, impulse-corrupted regression source, not the primary natural-photo acceptance sample. The delivered lines v4 had raw0.507554/UI1, 77 active source pixels, including40 in its reviewed negative ROI. The noisy nearest source impulses at (483,243) gray241 vs local median127 and (470,253) gray246 vs median99 spread directional Gabor responses into source x476–481/y242–252. The receipt contains every active grid/source coordinate, radial/orthogonal magnitude, direction ratio/gate, strongest frequency/theta and nearby impulse pixel. This diagnoses quadrature response lobes and short corner/texture support; it does not invent full negative labels.

Existing narrow native impulse sampling alone preserves both named positives exactly, but only changes the noise raw0.507554 → 0.184245 and reviewed-negative map40 → 17 (raw support44 → 23). UI0 hides that residual, so this stage is not accepted as the fix.

The final additional rule tests connected **accepted visible local support**, after the original ROI/occlusion/relative-brightness checks. A component must span at least one coarsest configured Gabor period: ceil(1/0.13)=8 analysis cells. This follows the unchanged filter bank, not a photo ID, desired score, or parameter search. It rejects the remaining short spot components (3×3/5×5 and other spans below8); coherent fine lines retain their values. No global blur, output rescale, UI rounding change, band expansion or quality override. Both card and PNG gradient derive from this same retained field and the original area denominator.

Local visual layers: `audit-results/lines-impulse-20261012/5bd42346-source-gabor-responses.png`. The final stage has zero raw signal and zero active source/grid support, not merely UI0. Unknown pixels outside reviewed support are never labeled healthy.

## Same real browser payloads and normal API

| Source | Before → after raw index | Active map in known source support | Raw support in known source support | Label task |
|---|---:|---:|---:|---|
| a94f1646 | 0.568984 → 0.568984 | 13 → 13 | 14 → 14 | partial-positive-polygons |
| 02386f86 | 2.512537 → 2.112975 | 34 → 34 | 34 → 34 | partial-positive-polygons |
| 01955323 | 0.000000 → 0.000000 | 0 → 0 | 0 → 0 | exploratory-visual-control-no-pixel-label |
| 20031f35 | 6.645156 → 6.556313 | 0 → 0 | 0 → 0 | exploratory-visual-control-no-pixel-label |
| 36e4010b | 1.276301 → 1.276301 | 0 → 0 | 0 → 0 | exploratory-visual-control-no-pixel-label |
| beda0290 | 0.000000 → 0.000000 | 0 → 0 | 0 → 0 | engineering-reviewed-negative-ROI |
| 4b13b16a | 0.105812 → 0.000000 | 0 → 0 | 0 → 0 | exploratory-visual-control-no-pixel-label |
| e0ee9f0c | 0.006457 → 0.000000 | 0 → 0 | 0 → 0 | engineering-reviewed-negative-ROI |
| 5bd42346 | 0.507554 → 0.000000 | 40 → 0 | 44 → 0 | engineering-reviewed-negative-ROI |

Fine positive retains its complete prior map and score0.568984. Pronounced positive changes2.512537 → 2.112975 while all34 previously captured annotated source pixels remain. Its total source map changes219 → 204: the removed short support is outside the partial annotation and therefore unknown, not established false positives. This version can exclude short real isolated segments; no claim of complete source-ROI recall/Dice or general accuracy is made.

Nine byte-pinned actual browser MediaPipe/crop/exclusion inputs were compared with frozen delivered code, then replayed through the normal shortcut API. All288 non-lines regional measurement/map pairs are exact, including bag sampling v3, dark, dryness and cheek/chin sag. API result equality excludes only model load/inference timing, retaining measurements, maps, contours, other general fields and hashes.

## Version and delivery

Gabor normalization remains `outer-canthus-gabor-radiating-hair-excluded-v4`; sampling is `native-impulse-one-cycle-lines-v1`, photometry `native-isolated-impulse-median-v1`, support `connected-local-one-coarsest-period-v1`. Existing history comparison keys resolve the sampling version in both regional and nested overview components. Actual own-profile old/new lines history splits into two series and blocks deltas; bag history remains one comparable v3 series. Old stored JSON bytes remain unchanged. User records were not opened/recomputed/rewritten.

26 focused regressions, typecheck and production build passed. Normal shortcut real scan/MediaPipe/API, new result/history source association, x/y and width/height×step, selected clip mask, criterion/region map clearing, all seven views/Turkish labels, narrow view and real browser200% passed. Natural source/colors, mesh/card/font design, integer bars and approved sounds are unchanged. Source receipt213 files, served JS18 chunks, backend source/index and the loaded accepted-model hash match. BUILD_ID `2W5568tfxsQ8bEjHc6Nmy`. PR2 stays Draft, main unmerged.

Machine receipt: `docs/lines-impulse-evidence-20261013.json`; acceptance values are computed from actual evidence. No local skin-type/Karma candidate is included. Wait for AG's separately frozen delivery after this task.
