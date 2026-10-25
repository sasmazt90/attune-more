# Regional Oily/Redness RF-DETR Seg Small diagnosis

This diagnosis is bound to training `af287a006e2e428f5ce4`, model `tolgar-sasmaz/attune-skin-regional-skin-map-1-rfdetr-seg-small-t2`, evaluation `vsQ6klUgSohCdtLwNMJf` and archive SHA-256 `a24793ca3490a48088abf47ba89fc9ab94e1c3a12c488ce52915e19b5bdf6fd6`.

## Decision

The model remains research-only. Training, final-test evaluation and activation are blocked. The 30-image test is below the provider's 50-image minimum, was already exposed during diagnosis and is not proven source/person independent. It is diagnostic evidence only.

## Per-class findings

| Class | Validation mAP50 | Validation mAP75 | Validation F1 | Test F1 at validation threshold | Finding |
|---|---:|---:|---:|---:|---|
| Oily | 0.527 | 0.028 | 0.571 | 0.475 | Coarse overlap is materially stronger than strict boundary localization. |
| Redness | 0.435 | 0.184 | 0.524 | 0.581 | Only 571 labels versus 1,065 Oily labels; small-object test-diagnostic mAP50 is 0. |

At provider confidence 0.2, the 63 validation images aggregate to 189 TP, 386 FP and 111 FN. The 30 diagnostic test images aggregate to 78 TP, 213 FP and 49 FN. Background false positives are therefore a real validation problem; whether they result from missing expert masks, scope ambiguity or appearance confounders still needs expert review.

One Oily/Redness wrong-class case does not support collapsing their taxonomies. Redness remains a separate red contour or hatching layer and may overlap oil or dryness; it is not a sensitivity result.

## Data boundary

The version contains only Oily and Redness polygons. It contains no Dry, evaluated Normal or combination-skin regional truth. Missing masks are not Normal labels, boxes are not polygons, and predictions are not expert truth. This model cannot complete dryness, normal/dry/oily classification or regional combination inference.

## Controlled next experiment

The executable release gate is `scripts/skin-research/check_regional_improvement_release.py`. It permits at most one validation-only change—either face-aligned higher effective resolution or expert-locked mask-extent standardization—and only after all of the following exist:

1. A complete source/person-grouped replacement split bound to the source archive.
2. An expert Oily/Redness mask-extent and hard-negative protocol preserving independent Redness semantics.
3. A new untouched final test with at least 50 images and no overlap with the exposed test.
4. A separately reserved independent product-camera holdout.

Even a passing release gate does not authorize test evaluation or product activation. Those remain subject to the shared model acceptance gate, independent camera evaluation and working integration evidence.
