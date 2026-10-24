# Acne source/person full-record coverage proposal

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

All 800 records are now represented exactly once in a privacy-safe grouping proposal. A private engineering review resolved every pair surfaced by the normalized-source-name similarity, lower name-similarity bands, full-image dHash/pHash, central-80%-crop pHash, central-80%-crop gradient pHash and six directional-crop pHash methods. The proposal preserves the resulting 32 confirmed groups and leaves every other record explicitly unreviewed rather than treating an algorithmic singleton as identity truth.

| Result | Count |
|---|---:|
| Dataset records | 800 |
| Proposal groups | 761 |
| Confirmed groups | 32 |
| Records in confirmed groups | 71 |
| Unreviewed singleton groups | 729 |
| Unreviewed records | 729 |
| Target splits assigned | 0 |

The proposal is complete as an inventory, not as reviewed person/source truth. It cannot authorize a group-locked split or training.

## All-split candidate review

The immutable export was scanned across train, validation and test with the same dHash/pHash methods used by the cross-split audit.

| Candidate evidence | Count |
|---|---:|
| Exact-content pairs | 0 |
| Usable normalized-source-name pairs | 0 |
| Normalized-source-name similarity pairs (minimum 0.94) | 33 |
| Cross-split-only name-similarity review pairs (0.90–0.94) | 54 |
| Within-split name-similarity review pairs (0.90–0.94) | 108 |
| dHash pairs | 9 |
| pHash pairs | 13 |
| Central-80%-crop pHash pairs | 10 |
| Central-80%-crop gradient pHash pairs | 13 |
| Left-80%-crop pHash pairs | 4 |
| Right-80%-crop pHash pairs | 3 |
| Top-80%-crop pHash pairs | 8 |
| Bottom-80%-crop pHash pairs | 6 |
| Left-70%-crop pHash pairs | 5 |
| Right-70%-crop pHash pairs | 4 |
| Deduplicated pairs | 227 |
| Confirmed same source/person | 41 |
| Reviewed different source/person | 186 |
| Unresolved pairs | 0 |
| Unresolved cross-split pairs | 0 |
| Unresolved within-split pairs | 0 |

All similarity remains review-only. Normalized source names are compared in memory at a general minimum sequence-similarity ratio of 0.94 and are never emitted. The lower 0.90–0.94 band has separate cross-split leakage and within-split candidate-review methods; neither is counted as full identity coverage. Private engineering review resolved all 162 lower-band pairs, confirming 17 as same-source or same-person series and rejecting 145 as false positives. The central gradient method compares low-frequency edge magnitude at Hamming distance 12; its six new pairs produced two same-person series and four false positives. Across all methods, 41 confirmed pair decisions produce 32 connected groups covering 71 records. The directional image methods use the left, right, top and bottom 80% crops plus the left and right 70% crops at Hamming distance 8. The proposal now establishes 16 cross-split groups covering 37 records; the existing test/validation arrangement is not person-independent. The absence of unresolved pairs at these thresholds does not prove that no other same-person leakage exists. The remaining 729 singleton records still lack reviewed provenance/person coverage.

## Controls and verification

- The committed proposal contains hashed record IDs, current split labels, methods and distances only.
- No image bytes, faces, filenames or raw source names are committed.
- Confirmed decisions are reused; unresolved similarity never merges records.
- Every record occurs in exactly one proposal group.
- The source-name, central-crop and directional-crop methods are deterministic, validate their configuration and remain review-only; they never merge records automatically. Both lower name-similarity methods explicitly carry `coverageEvidence=false`.
- Twenty-two focused tests pass across source grouping, full-record coverage, semantic review and split release.
- The real 800-image replay, Python compilation and privacy/exact-coverage checks pass.
- No Roboflow label, split, version, threshold, inference or training state changed.

Evidence:

- `docs/skin/evidence/acne-group-coverage-proposal-20261024-v1.json`
- `docs/skin/evidence/acne-source-group-review-decisions-20261024-v1.json`
- `docs/skin/evidence/acne-split-release-gate-20261024-v1.json`
