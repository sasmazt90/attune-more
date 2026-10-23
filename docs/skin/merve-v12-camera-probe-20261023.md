# External candidate camera probe — 2026-10-23

## Result

One hosted inference was executed on the supplied 2048x2048 front-camera image at confidence 0.08, using `ciltanalizi-rfa8m/12`. Roboflow resolved the candidate to immutable package `7ee34fce76456d9ff4cfe6e7049aad1e` (ONNX FP32). No training, project creation, dataset mutation or model activation occurred.

The returned low-threshold response was reused locally to derive every higher-threshold subset, avoiding four additional hosted calls and eliminating run-to-run prediction drift.

| Threshold | Total | akne | gozenek | kirisiklik | kizariklik | pul |
|---:|---:|---:|---:|---:|---:|---:|
| 0.08 | 27 | 8 | 6 | 3 | 10 | 0 |
| 0.15 | 17 | 4 | 6 | 3 | 4 | 0 |
| 0.20 | 12 | 2 | 5 | 2 | 3 | 0 |
| 0.30 | 6 | 2 | 2 | 2 | 0 | 0 |
| 0.50 | 3 | 1 | 2 | 0 | 0 | 0 |

This establishes that a global 0.50 threshold hides candidate outputs on this image, including all returned redness and wrinkle boxes. It does not establish that all lower-confidence boxes are correct or that 0.08 is a production threshold.

An identical box was returned as both `akne` (0.0993) and `kizariklik` (0.0937). The evidence preserves both instead of silently resolving the semantic conflict.

## Current merged product verification

The repository's current `main` branch already produces the nine appearance results through `appearance_analysis.py` and `skin_general.py`. These are a mixture of deterministic appearance measurements and accepted model outputs, so the product is not waiting for this Universe candidate to produce results.

The bundled `skin-focused.json` currently marks the skin-type, acne and bags heads as not accepted. Its acne confidence threshold is 0.10 but the rejected head is not loaded. The accepted learned head is whole-face redness; the product also has deterministic regional measurements. Therefore changing one global detector threshold cannot be assumed to unlock every existing criterion.

## Decision

Keep version 12 as a research candidate for acne, pores, wrinkle appearance and redness. Do not promote it yet. The next evidence required is a labelled, consented multi-image camera benchmark with class-specific validation thresholds, duplicate/cross-class handling and verified checkpoint rights. `pul` remains unsupported by this camera probe and must not be converted into regional dryness truth.

Evidence: `docs/skin/evidence/merve-v12-camera-probe-20261023-v1.json`

Reproducible threshold tool: `scripts/skin-research/evaluate_threshold_subsets.py`
