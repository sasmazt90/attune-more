# Acne v4: prepared data, budgeted objectness, finite training run (2026-10-16)

**Result: no candidate.** The selected checkpoint does not meet the pre-registered product-chain success rule. Nothing was exported, integrated or enabled. Acne stays `accepted:false, file:null`. The sealed Skin care v5 test was not opened.

## 1. Data

Both packages were hash-verified (`be0acf9e…`, `5799bf01…`) and extracted to the Git-ignored `audit-results/acne-v4-data/`. The original image bytes were used; gallery images, contact sheets and overlays were not used for training.

| | TRAIN | DEV (selection only) |
|---|---|---|
| Positive photos (package "acne" cohort ∩ v3 roles) | 855 | 95 |
| Positive boxes (Pimple/Acne/akne/acne/Whiteheads) | 8,371 | 1,091 |
| Explicit confounder negative boxes (Mole, Freckles, Pigmentation, pores, Dark-Spots) | 2,275 | 290 |
| Clear negative photos (assistant-engineering ROI) | 27 (34,228 px) | 15 (18,899 px) |
| CDC reviewed negative photos | 14 (375,395 px) | – |
| Research groups | 896 | 110 |

- **Roles:** the photo groups' v3 roles are unchanged. 115 RESERVED_V2_EVAL photos and 5 photos outside the v3 plan were not used.
- **Group check:** no research group and no package group is split across TRAIN and DEV. Person identity is unknown, apart from the filename-derived groups on the Clear photos.
- **Annotations:** each photo uses only its own source record; duplicate-group annotations were not merged.
  - Conflicting or oversize acne boxes, Blackheads, Post acne and the other classes are IGNORE.
  - **Unlabeled skin on positive photos is UNKNOWN, never background.**
  - Whiteheads are kept in scope as pale-white candidates.
- **941 UNKNOWN-cohort photos:** none was used (checked in code). One CDC reviewed negative belongs to that cohort and was excluded for that reason.
- **Clear photos:**
  - **Near-duplicates:** no near-duplicate of the 33,819 existing images (dHash ≤ 10 and NCC ≥ .85).
  - **Roles:** fixed by person group (sha256 % 10 < 7 → TRAIN).
  - **Masks:** cheeks, central forehead and nose bridge, from MediaPipe landmarks, with colour exclusion. Eyes, brows, lips, nostrils, chin/perioral, hairline and background are excluded.
  - **Visual check:** all 42 overlays were checked; none was rejected.
  - **Resolution:** native 250 px, padded, never upsampled.
  - **Status:** these are not human- or expert-verified negatives.
- **Positive-box audit:** a sample of 56 boxes was checked on the original photos (assistant engineering review). About 24 of the 56 were doubtful at this zoom: faint lesions or pigment marks. By source: SPD 15/24, SmartSkinCare 6/16, SA v11 4/8, ciltanalizi 0/8. No per-box relabelling was done; the counts are recorded.
- **Scale:**
  - Positives are only ever downscaled (s ≤ 1), never enlarged.
  - The target lesion side is drawn from SmartSkinCare TRAIN boxes at native resolution: median 15 px (p25 11.5, p75 20).

## 2. Training rule actually used (`scripts/skin-research/train_acne_v4.py`)

**Anchor states**

| State | What it covers |
|---|---|
| POSITIVE | YOLOX SimOTA assignment |
| KNOWN_NEG | Inside a reviewed negative ROI, inside a confounder box, or in tile padding |
| IGNORE | Everything else, including unlabeled skin and cut lesions |

**Objectness term**

`L_obj = Σ_POS BCE / num_fg + λ/K · (w_h Σ_HARD BCE + w_r Σ_RAND BCE)`

- HARD is the 64 KNOWN_NEG anchors with the highest current objectness.
- RAND is 192 further KNOWN_NEG anchors, chosen at random.
- K = 256 is fixed, so the term does not grow with negative area. A tile without positives gives a finite, bounded term.
- The per-anchor values are pre-scaled so that the shared head's normalisation (/num_fg; mean × 20) produces exactly this formula. Tests check both the value and the gradient.
- Box, class and L1 losses are YOLOX's own.
- Box, class, positive-objectness and negative-objectness losses, gradient norm before and after clipping, clipping, and the anchor counts are all logged.

**Settings fixed before the run**

| Setting | Value | Basis |
|---|---|---|
| λ | 256 / 7 = 36.6 | Per-anchor parity with the median Step0 TRAIN num_fg. A first rule (equal loss magnitudes) gave 6,166 and was rejected before training: Step0's negative BCE is ≈ 0, so magnitude balancing makes λ explode. Recorded. |
| LR | 5e-5 | Pilot fixed it |
| Warmup | 50 steps | Pilot fixed it |
| Clip | 2,000 | Spike guard above Step0's largest probe gradient (1,724) |
| Tile sampling | 40% negative-photo tiles | |
| Trainable layers | Head and neck | BatchNorm and backbone frozen |
| Start | Step0 (`18e94a95…`), new optimizer | |

**Tests:** `tests/unit/test_acne_v4_training.py`, 7/7 on the desktop and in the cloud. They cover formula value, formula gradient, UNKNOWN = 0, hard-negative selection, the bounded budget, padding, lesion and ignore states, no upscaling, and head anchor order.

## 3. Pilot (150 steps, fixed 120 TRAIN photos + 41 TRAIN negatives): PASS

Pre-registration: `acne-v4-pilot-preregistration-20261016.json`. Amendment 1 is a JSON crash fix only.

| | Step0 | Pilot |
|---|---|---|
| Hits, IoU .50 (out of 295) | 56 | 88 |
| False positives in negative masks (41 photos) | 0 | 2 |
| Median best target score | 0 | .093 |
| Box-area ratio | – | 1.28 |
| Clipped steps in the last 50 | – | 0 |

## 4. Main run (pre-registered `acne-v4-main-preregistration-20261016.json`)

- **Length:** the cap was 1,200 steps (3.8 s per step, about 11 passes) and the run used all of them.
- **Gradients:**
  - Before clipping: median 38, early spikes up to 183,812 from Step0's low-objectness positives.
  - 8 clipped steps in total, 7 of them in the first 50.
- **Losses per 200-step window:** posObj 13.4 → 0.86, negObj about 0.41–0.47, box about 1.8–2.0.

**DEV tile evaluation**

| | Step0 | 200 | 400 | 600 | 800 | **1000** | 1200 |
|---|---|---|---|---|---|---|---|
| Hits, IoU .50 (out of 1,091) | 108 | 182 | 195 | 257 | 263 | **274** | 267 |
| Clear DEV FP in mask | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Candidates per positive photo | 9.6 | 98.8 | 39.9 | 63.5 | 68.3 | 69.5 | 65.5 |

By the selection rule, the chosen checkpoint is **step 1000** (`7e2af5e2…`).

## 5. Product chain, unchanged v2 evaluator: no candidate

Settings are unchanged: conf .30, NMS .30, prelude masks, staging filter, one-to-one matching. Step0 parity was established earlier (74/74).

| Set | Step0 hits (.50 / .30) | v4 hits (.50 / .30) | Gained / lost (.50) | Small (< 16 px) / medium hits (.50), Step0 → v4 | Unlabeled candidates |
|---|---|---|---|---|---|
| Scope B positives (14) | 4 / 4 | 5 / 8 | +2 / −1 | 1/11 → 3/11; 3/3 → 2/3 | 19 → 137 |
| Product-valid controls (29) | 16 / 16 | 8 / 17 | +1 / −9 | 14/20 → 5/20; 2/9 → 3/9 | 81 → 299 |
| Held-out 20 photos (95; replay pass, eyewear UNKNOWN) | 39 / 52 | 42 / 63 | +11 / −8 | 19/58 → 17/58; 20/37 → 25/37 | 254 → 1,674 |
| **Reviewed negatives (7 valid): false candidates in the mask** | **3** (per photo 3,0,0,0,0,0,0) | **48** (per photo 18,6,4,16,4,0,0) | | | |

**Registered rule outcome**

| Condition | Required | Result | Pass? |
|---|---|---|---|
| Hits at IoU .50 | ≥ 62 (Step0 59 + 3) | 55 | No |
| Reviewed-negative FP | ≤ 7 | 48 | No |
| Lost targets | ≤ gained / 3 | 18 lost vs 14 gained | No |

Median product-chain time per photo: 3.2–5.4 s for v4, against 3.6–5.8 s for Step0.

## 6. Remaining concrete blocker

On real product-like clean skin, false candidates rose 16-fold even though Clear DEV stayed at zero. The model learned to fire on unlabeled skin, because that skin is (correctly) UNKNOWN and gets no gradient.

The available known negatives do not cover the product skin domain:
- 27 small 250 px press photos (about 1.3k px each);
- 14 CDC photos.

At IoU .50, localisation is still worse (matched-box area about 1.23–1.27×).

What would change this is product-domain clean-skin evidence on positive photos: confirmed clean ROIs or exhaustive lesion labels, for example from the existing 115-photo review package. More loss, threshold or architecture variations would not, and none were started.
