# Regional appearance mask evaluation — 2026-10-23

The regional NAS run finished. Oiliness needs improvement; redness has promising class-union overlap but no accepted camera calibration or normal/dry support. No research model has been activated in the product. Concurrent browser-contract work is preserved.

## Training and candidate identity

[Private dataset version 1](https://app.roboflow.com/tolgar-sasmaz/attune-skin-regional-skin-map/1) retains 337 images and 1,636 source polygons, split 244 train / 63 validation / 30 test. Training `3485f8c67f957a1b850d` finished, with model group `k3CenVIV6eguGn8fSMdT-3485f8c67f957a1b850d-rfdetrNasGroup`.

Roboflow returns **75 records and 74 distinct model IDs**. ID `e79545` appears twice with different candidate/baseline metadata. Raw records are preserved; this is not claimed to be 75 distinct deployed models. Candidate `2c07ef` has the highest observed provider `map5095` among returned records (20.96 provider units). Its real hosted inference resolves to immutable package `e1688c2c8447af39e51ce60dd8c7f1d0`. No hardware-winner conclusion is inferred from recommendation or frontier flags.

All 63 validation and 30 source-test images were inferred against this exact package. Inputs are exact images from the previously verified version export, SHA256 `e470c5f1a9b4bdaadd87a9ba9b714175bc62ab0a7e0b10d10b4880a72889aa40`. Source filenames, encoded image hashes, dimensions, class names, model/package identity and unique inference receipts are checked before scoring. Images/labels/splits were not changed.

## Locked instance-mask evaluation

Class-aware, confidence-ordered one-to-one matching uses **mask IoU0.5**. Validation-only F1 selection on the fixed 0.05–0.95 grid produced **0.35 for Oily and 0.35 for Redness**. A SHA256 lock was written at 07:21:14 UTC before any test inference. Thresholds and source-test membership remain unchanged.

| Source test, 30 images | Precision | Recall | F1 | TP / FP / FN |
|---|---:|---:|---:|---:|
| Oily |64.91%|41.11%|0.5034|37 / 20 / 53|
| Redness |62.50%|40.54%|0.4918|15 / 9 / 22|

COCO **segmentation** AP50 / AP50–95 is 0.46135 / 0.18973 at maxDets100, and 0.46351 / 0.19033 at maxDets300. These are mask AP metrics, not general accuracy. Per-class AP50–95 at maxDets300: Oily0.15196, Redness0.22869. Validation AP50–95 at maxDets300 is0.21045.

No detection box is substituted for a mask. Predicted contours are rasterized as supplied by COCO; self-touching raster contours are not repaired. Explicit empty model contours remain empty predictions and cannot match a source instance: 85 validation and 29 test empty masks were retained and counted. Missing contour fields, malformed coordinates or mismatched provenance fail evaluation. Source masks still require genuine valid polygons. Evaluation area is derived from the polygon raster rather than a publisher's enclosing-box area; source files remain immutable.

## Class-union analysis and failure review

Publisher instance subdivision matters for a regional appearance map. A separate exploratory analysis therefore unions each class's masks per full source frame, using the already locked thresholds; it changes no predictions, thresholds, clipping, model selection or source labels.

| Fixed-threshold class-union comparison | Oily | Redness |
|---|---:|---:|
| Validation micro IoU |0.4285|0.6650|
| Source-test micro IoU |0.3090|0.7095|
| Source-test annotated area covered |38.17%|86.61%|
| Source-test images carrying class annotations |21|9|

These are agreements with incomplete publisher masks. Missing annotations are **unknown**, not normal/negative skin; coverage is not a clinical or camera accuracy estimate.

Two deterministic worst validation examples were inspected by the assistant, not an expert:

- **Oily, valid41:** source annotations cover selected facial highlights; the model also segments chest/clavicle highlights. Source coverage and anatomical face scope affect false-positive interpretation. No post-test face clipping or relabeling was performed.
- **Redness, valid35:** source annotations subdivide continuous regions into nested/small instances; the model emits broader continuous masks. Instance matching gives zero TP on this selected example despite visible regional correspondence. Class-union results provide complementary evidence; they do not erase instance errors or prove label correctness.

Oiliness remains an improvement target. Redness remains a research candidate pending independent real-camera/skin-tone/lighting calibration, reviewed region coverage and complete negative/normal support. The source test contains only nine redness-annotated images. The accepted-method registry stays empty; no normal/dry/combination or sensitivity truth is inferred.

## Reproduction and evidence integrity

All **93 complete raw responses** are preserved losslessly as SHA256-pinned binary parts plus two indexes. Eight initial local writes were detected as incomplete before evaluation and replaced with eight additional requests using the same image, package and inference configuration: 101 requests in total, 93 retained responses. Every retained JSON record parses and checks against its input identity. Large replies now use atomic complete-file verification. There was no missing-response padding or fabricated geometry.

Reassemble the original gzip bytes with `scripts/skin-research/reassemble_evidence_bundle.py` using:

- `docs/skin/evidence/regional-mask-inferences-valid-20261023-v1.index.json`
- `docs/skin/evidence/regional-mask-inferences-test-20261023-v1.index.json`

The 7 validation and 4 test parts reproduce the original bundles byte-for-byte. Reassembled SHA256 values are `815bec7badbc4c1795e507f7eacf31f656981b4e75f4d528b2f659ae3986017a` and `b36d2c07ccc998e5b79095564bd20b8a1fc2e9a706d8e9a4fab123f88c8cf9e6` respectively. Run `evaluate_segmentation_snapshot.py` on validation first, then test with the validation JSON supplied through `--locked-validation`. The original validation-file lock remains intact; the later union analysis is a separate sidecar.

## Checks and continuation

145 current unit checks pass with zero failures/errors/skips, including 24 new regressions for exact-mask AP, equal boxes with disjoint masks, no box-to-mask fallback, package/source/dimension checks, empty masks, one-to-one matching, overlapping independent redness/oil masks, class unions, test-threshold locks, corrupt evidence parts, path safety and lossless reassembly. These tests verify tooling and data integrity; they are not camera acceptance. Prior browser-contract commit `cf7447b28e2c39cc976f0af9d66e4be5a44dff54` and its separate 48 executable checks are preserved on the parent branch.

Continue targeted oil coverage/anatomical-scope work on validation, redness camera/coverage validation, and under-eye cleaned grouping/segmentation. Dryness/normal truth, independent camera benchmark, SVG overlay wiring, longitudinal acceptance, wrinkles and sagging remain open. No production merge, deploy, photo upload or new subscription occurred. The full roadmap is not complete.
