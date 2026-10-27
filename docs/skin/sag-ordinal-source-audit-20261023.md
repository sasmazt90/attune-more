# Task 12 — generic ordinal sag source audit

The existing 18-criterion source does not contain a `sag` target. Its C..T
spreadsheet schema contains `elasticity`, which is not equivalent to localized
lower-face contour/fold appearance. The source ledger is explicitly not
person-independent; the expert label protocol and camera domain are also not
accepted. The later photo-feature calibration excludes both `sag` and
`elasticity`.

The active degree manifest remains unchanged: it exposes only whole-face
`redness`, has no local severity map and does not configure `sag`. No model was
activated and no training or inference was started.

## Implemented acceptance boundary

`generic_degree_target_policy` now filters the generic degree head before model
outputs are returned. A future manifest entry that lists `sag` is rejected with
`WHOLE_FACE_ORDINAL_SAG_NOT_A_LOCAL_APPEARANCE_TARGET`; a declared accepted
target missing from the model output list is rejected separately. The same
filter applies to the failure-path `unavailableTargets`, so an unavailable
whole-face degree cannot accidentally create a sag product heading.

This complements the existing downstream guard that prevents a whole-face
degree from replacing the localized contour/fold result or inheriting its map.

## Verification and remaining acceptance work

Three changed Python files compile and 11 focused product-contract checks pass.
The scratch runtime lacks OpenCV and ONNX Runtime, so the actual ONNX session was
not executed here; wiring is covered by the pure policy tests and a model-source
boundary assertion. Independent expert/localized truth, pose and expression
robustness, real camera evaluation and full browser/app acceptance remain open.

Machine-readable evidence:
`docs/skin/evidence/sag-ordinal-source-audit-20261023-v1.json`.
