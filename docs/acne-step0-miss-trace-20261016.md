# Step0 misses: model or product chain? Stage trace on the frozen layer-1 targets (2026-10-16)

**Scope and limits**
- This is a diagnostic only. There is no training, no new model or mode, no threshold change and no integration. Acne stays `accepted:false, file:null`.
- Layer 1 (114 TARGET, 209 UNCERTAIN, 16 other-category points), the separate post-hoc layer 2, and the tolerance r = 0.03 × face width are all unchanged. Earlier FAIL and label records are unchanged.
- The numbers are **localisation catches against AI engineering point labels** on the same 28 DEV photos. They are not ground-truth accuracy.
- Dewiin, tristan-gray and carsten12 were not re-run.

**Inference used**
- Only stored outputs were used where they existed. The stored Step0 rows keep final boxes only.
- Step0 was therefore run **once per photo** through the unchanged label-free chain (`eval_acne_v5_independent.run_photo`), with the same weights (`18e94a95…`) and fixed settings.
- An observing wrapper (`scripts/skin-research/trace_step0_chain.py`) recorded:
  - raw head outputs (obj×cls ≥ .01);
  - the ≥ .30 candidates;
  - the NMS-selected boxes;
  - the filter's assigned and rejected boxes, with reasons;
  - the product masks.
- **Final boxes equal the stored rows on 28/28 photos.**
- Traces and masks are kept outside Git, under `audit-results/acne-step0-trace/` (index with hashes), and are copied to `TOGG\claude-progress`.

## 1. Coordinate and scale check

- **Same coordinate system:**
  - Layer-1 points and Step0 final boxes are both in source pixels of the same product input file (sha256 checked).
  - Step0 runs on native tiles, so model input and source pixels are at scale 1.
  - Face width is |landmark 234 − landmark 454| in source pixels, and equals the layer-1 `faceWidthPx` on 28/28 photos.
- **Analysis raster:**
  - The staging filter maps boxes to the analysis raster with (source − origin) × scale. This is the same convention the product uses to build its masks (`appearance_analysis.analyze_skin`: origin = visible-mesh bounding box − pad, scale = analysis/source).
  - Accepted boxes keep their source coordinates unchanged. On every photo, assigned = final ⊂ NMS, and assigned + rejected = NMS.
- **Tests** (`tests/unit/test_acne_step0_trace.py`, 3/3 pass):
  - tile-local → source mapping and clipping;
  - the tile grid covers the crop with at least 48 px interior margin;
  - the filter's origin/scale mapping, unchanged accepted coordinates, and rejection outside the raster or on exclusion.
- **Empirical check:** on front-angle photos, every `OUTSIDE_SOURCE_SUPPORT` rejection lies outside the face oval (6 of 6). A coordinate offset would also reject boxes inside the face.

**Tolerance per photo (r = 0.03 × face width, source px):**

| Photo | Set | Size | Face width px | r px | Product angle (visible regions) | Targets |
|---|---|---|---|---|---|---|
| `0a8a14a662a5` | devext | 1280×1280 | 573.1 | **17.2** | SIDE (rightCheek) | 17 |
| `29069058884f` | devext | 640×640 | 331.3 | **9.9** | SIDE (leftCheek) | 3 |
| `2ad92b5eb9de` | dev | 2448×3264 | 1194.3 | **35.8** | FRONT (all 6 regions) | 0 |
| `33e42c603f10` | dev | 1280×1280 | 488.1 | **14.6** | FRONT (all 6 regions) | 7 |
| `453d2656c394` | dev | 1920×2560 | 1107.0 | **33.2** | FRONT (all 6 regions) | 0 |
| `46a79ef8d7a8` | dev | 1280×1280 | 824.3 | **24.7** | FRONT (all 6 regions) | 12 |
| `5aa51f53f86c` | devext | 1932×2576 | 1097.2 | **32.9** | FRONT (all 6 regions) | 0 |
| `6dcf4d7ab398` | devext | 640×640 | 348.0 | **10.4** | SIDE (rightCheek) | 0 |
| `77176e51db41` | dev | 1280×1280 | 592.5 | **17.8** | FRONT (all 6 regions) | 9 |
| `7b425c76a80f` | devext | 640×640 | 250.6 | **7.5** | FRONT (all 6 regions) | 0 |
| `8a78e9d6efd5` | dev | 1280×1280 | 586.1 | **17.6** | FRONT (all 6 regions) | 11 |
| `8ad2e156eef7` | dev | 1280×1280 | 594.0 | **17.8** | SIDE (leftCheek) | 6 |
| `9334509b3ae3` | devext | 1280×1280 | 595.5 | **17.9** | FRONT (all 6 regions) | 5 |
| `933e40d730e0` | dev | 1280×1280 | 582.3 | **17.5** | FRONT (all 6 regions) | 20 |
| `a007c24408ff` | dev | 1280×1280 | 690.7 | **20.7** | SIDE (leftCheek) | 1 |
| `a19346a0887a` | dev | 2316×3088 | 1211.5 | **36.3** | FRONT (all 6 regions) | 9 |
| `a2cd98ca9566` | dev | 1280×1280 | 565.8 | **17.0** | FRONT (all 6 regions) | 3 |
| `aff1efde301c` | dev | 1280×1280 | 565.8 | **17.0** | SIDE (rightCheek) | 0 |
| `b4ec4968102b` | devext | 1280×1280 | 650.7 | **19.5** | SIDE (rightCheek) | 0 |
| `b9dd30fde312` | devext | 640×640 | 234.4 | **7.0** | SIDE (rightCheek) | 4 |
| `c1ae0b437492` | devext | 1920×2560 | 1205.9 | **36.2** | FRONT (all 6 regions) | 0 |
| `c412587e8b7f` | dev | 1280×1280 | 595.8 | **17.9** | FRONT (all 6 regions) | 0 |
| `cb5ca5ca9a33` | devext | 241×300 | 163.6 | **4.9** | FRONT (all 6 regions) | 3 |
| `d79fcee141ca` | dev | 1944×2592 | 1102.7 | **33.1** | SIDE (leftCheek) | 0 |
| `dc089b3f7c38` | dev | 1936×2592 | 890.1 | **26.7** | FRONT (all 6 regions) | 1 |
| `e643059207e1` | dev | 1280×1280 | 434.4 | **13.0** | FRONT (all 6 regions) | 3 |
| `eeb843cadf66` | devext | 640×640 | 275.8 | **8.3** | SIDE (rightCheek) | 0 |
| `f30396853c41` | dev | 2448×3264 | 960.6 | **28.8** | FRONT (all 6 regions) | 0 |

## 2. Per-target trace: all 43 Step0 misses (all 114 targets are recorded in the JSON)

Stages followed for every target:
- source and reviewed mask;
- product crop and tile (tile id and tile-local px);
- analysis raster, visible-region envelope and masks at the target;
- raw head candidate within r;
- ≥ .30 candidate;
- NMS;
- filter result and reason;
- final box and the frozen one-to-one result.

**Every target is inside the product crop and inside a tile, at least 48.8 px from the tile edge.** No target is lost to crop, padding or tile mapping.

| Loss stage (first loss; other causes listed) | Targets | Target IDs | Evidence | Implementation error, or model/product-scope limit? |
|---|---|---|---|---|
| Product scope: the side-angle capture analyses only the exposed cheek. The model **did** detect the lesion. | **7** | 0a8a14a662a5 #P1, #P3, #P20, #P28; 29069058884f #P3; 8ad2e156eef7 #P1, #P4 | ≥ .30 candidate (.47–.81) within r, kept by NMS. The filter rejects it as `OUTSIDE_SOURCE_SUPPORT` because the target lies outside the analysis raster. The replayed frontend matched LEFT/RIGHT (|yaw| above the .20 front limit, e.g. .33 and −.39), so the snapshot holds only the exposed cheek mesh (`skinMultiAngle.ts`: "Side captures only measure the exposed cheek"). | **Product scope** (contract), not a code error. The side choice is correct: the analysed cheek is the visible one (checked visually on 3 photos; the close-up cannot be judged). |
| Model below .30 or no candidate, **and** outside the side-angle scope | **8** | 0a8a14a662a5 #P4, #P5, #P9, #P10, #P12, #P30; 29069058884f #P1; b9dd30fde312 #P7 | Best nearby score .02–.21 or none. The target is also outside the raster of the matched side angle. | Model limit; product scope would drop it anyway |
| Filter: anatomical hole on a non-full-face close-up | **1** | 29069058884f #P2 | ≥ .30 candidate (.66) kept by NMS. Rejected `ANATOMICAL_HOLE`: the target lies on the landmark-derived exclusion mask of a processed, padded close-up. Landmarks fitted to a cheek crop give misplaced eye/mouth holes. | Input/landmark limitation of an unsuitable photo, not a code error |
| Model, target in scope: best nearby score below .30 | **21** | 33e42c603f10 #P1, #P13, #P14; 46a79ef8d7a8 #P8, #P10, #P11; 77176e51db41 #P1, #P8, #P9, #P11, #P14; 8ad2e156eef7 #P12; 9334509b3ae3 #P1, #P8; 933e40d730e0 #P9, #P10, #P22; a19346a0887a #P2, #P18; b9dd30fde312 #P5; cb5ca5ca9a33 #P3 | Raw candidate within r, but its best obj×cls is .010–.298 (median ≈ .13). Six of these targets also lie outside every visible-region envelope and one on the exclusion mask (secondary scope causes, listed in the JSON). | **Model** |
| Model, target in scope: no raw candidate (≥ .01) within r | **6** | 9334509b3ae3 #P2; a19346a0887a #P6, #P13, #P19; b9dd30fde312 #P1, #P2 | No head output within r at any score ≥ .01. b9dd30fde312 has a 234 px face, so its lesions are a few px across. | **Model** |
| NMS | 0 | – | – | – |
| Final coordinate return / one-to-one matching | 0 | – | – | – |

**Forehead and 0a8a14a662a5:**
- The product replay matched this photo as a LEFT side capture (yaw .33), so the analysis covers only the right-cheek mesh.
- All 10 misses on this photo lie outside that raster: 7 on the forehead or temple, 1 on the far cheek, 2 on the lower face.
- Step0 detected 4 of them (scores .52–.81), but the filter removed them as outside support. For the other 6 the model was also below .30 or had no candidate.
- On front-angle photos the forehead is analysed. Forehead misses there are model misses (46a79ef8d7a8 #P8, #P10, #P11; 33e42c603f10 #P1; a19346a0887a #P2).

## 3. False points and duplicates through the stages

The categories follow the frozen layer-1 scoring order and were not mixed. UNCERTAIN and other categories were never counted as false.

All 305 Step0 final points:

| Class | Points | Stage evidence |
|---|---|---|
| Matched TARGET | 71 | – |
| **False on reviewed, non-uncertain skin** | **96** | All 96 passed the model (median score .49), NMS and filter. All 96 centres lie on `acne_skin` and not on hair. 93 were assigned by envelope overlap, 3 by distance fallback. Mostly on 9334509b3ae3 (16), 46a79ef8d7a8 (15), 8a78e9d6efd5 (13), 933e40d730e0 (12). |
| **Extra prediction on an already matched target (duplicate)** | **48** | Every duplicate has IoU < .30 with the matched box (median .14), so hard NMS .30 keeps both. Boxes are of similar size (median size ratio .94) and not nested. 27 come from the same tile, 21 from overlapping tiles. |
| On UNCERTAIN / other layer-1 category | 75 / 9 | Not counted as false |
| Non-skin (outside face oval) | 1 | – |
| Unreviewed photo (empty mask) | 5 | – |
| Coordinate or mask application error | **0** | None of the 96 false points is centred on exclusion or hair; accepted boxes are inside the raster by construction; coordinates are unchanged through the filter |

**Post-hoc layer-2 view of the 96 false points** (separate, does not change layer 1):

| Layer-2 finding | Points |
|---|---|
| Plain skin | 55 |
| Plain skin, with a lesion just outside r | 20 |
| Uncertain | 19 |
| Scar/pigment or mole | 2 |

Of these, 6 sit on non-lesion structures that lie inside the reviewed mask: lip border (3), nostril (1), specular highlight (1), hair edge (1). Layer-1 counts are not corrected by this; it is reported only as a separate view.

Duplicates and false points therefore come from the model's detections and the fixed NMS/filter policy. They do not come from a coordinate or mask implementation error. Changing NMS or the merge radius would be a policy change and was not done.

## 4. Answer

| Group | Targets |
|---|---|
| **True model losses** (target inside crop, tiles and analysed scope; no ≥ .30 detection within r) | **27** (21 below .30, 6 no candidate) |
| **Chain losses only** (model detected at ≥ .30 and NMS kept it, but the product chain dropped it) | **8**: 7 by side-angle visible-region scope, 1 by the anatomical-hole exclusion on a misfit close-up |
| **Both** (model below .30 or no candidate, and outside the side-angle scope) | **8** |
| Image, crop, tile or coordinate losses | **0** |

No implementation error was proven. Coordinates, scale, crop origin, tile mapping and mask indexing agree with the product contract (tests and 28/28 final parity), so **nothing was fixed** and no before/after measurement applies.

The 8 chain-only losses follow the existing product contract (side captures analyse only the exposed cheek) and one unsuitable close-up input. Changing them would be a policy or gating decision, not a bug fix.

## Files

- `docs/acne-step0-miss-trace-20261016.json`: per-target stage records for all 114 targets, categories, per-photo tolerance, and weight, code and input hashes.
- `scripts/skin-research/trace_step0_chain.py`: observing Step0 trace.
- `scripts/skin-research/external_acne/trace_targets.py`: stage logic.
- `tests/unit/test_acne_step0_trace.py`: coordinate tests.
- Not in Git: traces and masks in `audit-results/acne-step0-trace/` (and `.tgz`), index with hashes, and copies in `TOGG\claude-progress`.
