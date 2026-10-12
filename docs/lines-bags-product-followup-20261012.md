# Lines v4 and bag scope/noise: normal-product receipt, 2026-10-12

The delivered `ab475ff9` product is the baseline. Only the frozen AG range's lines band, multi-scale Gabor/orientation selectivity and relative brightness support were transferred. AG moving files, skin_models.py, skin-focused.json and local skin-type weights were not copied. Our closed eye cells, Turkish label adapter, dark v4, shared dryness and cheek/chin sag remain.

## Same actual product inputs

The two named lines positives and 01955323 were captured using real browser MediaPipe and the existing snapshot/crop/exclusion/quality utilities. The other six inputs are byte-pinned prior real browser captures with the delivered closed-cell mesh. Both methods run the identical source/payload, not AG's reference scores. Every current result was then reproduced by the normal shortcut API. Model runtime timings alone are excluded from result equality; numeric rows, maps, contours, hashes and the remaining general result match.

| Source SHA prefix | v3 → v4 raw lines index | UI | Raw accepted grid cells | Active source map cells | Active in known label / known source pixels | Label task |
|---|---:|---:|---:|---:|---:|---|
| a94f1646 | 0.0 → 0.5689840316772461 | 1 | 116 | 112 | 13 / 1415 | partial-positive-polygons |
| 02386f86 | 1.634156584739685 → 2.5125367641448975 | 3 | 156 | 219 | 34 / 561 | partial-positive-polygons |
| 01955323 | 0.0 → 0.0 | 0 | 0 | 0 | 0 / 0 | exploratory-visual-control-no-pixel-label |
| 20031f35 | 6.608452320098877 → 6.645156383514404 | 7 | 128 | 264 | 0 / 0 | exploratory-visual-control-no-pixel-label |
| 36e4010b | 0.0 → 1.2763010263442993 | 1 | 51 | 49 | 0 / 0 | exploratory-visual-control-no-pixel-label |
| beda0290 | 0.725189745426178 → 0.0 | 0 | 0 | 0 | 0 / 6035 | engineering-reviewed-negative-ROI |
| 4b13b16a | 0.1444261372089386 → 0.1058119460940361 | 0 | 8 | 6 | 0 / 0 | exploratory-visual-control-no-pixel-label |
| e0ee9f0c | 0.0 → 0.006457293406128883 | 0 | 2 | 1 | 0 / 5306 | engineering-reviewed-negative-ROI |
| 5bd42346 | 0.5044631958007812 → 0.5075540542602539 | 1 | 88 | 77 | 40 / 8567 | engineering-reviewed-negative-ROI |

PNG alpha is quantized 0..100; raw support is recorded independently. UI0 does not mean no signal. Known positives only measure local capture, not complete ROI recall/Dice. The reviewed lines negatives beda0290 and e0ee9f0c have no active/raw support inside their known-negative areas. e0ee9f0c retains raw 0.006457 outside that known area; 4b13b16a retains 0.105812 with no lines-specific pixel-negative ledger. The transformed noise source has raw 0.507554/UI1 and 40 active known-negative lines pixels: this remains open. Unlabeled areas are unknown.

All current active grid cells are inside the real v4 band and selected triangle union. Source-grid projection records origin/scale/step and boundary rasterization separately; source edges can differ by a pixel from re-rasterizing continuous source polygons. The browser's real image x/y and width/height×step and actual clip triangles match, for both new result and the same history record.

## Bag annotation target scope

20031f35's source `dc` class is `eyebag`, with a single partial polygon along the upper lower-lid/bag margin. The dataset provides no authoritative whole-bag-versus-fold ontology; the semantic finding is grounded in the actual polygon/image, not a newly invented class definition. V5 excludes the lid margin and measures supported lower folds. The three-panel local overlay is `audit-results/lines-bags-followup-20261012/20031f35-target-scope.png`.

Of 1224 annotated source pixels, 16 enter the projected v5 band and 1208 are outside. The 653 active source-map pixels overlap the annotation at 0 pixels. This is a target-scope mismatch, not demonstrated full-bag detection accuracy. Coordinates, band and selected closed cells were checked; no additional coordinate error was found. No band expansion, fixed score, quality override or threshold reduction was applied. Same-input bag positives remain **9.359850** and **0.976358**; the partial polygon is not claimed captured for 20031f35.

## Transformed noise regression

5bd42346 is an already transformed/rotated, impulse-corrupted source, not natural-photo accuracy evidence. Native residual >0.35 against a 3×3 median, limited to connected components of one/two pixels, identifies sparse extreme impulses. Its strongest paired-edge centers lie beside such impulses. In a same-geometry ablation, replacing only these native impulses removes the bag 0.509856/UI1 signal. Production now uses that photometric sample only for periorbital folds, before resizing. Source display, anatomy, quality/exposure masks and other criteria use the original image. Coherent fine lines and ordinary skin texture are not blurred; a focused regression verifies this and source immutability.

Bag formula remains `contour-fold-local-support-v5`; sampling is `tracked-center-closed-cells-impulse-v3`, photometry `native-isolated-impulse-median-v1`. The closed-cell support is retained. Noise bag becomes **0, zero active map**, both natural bag positives remain exactly unchanged, and e0ee9f0c/beda0290/4b13b16a remain zero. Quality rejection remains null with no map. This bag-specific fix does not solve the lines noise residual.

## History and normal delivery

Lines v3/v4 normalization and bag sampling v2/v3 form separate actual overview and regional series; comparisons/deltas are blocked. Old own-profile JSON bytes remain unchanged. No user records/photos were recalculated, rewritten or removed. All seven views were inspected in new result and history, including correct and corrupted old-label fixtures (168 label checks). Criterion/region switches clear the old map. Normal shortcut new scan uses real 478-point MediaPipe and the same API; natural photo/background, selected meshes, cards and typography remain. Camera YUV scan is a distinct source from the pinned PNG, not a claimed identical score comparison.

Focused regressions **23 passed**; typecheck and production build passed. Existing unrelated lint warnings remain. Real desktop, narrow view and native browser200% were checked; CSS zoom remains1, DPR3, inner width641, no horizontal overflow. Every one of 279 non-target regional measurement/map pairs is exact on the nine pinned inputs.

BUILD_ID `Lehkk49AObsF8QjoPR7GY`. The normal owned shortcut/API, 18 served JS chunks, staged frontend source receipt, backend files and loaded accepted-model SHA match. Hosted consent/config, approved sounds, production models, launcher and private user storage were preserved. No new training, hosted request, paid service or rejected neural activation. PR2 remains Draft; main is not merged. AG's local skin-type/Karma work remains separate and incomplete here.

Machine receipt: `docs/lines-bags-product-evidence-20261012.json`. Its acceptance fields derive from actual comparisons; failures and scope limits are recorded separately.
