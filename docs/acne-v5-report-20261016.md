# Acne v5: label-independent evaluation, reviewed TRAIN core, pilot and main run (2026-10-16)

**Result: no candidate.** The pilot passed its pre-registered gate by a narrow margin. The main run stopped early and selected step 150. That checkpoint does not meet the registered product-chain rule.

- Nothing was exported, integrated or packaged for CDC.
- Acne stays `accepted:false, file:null`.
- The v4 FAIL result and the v4 DEV numbers in `acne-v4-report-20261016.md` are unchanged.
- The sealed Skin care v5 test was not opened. No paid or hosted calls were made.

## Result table

| Item | Value |
|---|---|
| TRAIN coverage used | Engineering-reviewed TRAIN core: **65 positive photos**. All 348 source acne boxes on them were checked at native resolution by the assistant. This is not human or expert review. Plus 41 auxiliary TRAIN negative photos (27 Clear engineering ROIs, 14 CDC). The other ~790 v4 TRAIN positive photos (8,371 boxes in total) were **not** used, because they are unreviewed. |
| Clean-skin ROIs added (positive photos) | **67 accepted** of 193 candidates (761,884 px). 126 were rejected and stay UNKNOWN. 22 candidate regions carry a "possible unlabeled lesion" engineering note; they stay UNKNOWN and no box was drawn. |
| Boxes corrected or ignored | **111 set to IGNORE** after review, plus 1 unreviewed set to IGNORE. 236 were kept. No box was moved or redrawn, and no box was added. Source labels are unchanged; the decisions are stored separately (`acne-v5-core-review-20261016.json`). |
| Label-independent preprocessing test | `tests/unit/test_acne_v5_independent_eval.py` passes: changing or removing annotations leaves status, crop rects, tiles, raw post-NMS and final predictions identical. Full suite 10/10, including `test_acne_v4_training.py` 8/8. |
| Step0 → selected model, corrected DEV evaluation (17 photos, 137 targets) | Total hit50 **11 → 12**. Small (< 16 px) hit50 **8/19 → 9/19**. hit30 15 → 14. |
| Reviewed negative FP | Corrected evaluation, 14 Clear DEV: **0 → 0**. Product chain, 7 reviewed CDC negatives: **3 → 14** (v4 was 48). |
| Real product chain | hit50 **58 vs Step0 59** (required ≥ 62). FP 14 (required ≤ 7). Lost 10 vs gained 9 (required ≤ 3). **FAIL** on all three conditions. Median time per photo is 3.5–4.3 s on positive sets (Step0 3.6–5.8 s) and 1.4 s on negatives. |
| Active model | Unchanged: Step0 in the CDC pipeline. Acne is disabled in production (`accepted:false, file:null`). |

## 1. Label-independent evaluation (`scripts/skin-research/eval_acne_v5_independent.py`)

The v4 `evaluate()` rescaled positive photos with `photo_scale(p, side)`, which uses the true boxes. A product cannot do that. The new evaluator runs only the product contract on each photo:

1. `decode_photo` limits: side 16–4096 and ≤ 8.4 MP.
2. MediaPipe face landmarker on the ≤ 640 analysis canvas (same model SHA as the product).
3. A Node replay of the frontend gates and snapshot. The eyewear gate is not replayed and is recorded as UNKNOWN.
4. The product `photo_input` crop.
5. Native 384/288 tiles with a budget of 64.
6. conf .30, product NMS .30, product masks and the staging filter.

Annotations are read only by `metrics()`, after inference. Positive and negative photos go through the same rules.

- **Sizes:** there is no rescaling, so source px = model-input px, and the record says so.
- **Training:** scale augmentation stays in the trainer only.
- **Photos evaluated:** of 110 DEV photos, 31 pass (17 positive with 137 targets, 14 Clear negatives). The rest are excluded with their reason recorded:
  - 56 fail the pose or blur gates;
  - 16 hit PHOTO_LIMIT;
  - 1 exceeds the tile budget;
  - 4 have no face.
- **Same plan for every model:** all six models were evaluated on the identical 31 photos with identical crop rects. One excluded photo is labelled "tile-budget / POSE" in the earliest two runs and "PHOTO_LIMIT" in later ones. Only the order of the checks changed; that photo is excluded in every run.
- **Statistical power:** 137 targets on 17 photos is a small set, so a ±1 hit difference is within noise.

## 2. Step0 vs v4 step-1000 on the corrected evaluation (no new confidence sweep)

| | Step0 | v4 step-1000 |
|---|---|---|
| hit50 / hit30 (137) | 11 / 15 | 11 / 24 |
| Small hit50 (19) / medium (118) | 8 / 3 | 4 / 7 |
| Final candidates / unlabeled | 244 / 229 | 1,615 / 1,591 |
| Median matched-area ratio | 1.10 | 1.31 |
| Clear DEV FP (14) | 0 | 0 |

The v4 DEV "gain" (108 → 274 of 1,091 under rescaled tiles) does not appear under product preprocessing: hit50 is equal, small targets are halved and candidates rise 6.6-fold. This does not accept v4 retroactively.

Separating the possible causes (each is evidence, not a proven root cause):
- **Non-applicable DEV scaling:** this explains why v4 selection looked good while the product chain failed. The selection signal was measured on an input the product never produces.
- **Box quality:** at native zoom, 111 of 347 reviewed TRAIN boxes (32%) had no clearly visible lesion. v4 trained on such boxes as positives. Its looser placement (area 1.31) and its hits at .30 but not .50 are consistent with this.
- **Data coverage:** no known clean skin on positive photos. Unlabeled skin was UNKNOWN, so there was no signal against firing there, and v4's candidates multiplied.
- **What v5 cannot separate:** it changed coverage and box quality together and is also much smaller (65 vs 855 photos, 150 vs 1,000 steps), so these effects are not isolated.

## 3. TRAIN data correction (existing tools; roles from the 115-photo review package)

- **Box review:** each of the 347 key boxes was viewed on the original photo at native resolution (crop at 3× box size).
  - Rule: IGNORE when no clearly visible papule, pustule, whitehead bump or inflamed spot is inside the box (faint, empty, off-target, shadow, hair, edge or flat mark). KEEP otherwise.
  - The source record is unchanged. Each decision and its reason is stored per box, keyed by photo SHA and source id.
- **Clean ROIs (`build_acne_core_roi_v5.py`):**
  - Candidates are cheek and forehead polygons from the product landmarks, minus every source box dilated by max(10 px, box side), minus a colour exclusion.
  - Each candidate was reviewed as a contour on the original photo. It was accepted only if the whole region was clearly clean skin.
  - Hair, beard, eyes, mouth, shadow, glare and undecided regions stay outside the ROI and so remain UNKNOWN or IGNORE.
- **Trainer:** accepted ROIs become KNOWN_NEG in `train_acne_v4.py`. A test checks that lesion pixels are never negative.
- **Honest labelling:**
  - Review level: assistant engineering review.
  - Source rights: as recorded for the review package. A publisher licence is not individual consent.
  - No consent and no expert approval are claimed.
  - The 941 UNKNOWN-cohort photos, photos from the failed product evaluations and the sealed test were not used. Clear photos remain an auxiliary negative pool only.

## 4. Pilot (pre-registration `acne-v5-pilot-preregistration-20261016.json`, fixed before the run)

Setup: v4 architecture and loss unchanged; 150 steps from Step0 with a new optimizer; data change only.

| Gate (registered) | Required | Pilot | Pass? |
|---|---|---|---|
| hit50 | > 11 | 12 | Yes |
| Small hit50 | ≥ 8 | 9 | Yes |
| Clear DEV FP | ≤ 1 | 0 | Yes |
| Final candidates (no collapse) | ≥ 61 | 530 | Yes |
| Median area ratio | 0.75–1.35 | 1.07 | Yes |
| Gradients | Finite; ≤ 20% clipped in the last 50 steps | 0 clipped; max 95 | Yes |

**PASS**, by one target.

## 5. Main run (pre-registration `acne-v5-main-preregistration-20261016.json`)

**Budget and rules**
- Measured time is 3.8 s per step. The cap was 600 steps (≤ 1,200 allowed), because the core is 65 positive photos and 600 steps is already about 44 passes per photo.
- Evaluation every 150 steps on the corrected evaluation.
- Selection: maximum hit50 among checkpoints with small hit50 ≥ 8, Clear FP ≤ 1, candidates ≥ 61 and area ratio in 0.75–1.35.
- Early stop after two evaluations that do not raise the best by ≥ 2.

| Step | hit50 | hit30 | Small | Final | Area | Clear FP |
|---|---|---|---|---|---|---|
| 0 | 11 | 15 | 8 | 244 | 1.10 | 0 |
| **150** | **12** | 14 | 9 | 474 | 1.11 | 0 |
| 300 | 9 | 13 | 8 | 476 | 1.03 | 0 |
| 450 | 10 | 15 | 8 | 604 | 1.09 | 0 |

**Early stop and selection**
- The run stopped early after the step-450 evaluation. The process had reached step 500; checkpoints 475 and 500 were not evaluated and play no role.
- The selected checkpoint is **step 150** (`084af1d2…`).

**Training health**
- No clipped steps.
- Gradient before clipping: median 23–69, maximum 205.
- All losses finite. posObj fell 1.04 → 0.41; negObj stayed at about 0.24–0.33.
- Resume across 545 s segments was checked against the saved optimizer, scheduler and sampler state.

## 6. Real product chain (unchanged v2 evaluator, conf .30)

| Set | Step0 hit50 / hit30 | v5 step-150 hit50 / hit30 | Gained / lost (.50) | Small, Step0 → v5 | Unlabeled candidates |
|---|---|---|---|---|---|
| Scope B positives (14) | 4 / 4 | 3 / 8 | 0 / 1 | 1/11 → 1/11 | 19 → 53 |
| Product-valid controls (29) | 16 / 16 | 14 / 18 | 1 / 3 | 14/20 → 12/20 | 81 → 148 |
| Held-out 20 photos (95) | 39 / 52 | 41 / 59 | 8 / 6 | 19/58 → 19/58 | 254 → 634 |
| **Reviewed negatives (7): FP in mask** | **3** | **14** (10, 4, 0, 0, 0, 0, 0) | | | |

**Registered rule:**
- hit50 58 vs ≥ 62: fail.
- FP 14 vs ≤ 7: fail.
- Lost 10 vs ≤ 9/3: fail.

**→ FAIL.** Compared with v4 (FP 48, lost 18), clean ROIs and box cleaning reduced false candidates on real clean skin by about 3.4×. Localisation at .30 improved, but .50 matches did not.

**Not done, by rule:** no ONNX parity, no integration and no CDC package, because there is no candidate. No new architecture, loss or threshold work was started.

## Remaining blocker

The corrected evaluation now measures what the product does. However, only 17 DEV positive photos pass the product gates, so it can detect only large effects.

The TRAIN core is 65 photos with 236 kept boxes. That is enough to show the direction (fewer false candidates than v4, cleaner placement) but not to beat Step0 on the product chain.

Two things would change the outcome:
- more reviewed TRAIN positives with clean ROIs;
- a larger set of product-gate-passing DEV photos.

The next step is extending the same review to more TRAIN photos with the existing tools. Unreviewed boxes must not be added to the core.
