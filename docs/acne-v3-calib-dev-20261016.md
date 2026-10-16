# Acne v3: development comparison of the TRAIN-chosen confidence thresholds (2026-10-16)

This is a separate test with its own pre-registration (`acne-v3-calib-dev-preregistration-20261016.json`, SHA `035a60fa…`) and its own output directory (`audit-results/acne-v3-calib-dev-20261016`).
- The earlier finding is unchanged: the AUC condition **could not be computed**, so it is not claimed as "PRESERVED".
- No training was run, and nothing was enabled in production.
- The independent test is still sealed.

**Frozen thresholds and weights**
- **Step0** (`18e94a95…`): conf **.001**.
- **Corrected step-300** (`5644d62c…`): conf **.005**.
- **How they were chosen:** the TRAIN procedure of `acne-v3-calibration-analysis-20261016.json`.
- **What was not done:** no change after seeing development results, no per-photo threshold, no score normalisation, no new sweep.

**Evaluation chain**
- **Unchanged:** the v2 product chain: crop, native tiles, BGR channel order, NMS .30, anatomical support, exclusions, region ownership, one-to-one matching.
- **Only change:** `infer_tiles` was copied verbatim, with only the confidence value made a parameter.
- **Parity check:** Step0 at .30 through the copy matched the saved .30 rows on **75 of 75** (matched, cleanFP, candidates, unknown).
- **Earlier results:** the saved .30 results were kept and reused.
- **Completeness:** all runs finished with no resource limit and no candidate truncation.

## Results

Hits are at IoU ≥ .50, with IoU ≥ .30 in brackets. "Gained / lost" is at IoU .50, measured against Step0 at .30.

| Group | Step0 @.30 | Step0 @.001 | Corrected-300 @.30 | Corrected-300 @.005 |
|---|---|---|---|---|
| Scope B positives (14 targets) | 4 (4) | 4 (8); +0 / −0 | 2 (2); +0 / −2 | 4 (4); +0 / −0 |
| Product-valid controls (29) | 16 (16) | 17 (19); +1 / −0 | 1 (2); +0 / −15 | 8 (15); +1 / −9 |
| Held-out 20 photos (95) | 39 (52) | 47 (65); +8 / −0 | 4 (5); +0 / −35 | 42 (59); +11 / −8 |
| **Total (138)** | **59** | **68** | **7** | **54** |
| Reviewed negatives, false candidates per photo (7 photos) | 0.43 | **5.29** | 0 | **6.00** |
| UNKNOWN unlabelled candidates (positive groups) | 354 | 3,671 | 4 | 834 |
| Final / raw candidates, held-out 20 | 293 / – | 2,911 / 20,979 | 5 / – | 672 / 10,984 |
| Median time per photo, held-out 20 | 3.6 s | 3.9 s | 3.4 s | 4.1 s |

- The held-out 20 are a separate development group. Their eyewear check is UNKNOWN, so they are neither full product passes nor an independent final test.
- The 2 reviewed-negative photos that are not product-valid stay excluded.
- UNKNOWN candidates are not counted as real acne.
- **Corrected-300 @.005 vs Step0 @.001:** +7 / −21 at IoU .50.

## Answers

| Question | Result |
|---|---|
| Did calibration give a balanced gain over Step0 calibrated the same way? | **No.** Corrected-300 @.005 finds 54 of 138 targets; Step0 @.001 finds 68. At IoU .50 the corrected model gains 7 and loses 21, with similar false candidates (6.0 vs 5.3 per negative photo). |
| Did false candidates rise to an unacceptable level as hits went up? | **Yes, for both models.** On the reviewed development negatives, both exceed the frozen gate of ≤ 1 per negative photo (5.3 and 6.0); Step0 @.30 is at 0.43. The TRAIN threshold rule (≤ 1 per photo) did not carry over to development. Step0's TRAIN negatives were also part of its own training. |
| How much of the product-chain loss does the score shift explain? | **Most of it, not all.** On the held-out 20, the corrected model goes from 4 to 42 hits when the threshold is lowered, recovering the full .30 loss there (Step0 @.30 has 39). On the controls it goes from 1 to 8 at IoU .50, but from 2 to 15 at IoU .30, close to Step0's 16. The remaining shortfall at .50 is mostly box localization; the boxes are less precise. |

**Conclusion:** neither model has a usable operating point. The corrected model's main problem was the score scale, and lowering the threshold also brought false candidates on the clean negatives far above the gate. This does not authorise activation, and the acceptance criteria are unchanged.
