# Regional evidence checkpoint — 23 October 2026

The normal skin API finalizer now emits `general.regionalSkinMap`, a semantic
anatomical-region summary. It does not create pixel masks or claim that the UI
already renders the new colour system. Frontend rendering, model acceptance,
camera validation and longitudinal compatibility remain open roadmap work.

## Decision correction

The previous v2 rule treated any nonzero oil support as oily and measured-zero
oil/flake support as normal. Its documentation already acknowledged that tiny
unvalidated supports could produce combination. That is insufficient evidence
for the accepted regional map and combination contract.

`combination-regional-user-v3-accepted-evidence` preserves the raw three-class
prediction and uses the server-owned regional method registry instead. The
registry is currently empty. Thus raw legacy proxies cannot create normal
regions or a combination override; unknown regions are light grey, and the
global classifier remains separate. Historical stored records are not rewritten.

An accepted future method must pin its method, normalization and optional model
hash, validation evidence, positive/negative thresholds, minimum coverage and
pixel support. Request content cannot populate the registry. Synthetic fixture
policies in tests exercise the contract only; none are installed or fitted as
product calibration.

- T-zone: forehead, nose **and chin**, each independently supported. The legacy
  forehead-union-nose ROI cannot stand in for separate anatomical observations.
- Outside T-zone: both cheeks must be supported normal or dry. An unknown cheek
  never counts as normal. Normal needs accepted negative oil **and** dry evidence.
- Dry is blue, oily green, normal uncoloured, unknown light grey. Conflicting
  coarse oil/dry aggregates remain unknown pending local spatial support.
- Redness is an independent red contour/hatching descriptor, including on a dry
  or oily region. Missing redness evidence means unknown redness. No sensitivity
  label or synthetic confidence is produced.
- Re-finalization is idempotent, consumes final native measurements and retracts
  a derived combination when support is lost. Model inference and privacy/consent
  boundaries are unchanged. No production merge or deployment occurred.

## Source preparation findings

The directly exported Clean3 version 1 contains **3,240 COCO image records**;
the version API lists 3,261. This discrepancy is recorded, not explained by
guessing. The source URL and immutable archive hash are in the source summary.

| Target | Box-only annotations | Genuine valid polygons | Polygon splits |
|---|---:|---:|---|
| Oily-Skin | 889 | 10 | train 6 / valid 0 / test 4 |
| Dry-Skin | 2,117 | 6 | train 3 / valid 2 / test 1 |
| Skin-Redness | 123 | 0 | none |

The archive has 15 exact byte/pixel duplicate groups, 9 crossing existing splits;
229 cross-split perceptual candidate pairs and 56 filename candidate groups
require review. Perceptual/filename relations are not asserted person identities
or confirmed duplicates. There are 37 geometry issues, primarily wrinkle
polygons; all are retained in the source summary. No source labels, files or
remote splits were changed. No regional model was trained from these boxes.

The frozen acne Roboflow version was also exported and compared with the
original three-class upload: **800 unique name/dimension/full-geometry pairs,
all splits unchanged**, with no preprocessing or augmentation. Three files have
identical encoded bytes and 16 have identical decoded RGB pixels; maximum
per-image mean absolute RGB channel error is 0.351692/255. Exact photo identity
is therefore not asserted for all files. Re-encoding can change duplicate
heuristics, so the original source quarantine remains authoritative. The test
set remains provisional; these checks do not establish subject independence.

## Evidence and next work

- `evidence/clean3-source-summary-20261023-v1.json`: actual geometry, class/split
  counts, issues, exact cross-split groups, source hashes and reproducible command.
- `evidence/acne-remote-summary-20261023-v1.json`: remote export comparison,
  geometry summary, source hashes and reproduction command.
- `evidence/nas-frontier-20261023-v1.json`: bounded group-scoped snapshot only;
  a live run can add children, so it is not a final winner selection.
- `evidence/regional-checks-20261023-v1.json`: executable checks and code hashes.

Next: finish NAS child enumeration and per-class evaluation when available;
resolve source duplicate/exposure candidates; audit the selected v11 regional
source and prepare reviewed normal/negative coverage. Then validate/calibrate
regional methods before enabling them, and integrate the map into the UI. The
entire roadmap is still in progress, including independent real-camera testing.
