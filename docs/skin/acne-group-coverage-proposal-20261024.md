# Acne source/person full-record coverage proposal

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

All 800 records are now represented exactly once in a privacy-safe grouping proposal. A private engineering review resolved every pair surfaced by the full-image dHash/pHash and central-80%-crop pHash thresholds. The proposal preserves the resulting 13 confirmed groups and leaves every other record explicitly unreviewed rather than treating an algorithmic singleton as identity truth.

| Result | Count |
|---|---:|
| Dataset records | 800 |
| Proposal groups | 786 |
| Confirmed groups | 13 |
| Records in confirmed groups | 27 |
| Unreviewed singleton groups | 773 |
| Unreviewed records | 773 |
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
| Central-80%-crop pHash pairs | 10 |
| Deduplicated pairs | 19 |
| Confirmed same source/person | 14 |
| Reviewed different source/person | 5 |
| Unresolved pairs | 0 |
| Unresolved cross-split pairs | 0 |
| Unresolved within-split pairs | 0 |

Perceptual similarity remains review-only. The first review pass resolved ten whole-image pairs; the central-crop method then surfaced three new pairs plus an already reviewed false-positive pair through an additional method. Of the three new pairs, two were confirmed as same-person series and one cross-split pair was rejected as a false positive. The absence of unresolved cross-split pairs at these thresholds does not prove that no other same-person leakage exists. The remaining 773 singleton records still lack reviewed provenance/person coverage.

## Controls and verification

- The committed proposal contains hashed record IDs, current split labels, methods and distances only.
- No image bytes, faces, filenames or raw source names are committed.
- Confirmed decisions are reused; unresolved similarity never merges records.
- Every record occurs in exactly one proposal group.
- The central-crop method is deterministic, validates its crop range and remains review-only; it never merges records automatically.
- Seventeen focused tests pass across source grouping, full-record coverage, semantic review and split release.
- The real 800-image replay, Python compilation and privacy/exact-coverage checks pass.
- No Roboflow label, split, version, threshold, inference or training state changed.

Evidence:

- `docs/skin/evidence/acne-group-coverage-proposal-20261024-v1.json`
- `docs/skin/evidence/acne-source-group-review-decisions-20261024-v1.json`
- `docs/skin/evidence/acne-split-release-gate-20261024-v1.json`
