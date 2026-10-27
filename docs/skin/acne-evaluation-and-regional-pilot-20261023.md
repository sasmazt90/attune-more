# Acne evaluation and regional pilot — 2026-10-23

No model is accepted for product use. Training completion is not roadmap completion.

## Detection candidate

Finished RF-DETR NAS has 89 children (four baselines). Candidate `754885`, highest observed raw mAP50–95, was actually inferred on all 165 validation and 82 source-test images; resolved package `d336c1c2c6c791758326d9cc4f9afecc`. Recommended flags are not accuracy/hardware winner claims. Provider queued evaluation `0xMgfVLFzMyNEOhN1baC` evaluates different child `a5e262`; its evidence is separate.

Thresholds were selected on validation only (IoU0.5; max F1 on grid0.05..0.95), then locked for test. Test results:

| Class | Threshold | Precision | Recall | F1 | TP/FP/FN |
|---|---:|---:|---:|---:|---|
| Pimple | 0.30 | 35.78% | 32.28% | 0.3394 | 112/201/235 |
| Post acne | 0.30 | 38.90% | 39.76% | 0.3933 | 1387/2179/2101 |
| Pigmentation | 0.20 | 14.35% | 16.39% | 0.1531 | 30/179/153 |

Test COCO AP50=0.191917, AP50–95=0.052792 (maxDets100); maxDets300=0.195392/0.053620. These are detection AP, not general accuracy. Confidence floor0.05 truncates curves, and dense responses hit300 boxes (124/165valid,65/82test). Subject/exposure independence and expert semantics are not established. No real-camera evaluation or application acceptance yet.

Deterministic worst-case validation boards were rendered with supervision0.31.1 and visually inspected: tiny dense instances missed, wrong locations and incomplete label coverage need investigation. Input312 resolution is known for weak queued child only, not established for candidate754885. Avoid blindly attributing all failure to resolution. Next experiment should evaluate tiling/crops and annotation coverage on validation, without tuning on the exposed test.

The lossless gzip bundle stores all247 original snapshot JSON records, names, inference IDs, model/package identity and raw predictions, SHA256 `c2a8499015a5161ddc4e121c99187e2cca2af5bd5d88bb2b38a7cd0c98d6a5fc`. Replay using `evaluate_detector_snapshot.py --archive acne-remote-v1.zip --snapshots docs/skin/evidence/acne-best-inference-snapshots-20261023-v1.json.gz --split valid --output valid.json`, then `--split test --locked-validation valid.json --output test.json`. Source archive hash is pinned in receipts. Never upload new user photos without the existing consent flow.

## Regional research data

Selected public source: https://universe.roboflow.com/bread-7emlk/skin-analysis-wl7al/dataset/11 (`augmentation_version`, CC BY4.0, coco-segmentation). Source948images, split664/190/94, already fit-with-black640x640. Genuine polygons: Oily1168, Redness610; target Redness also has six unsupported RLE and two invalid polygons. Cross-split perceptual/filename candidates are quarantine candidates, not confirmed identities.

`prepare_regional_polygons.py` preserves original image bytes and polygon geometry/category IDs; quarantines whole images containing unsupported target geometry or cross-split candidate relations. It never converts boxes to masks or invents normal truth. Prepared337images/1636polygons:

| Split | Images | Oily | Redness |
|---|---:|---:|---:|
| Train |244|780|429|
| Valid |63|195|105|
| Test |30|90|37|

Upload task `jr8FWunZL1rM1mIowmxS` completed:337uploaded,337annotated,0duplicates,0upload/annotationerrors. Image search confirms337 and sampled annotation summaries; project summary remains stale at0. No version/training has started. Verify full imported geometry/split preservation before research-only training; checkpoint actual job IDs, avoid duplicate upload. Pilot masks have incomplete negative/normal coverage; two train examples inspected by assistant, not expert. No dry masks, supported normal map, combination truth, sensitivity conclusion or accepted regional method is created.

## Verification

98 tests pass, zero failures/errors/skips, covering regional API policy, archive/export provenance, pinned model identity/geometry, one-to-one matching, validation threshold locks, empty AP, gzip replay, quarantine and unchanged source masks. Evidence contains code hashes and dependency versions. No production deploy/merge or new accepted model integration.
