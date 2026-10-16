# Acne candidate verifier v2 — TRAIN label review, flat-skin negatives, one refit, single DEV measurement (2026-10-16)

Research staging only; not connected to the product (acne stays `accepted:false, file:null`). v1 (model b6fa6c05…, its
calibration, labels and DEV results) is unchanged. Review level: AI engineering review on crops, not expert verification.
Rights status of Step0 weights and data sources is unchanged by this training and tracked separately.

## Pre-registration (before any review) — commit e96a9b7
Protocol `docs/acne-verifier-v2-protocol-20261016.json`, list `docs/acne-verifier-v2-review-list-20261016.json`.
TRAIN only (158 photos, cached Step0 candidates and frozen features). DEV, DEV Clear, the 108-target scope and the sealed test
were not used. Budget 300: 60 controls from v1 positives, all 71 v1 negatives, 169 from the 1209 "unlabelled area" candidates;
strata pose × face-width tertile, per-photo caps, sha256 ordering (seed 20261016). Review sheets were blind (id + three crops only).

TRAIN distribution: FRONT 141, LEFT 10, RIGHT 7 photos; face width 200–1422 px (median 725; tertile edges 588 / 899 px).
Selected 300 candidates on 128 photos: FRONT 271, LEFT 18, RIGHT 11; face-width tertiles 99 / 117 / 84.

## Review (commit 90b2949, decisions written before any fit)
| pool | A acne-like | F flat skin | M mole/mark | P pore/shine | O other | U uncertain |
|---|---|---|---|---|---|---|
| v1 positives (60) | 40 | 1 | 0 | 1 | 0 | 18 |
| v1 negatives (71) | 8 | 8 | 35 | 0 | 0 | 20 |
| unlabelled area (169) | 6 | 47 | 7 | 17 | 19 | 73 |
| total | 54 | 56 | 42 | 18 | 19 | 111 |

- v1 positive controls: 40/60 confirmed (67%, 95% CI 54–77%); 2 contradicted, 18 uncertain. The 373 unreviewed v1 positives
  were kept as positives (protocol), so the positive class still carries this noise.
- 8 of the 71 v1 negatives (confounder boxes) looked acne-like on review.
- Flat-skin negatives: 56 on 44 photos, FRONT 54 / RIGHT 2 / LEFT 0, face-width tertiles 18 / 22 / 16. No more were sought.

## Labels v2, split, fit (commit 2a87019)
Labelled 562: positives 427 (54 review, 373 unreviewed v1), negatives flat 56, mole-mark 42, pore-shine 18, other 19; 111 uncertain excluded.
Protocol split: flat negatives on 31 photos in learn and 13 in calibration. Learn 361 (269 pos) / calibration 201 (158 pos, 43 neg), 82 / 35 groups.
One L2 LR (C = 0.1, balanced), standardiser on learn. Learn AUC 1.00 (overfit, as in v1). Calibration AUC 0.770. Threshold 0.0710 keeps 95.6% of positives.

| calibration negatives | n (photos) | removed at threshold | 95% CI | AUC vs positives |
|---|---|---|---|---|
| flat skin | 18 (13) | 8 (44%) | 25–66% | 0.77 |
| mole / mark | 11 (7) | 5 (45%) | 21–72% | 0.88 |
| pore / shine | 8 (7) | 2 (25%) | 7–59% | 0.66 |
| other | 6 (6) | 2 (33%) | 10–70% | 0.73 |
| all | 43 | 17 (40%) | 26–54% | 0.77 |

The v1-style gate (AUC ≥ .65, ≥ 15% removed) passed. Flat-skin separation is moderate: about half of the flat-skin false candidates are
removed at the 95% positive-keep point, with wide intervals (18 samples). v1's calibration (AUC .92, 56% removed) was on 25 mostly-mole
negatives and is not comparable.

## DEV, measured once (same 108 targets, layer 1, masks, r = 0.03 × face width, one-to-one matching)
| | A: Step0 + old filter | B: + v1 | C: + v2 |
|---|---|---|---|
| targets found (of 108) | 71 | 70 | 68 |
| points | 305 | 265 | 253 |
| false (reviewed skin) | 96 | 78 | 69 |
| duplicate | 48 | 42 | 38 |
| on uncertain | 75 | 64 | 65 |
| on other category | 9 | 8 | 7 |
| non-skin | 1 | 1 | 1 |
| unreviewed photo | 5 | 2 | 5 |

- C vs A: lost 77176e51db41#P15, 8a78e9d6efd5#P21, a2cd98ca9566#P2; gained none (cannot by design).
- C vs B: lost the same three; regained 0a8a14a662a5#P26 (v1's lost target; no special rule for that photo).
- False points C − B = −9 (paired photo bootstrap 95% CI −17 … −2); targets C − B = −2 (CI −6 … +2). C − A false −27 (CI −48 … −11).
- Removed by v2 (class under A): false 27, duplicate 8, uncertain 10, matched 5, other 2. 23 of v2's 52 removals were also removed by v1.
- DEV Clear: 0 points under A, so unaffected. dev set targets 60/60/57, devext 11/10/11.

**Decision (pre-registered):** v2 replaces v1 only if it finds ≥ the targets of v1 and has fewer false points. 68 < 70, so the rule
is not met: **v1 stays the preferred staging verifier**. v2 is kept as a recorded alternative. No retraining or recalibration after DEV.

## Runtime
`scripts/skin-research/acne_verifier_photo.py --out DIR --version v1|v2 [--replay FILE.jsonl] -- PHOTO…` (v1 default).
- v2, stored replay rows: 42/42 DEV photos identical to the frozen v2 DEV run (boxes, keep flags, probabilities).
- v2 from raw photo (local MediaPipe + node replay): 3/3 identical. v1 behaviour unchanged (tests).
- `tests/unit/test_acne_candidate_verifier.py`: 9 passed (adds v2 hash, TRAIN-only labels and split separation, v2 command parity).
- Same features as v1, so time and memory are unchanged (classifier < 0.01 s per photo).
