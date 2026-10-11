# TOGG Attune skin follow-up — 2026-10-11

Overall analysis completion: **OPEN**. Diagnosis, objective source corrections, finite predictor experiments and exact resume are complete. No failed candidate was promoted, and UI-only delivery is not represented as analysis completion.

## Preserved real product
Frontend source `81127319b1015f53dbbb8e3321b6cb9349ef1faa`, BUILD_ID `_YWFLetSYj_oTN7LuFj4H`. Normal Windows shortcut target, launcher-owned frontend/backend, preserved source bytes and every served build chunk were verified. Four previously exposed licensed source inputs exercised the normal API without writing user history. Two NASA portraits are front-only; two video frames belong to one person and are not independent people, new final tests or physical three-pose acceptance. UI, normal photograph/background, zoom/mesh, carousel/popups, exact voices and records were not edited.

## Training diagnosis

No CUDA device is available; this host has four physical/eight logical CPU cores and Intel UHD display graphics. Original YOLOX had one validated epoch; original Faster-RCNN had no saved trained checkpoint, including no partial weight file. They are undertrained, not definitive architecture failures. Native 384 BGR (YOLOX) versus RGB/255 (Faster) tensors and label overlays were inspected: class IDs 0 versus foreground 1/background 0, roundtrip error below 0.0001. No input upsample. 17.124% of positive tile boxes have a minimum side below eight source pixels. Native small lesions, black pre-cut source backgrounds and camera domain difference remain material.

YOLOX resumes original trained weights; the absent legacy optimizer makes the first continuation weights-only. All subsequent state includes optimizer tensors/scalars, Torch/NumPy/Python RNG, shuffled order, gradient cursor, epoch loss/components, patience and data/freeze identity with hashes. A Windows mapped-safetensors save collision was fixed by cloning loaded optimizer tensors and unique transactional generations. Exact restart/RNG/cursor equivalence and corruption checks passed. Frozen features are cached once. Newly trained stages adapt predictors only; they do not prove full-backbone convergence.

Faster-RCNN sampled frozen RPN proposal coverage: one of 136 train GT boxes and zero of 124 validation GT boxes overlap at IoU≥0.5. This is a deterministic 16-tile engineering sample, not corpus final performance. Smaller anchor priors alone gave the same result. Training ROI sampling inserts GT proposals; lower ROI loss cannot repair missing inference proposals. Same-ROI FP32 versus FP16 loss difference was below 0.00002. RPN/backbone adaptation with complete negative labels remains required.

Finite stages: YOLOX four extra predictor epochs; Faster-RCNN two predictor epochs; type heads maximum80/patience10. Detector initial preparation+training budget3600 seconds; any measured completion reserve is recorded below, remains finite, and resumes exact state. The original active first Faster validation lacked tile-level budget checks; its observed overrun is recorded, not concealed. The new path checkpoints partial validation and caches frozen FP32 inference ROI features without injecting GT.

| Detector stage | Epoch | Loss | Development F1 | Precision | Recall | AP50 | Cumulative seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| YOLOX predictor | 1 | 5.7052 | 0.4139 | 0.4959 | 0.3552 | 0.3019 | 1489.2 |
| YOLOX predictor | 2 | 5.6454 | 0.4290 | 0.5040 | 0.3734 | 0.3184 | 1905.2 |
| YOLOX predictor | 3 | 5.6378 | 0.4223 | 0.5004 | 0.3653 | 0.3110 | 2257.1 |
| YOLOX predictor | 4 | 5.6433 | 0.4241 | 0.4908 | 0.3734 | 0.3087 | 2671.0 |
| Faster-RCNN predictor | 1 | 0.1546 | 0.0030 | 0.0035 | 0.0027 | 0.0017 | 4022.0 |
| Faster-RCNN predictor | 2 | 0.0877 | 0.0021 | 0.0230 | 0.0011 | 0.0025 | 4595.2 |

Faster completion plan: `{"initialTotalSeconds": 3600, "totalLimitSeconds": 4800, "additionalMaximumSeconds": 1200, "finiteEpochCap": 2, "reason": "Measured preparation consumed most initial wall budget; reserve bounded time for completing predictor validation, preserving optimizer/RNG/cursor. No additional full-backbone epochs or acceptance change."}`. No confidence/acceptance gate was lowered: F1≥0.50/P≥0.60/R≥0.40 and independent camera/negative review remain required. YOLOX dev before 0.3854 → best 0.4290, using the same 94 development photos/83 source groups. Comparisons are development only, annotation-relative FP, not clinical FP.

## Objective source quality
All 2169 previously eligible development type source thumbnails and 113 degree-source thumbnails were inspected with class/prediction hidden for decisions. Additional native-source inspections confirmed sparse impulses on JPEG padding. Final type split {'train': 879, 'validation': 187}; degree split {'validation': 13, 'train': 93}. Exclusion reasons overlap: `{"isolated-bright-impulses-in-flat-source-padding": 410, "monochrome-or-clearly-stylized-heavy-processing": 273, "visible-cosmetic-mask-cream-or-application": 421, "superimposed-text-advertisement-or-diagram": 347, "opaque-occlusion-sunglasses-or-clipped-source": 122}`.

The original corruption rule inspected face crop only and required extreme luminance plus fraction>0.002. A verified old source has face fraction0.001225, yet 105 bright isolated pixels on flat RGB10–12 padding across ten spatial cells. The new source rule checks flat outer rows/columns, eroded near-black padding, ≥12 isolated islands, ≥4 spatial cells and minimum density0.0003. It flags 410 rows, 241 beyond the independent manual decisions. Natural high-frequency hair/iris/beard flags are review-only; five incorrectly rejected sources were restored. Source metrics are hash/crop keyed and checkpointed every100 rows.

Advertisements outside the face crop, creams/masks, opaque occlusion/sunglasses, monochrome and clear stylization now have explicit hash-bound source-family exclusions. No wrong prediction triggered an exclusion, labels were not changed, and ambiguous makeup is not automatically rejected. Native inspection of sixteen padding-positive sources confirmed the displayed corruption; contact-sheet review is engineering quality review, not expert clinical labels or a guarantee that every subtle manipulation is detected.

Training/product camera-crop-v1, RGB224 INTER_AREA, ImageNet mean/std and normal/dry/oily/combination order agree; four final-clean real source tensors have exact maximum difference0. Class-head random starts are unpaired; differences between their F1 scores are not evidence of backbone damage. The controlled degree comparison below uses identical source rows, train-only scaler, masks and ridge choices.

| Type predictor | Epochs | Development macro-F1 |
|---|---:|---:|
| resnet18-imagenet | 20 | 0.2944 |
| resnet18-type-finetuned | 14 | 0.3221 |
| efficientnet_b0-imagenet | 21 | 0.3210 |
| efficientnet_b0-type-finetuned | 21 | 0.3250 |

## Feature extractor comparison

The selected old EfficientNet-B0 has zero of309 inference feature tensors changed from ImageNet. Its two degree branches produce identical outputs. The selected ResNet18 changed15 of100 feature tensors, all in layer4. Batch counters were excluded because they are not inference features. Previous type validation overlaps degree development, so this is a diagnostic comparison rather than independent transfer validation. Elasticity is not relabelled sagging. All eighteen labels remain evaluated separately.

| Target / MAE on same clean development rows | R18 ImageNet | R18 type-FT | B0 ImageNet | B0 type-FT |
|---|---:|---:|---:|---:|
| acne | 1.073 | 1.021 | 0.745 | 0.745 |
| blackheads | 0.489 | 0.468 | 0.447 | 0.447 |
| whiteheads | 0.805 | 0.790 | 0.578 | 0.578 |
| pores | 0.849 | 0.862 | 0.811 | 0.811 |
| oil | 1.117 | 1.269 | 1.087 | 1.087 |
| irritation | 0.917 | 0.779 | 0.849 | 0.849 |
| sensitivity | 1.298 | 1.325 | 0.916 | 0.916 |
| redness | 0.915 | 0.932 | 0.721 | 0.721 |
| lines | 0.848 | 0.930 | 1.101 | 1.101 |
| bags | 0.843 | 0.880 | 0.864 | 0.864 |
| dark | 0.662 | 0.645 | 0.627 | 0.627 |
| foreheadLines | 0.769 | 0.747 | 0.585 | 0.585 |
| elasticity | 0.775 | 0.836 | 0.829 | 0.829 |
| dry | 0.699 | 0.697 | 0.610 | 0.610 |
| darkSpots | 0.853 | 0.747 | 0.741 | 0.741 |
| postAcne | 0.755 | 0.732 | 0.668 | 0.668 |
| tone | 0.803 | 0.670 | 0.620 | 0.620 |
| freckles | 1.414 | 1.387 | 1.270 | 1.270 |

These development MAEs do not replace product acceptance or an independent final. The existing redness model was retained exactly; better new development-only dry/tone MAE does not authorize promotion.

A matched comparison against the existing global appearance features was attempted separately for every relevant target. After quality cleaning, comparable support is only four photos for acne/oil/redness/lines/dark/dry/tone, one for bags and zero for elasticity. This does not meet the unchanged minimum of ten. Analytic-versus-model MAE is therefore unavailable rather than fabricated or estimated on a different subset. Sagging cannot be compared to elasticity labels. Current normal API outputs below remain separate from dataset accuracy.

## Bags annotation coverage
79 supervised development ROIs: Dice0.8407, IoU0.7298. Only the labelled polygon plus two-source-pixel band is supervised. Predicted area outside that band is measured as unknown; whole-lower-lid FPR is null. Engineering inspection of twelve labelled and twelve unlabelled lower lids showed broad outputs beyond supervised support. Visible normal folds, pigment/shadow and omitted bands have no complete expert-negative annotations. No expert labels are invented, and a few unlabelled portraits cannot prove architecture failure. Existing expression-gated bag appearance remains installed.

## Every requested criterion: actual normal product path

This table uses the preserved normal API response for exposed licensed video frame5, not a new user scan. Scores are cosmetic appearance units0–100, not biological sebum, hydration or a medical severity estimate. Other samples deliberately demonstrate null results on invalid capture/expression conditions.

| Criterion | Installed working method | Actual output |
|---|---|---|
| skinType | No accepted classifier | null / insufficient |
| acne | no accepted detector; old rejected centre-surround candidate remains research-only | null / insufficient |
| oil | local bright low-saturation/specular area / appearance proxy | 0.000000 /100; valid |
| dry | eligible fine bright flake area / appearance proxy | 0.000000 /100; valid |
| sag | expression-gated contour/fold appearance proxy; no absolute anatomical sagging model | 0.007195 /100; valid |
| redness | preserved accepted EfficientNet-B0 ordinal ridge photo head; regional analytic colour maps are separate | 42.517822 /100; valid |
| tone | LAB local colour variation / visible-surface proxy | 4.301155 /100; valid |
| lines | outer-canthus Gabor line appearance proxy | 0.406555 /100; valid |
| dark | lower-lid relative colour/contrast appearance proxy | 23.337845 /100; valid |
| bags | expression-gated contour/fold appearance proxy; candidate segmentation not installed | 0.066654 /100; valid |

Cilt type and acne remain unavailable; no accepted method is concealed by a failed candidate. Acne was already gated before this task and remains gated. Existing oil/dry/tone/lines/dark/sag/bags proxies were not removed. Sag needs expression/visible-contour conditions; there is no equivalent labelled trained sagging target in the present ordinal corpus.

## Export, real visual review and independence

YOLOX ONNX35,806,681bytes was checked against primitive CPU PyTorch convolution. oneDNN raw width rounding differed on rejected multi-thousand-pixel boxes; this was diagnosed explicitly. Raw coordinate relative tolerance1e-5/absolute0.001px, scores1e-5; retained NMS output difference below0.01px (measured0.000000298). Detection acceptance gates are unchanged. Exact production ORT crop/tile/NMS and analysis adapters were exercised with a private process-only candidate registry on two previously exposed NASA portraits. This is not installed API promotion or independent final acceptance. Visual review still found hair/clothing/pores/normal folds among candidate boxes; candidate remains rejected.

Development before/after sheet explicitly shows three largest and three smallest F1 deltas: some lesion matches improve; other labelled forehead/cheek lesions are missed. Source quality, tensor overlays, bags support and domain overlays were visually inspected. No interim user test was requested.

All currently eligible source groups had already been used for development or an opened old final. Old final images/predictions were not loaded for new selection. A new split of those groups would still be development. The previously unused public Telkom metadata endpoint returned HTTP403; no authentication bypass, paid compute or downloads occurred. New independent final is therefore unavailable.

## Evidence and checks

Local ignored evidence root: `audit-results/skin-followup-20261011/`. Native photographs, raw labels, checkpoints and model bytes are not added to Git. Aggregate tracked receipt: `docs/skin-research/skin-followup-20261011.json`.

- `tensor-label-overlay.png`, `tensor-label-evidence.json`: actual input/label roundtrip.
- `quality/padding-impulse-native-check.png`, `quality/impulse-native-review.png`: real corruption versus natural-edge false flags.
- `photo-product-tensor-parity.png/json`: final-clean product/training tensor agreement.
- `yolox/development-before-after.png/json`, `yolox/product-adapter/*`: actual improvements, misses and domain false candidates.
- `bags-development-coverage.png`, `bags-coverage-review.json`: polygon support versus unknown outer ROI.
- `product/preserved-delivery.json`, `product/front-*-actual-api.json`: exact normal shortcut/source/build and criterion outputs.
- `metric-equivalence.json`: matched eight development photos, identical old/new metrics;1.125s→0.109s component timing under concurrent training, not total training/inference speedup.

Focused restart/data-integrity/model-boundary checks passed. Production runtime/frontend/model files were not changed; preserved production build was verified rather than relabelled a new build. Main was not merged; PR#2 remains Draft. Previous production high fix remains at the preserved baseline; prior seven high/two moderate development dependency findings remain OPEN. No new security campaign ran.

Remaining blockers: independent unused commercial source groups, complete expert lower-lid negatives, accepted type/acne accuracy and detector RPN/backbone adaptation. All ten criteria remain in scope, but their requested analysis advancement is not fully accepted.
