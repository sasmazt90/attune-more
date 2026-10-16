# Acne candidate verifier — TRAIN calibration and single DEV measurement (2026-10-16)

Research staging only. Not connected to the product; acne stays `accepted:false, file:null`. No camera code changed.
Review level: AI engineering review of existing manifest labels, not expert verification. Licence status of Step0 and
data sources is unchanged by this work and is tracked separately; no "commercially clean" claim is made.

## What was built
- Second stage on the fixed Step0 chain (YOLOX-S P2, weights sha 18e94a95…, product crop, 384/288 tiles, conf .30, NMS .30,
  product masks, unchanged old box filter). Point filter not used.
- Features: frozen PAFPN outputs of the same tile forward pass (strides 4/8/16/32), bilinear centre + ±2-cell mean, 1920 dims.
- Classifier: one L2 logistic regression (C = 0.1, balanced, lbfgs) on z-scored features. One fit. Protocol fixed first (140895a).
- Frozen before DEV in commit dcc8e8c: model `docs/acne-verifier-model-20261016.json` (sha b6fa6c05…), calibration record
  `docs/acne-verifier-calibration-20261016.json`.

## TRAIN (manifest-v6, 158 photos with a replay row)
| | |
|---|---|
| Step0 final candidates | 2541 |
| positive (within r of a kept box centre) | 433 |
| negative (inside a kept confounder box) | 65 (Mole 46, Pigmentation 10, Freckles 5, Enlarged pores 4 box hits) |
| negative (inside reviewed clean ROI) | 6 |
| excluded (near/inside kept or ignore box) | 828 |
| excluded (unlabelled area) | 1209 |
| near-duplicates of DEV / DEV Clear (dHash ≤ 10) | 0 |
| near-duplicate groups inside TRAIN | 2 (kept in one split) |

Split by photo group (seed 20261016): learn 71 groups / 323 samples (277 pos), calibration 30 groups / 181 samples (156 pos, 25 neg).
Learn AUC 1.00 (1920 dims, 323 samples: overfit expected). Calibration AUC 0.918. Threshold 0.0766 (keeps 95.5% of calibration
positives) removes 14/25 = 56% of calibration negatives. Pre-registered gate (AUC ≥ .65 and ≥ 15% negatives removed) passed.

Caveat recorded before DEV: all 25 calibration negatives are confounder-box candidates (mostly moles); the 6 clean-ROI negatives
are all in learn; the 10 negative photos gave 0 candidates after the box filter. Calibration therefore does not directly measure
flat-skin false points. Person independence is not verified (groups are photos / near-duplicate clusters).

## DEV, measured once (same 108 targets, same layer 1, same r = 0.03 × face width, same one-to-one matching)
| | A: Step0 + old filter | B: A + verifier | B − A |
|---|---|---|---|
| targets found (of 108) | 71 | 70 | −1 (P26 on 0a8a14a662a5) |
| points | 305 | 265 | −40 |
| false (reviewed skin) | 96 | 78 | −18 (paired photo bootstrap 95% CI −35 … −5) |
| duplicate | 48 | 42 | −6 |
| on uncertain | 75 | 64 | −11 |
| on other category | 9 | 8 | −1 |
| non-skin | 1 | 1 | 0 |
| unreviewed photo | 5 | 2 | −3 |
| DEV Clear (14 photos) points | 0 | 0 | 0 |

Targets by set: dev 60 → 60, devext 11 → 10. Targets found CI (paired bootstrap) −3 … 0. No target gained (cannot by design).

The 40 removed points, by their class under A: false 18, uncertain 11, duplicate 4, matched 3 (one target lost; the other two
targets stayed matched through another point), other category 1, unreviewed photo 3.
14 of 28 photos changed. Largest changes: 46a79ef8d7a8 false 15 → 8; 8a78e9d6efd5 13 → 10; 77176e51db41 4 → 2; c412587e8b7f 6 → 4.

Limitation seen on DEV: on the side-angle photo 0a8a14a662a5 the verifier gave probability ≈ 0 to 5 of 20 points (1 target,
4 duplicates) — features far outside the TRAIN range. No recalibration was done after DEV.

## Cost (local CPU, 2 threads)
Chain per photo median 2.3 s (max 17.5 s under device load). Feature sampling ≤ 0.02 s, classifier ≤ 0.007 s per photo.
Extra memory: PAFPN maps kept for all tiles until the box filter finishes, median 33 MB, max 248 MB (many tiles); process peak RSS 759 MiB.

## Runtime parity
- Offline command `scripts/skin-research/acne_verifier_photo.py --out DIR PHOTO… [--replay FILE.jsonl]`:
  42/42 DEV photos with stored replay rows give the same A boxes, keep flags and probabilities as the frozen DEV run.
- The same command from the raw photo (local MediaPipe face_landmarker.task + node frontend replay, no stored row) gave identical
  A boxes and keep flags on 3/3 checked DEV photos.
- `tests/unit/test_acne_candidate_verifier.py`: 6 passed (sampling geometry, 1920 dims, formula, model and Step0 weight hashes,
  TRAIN/DEV duplicate leakage and split separation, TRAIN cached-vs-runtime feature parity with Step0 parameter digest unchanged).
- Legend before/after images: `audit-results/acne-verifier/photo-dev/*-before-after.jpg` (local only, not in Git).
