# TOGG Attune — focused skin training and integration, 2026-10-10

Production BUILD_ID: `_YWFLetSYj_oTN7LuFj4H`. Exact delivery SHA and served-file hashes: local `audit-results/all-health-20261010/delivery.json` after commit.

UI completion is separate from analysis accuracy. No interim user test, paid call, cloud training, new source search or failed-model fallback is used. All experiments/checkpoints/private photographs remain ignored. The existing source branch and prior fixes are preserved.

## Data and protocol

Type train/validation/test: 1802/367/342. Masked degree train/validation/test: 124/21/33. Source-family grouping spans both corpora; known duplicates and conflicting classes are excluded. Degree test groups are absent from backbone training/selection. Unknown person links remain; this is not patient-independent validation. Source labels lack a verified expert protocol. Original vendor 640×640 stretch cannot be reversed by cropping.

The numeric corruption filter and initial visual sample did not guarantee clean type inputs. Frozen validation error sheets show residual speckle, makeup, processing and text. This failed source-quality requirement is an additional promotion gate, not a post-test threshold adjustment. No new tuning/retraining cycle on the exposed split is opened. The separate ordinal subset was reviewed on validation and sampled training photographs before its protected test.

Predeclared epoch/patience/wall budgets, preprocessing, baselines, licenses and hashes: `skin-focused-protocol-20261010.md` and `THIRD_PARTY_NOTICES.md`. Wall checks occur at epoch starts and finish the ongoing epoch; recorded elapsed time includes any boundary overrun.

## Type: only ResNet18 vs EfficientNet-B0

| Candidate | Validation macro-F1 | Balanced accuracy | Selected checkpoint | Training seconds |
|---|---:|---:|---|---:|
| resnet18 | 0.331 | 0.334 | `07a12a8f3a791772760b7ce49bf81d59b6786f64479a9a3b5b6d9324699b8efb` | 3709.250 |
| efficientnet_b0 | 0.357 | 0.362 | `aeee122ca3e3f8ff29f4db6ea2717898f6503512458cbed3da0b53c05b49a7ad` | 915.953 |

| Candidate | ONNX bytes | Cold load ms | Median warm inference ms | Session RSS delta bytes | Max parity error |
|---|---:|---:|---:|---:|---:|
| resnet18 | 44704757 | 357.585 | 72.548 | 51867648 | 0.00000548 |
| efficientnet_b0 | 16040688 | 259.098 | 41.555 | 6971392 | 0.00001919 |

Both candidates used the same eight validation inputs, two CPU inference threads and crop/RGB/ImageNet preprocessing. Another bounded detector training process was active during these measurements. They are comparable observations under shared load, not idle-device benchmarks or a demonstrated speedup. RSS deltas do not include the entire interpreter/runtime.

Frozen selected candidate: **efficientnet_b0**. Protected test n=342, macro-F1=0.294, balanced accuracy=0.298; dataset metric acceptance=False; installed acceptance=False.

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| normal | 0.345 | 0.436 | 0.385 | 94 |
| dry | 0.260 | 0.318 | 0.286 | 85 |
| oily | 0.418 | 0.299 | 0.349 | 127 |
| combination | 0.179 | 0.139 | 0.156 | 36 |

Confusion matrix (truth rows/prediction columns, normal/dry/oily/combination): `[[41, 29, 18, 6], [20, 27, 27, 11], [49, 34, 38, 6], [9, 14, 8, 5]]`.

Temperature/confidence thresholds use validation only. Confidence never becomes appearance severity. Comparable two-model ONNX size, cold/warm time, parity and process memory: private `type-runtime-comparison.json`; these timings do not establish a camera-domain speedup.

## Eighteen masked ordinal targets

| Target | Validation MAE | Test MAE | Test ordinal agreement | Validation/test support | Frozen target acceptance |
|---|---:|---:|---:|---|---|
| acne | 0.806 | 0.906 | 0.394 | 21/33 | False |
| blackheads | 0.530 | 0.589 | 0.636 | 21/33 | False |
| whiteheads | 0.625 | 0.826 | 0.515 | 21/33 | False |
| pores | 0.691 | 0.729 | 0.485 | 21/33 | False |
| oil | 1.154 | 1.086 | 0.303 | 21/33 | False |
| irritation | 0.859 | 0.976 | 0.273 | 21/33 | True |
| sensitivity | 1.031 | 0.794 | 0.394 | 21/33 | True |
| redness | 1.046 | 0.953 | 0.273 | 21/33 | True |
| lines | 1.042 | 0.952 | 0.394 | 21/33 | False |
| bags | 0.718 | 0.895 | 0.303 | 21/33 | False |
| dark | 0.602 | 0.623 | 0.515 | 21/33 | False |
| foreheadLines | 0.610 | 0.736 | 0.364 | 21/33 | True |
| elasticity | 0.760 | 1.012 | 0.424 | 21/33 | False |
| dry | 0.767 | 0.585 | 0.485 | 21/33 | False |
| darkSpots | 0.719 | 0.949 | 0.212 | 21/33 | True |
| postAcne | 0.653 | 0.602 | 0.606 | 21/33 | False |
| tone | 0.566 | 0.808 | 0.364 | 21/33 | False |
| freckles | 1.267 | 0.991 | 0.394 | 21/33 | True |

| Target | Test constant median MAE | Test constant mean MAE | Comparable analytic MAE / learned MAE / n |
|---|---:|---:|---|
| acne | 1.000 | 0.853 | 1.100 / 1.169 / 10 |
| blackheads | 0.576 | 0.699 | unavailable |
| whiteheads | 0.758 | 0.953 | unavailable |
| pores | 0.727 | 0.826 | unavailable |
| oil | 1.273 | 1.236 | 2.498 / 1.412 / 10 |
| irritation | 1.152 | 1.215 | unavailable |
| sensitivity | 0.909 | 0.936 | unavailable |
| redness | 1.091 | 1.156 | 1.798 / 1.017 / 10 |
| lines | 1.061 | 1.076 | 2.332 / 0.894 / 10 |
| bags | 0.909 | 0.926 | unavailable |
| dark | 0.667 | 0.676 | 1.128 / 0.524 / 10 |
| foreheadLines | 0.939 | 0.928 | unavailable |
| elasticity | 1.000 | 1.040 | unavailable |
| dry | 0.788 | 0.714 | 2.498 / 0.612 / 10 |
| darkSpots | 1.091 | 1.150 | unavailable |
| postAcne | 0.485 | 0.801 | unavailable |
| tone | 0.788 | 0.887 | 2.116 / 0.718 / 10 |
| freckles | 1.061 | 1.108 | unavailable |

Per-target train-mean/median and available analytic-method comparisons are retained in `degrees-final-test.json`. Only accepted product targets may be promoted; all heads remain whole-photo predictions. No regional/pixel grade is inferred. Acne grade cannot replace detector-driven card/count/marks. Elasticity is not sagging; dehydration is not biological moisture.

## Native acne detector comparison

| Candidate | Precision | Recall | F1 | AP50 | mAP .50–.95 | TP / unmatched / missed | Unmatched/photo | Images |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| yolox | 0.420 | 0.428 | 0.424 | 0.299 | 0.072 | 616 / 850 / 822 | 9.770 | 87 |
| fasterrcnn | — | — | — | — | — | no validated epoch | — | no protected inference |

| Candidate | Completed epochs | Last epoch elapsed seconds | Frozen validation threshold | Checkpoint bytes |
|---|---:|---:|---:|---:|
| yolox | 1 | 4078.438 | 0.100 | 35892160 |
| fasterrcnn | 0 validated | 7200.072 operational elapsed | no selection | no trained checkpoint |

**Faster-RCNN comparison remains incomplete (runtime-budget FAIL).** Fresh initialization and the train-only 80-step learning-chain check passed (mean loss 0.194 to 0.031); the tiny check model was discarded before fresh full training. The epoch-start 3600-second rule permitted a first-epoch overrun. An operational 7200-second process ceiling was added during the run, not falsely described as predeclared. At 7200.072 seconds no validated checkpoint existed; only the verified owned training process was stopped. Its files/manifest/seed/initialization/learning evidence remain; partial in-memory weights were lost because that original loop had no intermediate checkpoint. No protected-test metric or architecture comparison success is claimed. No restart, new architecture or post-test threshold change was opened.

The epoch-boundary program was archived locally before changing the source. The future detector loop now checks its wall budget between batches, writes atomic partial safetensors/progress every 100 batches and saves partial weights before a budget exception. Partial weights are explicitly ineligible for validation selection and do not include optimizer state. This correction was syntax-checked; no new expensive training or retroactive recovery of the stopped in-memory weights is claimed.

| Research export | ONNX bytes | Cold session load ms | Median warm ms | Max parity error |
|---|---:|---:|---:|---:|
| yolox | 35806681 | 453.000 | 109.000 | 0.00988770 |
| bags | 49833121 | 297.000 | 32.000 | 0.00001097 |

These rejected research exports are not installed. Shared-load timings cover model load/inference only, not the complete native tiled request or clinical performance. No Faster-RCNN production ONNX is claimed; it is the fresh frozen research baseline. Process RSS snapshots are retained in local execution records; no unsupported peak-memory comparison is inferred.

The baseline and main detector were configured with the same fresh source split/native crop/tiles. A missing baseline final result is an incomplete comparison, not an inherited old result. Unmatched predictions are annotation-relative errors: unlabelled skin is not a verified healthy negative. Old Faster-RCNN results remain historical failures, not current evidence. Source-coordinate NMS deduplicates overlapping tiles. Boxes are displayed at box resolution, with no Gaussian or GradCAM severity.

## Eye-bag mask

Frozen polygon-supported test: n=91 ROIs, Dice=0.840, IoU=0.727; restricted mask metric acceptance=True; installed acceptance=False.

Supervision/metrics include actual nonrectangular polygons and a two-source-pixel boundary band. 122 rectangular polygons and 327 box-only annotations are not exact masks. Unknown outer ROI is excluded. These Dice/IoU values cannot establish whole-ROI specificity or separation from pigment, shadow and normal lower lids. Independent native portrait outputs and manual confounder review remain separate in `domain-review` and `independent-domain-review.json`.

## Installed product gates

| Task | Accepted | Version | ONNX hash |
|---|---|---|---|
| type | False | skin-type-efficientnet_b0-20261010-v1 | `f4b8e3a9a3ff5e0a86033f29675041eeb744624e32ef810c4e27e75fdab003b7` |
| degrees | True | skin-appearance-photo-ridge-20261010-v1 | `65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3` |
| acne | False | skin-acne-yolox-20261010-v1 | `3073b196b8e8fe469399f4c3f3e1472f98e4b54840434ded18139c40cbb9c8cc` |
| bags | False | skin-bags-bags-20261010-v1 | `b9e2667723ad5f737a0134f8fcde61c1c80e18e63d2f1d0092c598a6c273b30a` |

Rejected ONNX files remain private and are not shipped. The registry records rejection without loading them. No center-surround acne fallback or fake zero fills their gap. Existing real contour/fold bags and other analytic proxies remain independent. Source RGB/background/crop, new overview plus six region views, side-photo ownership, NULL semantics, fixed integer percent presentation and normalization/model-compatible history remain distinct.

## Criterion matrix

| Criterion | Global | Regional | Local layer | Acceptance/gap |
|---|---|---|---|---|
| Skin type | accepted four-class model only, otherwise NULL | none | none | dataset metrics, clean input and camera-domain acceptance separate |
| Tone / redness | actual union or accepted ordinal head | analytic eligible skin | actual analytic pixel signal | directional lighting/skin-tone confounders remain |
| Oil | eligible highlight union or accepted ordinal head | highlight area | actual highlight signal | natural shiny source miss remains; no moisture/sebum claim |
| Acne | deduplicated accepted source candidates | same owned candidates | source boxes/marks, not severity mask | detector plus independent domain gate; failed candidate yields NULL |
| Sagging | supported lower-face contour/fold summary | visible anatomy only | actual supported contour/fold only | some bands lack support; not elasticity |
| Dryness | eligible flake union or accepted ordinal head | flake candidates | actual eligible flake signal | pores/JPEG/shine confounders and natural positive support remain limited |
| Lines / dark circles | observed periorbital or accepted whole-photo target | local outer-corner/lower-lid | actual analytic signals | expression/lighting/detail confounders remain |
| Eye bags | observed contour or accepted mask/whole-photo target | actual lower lid | contour or accepted genuine mask | mask-specificity/domain acceptance separate from annotated-band Dice |

Global learned scores do not recolor analytic maps into learned severity. Every saved record retains analysis/capture identity, dimensions/transforms, method/normalization/hash and validity. Old six-region records retain six views. There is no total-health aggregate.

## Final evidence and limitations

A real cross-module history check caught a compatibility defect: the new seven-view adapter hid numeric indicators from legacy records without schemaVersion 3. The adapter now carries the existing regional rows unchanged. Three focused unit regressions passed; the fresh production dental/history check verifies the old 0.02 contour value as 20 ×10⁻³ contour ratio, not a percentage or fabricated overview. All thirteen current-build controlled checks passed. The initial API assertion before the normal launcher reached running status remains recorded as an unsuccessful startup-timing attempt; it is not copied as final acceptance.

Final current-build UI/API execution ledger: `audit-results/all-health-20261010/focused-final-execution.json`; fresh overview/regions/maps/history/quiet desktop/narrow/native200 screenshots are referenced there. Nine current-build captures were manually inspected; their file hashes and concrete observations are in `final-ui/visual-review.json`. The failed preliminary native200 scan remains recorded: vehicle-state safety lock returned to start and screenshot capture timed out during concurrent training. Its first desktop pass is not final-build acceptance.

Source-family bootstrap intervals use frozen outputs only (`frozen-group-uncertainty.json`); they do not estimate unknown person linkage, annotation bias or camera-domain shift. NASA high-detail portraits are FRONT-only. The three-angle video is controlled pose evidence, not three high-detail people or physical user acceptance.

Production npm audit: 0. Development audit: **7 high + 2 moderate remain**. No forced dependency change or paid API call was added. Physical eye closure/hand/object positives, auditory pronunciation and broader natural clinical accuracy are not inferred from callback/fixture/playback success. Normal profile/history are untouched by audits.

**Full skin analysis/user final acceptance is not automatically ready because the UI/build passed. The concrete frozen model gates and natural/physical gaps above control that decision.**

## Current production execution

| Check | Exit | Seconds | Fresh log |
|---|---:|---:|---|
| skin-api | 0 | 18.904 | `audit-results\all-health-20261010\focused-final-skin-api.log` |
| skin | 0 | 229.699 | `audit-results\all-health-20261010\focused-final-skin.log` |
| skin-history | 0 | 161.035 | `audit-results\all-health-20261010\focused-final-skin-history.log` |
| skin-wipe | 0 | 73.795 | `audit-results\all-health-20261010\focused-final-skin-wipe.log` |
| skin-followups | 0 | 82.615 | `audit-results\all-health-20261010\focused-final-skin-followups.log` |
| final-ui | 0 | 74.374 | `audit-results\all-health-20261010\focused-final-final-ui.log` |
| responsive | 0 | 149.425 | `audit-results\all-health-20261010\focused-final-responsive.log` |
| audio-focus | 0 | 8.310 | `audit-results\all-health-20261010\focused-final-audio-focus.log` |
| care | 0 | 16.417 | `audit-results\all-health-20261010\focused-final-care.log` |
| guidance | 0 | 18.401 | `audit-results\all-health-20261010\focused-final-guidance.log` |
| dental-camera | 0 | 89.552 | `audit-results\all-health-20261010\focused-final-dental-camera.log` |
| dental-history | 0 | 80.477 | `audit-results\all-health-20261010\focused-final-dental-history.log` |
| vision-negative | 0 | 43.220 | `audit-results\all-health-20261010\focused-final-vision-negative.log` |

Normal-launcher API: first request 4748.926 ms, repeated same-source request 3083.560 ms. These are complete request times, not isolated inference. Source-hash rejection and invalid-quality NULL/no-map checks passed. No normal history record was added.
Normal backend RSS before/after first request: 100184064 / 170020864 bytes; repeat: 170020864 / 177938432 bytes. These are process snapshots, not peak ONNX memory.
Accepted degree ONNX session initialization 380.595 ms; first degree inference 29.894 ms. Initialization is cached for the process; its recorded load time on subsequent results is not a repeated load. Image decoding/CV/map encoding and camera-worker preparation are outside these ONNX timings.

| Controlled scan | Worker initialization round trip ms | First frame round trip ms | Median later frame round trip ms |
|---|---:|---:|---:|
| Desktop | 3016.100 | 10331.600 | 76.600 |
| Native browser 200% | 3229.900 | 10095.200 | 51.050 |

Worker round trips include asset/runtime initialization or frame IPC/inference/response. Concurrent CPU training was active. They do not prove a speedup against the earlier approximately 19-second cold preparation. Camera preparation, accepted backend ONNX initialization, inference and complete API requests are reported separately.

**Ready for full user acceptance: NO.** Skin type, acne detection and learned eye-bag specificity failed their frozen gates. The Faster-RCNN comparison is incomplete at the operational ceiling. Natural oil/dryness and physical/audio acceptance gaps remain. The delivered UI and limited accepted global redness head do not close these accuracy gaps. No further user test is requested to finish independent work.
