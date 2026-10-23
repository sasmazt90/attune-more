# Skin research closeout — 2026-10-23

The requested UI/routine rules and localization changes are implemented in PR #6. The new 12-class model is **not OEM-ready**. No additional training was launched on that flawed 12-class version. Replacement specialist datasets were subsequently sourced, repaired and checked as described below. No research model was admitted to production.

## Completed comparison

- Frozen version 1: 669 train / 117 valid / 141 test; 927 labeled images. Import geometry/splits passed the earlier preflight. That preflight does not establish label meaning.
- 234 hosted inference calls compared the two validation-frontier candidates over all 117 validation images. Selection used validation only.
- 4360cc: validation AP50 29.98%, AP50–95 15.09%. 69fae3: 29.30% / 14.85%.
- Selected 4360cc once; 141 held-out test images, 1,195 annotations: **AP50 31.47%, AP50–95 15.78%**. No test-based threshold fitting.
- Protocol: pycocotools COCO bbox; IoU .50:.05:.95, maxDets [1,10,100], class-name mapping, confidence floor .05, overlap .5. Original source dimensions are asserted. Server candidate cap 300 was hit on 20/117 validation and 38/141 test images for the selected model. These are bounded, annotation-relative metrics, not clinical accuracy.
- The test split was previously inspected for baseline error diagnosis (including a worst-FP pilot). It remains held out from training, but is not an untouched final OEM camera acceptance set.
- Earlier platform evaluation of d2dbfd remains 27.68% / 12.63%. It is a different model/evaluation path; do not present the difference as a controlled training gain.

| Source class | Selected test AP50 | Production admission |
|---|---:|---|
| Akne | 17.41% | No |
| Beyaz Nokta | 21.87% | No |
| Egzema | 16.01% | No |
| Genis Gozenek | 13.76% | No |
| Gunes Lekesi | 19.90% | No |
| Kuru Cilt | 16.27% | No |
| Riskli Ben | 83.75% | No |
| Rozasea | 51.09% | No |
| Sedef ve Dokuntu | 21.52% | No |
| Siyah Nokta | 16.14% | No |
| Ucuk | 66.57% | No |
| Yagli Cilt | 33.33% | No |

## Verified blockers, not optional optimization

All 12 training boards were visually examined: 72 placements / 60 distinct source photos. The sample is the first six source-COCO training placements per class, not a representative 60-image error audit. Review covered visible geometry/domain/provenance; it did not medically relabel the photographs.

1. **Pinpoint annotations:** several pore boxes encompass broad cheek regions. These cannot train/score individual pore points. Whitehead and blackhead AP is also poor. Retained facial train/valid images need consistent, exhaustive individual-finding labels and explicit reviewed negatives before a new pinpoint detector run.
2. **Regional and clinical meaning:** a reviewed dry-skin image is a navel/body photo. Regional oily labels do not provide confirmed non-oily cheeks. Five of six “Riskli Ben” preview placements are stock portraits; a risk reference/labeling protocol was not supplied. High AP on that source class does not prove malignancy/risk discrimination.
3. **Acceptance:** freeze a corrected facial dataset and an independent camera-domain evaluation. Keep the existing 141 test images as the version-1 baseline; do not move them into training or tune thresholds on them. A box detector cannot supply wrinkle contours or true per-pixel boundaries by inventing geometry.

## Roboflow Agent work

The connected Roboflow Agent was given the product contract, preflight, per-class metrics, recipe schema, runtime findings and visual-review evidence. It confirmed that changing the NAS child or increasing epochs does not resolve these label-definition issues. It saved a separate research-only workflow pinned to 4360cc. Its actual execution on a worst-FP image returned the correct model ID, 640×640 source dimensions and normalized/pixel coordinates. Active Learning is disabled; there is no image logging/upload sink. Production workflows were not edited.

Workflow: `attune-research-nas-4360cc-boxes-1792755600064`. Conversation: `VSVVBhvRJa2eaSZ7vLWM`. Four Universe candidate smoke tests were also run; they do not establish independent acceptance. The whitehead candidate returned only ambiguous class `0` on its sample, while pore/wrinkle samples produced no predictions at .4. These one-image checks are not performance evaluations.

No bulk foundation auto-label run was started. Existing annotated source datasets were used instead. The connector catalog and public pricing expose different labeling units/rates, so no bulk labeling cost was inferred from that catalog value. The connected tools do not expose the actual remaining account balance.

## Reproduction

```sh
python scripts/skin-research/evaluate_roboflow_predictions.py \
  --export /private/roboflow-boxes-v1-coco.zip \
  --predictions /private/test-predictions.json --split test --out /private/metrics.json
```

The JSON companion contains all class metrics, source hashes, private-review member references and decision receipts. Raw prediction/image evidence is stored in the existing private Attune.more Drive evidence folder; no source photos or model weights are added to Git. UI verification from 121a239 remains 37 targeted tests, 142 EN/DE rendered states, production build and full CI (1,432 passed / 45 skipped). This evaluation-only addition does not change product runtime.


## Replacement specialist datasets and training

The user explicitly asked the Roboflow Agent to find appropriate images. Its search identified candidate datasets; all acceptance decisions below come from actual image/annotation inspection and exported data, not search titles.

| Target | Source | Final labeled images | Native annotations | Source groups* | Train / valid / test images |
|---|---|---:|---:|---:|---|
| Acne, whiteheads, blackheads | skin-lj9yp/jerawat-v | 2,201 | 14,572 boxes | 711 | 1,547 / 345 / 309 |
| Localized pores | dermascan-ai/pores-detection-rqkcb | 1,416 | 56,888 polygons | 609 | 1,018 / 192 / 206 |

*Source-file/decoded-pixel/near-hash groups, **not verified unique people**. Original variants were co-partitioned, rather than counted as independent photos. Group counts by split: comedones 497/108/106; pores 427/91/91.

- The publisher-declared license for both sources is CC BY 4.0. Private Roboflow copies and training bundles retain source attribution in the evidence report. The user's Core self-host model-license evidence remains separate from the source-data attribution.
- Comedones: one image with a zero-height box was excluded in full. An explicit mapping combines nodule/papule/pustule into `acne`, and preserves separately named `blackheads` and `whiteheads`. No boxes were invented. All 14,572 boxes in the actual Roboflow COCO export match the prepared boxes exactly. Maximum JPEG mean pixel difference is 1.665/255; 0 unannotated images and 0 known source/exact split overlaps.
- Pores: 12 malformed/conflicting images and 41 unverified empty images were excluded before upload. The platform canonicalized four further duplicate aliases. Those four aliases were excluded from the expected corpus; a one-image annotation set was restored to the exact prepared source after an alias merge. The final version-2 export passes full source-image/box/mask parity: **56,888 of 56,888 instance raster masks have IoU 1.0 against the source**. This is import integrity, not prediction accuracy. Maximum JPEG mean difference is 0.0144/255; maximum box rounding difference is 0.01 px.
- The initial 444-image pore candidate contained only 84 source-name groups; the initial 1,558-image wrinkle candidate contained only 247 source-name groups. Both had inherited variants across source splits. These were audited rather than accepted at their headline image counts.
- The acnes-wscug candidate uses broad whitehead/blackhead region masks and was rejected for pinpoint training. The pores-detection-bmwpr candidate is metal-weld radiography and was rejected. Wrinkle candidates with whole-region masks and nonfacial examples were not promoted into crease-line ground truth. Whole-face type labels were not relabeled as regional oil/dry evidence.

Comedone training `e45fb1f2578bf09750fb` is running on private `attune-comedones-boxes-grouped-r1/1`, RF-DETR Small, requested maximum 100 epochs. The standard recipe uses 512x512; most source photographs are 420x420, so this does not reproduce the previous 320-input reduction. Custom recipe lookup initially returned a new-version 404, then became available; this is recorded rather than claiming a 640 letterbox configuration was launched. No duplicate comedone training was started.

Pore training `66999f483e520c0353b9` is running on private `attune-pores-masks-grouped-r1/2`: YOLOv11 Small Segmentation, requested maximum 150 epochs, 640x640 Fit (black edges) in, no additional online augmentation. The actual YOLO training-format export was checked: 1,416 image label files and 56,888 polygon rows, finite normalized coordinates, 3–59 vertices. Its SHA-256 and split counts are recorded in `pores-yolo-format-preflight-20261023.json`. Both actual training receipts and source attribution are in `replacement-specialists-20261023.json`. Product admission remains disabled until the new models have actual held-out results. Existing UI/routine rules are already implemented; these new training jobs do not constitute completed model acceptance.


The existing native ChatGPT hourly monitor was re-enabled for only these two exact training IDs. It reads run status and existing model-linked evaluations, then summarizes changes in Turkish. It does not launch paid work, merge code or admit a model. The final prepared training ZIPs are saved in the existing [Drive evidence folder](https://drive.google.com/drive/folders/1VSRvppN-XySX9_J-dSo_Urf5dNcnsMG5).
