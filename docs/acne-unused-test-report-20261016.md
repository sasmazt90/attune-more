# Frozen v1 vs v3 on never-used photos — single comparison (2026-10-16)

Research only. No training, calibration or threshold change; product acne stays `accepted:false, file:null`; the photo command default
stays v1. Review level: AI engineering review, not expert verification, not fully blind, no clinical truth. Licence and source rights
are NOT resolved by this test (publisher-declared licences, no individual consent records).

## Frozen before any output
| item | sha256 |
|---|---|
| v1 verifier (standardiser + LR + threshold) | b6fa6c05b48a092623f7780200c07440ebaf934989ab66518ee21b23fa304f8a |
| v3 verifier | 94d18abb951c49847371f03513957681fd50392e0ebfb51c233a1db65492ab67 |
| Step0 weights | 18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655 |
| feature / chain / filter / landmark code | docs/acne-unused-test-freeze-20261016.json |
| labels + mask hashes | docs/acne-unused-test-labels-20261016.json (a0235f53…) |
Commits in order: 2bf0606 (freeze, protocol, scope) → bc9b101 (preflight, evaluation list) → 2c32337 (labels/masks) → inference.

## Unused-photo scope (sealed Skin care v5 test, opened only for this comparison)
- 903 sealed rows. Excluded 643 with recorded reasons: 289 already inferred by Step0 on 2026-10-15 (so that part of the "sealed"
  test was not unused), 288 dHash/flip ≤ 10 to rows of the other 14 local archives (crop / resize / augmented copies), 56 research-group
  links, 10 shared Roboflow families. ORB/RANSAC copy search against 2,362 research photos and the excluded rows: 0 copies ≥ 25 inliers;
  1 photo with 24 inliers excluded as suspected copy before any output. Kept 259 photos in 124 near-duplicate groups.
- Unchanged product preflight (local MediaPipe + frontend replay): only 23 photos replay-pass; 236 fail (POSE 82, BLURRY+POSE 76,
  no face 46, BLURRY 21, head frame 10, other 1) — listed, not counted as success. One photo per group → **17 evaluated photos**
  (16 FRONT, 1 LEFT; face width 292–568 px, all in the lowest TRAIN face-width tertile).
- Person identity unknown; visual check found 3 pairs that are the same person in different images (used as clusters). Step0's original
  pre-training data is unknown, so overlap with it cannot be ruled out.

## Labels (frozen before inference)
Full-face review with the DEV layer-1 rule. **0 TARGET** on all 17 photos (8 UNCERTAIN, 4 MOLE, 2 SCAR_PIGMENT, 3 OTHER). The eligible
unused photos are clear, aged or rosacea-like faces. Target recall and target loss therefore **cannot be measured** on this set.

## Result (one inference, same candidates and features for v1 and v3; DEV counting rules)
| | Step0 + old filter | v1 | v3 |
|---|---|---|---|
| photos / targets | 17 / 0 | 17 / 0 | 17 / 0 |
| distinct targets found | — | — | — |
| points | 9 | 7 | 4 |
| false points on reviewed skin | 5 | 4 | 2 |
| false per photo, mean / median | 0.29 / 0 | 0.24 / 0 | 0.12 / 0 |
| on uncertain / on other category | 1 / 3 | 0 / 3 | 0 / 2 |
| duplicate / non-skin | 0 / 0 | 0 / 0 | 0 / 0 |

- v3 − v1: false points −2 (photo bootstrap 95% CI −5 … 0; person-cluster CI the same), points −3 (CI −8 … 0); targets gained / lost: none (no targets exist).
- Only 5 of 17 photos had any Step0 candidate; 12 had none (kept in the denominator). v3 removed 5 Step0 points (3 false, 1 uncertain,
  1 other); v1 removed 2 (1 false, 1 uncertain); every point v1 removed, v3 also removed.
- Subgroups: FRONT 16 photos (false 4 / 3 / 1); side 1 photo (1 / 1 / 1); face-width tertiles 1–2: 0 photos. All denominators are tiny.
- Cost (same CPU, 2 threads): chain median 1.31 s (max 1.99 s) per photo; v1 ≤ 0.6 ms, v3 ≤ 0.2 ms; feature maps ≤ 17.7 MB; peak RSS 398 MiB.

## What this supports
- On never-used, product-eligible, mostly clear frontal faces, v3 produced fewer false points than v1 (2 vs 4 of 5 Step0 false points),
  consistent in direction with DEV. The interval reaches 0, the counts are very small, and this is not proof of a difference or of equivalence.
- It says **nothing** about the DEV trade-off "fewer catches": with 0 targets, no target can be lost. Catch rate on unused acne photos
  remains unmeasured; the sealed archive's acne-bearing part was already inferred earlier or fails the product preflight.
- No DEV numbers are pooled with this set and no new acceptance threshold is proposed.

Legend images (local only, not in Git): audit-results/acne-unused-test/figures/*-step0-v1-v3.jpg (all 5 photos with candidates).
