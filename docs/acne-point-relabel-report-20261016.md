# Acne point relabelling of the 28 DEV photos and rescoring of existing models (2026-10-16)

**Nature of this work.**
- The relabelling is an **AI (assistant) engineering review**. It was done after earlier model results on the same photos were known.
- It is **not blind**, **not independent**, **not expert-verified** and **not an acceptance test**.
- No training, threshold sweep, ensemble or integration was done.
- Original source labels, earlier FAIL reports, models and checkpoints are unchanged.
- Acne stays `accepted:false, file:null`.
- Licence status is a separate matter and is not part of the technical result (see `acne-external-models-20261016.md`).

## Records (all on `claude/acne-measurement-audit`, not pushed)

| Commit | Content |
|---|---|
| `dfed6e8` | Protocol (`acne-point-relabel-protocol-20261016.json`) incl. coordinate check, label rule, tolerance — fixed before review |
| `cd02fb6` | Layer 1 (`acne-point-relabel-layer1-20261016.json`, sha `fa1be5b4…`) — frozen before source boxes or model points were opened |
| `22bb8e4` | Scoring code + exact check of re-generated stored boxes |
| `fa486e1` | Layer-1 comparison results (`acne-point-relabel-layer1-comparison-20261016.json`) — frozen before layer 2 |
| `67396e7` | Layer-2 scope, fixed before any layer-2 sheet was viewed |
| `c7c265a` | Layer 2 (`acne-point-relabel-layer2-20261016.json`) — post-hoc, model/source-assisted, separate from layer 1 |

**Stored predictions.**
- The 36 third-party stored box records had been kept only in an earlier cloud workspace, which was reset.
- They were re-generated with the same weights (sha256 identical to the committed list) and the committed scripts and settings.
- **36/36 matched the committed earlier per-target and per-photo records exactly** (`acne-external-rows-regen-verify-20261016.json`). They are used only because of that check.
- Step0 rows are the original stored product-chain rows.

## 1. Coordinate and scale check

- All 201 source boxes lie inside their images and use the same source-pixel system as the stored predictions. The pack image is the product input file; it is not resized.
- Normalised by face width (MediaPipe landmarks 234–454), box sides are:
  - v4 DEV (137 boxes): median 0.054 face width (p10–p90: 0.023–0.103);
  - DEV-EXT (64 boxes): median 0.026 face width (p10–p90: 0.016–0.092).
- The size gap therefore remains after normalisation: it is a difference in what was labelled, not a pixel-scale artefact. The visual review below confirms it.

## 2. Labelling rule (protocol, fixed before review)

- **TARGET:** the centre of one visible acne-like single lesion (papule, pustule or whitehead-like bump).
- **Separate categories:** BLACKHEAD, SCAR_PIGMENT, PORE, MOLE, OTHER.
- **UNCERTAIN:** used when the photo does not allow a reliable decision.
- A scar or texture area is never one TARGET. Close but separately visible lesions get separate points. No clinical subtype diagnosis.
- **Reviewed-skin mask:** face oval minus eyes, brows and lips, minus regions marked not reviewable (hair, beard, blur, shadow, glare, seams, non-skin).
- **Empty masks (no negative claims):** collage photos (`6dcf4d7ab398`, `7b425c76a80f`, `eeb843cadf66`), the close-up/padded photo `29069058884f`, and the blurred/noisy photos `d79fcee141ca` and `c1ae0b437492`.
- **Tolerance:** r = 0.03 × face width in source px (about 4 mm on a ~14 cm face), with sensitivity runs at 0.02 and 0.05. Fixed before any comparison and never widened.

## 3. Layer 1 (frozen review)

- **Points:** 114 TARGET, 209 UNCERTAIN, 6 MOLE, 5 SCAR_PIGMENT, 5 OTHER.
- **Reviewed skin:** 8.9 MP on 22 photos.
- **Per-photo flags:** collage, upscaled, smoothed, noisy/sharpened, blurred and overexposed photos are flagged in the JSON.
- **Limits:** "Complete" applies only to the reviewed mask. On low-resolution and upscaled photos, magnification does not verify fine detail.
- **High UNCERTAIN count:** many small red or whitish marks cannot be separated from PIH, closed comedones or texture in these photos.

## 4. Agreement with the source labels (opened after the freeze)

**Source boxes**
- Only **32 of 201** source boxes contain a layer-1 TARGET; 38 if "within r of the box centre" is also allowed.
- No source box contains more than one layer-1 TARGET.
- The other boxes contain:
  - only UNCERTAIN points: 33;
  - SCAR_PIGMENT or OTHER: 4;
  - nothing, with the box centre on reviewed skin: 77;
  - nothing, with the box centre outside reviewed skin: 28;
  - nothing, on photos without a reviewed mask: 27.

**Layer-1 targets**
- **82 of 114** layer-1 TARGETs have no source box (79 with the lenient rule).
- Several sharp 1280-px DEV photos have **one** source box but 9–12 visible inflamed lesions: `46a79ef8d7a8`, `8a78e9d6efd5`, `77176e51db41`, `33e42c603f10`.

**Layer 2 on the 77 "nothing marked" source boxes** (post-hoc, source box shown):

| Result | Boxes |
|---|---|
| Area or texture box, not one lesion | 18 |
| Wide box containing a row of small papules not marked in layer 1 (`a19346a0887a`) | 1 |
| Scar or pigment | 8 |
| Uncertain | 33 |
| Nothing visible | 12 |
| A lesion I would mark | 5 |

Of those 5 lesions:
- 3 are the same lesion I had marked in layer 1, with my point just outside a small source box (0.015–0.026 face width away);
- 1 I had marked UNCERTAIN;
- 1 (`9334509b3ae3`) is a genuine layer-1 miss.

So the source labels are both **incomplete** (most visible lesions are unlabelled) and **inconsistent** (many boxes mark areas, scars or nothing clearly visible). Layer 1 also has misses, but few found this way.

## 5. Rescoring all 37 stored model/mode records against layer 1

**Columns**
- Distance one-to-one matching: maximum cardinality, then minimum distance, r = 0.03 face width.
- **False** = unmatched point on reviewed skin with no layer-1 point within r. 8.9 MP of reviewed skin on 22 photos.
- **Unc · oth** = points on UNCERTAIN or other-category layer-1 points; never counted as right or wrong.
- **Unreviewed** = inside the face oval but outside the mask · outside the face oval (non-skin or unreviewed) · on photos with an empty mask.
- **Diff vs Step0** = point hits minus Step0, with a photo-bootstrap 95% interval (descriptive).
- **LOO** = range of that difference when any one photo is removed.
- **Old** = point-in-source-box and IoU .50 hits out of 201 source boxes (earlier diagnostic records, unchanged).
- **Clear FP** = false points on the 14 Clear negatives, from the earlier records (separate and unchanged).

Jasnk/yolo-acne-detector is byte-identical to HilmiZr YOLOv8s and is not listed. `unzelanoor-app` uses the same weights as `unzelanoor`, with the class `fore` included.

| Model | Input | Found / 114 | r 0.02 · 0.05 | False on reviewed skin | Dup | Unc · oth | Unreviewed: oval · outside oval · empty-mask photo | Points | Diff vs Step0 [95%] | LOO | Old: in box · IoU .50 (of 201) | Clear FP (14 photos) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| step0 | product-chain | 71/114 | 71 · 75 | 96 (10.79/MP) | 48 | 75 · 9 | 0 · 1 · 5 | 305 | — | — | 36 · 17 | 0 |
| dewiin-anyacne | tiles | 85/114 | 80 · 87 | 54 (6.07/MP) | 4 | 53 · 6 | 4 · 51 · 20 | 277 | +14 [0, 30] | [9, 16] | 60 · 13 | 0 |
| tristan-gray | tiles | 84/114 | 81 · 87 | 70 (7.87/MP) | 1 | 47 · 5 | 2 · 26 · 11 | 246 | +13 [-7, 35] | [6, 17] | 57 · 12 | 0 |
| dewiin-acne | app | 70/114 | 66 · 77 | 174 (19.56/MP) | 86 | 74 · 7 | 0 · 35 · 2 | 448 | -1 [-24, 22] | [-9, 6] | 39 · 7 | 0 |
| tristan-gray | crop | 55/114 | 53 · 56 | 13 (1.46/MP) | 6 | 19 · 3 | 1 · 6 · 2 | 105 | -16 [-45, 5] | [-19, -4] | 26 · 12 | 0 |
| unzelanoor-app (same weights as unzelanoor) | tiles | 52/114 | 51 · 56 | 28 (3.15/MP) | 1 | 18 · 1 | 0 · 6 · 1 | 107 | -19 [-50, 2] | [-21, -6] | 22 · 7 | 1 |
| tinny-robot | full | 49/114 | 48 · 54 | 31 (3.48/MP) | 11 | 33 · 10 | 1 · 56 · 7 | 198 | -22 [-48, -2] | [-25, -14] | 35 · 15 | 1 |
| carsten12 | tiles | 48/114 | 47 · 49 | 24 (2.7/MP) | 0 | 26 · 3 | 0 · 13 · 3 | 117 | -23 [-52, 0] | [-26, -12] | 27 · 12 | 0 |
| drpauloreis-onnx (same data as Tinny-Robot) | full | 48/114 | 47 · 53 | 32 (3.6/MP) | 10 | 34 · 10 | 1 · 60 · 7 | 202 | -23 [-49, -3] | [-26, -15] | 34 · 14 | 1 |
| drpauloreis-onnx (same data as Tinny-Robot) | tiles | 47/114 | 44 · 53 | 59 (6.63/MP) | 0 | 49 · 7 | 24 · 348 · 184 | 718 | -24 [-60, -1] | [-25, -8] | 37 · 9 | 1 |
| drpauloreis-onnx (same data as Tinny-Robot) | crop | 46/114 | 45 · 52 | 42 (4.72/MP) | 14 | 44 · 15 | 1 · 34 · 5 | 201 | -25 [-53, -3] | [-27, -16] | 37 · 16 | 2 |
| hilmizr-m | tiles | 46/114 | 45 · 49 | 33 (3.71/MP) | 0 | 30 · 7 | 2 · 17 · 3 | 138 | -25 [-42, -10] | [-26, -19] | 19 · 6 | 0 |
| dewiin-anyacne | crop | 44/114 | 43 · 46 | 6 (0.67/MP) | 3 | 11 · 1 | 0 · 4 · 2 | 71 | -27 [-62, -1] | [-29, -12] | 17 · 10 | 0 |
| tinny-robot | crop | 44/114 | 43 · 49 | 40 (4.5/MP) | 13 | 40 · 13 | 1 · 24 · 6 | 181 | -27 [-55, -5] | [-29, -18] | 34 · 17 | 2 |
| tristan-gray | full | 42/114 | 37 · 42 | 8 (0.9/MP) | 1 | 8 · 1 | 1 · 5 · 2 | 68 | -29 [-62, -4] | [-32, -15] | 15 · 8 | 0 |
| carsten12 | crop | 41/114 | 38 · 42 | 13 (1.46/MP) | 1 | 12 · 4 | 0 · 2 · 1 | 74 | -30 [-60, -7] | [-32, -18] | 20 · 8 | 0 |
| hilmizr-s | tiles | 40/114 | 40 · 43 | 35 (3.93/MP) | 0 | 25 · 6 | 0 · 15 · 6 | 127 | -31 [-57, -11] | [-32, -21] | 16 · 6 | 0 |
| tinny-robot | tiles | 40/114 | 40 · 46 | 40 (4.5/MP) | 0 | 49 · 7 | 7 · 86 · 33 | 262 | -31 [-65, -5] | [-33, -17] | 35 · 8 | 1 |
| unzelanoor-app (same weights as unzelanoor) | crop | 40/114 | 39 · 41 | 21 (2.36/MP) | 1 | 15 · 2 | 0 · 3 · 0 | 82 | -31 [-69, -4] | [-33, -15] | 20 · 8 | 0 |
| unzelanoor-app (same weights as unzelanoor) | full | 40/114 | 40 · 42 | 14 (1.57/MP) | 2 | 13 · 1 | 0 · 1 · 1 | 72 | -31 [-69, -5] | [-33, -15] | 19 · 8 | 1 |
| carsten12 | full | 39/114 | 38 · 39 | 10 (1.12/MP) | 2 | 9 · 2 | 0 · 2 · 2 | 66 | -32 [-58, -10] | [-34, -23] | 20 · 10 | 0 |
| hilmizr-s | crop | 33/114 | 33 · 35 | 16 (1.8/MP) | 4 | 19 · 5 | 0 · 9 · 2 | 88 | -38 [-66, -15] | [-39, -27] | 15 · 5 | 0 |
| dewiin-anyacne | full | 28/114 | 25 · 29 | 3 (0.34/MP) | 0 | 5 · 1 | 0 · 3 · 3 | 43 | -43 [-80, -13] | [-45, -28] | 11 · 6 | 0 |
| hilmizr-m | crop | 27/114 | 27 · 28 | 10 (1.12/MP) | 0 | 19 · 5 | 0 · 15 · 0 | 76 | -44 [-74, -19] | [-45, -33] | 16 · 4 | 0 |
| aldinnasrun-kerascv | crop | 21/114 | 20 · 22 | 9 (1.01/MP) | 2 | 6 · 1 | 1 · 12 · 3 | 55 | -50 [-91, -19] | [-52, -33] | 11 · 8 | 0 |
| hilmizr-s | full | 20/114 | 20 · 20 | 7 (0.79/MP) | 2 | 8 · 1 | 0 · 10 · 2 | 50 | -51 [-91, -21] | [-52, -35] | 11 · 5 | 0 |
| hilmizr-m | full | 17/114 | 17 · 18 | 9 (1.01/MP) | 0 | 11 · 2 | 0 · 10 · 2 | 51 | -54 [-93, -23] | [-55, -39] | 11 · 4 | 0 |
| aldinnasrun-kerascv | full | 13/114 | 12 · 15 | 4 (0.45/MP) | 1 | 4 · 0 | 3 · 15 · 5 | 45 | -58 [-100, -24] | [-60, -41] | 8 · 5 | 0 |
| dewiin-acne | tiles | 1/114 | 1 · 1 | 0 (0.0/MP) | 0 | 1 · 0 | 0 · 7 · 2 | 11 | -70 [-115, -34] | [-70, -53] | 2 · 0 | 0 |
| khaminh-11s | tiles | 1/114 | 1 · 1 | 0 (0.0/MP) | 0 | 1 · 0 | 0 · 0 · 0 | 2 | -70 [-115, -34] | [-70, -53] | 2 · 1 | 0 |
| dewiin-acne | crop | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |
| dewiin-acne | full | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |
| khaminh-11s | crop | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |
| khaminh-11s | full | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |
| unzelanoor | crop | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |
| unzelanoor | full | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |
| unzelanoor | tiles | 0/114 | 0 · 0 | 0 (0.0/MP) | 0 | 0 · 0 | 0 · 0 · 0 | 0 | -71 [-116, -34] | [-71, -54] | 0 · 0 | 0 |

**What changes from the old evaluation**
- Against layer-1 points, Step0 finds 71/114 targets. Against source boxes it had 36/201 point hits and 17/201 at IoU .50.
- The best third-party tile modes find 84–85/114.
- The model ranking is similar to the old point-in-box ranking (Spearman 0.94 over 37 rows) but differs from the IoU .50 ranking.
- The gap shrinks: tile models were +21 to +24 over Step0 against source boxes, and are +13 to +14 against layer 1.

## 6. What each model finds and where it marks wrongly

**Overlap (Step0, Dewiin no-acne model/tiles, tristan-gray/tiles)**
- 55 targets are found by all three; 99 by at least one; 15 by none.
- Only-Step0: 8. Only-Dewiin: 1. Only-tristan: 4.

**Where the difference comes from**
- On the 17 v4 DEV photos (82 targets), the three are level: Step0 60, Dewiin 63, tristan 60.
- On DEV-EXT (32 targets), Step0 finds 11 and the tile models 22–24. The difference comes from:
  - `0a8a14a662a5`: Step0 7/17, Dewiin 11/17, tristan 14/17. Step0 misses the forehead lesions.
  - The small-face photo `b9dd30fde312`: Step0 0/4, tile models 2/4.
  - The close-up photo `29069058884f`: Step0 0/3, tile models 3/3.
- Removing any single photo leaves Dewiin tiles at +9 to +16 over Step0 and tristan tiles at +6 to +17.
- The photo-bootstrap intervals are [0, +30] and [−7, +35]: both tile models catch more in this set, but the size of the advantage is not well determined with 28 photos.

**False points on reviewed skin (layer 1)**

| Model | False points | Per reviewed MP | Most concentrated photos |
|---|---|---|---|
| Step0 | 96 | 10.8 | `9334509b3ae3` 16, `46a79ef8d7a8` 15, `8a78e9d6efd5` 13, `933e40d730e0` 12 |
| Dewiin tiles | 54 | 6.1 | – |
| tristan tiles | 70 | 7.9 | – |

**Layer-2 check of those false points** (crosshair only, model identity hidden):

| Model | Not a lesion | Not a lesion, lesion just outside r | Uncertain | Scar/pigment | Mole | Missed target |
|---|---|---|---|---|---|---|
| Step0 | 55 | 20 | 19 | 1 | 1 | 0 |
| Dewiin tiles | 35 | 2 | 16 | 1 | 0 | 0 |
| tristan tiles | 41 | 12 | 14 | 3 | 0 | 0 |

- **Not a lesion** is mostly plain skin, pores, specular highlights, lip and nostril edges, under-eye texture and sensor noise on dark skin.
- **Agreement between models does not confirm a lesion.** 9 spots were marked by all three models: 5 uncertain, 4 not a lesion (one with a lesion just outside r).

**Points outside the face oval** (background, hair, clothing or unreviewed neck/ear skin):
- Dewiin tiles 51, tristan tiles 26, Step0 1.
- Step0's product masks keep it on the face; the third-party models in tile mode do not.

**Duplicates**
- Step0 places 48 extra points on already matched lesions, against 1–4 for the tile models.

**Clear photos (earlier records, unchanged)**
- Step0, Dewiin tiles and tristan tiles: 0 false points on the 14 Clear photos.
- Tinny-Robot and drpauloreis: 1–2.

## 7. What can and cannot be said

**Supported by this evidence**
- The earlier box-based numbers mainly measured label inconsistency. With one point rule, Step0 localises about 62% of the visible lesions in this set. It is not the 8–18% the IoU and point-in-box scores suggested.
- On reviewed skin, the two best third-party models in tile mode find more lesions (+13 to +14), with fewer false points (54–70 against 96), but with many points outside the face. The gain is concentrated on DEV-EXT photos.
- Step0's product chain misses lesions on part of some photos, for example the forehead of `0a8a14a662a5`. Its false points are mostly on plain skin and next to real lesions.

**Not supported**
- No claim of clinical accuracy.
- No claim that any model is ready for the product: the set is 28 photos, the labels are a non-expert, non-blind AI review, and 209 UNCERTAIN points are excluded from both sides.
- No licence clearance for the third-party models (all Ultralytics-trained, AGPL-3.0 metadata).

**Open question**
- Whether Step0's misses on DEV-EXT come from the product crop and region masks, or from the detector itself, is not separated here.
