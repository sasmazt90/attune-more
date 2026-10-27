# Under-eye source-photo grouping checkpoint — 2026-10-23

The private `DC EB 2` source remains unchanged: 399 images and 869 valid
non-rectangular polygons (`darkcircle` 382, `eyebag` 487). This checkpoint
prepares a research-only split-safe export without changing image bytes,
polygon geometry, labels or category names.

## What was reviewed

Eight explicit `<numeric-source-id>_left` / `_right` pairs were inspected. All
eight are visually consistent with complementary crops from the same source
photo; this is a source-photo relation, not a person-identity or clinical-label
claim. Three pairs crossed the publisher's train/validation/test boundaries:

- `10617538`: train + validation
- `24300353`: train + validation
- `34786791`: validation + test

The four non-train members of those pairs were assigned to train in the derived
export, producing 283 train / 78 validation / 38 test images. The eight pair
groups are now split-safe. Eighty-six one-sided explicitly named crops remain
singletons and are not invented into pairs.

Two cross-split dHash candidates were inspected and are visibly different
people/source photos. A broader short-numeric-stem experiment produced 21
cross-split groups, many pairing visibly unrelated people. Both automatic rules
were therefore rejected; they do not alter the split. The post-build audit has
zero exact duplicates, zero cross-split explicit filename-pair groups and zero
geometry issues. One cross-split dHash candidate remains intentionally because
visual review rejected it as a same-photo match.

## Reproducibility and acceptance boundary

`prepare_under_eye_group_split.py` regenerates the derived COCO ZIP from the
source archive and refuses to overwrite an existing output. The source archive
SHA-256 is `3c5f800e2460c6388a3a2755050484b82d619052bedbc6eef153641d8d647b6d`;
the verified derived ZIP SHA-256 is
`41985daef4e2ba6336be5b67ada1c0001cd188a930df6ce29ef67cdf2999fbc8`.
The derived archive is not committed because it contains facial images; the
code and metadata-only receipt are committed, while the original private
Roboflow project remains the durable image source.

Fourteen focused archive/grouping tests pass. This authorizes a research-only
segmentation version/training from the derived split when a private bulk import
path is available. It does not establish person-independent splits, consent or
per-photo rights; it is not expert semantic review, an independent Attune
camera benchmark, model acceptance, or product integration.

Evidence: `docs/skin/evidence/under-eye-group-split-20261023-v1.json`.
