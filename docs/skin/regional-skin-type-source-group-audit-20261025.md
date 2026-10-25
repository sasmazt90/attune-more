# Regional skin-type source-group audit

## Scope

The actual COCO export for `tolgar-sasmaz/attune-skin-type-regional-r1` version 2 was checked for cross-split source/person leakage without persisting raw file names, source names or images. This audit is independent of the earlier geometry audit and does not convert detection boxes into regional masks.

## Result

- 1,711 generated images represent 990 filename-bound source IDs.
- Filename-bound source IDs do not directly cross train, validation and test.
- Cross-split pixel/perceptual review produced four candidates. All four were privately reviewed from the exact representative images.
- Three candidates are the same source/person and connect four nominal source IDs into one train/test group.
- One candidate is a false-positive visual match.
- Therefore the existing test split is not source/person independent. The confirmed leakage group contains four nominal source IDs.
- The remaining 986 source IDs do not have complete reviewed person identity coverage. A lack of additional hash candidates is not proof that they are distinct people.

## Acceptance decision

The version remains research-only. Training and final-test acceptance are unauthorized because:

1. a confirmed source/person group crosses train and test;
2. complete person identity coverage is missing;
3. all target annotations are boxes, not regional polygons;
4. evaluated normal truth is absent;
5. expert label protocol, rights review and real-camera acceptance are incomplete; and
6. the prior model evaluation already exposed the test split during threshold interpretation.

The correct next data action is a rights-reviewed, expert-labelled regional polygon set for normal/dry/oily with person-grouped train/validation/locked-test assignment. The existing version must not be silently rebalanced and reused as an untouched final test.

## Reproduction

Run:

```bash
python scripts/skin-research/audit_regional_skin_type_source_groups.py \
  <private-export-root> \
  --archive-sha256 4af7732298a0f54c3e1bd4aa68ca954429c39a19a832331a4ce542ae365fa228 \
  --salt attune-regional-skin-type-r1-v2-20261025 \
  --output docs/skin/evidence/regional-skin-type-source-group-audit-20261025-v1.json \
  --private-resolver <private-resolver-path>

python scripts/skin-research/resolve_regional_skin_type_source_groups.py \
  docs/skin/evidence/regional-skin-type-source-group-audit-20261025-v1.json \
  docs/skin/evidence/regional-skin-type-source-group-decisions-20261025-v1.json \
  --output docs/skin/evidence/regional-skin-type-source-group-resolution-20261025-v1.json
```

The private resolver and source images are deliberately excluded from Git.
