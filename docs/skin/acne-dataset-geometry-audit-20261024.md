# Acne / post-acne / pigmentation dataset geometry audit

This audit used the private Roboflow version
`tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1` COCO export.
The export archive was 103,665,003 bytes with SHA-256
`29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`.
No labels, splits, images, models or thresholds were changed.

## Verified inventory

- 800 images: 553 train, 165 validation, 82 test.
- 37,342 boxes: 3,640 Pimple, 32,123 Post acne, 1,579 Pigmentation.
- No invalid or out-of-bounds boxes were found.
- No exact file SHA-256 duplicate group crossed train/validation/test.
- Source-person identity is absent, so these checks do not establish
  person-independent holdout separation.

## Geometry and balance

The audit defines a tiny instance as a box occupying less than 0.04% of its
image. This is a diagnostic boundary, not a model threshold.

| Class | Median image-area fraction | Tiny fraction | Boxes |
|---|---:|---:|---:|
| Pimple | 0.0111% | 94.23% | 3,640 |
| Post acne | 0.0084% | 94.95% | 32,123 |
| Pigmentation | 0.0115% | 94.05% | 1,579 |

Post acne has 8.825 times as many boxes as Pimple and 20.344 times as many as
Pigmentation. Validation is especially dominated by tiny instances: 95.89% of
Pimple boxes and 96.77% of Post acne boxes fall below the diagnostic boundary.

## Decision

Do not start another blind training run. The next experiment must be
validation-only and targeted:

1. expert-review class semantics and negative coverage;
2. create source/person groups before a new locked split;
3. test higher-resolution or crop-aware training against the frozen validation
   baseline;
4. improve Pimple and Pigmentation coverage without fabricating annotations.

The current learned model remains unaccepted and Post acne/Pigmentation remain
unavailable product headings. The existing nine-criterion Attune.more result
flow is unaffected.
