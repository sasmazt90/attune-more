# Acne / post-acne / pigmentation semantic review queue

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

A deterministic, privacy-safe expert review queue now covers the concrete semantic and hard-negative questions blocking tasks 01–03. It selects 81 review items from the 718 train/validation images. All 82 locked test images remain excluded.

| Class | Tiny positive | Large positive | Isolated positive | Co-occurrence positive | Other-class hard negative | Unlabelled negative | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pimple | 6 | 3 | 3 | 4 | 8 | 4 | 28 |
| Post acne | 6 | 3 | 3 | 4 | 8 | 4 | 28 |
| Pigmentation | 6 | 3 | 0 | 4 | 8 | 4 | 25 |
| **Total** | **18** | **9** | **6** | **12** | **24** | **12** | **81** |

No train/validation image contains Pigmentation as the only annotated target class, so the isolated-positive stratum is empty for Pigmentation. This is a source-coverage finding, not proof that Pigmentation labels are incorrect.

## Review contract

For each class, an expert receipt must lock:

1. the visible positive definition;
2. the hard-negative policy against the other two target classes;
3. the ambiguous-case policy;
4. the reviewed queue item IDs.

The blank receipt is bound to both the immutable archive SHA-256 and the canonical queue SHA-256. Engineering review alone cannot complete it. The replacement-split gate requires `reviewer: expert_review`, non-empty reviewed-item IDs and all four class conditions before marking a class complete.

## Privacy and controls

- Committed artifacts contain hashed record IDs, present-class names and aggregate target area fractions only.
- No image bytes, faces, filenames, raw source names or bounding-box coordinates are committed.
- A private hash-to-filename resolver was generated locally only and is deliberately excluded from Git.
- Test images are inventoried but never selected.
- Eleven focused tests pass across source grouping, split release and semantic queue generation.
- No Roboflow label, split, version, threshold, inference or training state changed.

Evidence:

- `docs/skin/evidence/acne-semantic-review-queue-20261024-v1.json`
- `docs/skin/evidence/acne-semantic-negative-review-20261024-v1.json`
- `docs/skin/evidence/acne-split-release-gate-20261024-v1.json`
