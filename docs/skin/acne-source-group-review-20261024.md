# Acne / post-acne / pigmentation source-group review

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

The existing 553/165/82 train/validation/test split is not source/person-independent. A privacy-safe replay using two independent perceptual methods found five distinct cross-split source/person groups after engineering visual review:

- one source photo/person appears in both train and validation with a crop/encoding change;
- another source photo/person appears in both train and validation with crop and watermark changes.
- three additional people appear in both train and validation in different poses from the same photo series.

This is source-identity review only. It is not expert lesion-label review and does not validate any class semantics. The images, filenames and raw source names are not committed.

The result materially changes the next action: do not retrain or report the current test metrics as person-independent generalization. First reconstruct reviewed source/person groups, then create a new group-locked split. Keep the current test split untouched for the already completed diagnostic record; it must not be used to tune the replacement split or thresholds.

## Method and controls

`scripts/skin-research/build_acne_source_group_review.py` reads the immutable COCO export and creates review candidates from:

1. exact file SHA-256 matches;
2. normalized source-name tokens;
3. 9x8 grayscale difference hashes with Hamming distance at most 8.
4. 32x32 grayscale DCT perceptual hashes using the 8x8 low-frequency block, with Hamming distance at most 10.

All non-exact matches are candidates only. A review decision must bind to the deterministic candidate ID. Unknown decisions fail closed. The committed evidence contains only hashed record IDs and aggregates.

The evidence also emits a deduplicated five-group regrouping plan. Each group contains hashed member IDs and the rule `assign_all_members_to_one_split`; no target split is assigned yet. This makes the confirmed repair actionable without pretending that the remaining 790 images have complete person/source identity.

| Check | Result |
|---|---:|
| Images | 800 |
| Exact-content cross-split groups | 0 |
| Normalized-name candidates | 2 |
| Perceptual candidates | 3 |
| DCT perceptual candidates | 5 |
| Reviewed same-source/person candidate decisions | 7 |
| Distinct confirmed cross-split source/person groups | 5 |
| Reviewed different-source groups | 1 |
| Unresolved usable candidates | 0 |
| Person/source coverage complete | No |
| Split independence established | No |
| Split independence violated | Yes |
| Training authorized | No |
| Replacement target splits assigned | No |

Two confirmed pairs were found by both perceptual methods and are counted once. The two normalized-name candidates are weak/degenerate short keys and remain unresolved; they are not treated as leakage or independence evidence.

## Verification

- Three focused unit tests pass.
- The script compiles under Python 3.
- The actual 800-image export replay reproduces the privacy-safe evidence.
- No label, split, model, threshold, upload, inference or training state was changed.

Evidence:

- `docs/skin/evidence/acne-source-group-review-20261024-v1.json`
- `docs/skin/evidence/acne-source-group-review-decisions-20261024-v1.json`

