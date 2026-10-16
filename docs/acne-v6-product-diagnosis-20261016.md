# Acne v6 pilot on the real product chain: diagnostic comparison (2026-10-16)

**Scope.** This run is diagnostic only. It does not change any of the following:
- The V6 pilot FAIL record and its G1–G8 gates (G5 and G7 failed).
- The V4 and V5 results.
- The production state: acne stays `accepted:false, file:null`.

No training, threshold sweep, data change or label change was made. The sealed Skin care v5 test was not opened.

**Model checked.** The V6 pilot step-150 weights were verified against the recorded hashes before use:

| Item | SHA-256 |
|---|---|
| Weights | `8043de61…` (equal to the recorded checkpoint) |
| Config | `493ebef5…` (the hash of the pre-registered config) |
| Manifest | `f90be74b…` |

**Evaluator.** The unchanged v2 product evaluator was used:
- same photos and source coordinates;
- same product crop and native tiles;
- same preflight and exclusion masks;
- conf .30, NMS .30;
- one-to-one matching;
- the same reviewed-negative masks.

**Recording of intermediate outputs.** The new wrapper `eval_acne_v6_product.py` only observes the evaluator. It records the intermediate outputs that the loss breakdown needs:
- raw head boxes with score ≥ .01;
- the ≥ .30 candidates;
- the NMS-selected boxes.

**Parity check.** Before the V6 run, the wrapper was run on Step0 and compared with the saved Step0 results. 75/75 evaluation rows and 74/74 final box sets were identical.

**Reused results.** Step0 and V5 are the saved, verified results. V6 was run once.

## Comparison (IoU .50 and .30 reported separately)

| Group | Model | Hits .50 / .30 | Small (< 16 px) .50 / .30 | Medium .50 / .30 | Reviewed-negative FP | Unlabeled candidates | Median area ratio (matched at .30) | Share of matches with area > 1.5× |
|---|---|---|---|---|---|---|---|---|
| Scope B positives (14 targets) | Step0 | 4 / 4 | 1/11 / 1/11 | 3/3 / 3/3 | – | 19 | 0.77 | 0.00 |
| | V5 step-150 | 3 / 8 | 1/11 / 5/11 | 2/3 / 3/3 | – | 53 | 1.60 | 0.50 |
| | V6 pilot | 4 / 6 | 1/11 / 3/11 | 3/3 / 3/3 | – | 42 | 1.22 | 0.33 |
| Product controls (29) | Step0 | 16 / 16 | 14/20 / 14/20 | 2/9 / 2/9 | – | 81 | 1.10 | 0.12 |
| | V5 step-150 | 14 / 18 | 12/20 / 15/20 | 2/9 / 3/9 | – | 148 | 1.24 | 0.28 |
| | V6 pilot | 11 / 19 | 9/20 / 15/20 | 2/9 / 4/9 | – | 112 | 1.81 | 0.58 |
| Held-out development (95; replay pass, **eyewear UNKNOWN**, not a full preflight pass) | Step0 | 39 / 52 | 19/58 / 26/58 | 20/37 / 26/37 | – | 254 | 1.17 | 0.29 |
| | V5 step-150 | 41 / 59 | 19/58 / 29/58 | 22/37 / 30/37 | – | 634 | 1.19 | 0.34 |
| | V6 pilot | 39 / 55 | 15/58 / 26/58 | 24/37 / 29/37 | – | 554 | 1.51 | 0.53 |
| Reviewed negatives (7 product-valid photos) | Step0 | – | – | – | **3** (3,0,0,0,0,0,0) | – | – | – |
| | V5 step-150 | – | – | – | **14** (10,4,0,0,0,0,0) | – | – | – |
| | V6 pilot | – | – | – | **10** (6,3,0,1,0,0,0) | – | – | – |
| **Total (138 targets)** | Step0 | **59 / 72** | | | 3 | 354 | | |
| | V5 step-150 | **58 / 85** | | | 14 | 835 | | |
| | V6 pilot | **54 / 80** | | | 10 | 708 | | |

**Registered product rule, for reference only** (V6 is not a candidate): hit50 54 against ≥ 62, false candidates 10 against ≤ 7, lost 13 against ≤ 8/3. Every condition fails.

Unlabeled candidates are reported separately and are never counted as right or wrong.

**Timing.** Median time per photo over all 74 photos:
- Step0 saved: 4.57 s;
- Step0 parity run, same session with recording: 5.49 s;
- V5 saved: 4.42 s;
- V6 with recording: 6.40 s.

The V6 figure includes the recording overhead and the machine load at the time of the run.

## Gained and lost targets against Step0 (target IDs: photo SHA prefix # source annotation ID or index)

**V6 at IoU .50**

| Group | Gained | Lost |
|---|---|---|
| Scope B | 0 | 0 |
| Controls | 0 | 5: `f2ed24a9b9a7` #2, #6, #7, #12, #17 |
| Held-out | 8: `e67dc50fb2ab#3837`, `7cdc876f2aa6#22701`, `f859de125798#27848`, `fc2fc6a1a2a2#21530`, `e7f8db3d4c5f#13526`, `693c4f4c25d1` #8380, #8396, #8411 | 8: `c739064b742d#7580`, `fc2fc6a1a2a2` #21524, #21529, `bc63081a3391` #2071, #2073, #2074, #2098, `e924914cd2ad#5206` |

**V6 at IoU .30**

| Group | Gained | Lost |
|---|---|---|
| Scope B | 2 | 0 |
| Controls | 3 | 0 |
| Held-out | 7 | 4 |

The full lists, and the same lists for V5, are in `acne-v6-product-diagnosis-20261016.json`.

## Why V6 misses targets (from the recorded intermediate outputs)

**The 13 targets that Step0 hit and V6 lost at .50:**
- **11: a final box lands on the target but is too large.** Final IoU is .30–.50, and the box area is 2.1–3.2× the target.
- **1: too large before the filters too.** The best box at any stage is badly placed, at 2.1× the area.
- **1: below the score threshold.** A well-placed raw box exists but scores .24, under the .30 threshold.
- None was lost to NMS. None was lost to the anatomical/staging filter.

**All V6 misses at .50:**

| Group | Box too large or misplaced (final / pre-filter) | Below score | Removed by filter | No box at IoU ≥ .30 |
|---|---|---|---|---|
| Scope B | 2 / 4 | 1 | 0 | 3 |
| Controls | 8 / 1 | 2 | 3 | 4 |
| Held-out | 16 / 11 | 7 | 7 | 15 |

Among the 42 misplaced misses, 34 are too large (area > 1.5×), 6 are too small (< 0.67×), and the median area ratio is 2.18. No miss was lost to NMS. Raw boxes with a score below .01 are not recorded, so "no box" means nothing scored ≥ .01 at IoU ≥ .30.

## Direct answers

1. **Does V6 raise catch on the real product scope? No.**
   - At IoU .50, V6 catches 54 of 138 targets, against 59 for Step0 and 58 for V5.
   - Small targets fall in controls (14 → 9) and in held-out (19 → 15).
   - At IoU .30 V6 catches more (72 → 80). The difference between .30 and .50 is the box size, not detection.
2. **Does V6 reduce false candidates on reviewed clean skin? No.**
   - It produces 10 false candidates against 3 for Step0.
   - That is fewer than V5's 14, but still above Step0. Two photos carry most of them (6 and 3).
3. **Do the G5 proxy and the real false-candidate measurement point the same way? Yes, in direction and in ranking.**
   - DEV unlabeled candidates rank Step0 280 < V6 544 < V5 588.
   - Product reviewed-negative false candidates rank Step0 3 < V6 10 < V5 14.
   - Product unlabeled candidates rank 354 < 708 < 835.
   - The proxy is still an approximation. It does not separate real unlabeled lesions from false ones.
4. **Does the box-placement problem (G7) appear on real product targets too? Yes.**
   - The median matched area ratio rises from 1.10 to 1.81 in controls and from 1.17 to 1.51 in held-out.
   - The share of matches with area > 1.5× roughly doubles (controls 0.12 → 0.58, held-out 0.29 → 0.53).
   - 11 of the 13 lost targets are too-large boxes.

## Limitations

- **Labels differ between TRAIN and DEV.** The TRAIN boxes went through assistant engineering review. In V6, 77% of the extension's source boxes were set to ignore. The DEV and product targets remain unreviewed source labels. Part of the V6 "misses" could therefore come from targets that the TRAIN review would have ignored. This task did not change DEV labels to improve the results.
- **Held-out group status.** The held-out group passes the replayed gates with the eyewear gate UNKNOWN. It is not a full product preflight pass.
- **Sample size.** The sets are small: 138 targets and 7 reviewed negatives. Differences of a few targets are within noise.
- **Timing.** The V6 timing includes the recording overhead and the current machine load. Compare it with the Step0 parity run from the same session, not with the earlier saved Step0 timing.
- **No conclusion is drawn for new training, thresholds or architecture.** Acne remains disabled.
