# Acne source/person full-record coverage proposal

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

All 800 records are now represented exactly once in a privacy-safe grouping proposal. The proposal preserves the five previously confirmed train/validation source/person groups and leaves every other record explicitly unreviewed rather than treating an algorithmic singleton as identity truth.

| Result | Count |
|---|---:|
| Dataset records | 800 |
| Proposal groups | 795 |
| Confirmed groups | 5 |
| Records in confirmed groups | 10 |
| Unreviewed singleton groups | 790 |
| Unreviewed records | 790 |
| Target splits assigned | 0 |

The proposal is complete as an inventory, not as reviewed person/source truth. It cannot authorize a group-locked split or training.

## All-split candidate review

The immutable export was scanned across train, validation and test with the same dHash/pHash methods used by the cross-split audit.

| Candidate evidence | Count |
|---|---:|
| Exact-content pairs | 0 |
| Usable normalized-source-name pairs | 0 |
| dHash pairs | 9 |
| pHash pairs | 13 |
| Deduplicated pairs | 16 |
| Confirmed same source/person | 5 |
| Reviewed different source/person | 1 |
| Unresolved pairs | 10 |
| Unresolved cross-split pairs | 0 |
| Unresolved within-split pairs | 10 |

Perceptual similarity remains review-only. The absence of additional unresolved cross-split pairs at these thresholds does not prove that no other same-person leakage exists. The ten within-split candidates are useful for expanding reviewed identity groups before constructing a replacement split.

## Controls and verification

- The committed proposal contains hashed record IDs, current split labels, methods and distances only.
- No image bytes, faces, filenames or raw source names are committed.
- Confirmed decisions are reused; unresolved similarity never merges records.
- Every record occurs in exactly one proposal group.
- Fourteen focused tests pass across source grouping, full-record coverage, semantic review and split release.
- The real 800-image replay, Python compilation and privacy/exact-coverage checks pass.
- No Roboflow label, split, version, threshold, inference or training state changed.

Evidence:

- `docs/skin/evidence/acne-group-coverage-proposal-20261024-v1.json`
- `docs/skin/evidence/acne-source-group-review-decisions-20261024-v1.json`
- `docs/skin/evidence/acne-split-release-gate-20261024-v1.json`
