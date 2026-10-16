# Acne v6: product-like clean-skin coverage on DEV and TRAIN, extended selection control, pilot (2026-10-16)

**Result: pilot FAIL, so there is no candidate.** The 150-step pilot failed two of its eight pre-registered gates:
- unlabeled-candidate growth: 544 against a limit of 420;
- box placement: median area ratio 1.52 against a limit of 1.29.

Consequences:
- **No main run** was started.
- No product-chain run, export, integration or CDC package.
- No new architecture, loss or threshold work.
- Acne stays `accepted:false, file:null`.
- The v4 and v5 FAIL results and their numbers are unchanged.
- The sealed Skin care v5 test was not opened.

## Result table

| Item | Step0 | V5 step-150 | V6 pilot (step 150) |
|---|---|---|---|
| Pooled DEV hit50 / hit30 (28 photos, 201 targets) | 17 / 25 | 20 / 29 | 19 / 27 |
| Small (< 16 px) hit50 (63) | 14 | 17 | 16 |
| Medium hit50 (138) | 3 | 3 | 3 |
| Final candidates / unlabeled candidates | 305 / 280 | 617 / 588 | 571 / 544 |
| Median matched-area ratio | 1.14 | 1.23 | 1.52 |
| False candidates on frozen clean ROIs of positive DEV photos (13 photos, 226,001 px) | 0 | 1 | 1 |
| Clear negatives FP (14) | 0 | 0 | 0 |
| v6 pilot gate (G1–G8) | (reference) | FAIL (G5) | **FAIL (G5, G7)** |
| Real product chain, unchanged v2 evaluator (138 targets) | hit50 59; reviewed-negative FP 3 | hit50 58; FP 14 (v5 report, FAIL) | not run: no candidate |
| Median time per photo, label-independent chain | 4.5 s | 4.2 s | 4.2 s |
| Active model | Step0 in CDC; acne disabled in production | – | – |

**Real coverage used**
- **TRAIN:** v5 core (65 photos; 236 kept boxes; 67 accepted ROIs) plus 83 photos from the v6 extension (278 kept boxes; 47 accepted ROIs on 35 photos). Together that is 148 positive photos, 514 kept boxes and clean ROIs on 76 photos (1,656,838 px), plus the same 41 auxiliary TRAIN negatives.
- **DEV:** 17 v4-DEV photos plus 11 VALIDATION DEV-EXT photos (28 photos), 14 Clear negatives, and 13 photos with frozen clean ROIs.
- **What does not count as DEV coverage:** the TRAIN growth. The DEV coverage gain is only the 11 DEV-EXT photos.

## 1. DEV negative coverage (`build_acne_roi_v6.py`, `eval_acne_v6.py`)

**Review**
- **Scope:** clean-skin regions on the positive DEV photos that enter the label-independent evaluation.
- **Candidates:** cheek and forehead polygons from the product landmarks, minus every source box (any class) dilated by max(10 px, box side), minus a colour exclusion.
- **Method:** each candidate was shown as a contour on the original pixels. No model prediction was shown or read.
- **Decisions:** accepted only if the whole region was clearly clean, measurable skin. Spots, redness, raised texture, pigment, hair or beard, shadow, glare, blur and fragments stayed UNKNOWN. Region-level notes record possible unlabeled lesions; no boxes were drawn.
- **Freezing:** files and hashes were frozen before any comparison. The evaluator re-checks every mask hash, and a test proves that a changed mask is refused.

| DEV set | Candidates | Accepted | Photos with ROI | Pixels | Decisions SHA |
|---|---|---|---|---|---|
| v4 DEV (17 photos) | 46 | 9 | 6 | 107,885 | `3987e8e5…` |
| DEV-EXT (11 photos) | 28 | 9 | 7 | 118,116 | `b58481e0…` |

Main rejection reasons in v4 DEV:
- 20 possible lesions;
- 5 raised texture or possible whiteheads;
- 4 hair;
- 5 shadow, blur or low light;
- 3 fragments.

**False candidates on the same fixed areas**

Per-photo values for the 13 ROI photos are in `acne-v6-eval-20261016.json`.

| Model | v4 DEV ROI FP (per photo) | DEV-EXT ROI FP (per photo) | Total | Clear FP |
|---|---|---|---|---|
| Step0 | 0 (0,0,0,0,0,0) | 0 | 0 | 0 |
| V5 step-150 | 0 | 1 (0,1,0,0,0,0,0) | 1 | 0 |
| V4 step-1000 | 16 (3,11,0,0,2,0) | 18 (0,17,1,0,0,0,0) | 34 | 0 |

**Did the selection control catch V5's false-candidate increase?** Not through the clean ROIs alone.

These ROIs catch V4's false-candidate explosion clearly: 34 against 0. V5 rose only from 0 to 1 on them, while its reviewed-negative false candidates on the real product chain rose from 3 to 14.

The fixed, reviewed product-like clean area is small, 0.23 MP on 13 photos. That is enough to detect a large explosion but not a 3 → 14 increase.

So the v6 gate adds a pre-registered growth limit on unlabeled candidates (G5, at most 1.5 × Step0). With it the same comparison does reject V5: 588 against a limit of 420.

G5 is a conservative proxy, not a false-candidate count. Unlabeled candidates include real but unannotated lesions, so it can also reject a genuinely better model.

## 2. Limited TRAIN extension (`select_acne_train_ext_v6.py`, `build_acne_box_review_v6.py`, `prepare_acne_v6.py`)

**Pool:** 798 v4-TRAIN positive photos (acne cohort, v3 role TRAIN only). Excluded from it:
- the v5 core;
- every photo, and the research group of every photo, listed in the v3 product-evaluation file (conservatively including its TRAIN-probe rows);
- groups shared with any other role.

The 941 UNKNOWN-cohort photos are not in the pool.

**Product suitability** was decided from pixels and the product contract only: decode limits, MediaPipe, replayed gates with eyewear UNKNOWN, and the tile budget. 100 of 798 photos qualified, and all 100 were selected.

**Selection** was model-free and deterministic:
- round-robin over source × face-brightness tercile;
- confounder or small-box photos first;
- one photo per research group.

| Selected by source | |
|---|---|
| Skin-Problem-Detection | 82 |
| SmartSkinCare | 10 |
| ciltanalizi | 6 |
| Skin Analysis v11 | 2 |

**Box review** (assistant engineering review on native-resolution crops; source records unchanged; each decision stored per box in `acne-v6-trainext-review-20261016.json`):
- **Acne boxes:** 1,229 reviewed. **278 kept** and **951 set to IGNORE**. The reasons for ignoring:
  - mostly faint or empty boxes;
  - flat brown or purple post-inflammatory marks;
  - uniform bumpy texture where the boxed bump is not distinct;
  - lip, nose-pore or eye areas;
  - beard or hair;
  - blur or low light.
- **Confounder boxes** (moles, pigment, pores): 120 reviewed. **34 kept** as explicit negatives. 86 set to IGNORE because they were large, ambiguous or possibly contained a lesion.

**Clean ROIs:** 196 candidates, **47 accepted** on 35 photos (894,954 px). Masks are cleared within max(10 px, side) of every box.

**What was left out or not added:**
- 17 photos with neither a kept box nor an accepted ROI were left out.
- No new lesion boxes were drawn.
- No expert, human-verification, consent or rights record is claimed; rights are publisher declarations only.

## 3. Separate DEV (`select_acne_devext_v6.py`)

**Candidates:** v3 VALIDATION-only photos whose group has no other role and that have at least one source acne box. Excluded:
- 94 already in v4 DEV;
- 4 failed product-evaluation photos;
- 17 near-duplicates (dHash ≤ 10) of a v6 TRAIN or v4 DEV photo.

No 941-cohort, TRAIN, RESERVED, TEST or sealed-archive photo is included. That left 162 photos.

**Product gates were not relaxed.** Of the 162, 74 had no face, 77 failed the pose, blur or snapshot gates, and **11 are evaluable** (64 publisher targets).

"Evaluable" means replay-pass with eyewear UNKNOWN. It is not a full product preflight pass. DEV-EXT source boxes are publisher labels and were not reviewed.

A test asserts that the v6 TRAIN manifest shares no photo or research group with DEV or DEV-EXT.

## 4. Pilot (pre-registration `acne-v6-pilot-preregistration-20261016.json`, SHA `3d428eb0…`, frozen before the run)

Setup:
- v4/v5 architecture, loss and settings unchanged; conf and NMS unchanged.
- 150 steps from Step0 with a new optimizer.
- New manifest (`f90be74b…`) and a separate directory.

| Gate | Required | V6 pilot | Pass? |
|---|---|---|---|
| G1 total hit50 | ≥ 18 | 19 | Yes |
| G2 small hit50 | ≥ 14 | 16 | Yes |
| G3 Clear FP | ≤ 1 | 0 | Yes |
| G4 positive-DEV clean-ROI FP | ≤ 1 | 1 | Yes |
| G5 unlabeled candidates | ≤ 420 | **544** | **No** |
| G6 no collapse (final candidates) | ≥ 76 | 571 | Yes |
| G7 median area ratio | 0.75–1.29 | **1.519** | **No** |
| G8 finite, ≤ 20% clipped in the last 50 steps | – | 0 clipped; max gradient 926 | Yes |

The total gain over Step0 (+2) comes only from DEV-EXT (6 → 8). On the original 17 DEV photos, hit50 is 11 → 11.

As the pre-registration requires, a higher total catch with more false candidates and looser boxes does not pass.

## Notes

- **Statistical power:** 28 evaluable DEV photos with 201 targets can detect large effects only. Differences of ±1–3 hits are within noise.
- **Coverage is limited by the product gates:** of 257 DEV and DEV-EXT positive photos (95 + 162), only 28 pass the replayed product gates.
- **The TRAIN extension is noisy:** 77% of the reviewed source boxes in the extension were not clearly visible lesions at native resolution.
- **No promise:** more data or longer training is not claimed to lead to success.
