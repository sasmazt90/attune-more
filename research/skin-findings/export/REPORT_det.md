# Acne (Sivilce) + redness (Kızarıklık) classifiers — re-fit and saved (2026-10-26)

Exporter `export_det.py` (research recipes `lesion_eval.py` TASK=Sivilce "Dedektör (öğrenilmiş birleşim)" and
`redness_prev.py` "Dedektör"; cached features, same labels/folds/C/threshold rule). Report: `export_det_report.json`.

## Reproduction (held-out 80 test persons; also used for method selection — not an independent validation)

| finding | Ön + 20° (app capture) | recorded |
|---|---|---|
| acne | thr 0.5993, TP 6 FP 1 FN 0, P 0.86 R 1.00 AUC 1.00 (trained on 260 persons, 46 positive) | identical |
| redness | thr 0.5358, TP 30 FP 5 FN 1, P 0.86 R 0.97 AUC 0.99 (trained on 210 persons, 98 positive) | identical |

The old handoff quoted redness P 0.89 R 1.00: that is the Ön + 20° + ~25° row; the app captures no ~25° frame.

## Feature parity (`parity_det.py`, `parity_det_L{1,2,3}.json`; K-265, K-258, K-260, K-252, 12 photos, 60 regions)

- Detector evidence (`model_evidence`) and ITA: exact.
- `cv_red`, `cv_redp90`, `c_red`: production `bare_skin_features` differs from research → research definitions in
  `skin_findings_det.color_features` (exact).
- Region polygons: exact only when landmarks are re-detected on the 1024 crop as in research (needs Python
  `mediapipe`, tested 0.10.32): acne prob max diff 0.0027, redness 0.0004, no threshold flips. Without mediapipe the
  module falls back to the client landmarks (`landmarkSource: 'client-landmarks'`): acne prob up to 0.46 diff, one
  threshold flip in the test, no redness measures.
- Redness display measures (light-corrected a*, `light_redness`): areaPct = 100·mean(a > face median + 4),
  toneDiff = median(a) − face median; exact vs `redness_feats.json` on 60 regions. toneDiff is integer (8-bit Lab).

## Display numbers (not validated against ground truth)

- Acne count (lead, `skin_findings_v1`): boxes ≥ 0.35 of findings Akne / Siyah Nokta / Beyaz Nokta and acnes
  blackhead / whitehead / papule / pustule, one lesion per location (centre inside a kept higher-score box = same lesion;
  a typed class names the lesion over generic Akne), from one photo per region (FRONT forehead/nose/chin, LEFT right
  cheek, RIGHT left cheek). Types add up to the total. Seen region with no box → "1+" unspecified.
- Redness / rosacea / eczema: light-corrected red area % and tone difference of the region.

## Files

| file | sha256 |
|---|---|
| findings-v2/acne.json | 21bf8c718e1642c07da29fc0490c2c7071a5e4dacb1247a12eb6f74b00e0e6d5 |
| findings-v2/redness.json | 2b455387db17d89c62ca69926402dae3558c65662769fb7014c72b6dd2ef3fd9 |
