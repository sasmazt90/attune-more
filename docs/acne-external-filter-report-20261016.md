# External detector boxes through Step0's current post-processing: does the advantage survive? (offline staging, 2026-10-16)

**What this is**
- An offline staging experiment on stored predictions only. No training, no inference, and no change to weights, confidence, class map or NMS.
- No live camera and no product integration. Acne stays `accepted:false, file:null`.
- Labels are the frozen layer-1 **AI engineering** points on the **same, re-used DEV set**. This is not an independent test or product acceptance.
- Licence is separate. All three third-party weights carry AGPL-3.0 metadata, and a good result is not permission to integrate.
- **Settings differ:**
  - Step0: conf .30 and NMS .30;
  - third-party models: Ultralytics conf .25, NMS .7 per tile, and a .30 box merge across tiles.
  - So this measures how well each model adapts to the same product post-processing. It is not a controlled architecture comparison.

**Protocol** (`docs/acne-external-filter-protocol-20261016.json`, sha `9e2c2bd5…`) was committed before any filtered number (`c113048`).

## 1. The filter, reused exactly

**Code identity**
- `services/core-api/acne_box_support_staging.principled_accepted_boxes`, sha `11dd8e04…`, with its default parameters.
- Its masks come from the production prelude `acne_takeover_support.current_product_masks` (`appearance_analysis` sha `1102117b…`).
- Each photo uses the same replay landmarks, snapshot meshes and exclusions, visible regions (including the side-angle scope), analysis origin and scale as Step0.
- Script: `scripts/skin-research/filter_external_staging.py`.

**Parity, checked before any external row**
- The recomputed masks equal the stored Step0-trace masks on **28/28** positive photos.
- The filter applied to the recorded Step0 NMS boxes reproduces the stored Step0 final boxes on **28/28**.

**Adapter**
- An external final box `[x1, y1, x2, y2, score]` in source px is passed through as `[x1, y1, x2, y2, confidence]`.
- The score is not used by any filter decision, and no field is invented.

**YOLOX-specific assumptions: none in the filter's decisions.** They use box geometry, masks and pixels only. Some rules depend on box size: exclusion > .25, hair > .25, skin support < .50, envelope overlap ≥ .15 and the box-centre checks. These are recorded per rejection with the box side.

## 2. One table (common scope: frozen reviewed mask, 108 in-scope targets, r = 0.03 × face width, one-to-one)

| Row | Found / 108 | False on reviewed skin (per reviewed photo, 22) | Duplicates | On UNCERTAIN | Non-skin (outside face oval) | Unreviewed: in oval · empty-mask photo | vs Step0 final: gained / lost | v4 DEV · DEV-EXT found | Clear: false (14 photos, 17,567 px reviewed mask) |
|---|---|---|---|---|---|---|---|---|---|
| Step0 final (product) | 71/108 | 96 (4.36) | 48 | 75 | 1 | 0 · 5 | — | 60/81 · 11/27 | 0 (earlier record) |
| Dewiin anyacne / tiles — before filter | 81/108 | 54 (2.45) | 4 | 53 | 51 | 4 · 20 | +20 / −10 | 63/81 · 18/27 | 0 (1 points) |
| Dewiin anyacne / tiles — **after Step0 filter** | 75/108 | 45 (2.05) | 3 | 41 | 0 | 0 · 4 | +14 / −10 | 62/81 · 13/27 | 0 (1 points) |
| tristan-gray / tiles — before filter | 79/108 | 70 (3.18) | 1 | 47 | 26 | 2 · 11 | +22 / −14 | 60/81 · 19/27 | 0 (0 points) |
| tristan-gray / tiles — **after Step0 filter** | 71/108 | 58 (2.64) | 1 | 37 | 0 | 0 · 1 | +14 / −14 | 59/81 · 12/27 | 0 (0 points) |
| carsten12 / tiles — before filter | 45/108 | 24 (1.09) | 0 | 26 | 13 | 0 · 3 | +11 / −37 | 34/81 · 11/27 | 0 (0 points) |
| carsten12 / tiles — **after Step0 filter** | 43/108 | 16 (0.73) | 0 | 20 | 0 | 0 · 1 | +9 / −37 | 34/81 · 9/27 | 0 (0 points) |

Filter-removed targets stay in the denominator.

## 3. What the filter removed

**Targets lost by the filter** (all because the photo is a side capture and only the exposed cheek is analysed):
- dewiin-anyacne/tiles: 0a8a14a662a5#P1 (OUTSIDE_SOURCE_SUPPORT, box 0.0643 fw), 0a8a14a662a5#P20 (OUTSIDE_SOURCE_SUPPORT, box 0.0383 fw), 0a8a14a662a5#P28 (OUTSIDE_SOURCE_SUPPORT, box 0.0515 fw), 0a8a14a662a5#P3 (OUTSIDE_SOURCE_SUPPORT, box 0.0501 fw), 0a8a14a662a5#P9 (OUTSIDE_SOURCE_SUPPORT, box 0.066 fw), 8ad2e156eef7#P1 (OUTSIDE_SOURCE_SUPPORT, box 0.0379 fw)
- tristan-gray/tiles: 0a8a14a662a5#P1 (OUTSIDE_SOURCE_SUPPORT, box 0.0426 fw), 0a8a14a662a5#P10 (OUTSIDE_SOURCE_SUPPORT, box 0.0449 fw), 0a8a14a662a5#P20 (OUTSIDE_SOURCE_SUPPORT, box 0.0444 fw), 0a8a14a662a5#P28 (OUTSIDE_SOURCE_SUPPORT, box 0.0575 fw), 0a8a14a662a5#P3 (OUTSIDE_SOURCE_SUPPORT, box 0.0478 fw), 0a8a14a662a5#P4 (OUTSIDE_SOURCE_SUPPORT, box 0.0412 fw), 0a8a14a662a5#P9 (OUTSIDE_SOURCE_SUPPORT, box 0.0645 fw), 8ad2e156eef7#P1 (OUTSIDE_SOURCE_SUPPORT, box 0.0405 fw)
- carsten12/tiles: 0a8a14a662a5#P1 (OUTSIDE_SOURCE_SUPPORT, box 0.07 fw), 0a8a14a662a5#P9 (OUTSIDE_SOURCE_SUPPORT, box 0.0863 fw)

- No target was lost to a size-dependent rule. The box sides of the lost boxes are 0.04–0.09 face width.
- All lost targets are on `0a8a14a662a5` and `8ad2e156eef7`, the same side-angle scope that removes Step0's 6 targets.

**All rejections, by reason:**
- dewiin-anyacne/tiles: OUTSIDE_SOURCE_SUPPORT 69, ANATOMICAL_HOLE 21, ANATOMICAL_HAIR_OR_NOT_SKIN 13
- tristan-gray/tiles: OUTSIDE_SOURCE_SUPPORT 50, ANATOMICAL_HOLE 11, ANATOMICAL_HAIR_OR_NOT_SKIN 11, ANATOMICAL_HAIR_DENSE 1
- carsten12/tiles: OUTSIDE_SOURCE_SUPPORT 27, ANATOMICAL_HOLE 5, ANATOMICAL_HAIR_OR_NOT_SKIN 2

**Clear photos (14 replay-pass Clear negatives)**
- Product masks were computed from geometry only; no model was run.
- There are no Step0 pre-filter records for Clear photos, so Step0's Clear parity cannot be checked. Step0's earlier Clear result (0 false points) comes from the stored product rows.
- The third-party models put only 1 point (Dewiin) on these 14 photos, and it is not on the reviewed mask.

## 4. Answer: is Dewiin's advantage kept after the product filter?

**Targets: only partly.**
- After the same filter, Dewiin finds **75**/108, against Step0's 71: **+4**, photo bootstrap 95% [−9, +18].
- Without the most influential photo (`a19346a0887a`) the difference is **−1**. The target advantage is no longer distinguishable.
- tristan-gray ties Step0 at 71 (0, [−16, +16]). carsten12 finds 43 (−28).
- Of the 10 targets Dewiin found before the filter, 6 are lost to the side-angle scope rule, exactly like Step0's 6.

**False points: yes, the advantage holds.**
- After the filter, Dewiin has **45** false points on reviewed skin against Step0's **96**: −51 [−100, −8]. The interval excludes 0.
- It has **3** duplicates against Step0's **48**, and **0** non-skin points.
- tristan-gray has 58 false points (−38, [−81, 0]).
- carsten12 has 16 false points (−80) but misses many more targets.

**Trade-offs after the same post-processing**

| Row | Found | False points | Duplicates |
|---|---|---|---|
| Dewiin | 75 | 45 | 3 |
| Step0 | 71 | 96 | 48 |
| tristan-gray | 71 | 58 | 1 |
| carsten12 | 43 | 16 | 0 |

**Open limits**
- 108 targets on 22 photos, labelled by one non-expert, non-blind AI review, on the same DEV set used for every earlier comparison. 209 UNCERTAIN points are excluded.
- Confidence and NMS settings differ between models.
- The post-hoc layer-2 view exists only for the pre-filter false points. Dewiin's 45 are a subset of its 54, whose layer-2 view was 35 plain skin, 2 lesion just outside r, 16 uncertain and 1 scar.
- Licence remains unresolved.

**Records**
- `docs/acne-external-filter-results-20261016.json`: tables, lost targets with reasons, Clear results, input hashes.
- Not in Git: raw per-photo filter outputs in `audit-results/acne-external-filter/results.json`.
