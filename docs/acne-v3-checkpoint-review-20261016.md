# Acne v3: checkpoint review without further training (2026-10-16)

**Result:** the pre-registered selection rule picks **Step0**. No v3 checkpoint beats Step0 on validation F1. The best trained checkpoint is step 900; on the real product chain it is worse than Step0. Acne stays `accepted:false, file:null`. No new training was started, and the independent test set is still sealed.

**Step0 is not an accepted, working product model either.** It is only the comparison baseline. The owner accepted this experiment as failed (2026-10-16); the remaining 550 steps will not be run. Diagnosis: `acne-v3-regression-diagnosis-20261016.md`.

## Preserved state

- Training stopped at step 1,250 of 1,800. This happened because the automated permission classifier blocked further training calls; the training itself did not fail.
- The resume checkpoint lives in the cloud workspace only: `run/v3/step-001250` (model `b752b8c1…`, optimizer/scheduler `63fc830c…`, state `9ab37000…`, CURRENT `06c561ba…`).
- Data RNG is stateless per step (`Random(SEED*1000003+step)`), so resuming is exact.
- Step-300/600/900 weights were copied to the desktop before 2026-10-15 23:36 for evaluation only. Nothing was trained locally.

## Validation selection

The rule was frozen in `acne-v3-preregistration-20261015.json` (SHA `4fa1b84c…`): pick the best validation F1 at IoU ≥ .30 and conf ≥ .30, with Step0 included. Validation has 150 photos and no group overlap with training. The same numbers were computed twice, in the desktop and cloud environments.

| Model | Recall | Precision | F1 | Unmatched candidates per photo |
|---|---|---|---|---|
| **Step0** | .247 | .280 | **.262** | 5.3 |
| step 300 | .492 | .141 | .220 | 24.8 |
| step 600 | .503 | .130 | .206 | 28.0 |
| step 900 | .490 | .166 | .248 | 20.4 |
| step 1200 | .510 | .148 | .229 | 24.4 |

Validation labels are incomplete, so some unmatched candidates are probably real but unlabeled acne. Under the official metric these still count as false positives; the label gap is a diagnostic note only.

## Product chain: Step0 vs step 900

Step 900 is diagnostic only; it was not selected.

**Evaluator.** The v2 evaluator is unchanged:
- product `photo_input` crop and native 384/288 tiles;
- conf ≥ .30, hard NMS .30;
- current production prelude masks and the principled staging filter;
- one-to-one matching at IoU ≥ .50.

The final boxes are also scored at IoU ≥ .30. The two thresholds are reported separately and never mixed.

**Parity.** The Step0 re-run matches the 2026-10-15 historical fixed-scope result on 74 of 74 rows.

| Set | Step0 hits (.50 / .30) | Step 900 hits (.50 / .30) | Gained / lost (.50) | Gained / lost (.30) | Unmatched candidates | Reviewed-negative FP |
|---|---|---|---|---|---|---|
| Scope B positives: 3 photos, 14 targets | 4 / 4 | 3 / 4 | 0 / 1 | 0 / 0 | 19 → 45 | – |
| Scope B reviewed negatives: 7 valid photos (2 not product-valid, excluded) | – | – | – | – | – | **3 → 41** |
| Product-pass controls: 3 photos, 29 targets | 16 / 16 | 5 / 13 | 1 / 12 | 2 / 5 | 81 → 111 | – |
| 20 held-out photos, 95 targets (replay pass; eyewear UNKNOWN, so not a full product pass) | 39 / 52 | 36 / 56 | 9 / 12 | 10 / 6 | 254 → 543 | – |

The median product-chain time per photo is about the same for both models (same architecture). For example, the 20 held-out photos take 3.58 s with Step0 and 3.45 s with step 900. The train-probe photos were also part of the v3 training, so they do not count as generalization.

**Pre-registered outcome criteria.** Step 900 fails both product-chain limits:
- reviewed-negative FP 41, against a limit of ≤ 3;
- unmatched candidates 543, against a limit of ≤ 1.5 × 254 = 381.

## Acceptance criterion source

`attune-live-test/audit-results/acne-trained-20261010/acceptance.json`, SHA `90dc84fa…`, frozen 2026-10-10T06:27:48Z.
- Requirements: P, R and F1 ≥ .80 at IoU ≥ .30; ≥ 50 positive and ≥ 50 negative independent photos; subject-disjoint; native camera; expert review.
- These conditions are not available here. The product-chain evaluator's IoU ≥ .50 is the separate, older fixed-scope rule.

## Independent test (sealed)

- Skin care v5 has 338 photo groups. None of them overlaps training, validation or the reserved v2 groups, by group (dHash ≤ 6 + NCC ≥ .92, mirror-aware) or by file SHA.
- 11 copies of test photos found in other archives were excluded from training.
- Person identity is unknown, so subject independence is **not verified**.
