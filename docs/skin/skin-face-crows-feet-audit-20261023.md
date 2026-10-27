# Skin-face crows-feet source audit — 2026-10-23

The current public `elisabeth-hui/skin_face_detection` snapshot is the first
audited candidate in this roadmap with an explicit `crows_feet` class and
localized polygon supervision. It is promising source material, but its
existing splits are not eligible for model evaluation and no training was
started.

The source was forked once into the private project
`tolgar-sasmaz/skin_face_detection-emora`. Version 1 was generated with no
preprocessing and no augmentation so the audit would preserve the available
geometry. The resulting 2,811-image COCO archive is pinned by SHA-256
`1271091931876b3fce1a6bc22865cc7ce112c93042bba589be0412d05070b163`.
This snapshot is not treated as identical to the prior 6,749-image augmented
archive recorded in the source ledger.

## What the source supports

- 875 `crows_feet` annotations occur on 166 images: 606/206/63 annotations
  and 119/34/13 positive images in train/validation/test.
- 855 annotations are valid polygons. The median polygon covers 0.0225% of
  the image and the maximum covers 0.237%, so these are localized line masks,
  unlike the broad FACE v3 regions rejected earlier.
- A deterministic twelve-image engineering review found lateral-eye masks in
  every reviewed example. It also exposed glasses/occlusion cases and one
  semantically questionable child/dynamic-expression example.

## Why training is still blocked

- Twenty `crows_feet` polygons on fifteen images are invalid: nineteen
  self-intersect and one is invalid or outside the frame.
- Across the whole project there are three exact cross-split duplicate groups,
  31 cross-split filename candidate groups and 83 cross-split perceptual
  candidate pairs. For crows-feet-positive images specifically, two filename
  groups spanning train and validation were visually confirmed as the same
  source photos with different transforms and annotation counts.
- The source does not prove that images without `crows_feet` were evaluated as
  true negatives. Missing class labels must not be converted into negative
  skin truth.
- Expression, pose, age, lighting, independent-camera performance, expert
  semantics and individual-photo rights remain unaccepted.

Next, derive source-photo groups, quarantine invalid polygons and confirm the
negative-label policy before creating a replacement split. Only then may a
research training run be considered; the current test split must not be used
as a locked holdout.
