# Box-area anatomical filter vs a box-size-independent POINT filter (offline staging, 2026-10-16)

**What this is**
- An offline staging comparison on stored pre-filter predictions only. No training, no inference, and no change to weights, confidence, class map, NMS, side-angle classification, visible regions, analysis scope, labels or evaluation masks.
- The point filter is a separate staging module. It is **not** connected to the product, and acne stays `accepted:false, file:null`.
- The previous finding stands: in the last run the box-size rules removed **no** target; the target losses came from the side-angle scope. This is therefore **not** a fix of a proven box error. It measures what happens when the decision is made independent of box size.
- Labels are frozen layer-1 **AI engineering** points on the **re-used DEV set**. This is not an independent test, expert validation or product acceptance.
- Licence is separate and unchanged.

**Protocol** (`docs/acne-point-filter-protocol-20261016.json`, sha `d7370362…`) and module (`services/core-api/acne_point_support_staging.py`, sha `f5d4bec2…`, `point-anatomical-support-staging-v1`) were committed before any result (`4d52e00`). There is one version and one comparison; the rule was not revised after seeing results.

## 1. Old vs new rule

| Check | Old box filter (`principled_accepted_boxes`, unchanged) | New point filter (`point_accepted`) |
|---|---|---|
| Point | – (box) | px = (x1+x2)/2, py = (y1+y2)/2, never moved |
| Source bounds | box clipped to the raster; rejected only if the clipped box is empty; centre clamped | non-finite or outside image → reject; no clamping |
| Analysis scope | a box overlapping the raster can pass with a clamped centre | point outside the raster (visible-region scope) → reject |
| Exclusion | centre on exclusion **or box exclusion fraction > .25** | point on exclusion |
| Hair | **box hair fraction > .25**; centre on hair → redness/contrast rescue if box skin ≥ .50 | point on hair → reject; no rescue |
| Skin support | centre not skin → rescue; **box skin fraction < .50** → reject | point not on `acne_skin` → reject; no rescue |
| Region | largest **box** envelope∩skin overlap ≥ .15, else distance fallback (midline, .15 fw) | envelope containing the point (first in order forehead, rightCheek, leftCheek, nose, chin), else the same distance fallback |

**Sampling:** the analysis pixel is floor((p − origin) × scale), using the existing origin/scale contract. No review or ground-truth mask is an input.

**Tests** (`tests/unit/test_acne_point_support_staging.py`): **8/8 pass**, plus 3/3 earlier coordinate tests. They cover:
- same centre with 4 box sizes gives the same decision and region;
- a point on skin is accepted;
- points on eye/mouth, on hair or out of scope are rejected;
- a point outside the image is rejected without clamping;
- origin/scale mapping at a pixel boundary;
- deterministic region choice where envelopes overlap;
- the side-angle scope is kept (no fallback across the midline);
- the output does not depend on any label input.

## 2. Old-path parity (before any new number)

The unchanged box filter on the same pre-filter inputs and the same recomputed product masks reproduces the committed results exactly:

| Row | Found | False | Duplicates |
|---|---|---|---|
| Step0 | 71/108 | 96 | 48 |
| Dewiin | 75/108 | 45 | 3 |
| tristan-gray | 71/108 | 58 | 1 |
| carsten12 | 43/108 | 16 | 0 |

Step0's box-filtered finals equal the stored finals on 28/28 photos.

## 3. One comparison table (common scope: 108 in-scope targets, frozen reviewed masks, r = 0.03 × face width, one-to-one; removed targets stay in the denominator)

| Model | Stage | Found | False on reviewed skin | Duplicates | On UNCERTAIN | Non-skin (outside oval) | Unreviewed: oval · empty-mask photo | vs Step0 box: gained / lost | Clear: false (14 photos) |
|---|---|---|---|---|---|---|---|---|---|
| Step0 | before filter | 77/108 | 111 | 52 | 89 | 44 | 6 · 9 | +6 / −0 | — |
| Step0 | old box filter | 71/108 | 96 | 48 | 75 | 1 | 0 · 5 | — | — |
| Step0 | **new point filter** | 71/108 | 96 | 48 | 75 | 1 | 0 · 5 | +0 / −0 | — |
| Dewiin anyacne / tiles | before filter | 81/108 | 54 | 4 | 53 | 51 | 4 · 20 | +20 / −10 | 0 (1 pts) |
| Dewiin anyacne / tiles | old box filter | 75/108 | 45 | 3 | 41 | 0 | 0 · 4 | +14 / −10 | 0 (1 pts) |
| Dewiin anyacne / tiles | **new point filter** | 75/108 | 46 | 3 | 41 | 0 | 0 · 4 | +14 / −10 | 0 (1 pts) |
| tristan-gray / tiles | before filter | 79/108 | 70 | 1 | 47 | 26 | 2 · 11 | +22 / −14 | 0 (0 pts) |
| tristan-gray / tiles | old box filter | 71/108 | 58 | 1 | 37 | 0 | 0 · 1 | +14 / −14 | 0 (0 pts) |
| tristan-gray / tiles | **new point filter** | 71/108 | 60 | 1 | 37 | 0 | 0 · 1 | +14 / −14 | 0 (0 pts) |
| carsten12 / tiles | before filter | 45/108 | 24 | 0 | 26 | 13 | 0 · 3 | +11 / −37 | 0 (0 pts) |
| carsten12 / tiles | old box filter | 43/108 | 16 | 0 | 20 | 0 | 0 · 1 | +9 / −37 | 0 (0 pts) |
| carsten12 / tiles | **new point filter** | 43/108 | 16 | 0 | 20 | 0 | 0 · 1 | +9 / −37 | 0 (0 pts) |

Step0 has no pre-filter records for Clear photos, so its Clear rows are not evaluable here. The earlier stored Step0 Clear result is 0 false points.

## 4. What changed between the box filter and the point filter

| Model | Accept/reject decisions changed | Region-only changes | Targets gained | Targets lost |
|---|---|---|---|---|
| Step0 | 1 | 48 | none | none |
| Dewiin anyacne / tiles | 1 | 32 | none | none |
| tristan-gray / tiles | 2 | 25 | none | none |
| carsten12 / tiles | 1 | 13 | none | none |

**All 5 changed accept/reject decisions go the same way:**
- The box filter rejected them as `ANATOMICAL_HOLE` **only because of the box exclusion fraction** (.27–.41). Their centres are not on the exclusion mask, so the point filter accepts them.
- Where they land, in the legend figure (not in Git, `audit-results/acne-point-filter/figures/`):

| Model | Photo | Location | Scored as |
|---|---|---|---|
| Dewiin | `a19346a0887a` | Inner corner of the upper eyelid | false |
| tristan-gray | `2ad92b5eb9de` | Lower eyelid, just below the eye | false |
| tristan-gray | `33e42c603f10` | Philtrum between nostril and lip | false |
| Step0 | `29069058884f` (misfit close-up) | Just outside a misplaced exclusion | near an out-of-scope target |
| carsten12 | `29069058884f` (misfit close-up) | Just outside a misplaced exclusion | near an out-of-scope target |

**Region-only changes** (Step0 48, Dewiin 32, tristan-gray 25, carsten12 13) are nearly all nose → forehead. Where the nose and forehead envelopes overlap at the glabella, the pre-fixed REGIONS order picks forehead; the box filter picked the larger overlap (nose). Region does not affect the point scoring, but it would change which region a point is reported under.

## 5. Answer

**The result is the same or slightly worse.**
- Found targets: unchanged for every model (Step0 71, Dewiin 75, tristan-gray 71, carsten12 43).
- Duplicates and non-skin points: unchanged.
- False points: Dewiin 45 → 46, tristan-gray 58 → 60; Step0 96 and carsten12 16 unchanged.
- Clear photos: unchanged (Dewiin 1 point, not on the reviewed mask).

**What we learned**
- Removing box-size dependence does not change any target on this set.
- The box exclusion-fraction rule was in fact acting as a **margin around the eyes and nostrils**. Without it, centre points just outside the exclusion mask are accepted.
- A size-independent filter would need an explicit point margin around these structures. That would be a new rule, so it was **not** tried here.

**Ranking:** unchanged. Dewiin keeps its lead over Step0 in false points (46 vs 96) and is +4 in targets (75 vs 71), as before.

**Not claimed:** no independent test, no expert validation, no product acceptance, no licence clearance. The point filter is staging-only and is not active in the product.

**Records**
- `docs/acne-point-filter-results-20261016.json`: tables, per-target classes, changed decisions with old/new reasons, Clear results, code/input hashes.
- Not in Git: raw outputs in `audit-results/acne-point-filter/results.json`.

## 6. Closure (2026-10-16, on request)

This experiment is **closed**.
- **Not enabled:** the point filter (`acne_point_support_staging.py`) stays an offline staging module and is not imported or used anywhere in the product.
- **Reference unchanged:** the unchanged box filter (`principled_accepted_boxes`) remains the reference.
- **No further variants:** no buffer, margin, threshold or filter variant is to be tried as a follow-up of this run.

**Point display and acceptance filtering are separate questions.**
- The point metric evaluates a prediction by its box centre. Any prediction **accepted by the existing box filter** can therefore be shown as a centre point, with the same acceptance decision, region and coordinates as today.
- Showing points does not require the point acceptance filter. This run only tested replacing the acceptance rule, and that replacement did not help.

**Open staging limitation:**
- The point filter's region assignment (first containing envelope in the order forehead, rightCheek, leftCheek, nose, chin) moves predictions in the nose/forehead overlap from **nose to forehead**. The counts are Step0 47 of 48 region-only changes, Dewiin 31/32, tristan-gray 24/25, carsten12 12/13.
- This does not change the point scores, but it would change which region a point is reported under.
- It is recorded as an unresolved staging limitation. It is not corrected here, and no product file was changed.

**Kept locally:**
- Code: module, tests, runner and scorer.
- Comparisons: this report and the results JSON.
- Reproduction records:
  - raw `audit-results/acne-point-filter/results.json`;
  - `audit-results/acne-step0-trace`;
  - the verified external stored rows.
- Copies, with hashes, are in `TOGG\claude-progress`.
