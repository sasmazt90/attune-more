# Acne point evaluation of existing models (diagnostic, no training) — 2026-10-16

**This is a separate diagnostic experiment.**
- Earlier FAIL results (V4, V5, V6 pilot and its product-chain diagnosis) are unchanged and are not renamed as successes.
- No model was trained, fine-tuned or re-run. All numbers come from stored final boxes in source pixels.
- Thresholds, class mappings, input modes, NMS and filters are exactly those used before.
- **Only the evaluation and display target changed.** The models and their box-based NMS are not point-based.
- Acne stays `accepted:false, file:null`. The sealed Skin care v5 test was not opened.

**Protocol.** `docs/acne-point-eval-protocol-20261016.json` (SHA `1c93157e…`) was committed in `ad1d3ee` before any point metric was computed.

## Data and denominators (verified from the files)

- **Pack and labels**
  - Frozen DEV pack `evalpack.zip` (`fa83a743…`), manifest `2c82ace7…`.
  - 28 replay-pass positive photos (17 v4 DEV + 11 DEV-EXT) with **201 publisher targets: 63 small (< 16 px) and 138 medium**.
  - 14 Clear negative photos.
  - The labels are publisher boxes, not lesion masks, and were not reviewed.
- **Reviewed masks**
  - Frozen clean-skin ROIs on 13 positive photos (226,001 px; `fe828487…`, `99a2073d…`).
  - Reviewed Clear masks on 14 photos (17,567 px).
  - **"0 false points" applies only to these masks.**
- **Prediction records**
  - `external-results.json` (`a027cf35…`).
  - Step0 product-chain rows `infer-step0.jsonl` (dev `bc2f7963…`, devext `7890b01a…`).
  - IoU .50/.30 recomputed from the stored boxes equals the earlier records for every row (Step0 17/25 included).
- **Identical weights counted once**
  - Jasnk/yolo-acne-detector is byte-identical to HilmiZr YOLOv8s (`06f06b58…`) and is not listed separately.
  - `unzelanoor` and `unzelanoor-app` are the same weights with two class mappings that were both run before. The `acne` class never fires; the app shows class `fore` as acne.
- **Settings as used before**
  - Ultralytics models: conf .25, NMS IoU .7, the listed acne classes, imgsz 640 (Dewiin 320).
  - Dewiin "app": no-acne gate model, then conf .01 with agnostic NMS, as published.
  - KerasCV: built-in decoder (conf .2, NMS .7), then ≥ .25.
  - Step0: unchanged product chain (conf .30, NMS .30, product masks, staging filter).
  - "tiles": product native tiles at imgsz 384, merged with box NMS .30.
  - "crop": product face crop. "full": whole photo.
  - Step0's thresholds differ from the third-party models' thresholds.

## Method (as registered)

- **Point.** Each prediction's point is the centre of its final box: px = (x1+x2)/2, py = (y1+y2)/2.
- **Primary metric: point inside the labelled box ("etiket kutusu içine nokta isabeti").**
  - Feasible pair: the point lies inside the label box (edges inclusive).
  - Matching is one-to-one: maximum number of pairs first, then minimum total normalized distance (`scipy.optimize.linear_sum_assignment` on cost = d_norm − 10⁶ for feasible pairs, 0 otherwise).
  - Remaining ties are broken by manifest and prediction order.
  - This is **not** a hit inside the true lesion boundary.
- **Secondary metric (sensitivity only, not an acceptance threshold).** Normalized distance d = |point − label centre| / label diagonal, one-to-one matching at d ≤ .25 and d ≤ .50.
- **False point.** A point inside a reviewed clean ROI (positive photos) or a reviewed Clear mask (negatives). Mask–label conflicts were recorded: there were 0. Every other unmatched point is UNKNOWN and is never counted as right or wrong.
- **Duplicates.** Extra points inside an already matched label box. The same lesion is counted once, and no new merging was added.
- **Unit tests (7/7 pass), `test_point_eval.py`:**
  - one point cannot hit two targets;
  - two points on one target count once;
  - a point outside the label box does not match;
  - maximum cardinality is preferred over nearest-greedy matching;
  - an UNKNOWN point is not a false point;
  - the IoU matcher equals the earlier harness;
  - crop and tile outputs stay in source coordinates.

## Main table (every model × input mode is its own row; no best-mode selection)

| Model | Input | Point hit n/N | Small · medium point hits | d ≤ .25 · ≤ .50 (median d of hits) | IoU .50/.30 | Clean-ROI false points (per photo, 13 photos) | Clear false points (per photo, 14 photos) | UNKNOWN points (+ duplicates) | Time / photo | Licence (from previous report) |
|---|---|---|---|---|---|---|---|---|---|---|
| step0 | product-chain | 36/201 | 21/63 · 15/138 | 35 · 38 (med d 0.073) | 17/25 | 0 (0.0) | 0 (0.0) | 265 (+4 dup) | ~3.3 s (device CPU, whole product chain) | CDC production model (internal) |
| aldinnasrun-kerascv | crop | 11/201 | 6/63 · 5/138 | 8 · 12 (med d 0.107) | 8/8 | 0 (0.0) | 0 (0.0) | 42 (+2 dup) | 0.673 s (cloud CPU, model only) | tag Apache-2.0; KerasCV (Apache-2.0); data unstated |
| aldinnasrun-kerascv | full | 8/201 | 4/63 · 4/138 | 6 · 10 (med d 0.092) | 5/6 | 0 (0.0) | 0 (0.0) | 37 (+0 dup) | 0.679 s (cloud CPU, model only) | tag Apache-2.0; KerasCV (Apache-2.0); data unstated |
| carsten12 | crop | 20/201 | 9/63 · 11/138 | 16 · 20 (med d 0.084) | 8/12 | 0 (0.0) | 0 (0.0) | 53 (+1 dup) | 0.708 s (cloud CPU, model only) | none stated; checkpoint AGPL-3.0 |
| carsten12 | full | 20/201 | 7/63 · 13/138 | 19 · 20 (med d 0.096) | 10/13 | 0 (0.0) | 0 (0.0) | 45 (+1 dup) | 0.716 s (cloud CPU, model only) | none stated; checkpoint AGPL-3.0 |
| carsten12 | tiles | 27/201 | 11/63 · 16/138 | 24 · 29 (med d 0.114) | 12/17 | 0 (0.0) | 0 (0.0) | 90 (+0 dup) | 2.22 s (cloud CPU, model only) | none stated; checkpoint AGPL-3.0 |
| dewiin-acne | app | 39/201 | 22/63 · 17/138 | 31 · 43 (med d 0.133) | 7/16 | 2 (0.154) | 0 (0.0) | 379 (+28 dup) | 0.039 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| dewiin-acne | crop | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.036 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| dewiin-acne | full | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.037 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| dewiin-acne | tiles | 2/201 | 2/63 · 0/138 | 2 · 2 (med d 0.131) | 0/0 | 0 (0.0) | 0 (0.0) | 9 (+0 dup) | 0.383 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| dewiin-anyacne | crop | 17/201 | 8/63 · 9/138 | 16 · 19 (med d 0.092) | 10/11 | 0 (0.0) | 0 (0.0) | 52 (+2 dup) | 0.037 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| dewiin-anyacne | full | 11/201 | 5/63 · 6/138 | 8 · 12 (med d 0.08) | 6/6 | 0 (0.0) | 0 (0.0) | 32 (+0 dup) | 0.038 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| dewiin-anyacne | tiles | 60/201 | 22/63 · 38/138 | 56 · 64 (med d 0.09) | 13/36 | 0 (0.0) | 0 (0.0) | 216 (+1 dup) | 0.366 s (cloud CPU, model only) | repo MIT; checkpoint AGPL-3.0 |
| drpauloreis-onnx | crop | 37/201 | 16/63 · 21/138 | 33 · 37 (med d 0.082) | 16/24 | 1 (0.077) | 2 (0.143) | 152 (+11 dup) | 0.392 s (cloud CPU, model only) | tag Apache-2.0; ONNX metadata AGPL-3.0 |
| drpauloreis-onnx | full | 34/201 | 15/63 · 19/138 | 30 · 34 (med d 0.076) | 14/20 | 0 (0.0) | 1 (0.071) | 159 (+9 dup) | 0.437 s (cloud CPU, model only) | tag Apache-2.0; ONNX metadata AGPL-3.0 |
| drpauloreis-onnx | tiles | 37/201 | 13/63 · 24/138 | 34 · 37 (med d 0.134) | 9/23 | 0 (0.0) | 1 (0.071) | 679 (+2 dup) | 3.252 s (cloud CPU, model only) | tag Apache-2.0; ONNX metadata AGPL-3.0 |
| hilmizr-m | crop | 16/201 | 10/63 · 6/138 | 15 · 16 (med d 0.106) | 4/13 | 0 (0.0) | 0 (0.0) | 58 (+2 dup) | 0.692 s (cloud CPU, model only) | none stated; Ultralytics-trained (AGPL-3.0) |
| hilmizr-m | full | 11/201 | 7/63 · 4/138 | 11 · 12 (med d 0.09) | 4/8 | 0 (0.0) | 0 (0.0) | 40 (+0 dup) | 0.726 s (cloud CPU, model only) | none stated; Ultralytics-trained (AGPL-3.0) |
| hilmizr-m | tiles | 19/201 | 12/63 · 7/138 | 17 · 19 (med d 0.089) | 6/14 | 0 (0.0) | 0 (0.0) | 119 (+0 dup) | 1.885 s (cloud CPU, model only) | none stated; Ultralytics-trained (AGPL-3.0) |
| hilmizr-s | crop | 15/201 | 8/63 · 7/138 | 15 · 15 (med d 0.092) | 5/13 | 0 (0.0) | 0 (0.0) | 71 (+2 dup) | 0.287 s (cloud CPU, model only) | none stated; Ultralytics-trained (AGPL-3.0); = Jasnk (Apache tag), counted once |
| hilmizr-s | full | 11/201 | 6/63 · 5/138 | 10 · 12 (med d 0.094) | 5/10 | 0 (0.0) | 0 (0.0) | 38 (+1 dup) | 0.291 s (cloud CPU, model only) | none stated; Ultralytics-trained (AGPL-3.0); = Jasnk (Apache tag), counted once |
| hilmizr-s | tiles | 16/201 | 10/63 · 6/138 | 13 · 16 (med d 0.124) | 6/11 | 0 (0.0) | 0 (0.0) | 110 (+1 dup) | 0.811 s (cloud CPU, model only) | none stated; Ultralytics-trained (AGPL-3.0); = Jasnk (Apache tag), counted once |
| khaminh-11s | crop | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.26 s (cloud CPU, model only) | none stated; checkpoint AGPL-3.0 |
| khaminh-11s | full | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.256 s (cloud CPU, model only) | none stated; checkpoint AGPL-3.0 |
| khaminh-11s | tiles | 2/201 | 1/63 · 1/138 | 2 · 2 (med d 0.107) | 1/1 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.812 s (cloud CPU, model only) | none stated; checkpoint AGPL-3.0 |
| tinny-robot | crop | 34/201 | 14/63 · 20/138 | 30 · 34 (med d 0.081) | 17/23 | 1 (0.077) | 2 (0.143) | 135 (+11 dup) | 0.683 s (cloud CPU, model only) | card Apache-2.0; Ultralytics-trained -> AGPL-3.0 (checkpoint pre-dates license field) |
| tinny-robot | full | 35/201 | 15/63 · 20/138 | 31 · 35 (med d 0.075) | 15/21 | 0 (0.0) | 1 (0.071) | 153 (+10 dup) | 0.74 s (cloud CPU, model only) | card Apache-2.0; Ultralytics-trained -> AGPL-3.0 (checkpoint pre-dates license field) |
| tinny-robot | tiles | 35/201 | 16/63 · 19/138 | 34 · 36 (med d 0.098) | 8/17 | 0 (0.0) | 1 (0.071) | 226 (+1 dup) | 2.127 s (cloud CPU, model only) | card Apache-2.0; Ultralytics-trained -> AGPL-3.0 (checkpoint pre-dates license field) |
| tristan-gray | crop | 26/201 | 11/63 · 15/138 | 24 · 27 (med d 0.098) | 12/18 | 0 (0.0) | 0 (0.0) | 79 (+0 dup) | 0.101 s (cloud CPU, model only) | tag WTFPL; checkpoint AGPL-3.0 |
| tristan-gray | full | 15/201 | 6/63 · 9/138 | 14 · 16 (med d 0.082) | 8/10 | 0 (0.0) | 0 (0.0) | 53 (+0 dup) | 0.111 s (cloud CPU, model only) | tag WTFPL; checkpoint AGPL-3.0 |
| tristan-gray | tiles | 57/201 | 21/63 · 36/138 | 53 · 58 (med d 0.09) | 12/32 | 0 (0.0) | 0 (0.0) | 186 (+3 dup) | 0.314 s (cloud CPU, model only) | tag WTFPL; checkpoint AGPL-3.0 |
| unzelanoor-app | crop | 20/201 | 10/63 · 10/138 | 19 · 21 (med d 0.09) | 8/14 | 0 (0.0) | 0 (0.0) | 60 (+2 dup) | 0.244 s (cloud CPU, model only) | none (all rights reserved); checkpoint AGPL-3.0 |
| unzelanoor-app | full | 19/201 | 7/63 · 12/138 | 17 · 20 (med d 0.092) | 8/13 | 0 (0.0) | 1 (0.071) | 53 (+0 dup) | 0.252 s (cloud CPU, model only) | none (all rights reserved); checkpoint AGPL-3.0 |
| unzelanoor-app | tiles | 22/201 | 13/63 · 9/138 | 18 · 24 (med d 0.087) | 7/11 | 0 (0.0) | 1 (0.071) | 85 (+0 dup) | 0.638 s (cloud CPU, model only) | none (all rights reserved); checkpoint AGPL-3.0 |
| unzelanoor | crop | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.238 s (cloud CPU, model only) | none (all rights reserved); checkpoint AGPL-3.0 |
| unzelanoor | full | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.261 s (cloud CPU, model only) | none (all rights reserved); checkpoint AGPL-3.0 |
| unzelanoor | tiles | 0/201 | 0/63 · 0/138 | 0 · 0 (med d None) | 0/0 | 0 (0.0) | 0 (0.0) | 0 (+0 dup) | 0.697 s (cloud CPU, model only) | none (all rights reserved); checkpoint AGPL-3.0 |

Step0 time is the whole product chain on the user's PC. Third-party times are model-only on the cloud CPU. They are not comparable.

## Paired comparison with Step0 (same 28 photos / 201 targets)

This analysis is descriptive and was not pre-registered. The interval is a 95% photo-level bootstrap (5,000 resamples) of the difference in point hits.

| Model / mode | Both | Model only | Step0 only | Difference | 95% interval | Photo contributing most |
|---|---|---|---|---|---|---|
| Dewiin no-acne model / tiles | 23 | 37 | 13 | +24 | [−1, +57] | `a19346a0887a` (42 targets, +14) |
| tristan-gray / tiles | 22 | 35 | 14 | +21 | [−7, +60] | `a19346a0887a` (+16) |
| drpauloreis ONNX / crop | 20 | 17 | 16 | +1 | [−18, +17] | – |
| Tinny-Robot / full | 18 | 17 | 18 | −1 | [−20, +15] | – |
| carsten12 / tiles | 12 | 15 | 24 | −9 | [−31, +10] | – |
| Dewiin 7-class / app | 16 | 23 | 20 | +3 | [−16, +22] | – |

Per target, models and Step0 find largely **different** lesions: the union is about 1.5–2× either side.

## Required lists (full lists in the JSON)

- **Per target:** point hit, matched prediction, d, d ≤ .25/.50, IoU .50/.30 for every model/mode (`perTarget`).
- **Point hits missed at IoU .50:** `pointHitButIoU50Miss`, e.g. Step0 19, Dewiin tiles 47, tristan-gray tiles 45, carsten12 tiles 15 / full 10 / crop 12.
- **False points per photo:** `roiPerPhoto` and `clearPerPhoto`. The only non-zero values:
  - Tinny-Robot and drpauloreis: Clear photo `199365731cc9` (1–2 points), and clean ROI on `eeb843cadf66` (1 point at a collage seam of that photo; crop mode).
  - Dewiin app: clean ROI `8ad2e156eef7` (2 points).
  - UnzelaNoor (`fore` class): Clear `6406ffd23779` (1 point).

## Visual examples (not in Git)

The photos were chosen by a fixed rule, not by result quality:
- the photo with the most targets;
- the two photos where the tile models lose the most Step0 hits;
- every photo with a false point.

What they show:
- **Most-targets photo:** the tile models put points on many cheek papules that Step0 misses. They also place UNKNOWN points on background, clothing and the nose bridge.
- **Missed targets:** some are large scar or texture boxes in the publisher labels.
- **Other photos:** several UNKNOWN points sit on visible red spots that have no label, so the labels are incomplete.
- **False points:** one is on a small mark of dark skin inside the ROI. Another sits at the edge of a collage tile, a data-quality artefact of a DEV photo.

## Answer

**Does any existing model show a meaningful box-size-independent localisation advantage, and does it hold together with false marks on clean skin?**

- **Not robustly.**
  - Two tile-mode models put points inside more labelled boxes than Step0 (Dewiin no-acne model 60/201, tristan-gray 57/201, against Step0 36/201). Both have 0 false points in the reviewed masks.
  - But the advantage is concentrated in one 42-target photo, and the photo-level 95% interval for the difference includes 0 (−1 and −7).
  - Their UNKNOWN points (216 and 186) include clearly non-skin locations that the reviewed masks do not cover. "0 false points" therefore does not mean "clean": it only covers 0.24 MP of reviewed area.
- **On small lesions point hits are similar.** Step0 21/63, Dewiin tiles 22/63, tristan-gray tiles 21/63.
- **The point metric shows Step0's localisation is better than IoU suggested.** Step0 has 36 point hits against 17 at IoU .50; it is box size that hurts IoU.
- **carsten12 does not show an advantage** (20–27/201 depending on the mode).
- **Licence.** None of the models with a higher point count is licence-clean: their checkpoints carry AGPL-3.0 and their training-data rights are undocumented. Good localisation is not permission to use.

**Open concrete question.** The labels are incomplete and some mark scars. Deciding whether the models' UNKNOWN points are real lesions needs reviewed lesion points (or exhaustive labels) on these photos. Without that, neither side's advantage can be confirmed.
