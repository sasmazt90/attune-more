# Regional dry/oily box audit — 2026-10-25

Project: `tolgar-sasmaz/attune-skin-type-regional-r1`, version 2  
Training: `a9e8b8a021825191cf5b`, RF-DETR Small, finished  
Model: `tolgar-sasmaz/attune-skin-type-regional-r1-2-rfdetr-small-t1`

## Outcome

This existing run is a useful research baseline, but it is not eligible for the regional skin map or product activation. The actual COCO export contains bounding boxes only: zero non-empty segmentations across 5,252 annotations. A dry/oily box cannot be rendered or evaluated as a regional polygon, and an image without a box is not evaluated normal skin.

The export contains 1,711 generated images representing 990 source IDs. Train contains 721 source images with one augmented copy of each; validation has 150 and test has 119. No source ID appears in more than one split, but person independence is still unestablished because source ID separation does not prove subject separation.

| Split | Images | Unique sources | Boxes | Dry | Oily | Empty images |
|---|---:|---:|---:|---:|---:|---:|
| Train | 1,442 | 721 | 4,378 | 3,058 | 1,320 | 30 |
| Validation | 150 | 150 | 474 | 311 | 163 | 4 |
| Test | 119 | 119 | 400 | 279 | 121 | 4 |

## Model evaluation

Roboflow evaluation `0CmXsrY0XavjXmUjjhBv` is complete. Overall source-test mAP@50 is 0.1805, mAP@50–95 is 0.0675 and F1 is 0.286. At the validation-selected 0.21 diagnostic threshold, neither class passes a quality gate:

| Class | Validation P/R/F1 | Test P/R/F1 at 0.21 | Test mAP@50 / mAP@50–95 |
|---|---|---|---|
| Dry | 0.194 / 0.193 / 0.193 | 0.199 / 0.233 / 0.215 | 0.1457 / 0.0561 |
| Oily | 0.166 / 0.454 / 0.243 | 0.198 / 0.471 / 0.279 | 0.2153 / 0.0789 |

Provider recommendations at 30% identify 237 missed dry detections and 96 oily false positives against 47 oily true positives. These are diagnosis signals, not authorization to tune on the exposed test split.

## Release decision

- Keep the accepted regional-method registry empty for this candidate.
- Do not convert boxes into blue/green polygons.
- Do not infer normal or mixed skin from missing boxes.
- Obtain reviewed polygon truth for dry, oily and evaluated normal regions, establish subject-independent splits, select thresholds on validation, then run locked test and independent product-camera acceptance.
- The shared learned-model acceptance gate remains fail-closed; no model, API, history or product activation is authorized.

Evidence:

- `docs/skin/evidence/regional-skin-type-box-audit-20261025-v1.json`
- `docs/skin/evidence/regional-skin-type-box-model-receipt-20261025-v1.json`
- `docs/skin/evidence/regional-skin-type-box-model-verdict-20261025-v1.json`
