# Acne candidate verifier v3 — reviewed-only TRAIN labels, one refit, single DEV comparison (2026-10-16)

Research staging only; product acne stays `accepted:false, file:null`. v1 (default) and v2 (fewer false points / fewer catches
trade-off) are unchanged, with all their files. Review level: AI engineering review on crops, not expert verification. Rights status
of Step0 weights and data sources is tracked separately and is not resolved by this training.

## Label completion (fixed before review: commit d3c1d38; decisions: be33c0e)
- Still unreviewed after v2: exactly the 373 v1 positives not in the v2 list (72 photos; FRONT 368, LEFT 4, RIGHT 1). All were
  reviewed (no sampling); v2's 300 decisions were not redone.
- v3 review (blind sheets, each decision with a written reason): acne-like 233, uncertain 133, other 4, mole/mark 2, flat 1.
  Uncertain mostly = marker on plain skin beside a lesion (offset), faint spots, pale dots on dark skin.
- Conflicts (same location, centres within r, one acne-like and one not-acne): 3 pairs, 6 candidates; all excluded and listed
  in `docs/acne-verifier-v3-conflicts-20261016.json`, not forced into a class.

## Training data (reviewed only; no automatic v1 label)
423 labelled samples on 115 photos: 284 acne-like, negatives flat 56, mole/mark 44, pore/shine 17, other 22.
Excluded: 244 uncertain, 6 conflicts, 1868 never-reviewed candidates.

| split | positives (photos) | flat | mole/mark | pore/shine | other |
|---|---|---|---|---|---|
| learn | 182 (55) | 38 (31) | 32 (20) | 10 (9) | 14 (13) |
| calibration | 102 (26) | 18 (13) | 12 (8) | 7 (6) | 8 (7) |

No category has fewer than 2 photos in either split, but pore/shine and other remain small (< 10 calibration samples).
TRAIN distribution: 158 photos, FRONT 141 / LEFT 10 / RIGHT 7; face width 200–1422 px (median 725). Used samples: FRONT 405,
LEFT 10, RIGHT 8; face-width tertiles 117 / 184 / 122. Side-pose coverage stays thin.

## Fit and calibration (commit 7e83768, frozen before DEV)
Same features, L2 LR C = 0.1 balanced, standardiser on learn, one fit. Learn AUC 1.00 (not a success criterion).
Calibration AUC 0.861; threshold 0.0444 keeps 95.1% of positives; removes 22/45 negatives (49%, 95% CI 35–63%).

| calibration negatives | n (photos) | removed | 95% CI | AUC vs positives |
|---|---|---|---|---|
| flat skin | 18 (13) | 10 (56%) | 34–75% | 0.88 |
| mole / mark | 12 (8) | 6 (50%) | 25–75% | 0.89 |
| pore / shine | 7 (6) | 3 (43%) | 16–75% | 0.86 |
| other | 8 (7) | 3 (38%) | 14–69% | 0.77 |

Gate (AUC ≥ .65, ≥ 15% removed) passed. Intervals are wide; calibration sets per type are small.

## DEV, measured once (same 108 targets, layer 1, masks, r = 0.03 × face width, one-to-one matching)
| | Step0 + old filter | v1 | v2 | v3 |
|---|---|---|---|---|
| targets found (of 108) | 71 | 70 | 68 | 68 |
| points | 305 | 265 | 253 | 236 |
| false (reviewed skin) | 96 | 78 | 69 | 60 |
| duplicate | 48 | 42 | 38 | 36 |
| on uncertain | 75 | 64 | 65 | 58 |
| on other category | 9 | 8 | 7 | 9 |
| non-skin | 1 | 1 | 1 | 1 |

- v3 vs v1: lost 77176e51db41#P15, 8a78e9d6efd5#P21, a2cd98ca9566#P2; regained 0a8a14a662a5#P26. Same target set as v2.
- False points v3 − v1 = −18 (paired photo bootstrap 95% CI −31 … −7); targets −2 (CI −6 … +2). v3 − Step0 false −36 (CI −64 … −16).
- 19 of 28 photos differ from v1; largest false-point drops: 46a79ef8d7a8 8 → 3, a19346a0887a 6 → 3, c412587e8b7f 4 → 2, 33e42c603f10 5 → 3.
  8a78e9d6efd5: 10 → 11 false (re-matching) and one target lost.
- Removed by v3 (class under Step0): false 36, uncertain 17, duplicate 9, matched 6, unreviewed photo 1. DEV Clear: 0 points under Step0.

**Decision (same rule):** v3 would replace v1 only with ≥ 70 targets and < 78 false points. 68 < 70, so **v1 stays the default**.
v3 gives the strongest false-point reduction of the three at the cost of the same 2 net targets as v2. This rule is not a product
acceptance or independent proof. No threshold change or retraining after DEV.

## Runtime
`scripts/skin-research/acne_verifier_photo.py --out DIR --version v1|v2|v3 [--replay FILE.jsonl] -- PHOTO…`; default remains v1.
- v3 with stored replay rows: 42/42 DEV photos identical to the frozen v3 DEV run. From raw photo (local MediaPipe + node replay): 3/3 identical.
- Step0 parameter digest checked unchanged on every run; `tests/unit/test_acne_candidate_verifier.py` 11 passed.
