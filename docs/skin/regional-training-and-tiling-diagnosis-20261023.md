# Regional pilot training and acne tiling diagnosis — 2026-10-23

No model has been accepted for product use. This branch is research and implementation work; no production activation, merge or deployment occurred.

## Regional oiliness/redness

[Private version 1](https://app.roboflow.com/tolgar-sasmaz/attune-skin-regional-skin-map/1) was generated with empty preprocessing and augmentation dictionaries. Its 337 images retain 244 train / 63 valid / 30 test. Full export comparison initially failed: Roboflow recomputed source bounding boxes on 316 images. A task-specific **exact polygon** comparison then paired every image using original name, dimensions, class and unrounded polygon coordinates; all 1,636 source polygons and split assignments match. Box changes are explicitly recorded, never called identical geometry. Pixel bytes changed on some exported images; exact photo identity and subject independence are not asserted.

Dataset board confirms 337 annotated images with zero expert approvals. The project's `unannotated=337` summary is inconsistent with the board; no duplicate upload was made. Source labels retain incomplete coverage, source semantics and normal/dry limitations.

Training `3485f8c67f957a1b850d` (`rfdetr-nas-seg-parent`) started at **2026-10-23 05:28:00 UTC**, and remained running at the final check. The first training request only triggered the required COCO export and returned an export-not-ready error; after export readiness, exactly one training was created. Continue the same job, page resulting children by modelGroup, evaluate real masks per class. Do not activate a product method merely because this research run finishes.

## Validation-only acne experiment

Pinned model `754885`, package `d336c1c2c6c791758326d9cc4f9afecc`, was inferred on 24 JPEG95 crops from six original validation images. Four 60%-width/height corner crops overlap; crop predictions are translated back into original coordinates and deduplicated by class-aware IoU0.5 NMS. No truth boxes were cropped, relabelled or fabricated. All payload hashes reproduced independently using the committed preparation script and Pillow12.3.0.

Selection was fixed before the requests: three previously selected worst cases (26,144,19), plus the first three remaining SHA256(filename) controls (34,7,23). These groups are reported separately. Original confidence thresholds remain Pigmentation0.2 / Pimple0.3 / Postacne0.3; no new threshold fitting or test inference occurred.

| All six images, fixed thresholds | Full-frame TP / FP / FN | Tiled TP / FP / FN |
|---|---:|---:|
| Pimple | 4 / 16 / 29 | 11 / 31 / 22 |
| Post acne | 124 / 115 / 285 | 148 / 193 / 261 |
| Pigmentation | 0 / 25 / 62 | 0 / 26 / 62 |

Pimple recall rose12.1%→33.3%, but false positives rose16→31. Postacne recall rose30.3%→36.2%, while precision fell51.9%→43.4%. Pigmentation remains unresolved at its operating threshold. Hash controls' AP50 fell0.2034→0.1870; there is no claim of general improvement. Tiling jointly changes scale/context/JPEG encoding and prediction budget, so this is not an isolated causal resolution test. This biased small sample does not replace full validation, independent subjects or real-camera acceptance. Do not promote this detector or blindly retrain the same data.

Replay the lossless `acne-tiling-snapshots-20261023-v1.json.gz` with `scripts/skin-research/evaluate_tiling_experiment.py`, passing the frozen remote acne archive, original baseline inference gzip and original validation JSON. `prepare_tiling_experiment.py` reproduces request payloads from that same source. Next investigate label taxonomy/coverage and localization before choosing a targeted data/training correction.

## Checks and continuation

115 unit checks passed, with zero failures/errors/skips, covering existing API/combination safeguards, source/export matching, exact masks versus recomputed boxes, coordinate translation, class-aware duplicate removal, pinned package/dimension validation, fixed experiment selection and threshold provenance. Code hashes and payload reproduction are in `tiling-and-regional-checks-20261023-v1.json`.

The API's accepted regional-method registry remains empty. Normal remains uncoloured only with accepted evidence; unknown is grey; redness is independent of oil/dry and does not imply sensitivity. No real-camera benchmark or complete roadmap acceptance is claimed. Under-eye399images remain available without a generated version; all other pending work remains in EXECUTION_STATE.json.
