# Acne RF-DETR Small T2 targeted diagnosis

The finished model remains research-only. Provider evaluation and the existing geometry audit agree on a concrete resolution problem: the median source image is 1280×1280, inference is 640×640, and roughly 94% of every class occupies less than 0.04% of source image area. The dataset is also highly imbalanced: 32,123 Post acne labels versus 3,640 Pimple and 1,579 Pigmentation labels.

At provider confidence 0.2, the diagnostic test aggregate contains 1,414 true positives, 4,896 false positives and 2,604 false negatives across 82 images. Provider recommendations identify 2,451 missed Post acne detections, 52 Post acne/Pimple wrong-class cases and an overconfident Pimple false-positive problem. These are review cues, not proof that labels are wrong.

## Controlled next step

Training stays blocked until all of the following are true:

1. An expert locks positive, hard-negative and ambiguous-case policy for Pimple, Post acne and Pigmentation using the existing 81-item train/validation queue.
2. Source/person grouping covers all 800 records and a new group-locked split is re-audited.
3. A new final holdout is frozen before training and has zero overlap with the exposed test.
4. A proposal changes exactly one factor and selects only on validation: face-aligned single ROI or higher effective resolution.

Arbitrary four-corner tiling is not authorized because the earlier validation diagnostic increased false positives and reduced hash-control AP50. The new executable release gate enforces these constraints and never authorizes test evaluation or activation.

Evidence: `docs/skin/evidence/acne-rfdetr-small-t2-diagnosis-20261025-v1.json`  
Gate: `scripts/skin-research/check_acne_improvement_release.py`
