# Same reviewed-skin scope: which existing method finds more distinct targets, and with how many false points? (2026-10-16)

**What this is**
- A single diagnostic comparison on the same 28 DEV photos, against **AI engineering point labels** (frozen layer 1).
- It is not an independent test, not expert validation and not product acceptance.
- Licence status is a separate matter: all third-party weights here are Ultralytics-trained, with AGPL-3.0 metadata.

**What was used**
- Stored predictions only; no new inference.
  - Step0 final: the stored product rows.
  - Step0 before filter: the recorded trace.
  - Third-party rows: the verified re-generated stored rows.
- No change to confidence, NMS, class mapping or weights.
- No live-camera, capture or guidance code was touched.

**Settings differ between rows.** Step0 uses conf .30 with NMS .30. The third-party rows use Ultralytics conf .25 and NMS .7 inside each tile, then a .30 box-NMS merge across tiles. This is not a controlled architecture comparison.

**Protocol** (`docs/acne-common-scope-protocol-20261016.json`, sha `8bd3f0c9…`) was committed before any number was computed (`3fd0dec`).

## 1. Common scope

**Evaluation mask**
- The frozen layer-1 reviewed-skin mask, the same for every row: 22 photos, 8.9 MP.
- **In-scope target** = a layer-1 TARGET whose point lies inside that mask. The same rule applies to every target, found or missed.
- **108 of 114 targets are in scope.** The 6 outside:
  - 3 on the close-up/padded photo `29069058884f`, which has no reviewed mask: #P1, #P2, #P3;
  - 3 inside excluded areas of the mask (hair, eye/brow margin): `0a8a14a662a5` #P5 and #P12, `933e40d730e0` #P10.
- Predictions near an out-of-scope target count as neither a hit nor a false point.

**Counting rules (unchanged)**
- A point is the box centre, in source px. Tolerance r = 0.03 × face width.
- Matching is deterministic one-to-one: maximum cardinality, then minimum distance.
- **False** = unmatched point inside the reviewed mask, with no TARGET, UNCERTAIN or other-category point within r.
- **Duplicates, UNCERTAIN and non-skin points are separate columns.** Non-skin means outside the face oval.

## 2. Comparison table (common scope, layer 1)

| Method / stage | In-scope targets N | Found | False points (per reviewed photo, 22) | Duplicates | On UNCERTAIN | Non-skin | vs Step0 final: gained / lost |
|---|---|---|---|---|---|---|---|
| Step0 final (product) | 108 | **71** (66%) | **96** (4.36/photo) | 48 | 75 (+9 other, +0 near out-of-scope) | 1 (+0 unreviewed, +5 empty-mask photo) | — |
| Step0 before region/anatomical filter (diagnostic only) | 108 | **77** (71%) | **111** (5.05/photo) | 52 | 89 (+11 other, +2 near out-of-scope) | 44 (+6 unreviewed, +9 empty-mask photo) | +6 / −0 |
| Dewiin anyacne / tiles | 108 | **81** (75%) | **54** (2.45/photo) | 4 | 53 (+6 other, +4 near out-of-scope) | 51 (+4 unreviewed, +20 empty-mask photo) | +20 / −10 |
| tristan-gray / tiles | 108 | **79** (73%) | **70** (3.18/photo) | 1 | 47 (+5 other, +5 near out-of-scope) | 26 (+2 unreviewed, +11 empty-mask photo) | +22 / −14 |
| carsten12 / tiles | 108 | **45** (42%) | **24** (1.09/photo) | 0 | 26 (+3 other, +3 near out-of-scope) | 13 (+0 unreviewed, +3 empty-mask photo) | +11 / −37 |

**Separate post-hoc layer-2 view of the false points.** This does not change the table above. Layer 2 reviewed only Step0 final, Dewiin and tristan-gray.

| Row | False points (layer 1) | Plain skin | Plain skin, lesion just outside r | Uncertain | Scar/pigment/mole |
|---|---|---|---|---|---|
| Step0 final | 96 | 55 | 20 | 19 | 2 |
| Dewiin | 54 | 35 | 2 | 16 | 1 |
| tristan-gray | 70 | 41 | 12 | 14 | 3 |

The 19 Step0 points that layer 2 calls uncertain stay counted as false in layer 1; they are not silently removed.

**Original 114-target results (reference, unchanged; `acne-point-relabel-report-20261016.md`):**

| Row | Found / 114 | False points |
|---|---|---|
| Step0 | 71 | 96 |
| Dewiin tiles | 85 | 54 |
| tristan-gray tiles | 84 | 70 |
| carsten12 tiles | 48 | 24 |

## 3. Sets, influence, before/after the Step0 filter

| Row | v4 DEV found/81 · false | DEV-EXT found/27 · false | Diff vs Step0 final | Photo bootstrap 95% | Most influential photo | Diff without it |
|---|---|---|---|---|---|---|
| Step0 before region/anatomical filter (diagnostic only) | 62/81 · 75 | 15/27 · 36 | +6 | [0, 16] | `0a8a14a662a5` (+4) | +2 |
| Dewiin anyacne / tiles | 63/81 · 35 | 18/27 · 19 | +10 | [-3, 24] | `a19346a0887a` (+5) | +5 |
| tristan-gray / tiles | 60/81 · 43 | 19/27 · 27 | +8 | [-9, 26] | `0a8a14a662a5` (+5) | +3 |
| carsten12 / tiles | 34/81 · 8 | 11/27 · 16 | -26 | [-55, -4] | `933e40d730e0` (-11) | -15 |

**Step0 targets found before the region/anatomical filter and removed by it (6):** 0a8a14a662a5#P1, 0a8a14a662a5#P20, 0a8a14a662a5#P28, 0a8a14a662a5#P3, 8ad2e156eef7#P1, 8ad2e156eef7#P4.
- All six are `OUTSIDE_SOURCE_SUPPORT`: the photo was matched as a side capture, so only the exposed cheek is analysed.
- The filter also removes 15 false points, 4 duplicates and 43 non-skin points. Before the filter Step0 has 111 false points and 44 non-skin points; after it, 96 and 1.

**Against Step0 before the filter** (gained / lost):
- Dewiin: +15 / −11.
- tristan-gray: +17 / −15.
- carsten12: +10 / −42.

**Per photo** (found · false). Photos with no targets and no false points are omitted.

| Photo | Targets | Step0 final | Step0 before filter | Dewiin | tristan-gray | carsten12 |
|---|---|---|---|---|---|---|
| `933e40d730e0` | 19 | 17 · 12 | 17 · 12 | 15 · 4 | 13 · 9 | 6 · 4 |
| `0a8a14a662a5` | 15 | 7 · 4 | 11 · 11 | 10 · 1 | 12 · 5 | 5 · 1 |
| `46a79ef8d7a8` | 12 | 9 · 15 | 9 · 15 | 11 · 3 | 11 · 4 | 6 · 1 |
| `8a78e9d6efd5` | 11 | 11 · 13 | 11 · 13 | 10 · 0 | 9 · 1 | 5 · 0 |
| `77176e51db41` | 9 | 4 · 4 | 4 · 4 | 5 · 4 | 6 · 3 | 4 · 1 |
| `a19346a0887a` | 9 | 4 · 7 | 4 · 7 | 9 · 13 | 9 · 16 | 6 · 1 |
| `33e42c603f10` | 7 | 4 · 5 | 4 · 5 | 3 · 1 | 3 · 1 | 1 · 0 |
| `8ad2e156eef7` | 6 | 3 · 1 | 5 · 4 | 2 · 2 | 2 · 0 | 1 · 0 |
| `9334509b3ae3` | 5 | 2 · 16 | 2 · 17 | 3 · 6 | 2 · 10 | 1 · 4 |
| `b9dd30fde312` | 4 | 0 · 0 | 0 · 0 | 2 · 7 | 2 · 5 | 2 · 9 |
| `a2cd98ca9566` | 3 | 3 · 2 | 3 · 2 | 3 · 1 | 2 · 1 | 3 · 0 |
| `cb5ca5ca9a33` | 3 | 2 · 1 | 2 · 2 | 3 · 0 | 3 · 1 | 3 · 2 |
| `e643059207e1` | 3 | 3 · 5 | 3 · 5 | 3 · 1 | 3 · 2 | 2 · 1 |
| `a007c24408ff` | 1 | 1 · 0 | 1 · 0 | 1 · 0 | 1 · 0 | 0 · 0 |
| `dc089b3f7c38` | 1 | 1 · 1 | 1 · 1 | 1 · 1 | 1 · 2 | 0 · 0 |
| `2ad92b5eb9de` | 0 | 0 · 0 | 0 · 0 | 0 · 1 | 0 · 2 | 0 · 0 |
| `453d2656c394` | 0 | 0 · 1 | 0 · 1 | 0 · 4 | 0 · 2 | 0 · 0 |
| `5aa51f53f86c` | 0 | 0 · 2 | 0 · 2 | 0 · 4 | 0 · 2 | 0 · 0 |
| `b4ec4968102b` | 0 | 0 · 1 | 0 · 4 | 0 · 1 | 0 · 4 | 0 · 0 |
| `c412587e8b7f` | 0 | 0 · 6 | 0 · 6 | 0 · 0 | 0 · 0 | 0 · 0 |

**Timing** is not compared. Step0 times come from the desktop CPU (whole chain); the third-party times come from the cloud CPU (model only).

Legend figures (not in Git, `audit-results/acne-common-scope/figures/`) show the five rows side by side on the same photos: `0a8a14a662a5`, `933e40d730e0`, `a19346a0887a`, `9334509b3ae3`. Colours encode status only: found/missed in-scope target, out-of-scope target, matched, duplicate, false, uncertain/other, unreviewed/non-skin.

## 4. Answers

**How much of Step0's gap comes from the product filter?**
- Of Dewiin's +10 lead over Step0 final (81 vs 71 of 108), 6 targets are ones Step0 detects but its side-angle region filter removes.
- Before the filter, Step0 finds 77. The remaining gap is +4 for Dewiin and +2 for tristan-gray.
- So **more than half of the lead comes from the filter's scope rule** (60% for Dewiin, 75% for tristan-gray). The rest is model differences that go both ways: Dewiin gains 15 and loses 11 targets against Step0 before the filter.

**Difference in the same reviewed-skin scope**
- Found: Dewiin 81, tristan-gray 79, Step0 final 71, Step0 before filter 77, carsten12 45 (of 108).
- False points: Dewiin 54, tristan-gray 70, Step0 final 96, Step0 before filter 111, carsten12 24.
- Duplicates: Step0 48–52, the others 0–4.
- Non-skin points: Step0 final 1, Dewiin 51, tristan-gray 26, carsten12 13.
- Dewiin vs Step0 final is +10 [−3, +24]; tristan-gray is +8 [−9, +26]. Both intervals include 0. Without the most influential photo the difference is +5 and +3.

**Trade-offs between found targets and false marks**

| Method | Found | False points | Other cost |
|---|---|---|---|
| Dewiin | most (81) | 54 | 51 non-skin points: no anatomical filter |
| tristan-gray | 79 | 70 | 26 non-skin |
| Step0 final | 71 | most (96) | 48 duplicates; the filter keeps it on the face (1 non-skin), but side captures lose targets |
| carsten12 | 45 | fewest (24) | misses 37 Step0 targets |

**Is the evidence enough to decide? No.**
- 108 targets on 22 photos; the bootstrap intervals include 0.
- The labels are one non-expert, non-blind AI review, with 209 UNCERTAIN points excluded.
- Step0's lead/lag depends on the side-angle scope rule, which is a product policy rather than a model property.
- The third-party models were not run through Step0's anatomical filter, so their non-skin points would be partly removed in a product. That was not measured.
- The settings differ.
- The concrete open questions:
  1. Whether the third-party models keep their lead after the same product filter.
  2. Whether Step0's 96 false points on plain skin, and the duplicates, are acceptable to the product.
