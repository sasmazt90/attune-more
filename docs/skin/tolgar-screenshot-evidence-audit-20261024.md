# Tolgar screenshot evidence and measurement-boundary audit

Observed: 2026-10-24T04:52:36Z

## Inputs and scope

- User-authorized Library text: `Pasted text(3).txt`
- Library file ID: `libfile_b2643531fd28819182f06bf3f733e354`
- SHA-256: `2e35620fc3531f7014ac7f672534ffe205a36e7412a7d13421f9b941f452956c`
- The text describes screenshots from `Tolgar-Skin(1).docx` and results in `Tolgar_Roboflow_Results_20261024.html`; neither raw document nor raw camera image was added to the repository in this run.
- Existing generated V5 replay and Roboflow comparison evidence remains non-expert and non-physical-camera evidence.

## Evidence decisions

| Claim/proposal | Decision | Reason |
|---|---|---|
| UI screenshots are not raw camera evidence | Accepted | A composed screen image cannot establish physical-camera accuracy or source-pixel model behaviour. Any inference on a crop containing UI graphics is confounded by those graphics. |
| The app necessarily sends the turquoise mesh to the backend | Rejected | `SkinFacePanel.tsx` renders the guide as a separate SVG overlay, while `captureSkinAngle` reads camera canvas pixels. A screenshot crop can include the mesh even though the captured analysis payload does not. |
| LEFT/RIGHT capture is reversed | Rejected | `skinMultiAngle.ts` explicitly maps the user's right turn to the exposed anatomical left cheek and vice versa under the unmirrored-camera convention. |
| Landmark overlay is proven 5–10 px misaligned | Unverified | Video and overlay share the same wrapper/stretch contract; no source-bound measurement in the supplied text establishes a pixel error. Browser/camera replay is still required. |
| Disable/archive V5 from these screenshots | Rejected | Screenshot observations do not satisfy the learned/analytic method acceptance gate and cannot authorize disabling an existing result. |
| Add a pink `Sensitive` map | Rejected | Product contract requires independent `Redness` as red contour/hatching. Sensitivity is not an inferred synonym for redness. |
| Adopt a 3.5 second SLA | Rejected | No measured product requirement or representative device/runtime benchmark was supplied. |
| Missing measurements may be confused with measured zero | Accepted as a defensive boundary risk | The contour call used `value or 0`, which erased the semantic distinction before the common row boundary. Known limitation paths still failed closed, but a future or malformed upstream `None` without a limitation could become valid zero. |

## Implemented change

`services/core-api/appearance_analysis.py` now validates every value at the common regional measurement boundary:

- measured numeric zero remains valid;
- `None`, booleans, non-numeric values and non-finite values become `value=null`, `quality=insufficient`, `limitationCode=MEASUREMENT_UNAVAILABLE` when no more specific limitation exists;
- an upstream limitation always wins and clears the value;
- the contour path passes `value` unchanged instead of applying `value or 0`;
- unavailable rows cannot generate a local map because `usable` is false.

The focused test covers valid zero, missing value, NaN, a specific upstream limitation and source wiring.

## Verification

- `py_compile`: passed for the changed source and test file.
- Exact extracted implementation: 4 boundary checks passed.
- Source wiring: 2 checks passed.
- Full `pytest` did not run in this execution environment because `pytest` and OpenCV are not installed.
- Frontend smoke did not run because this partial workspace lacks `tests/unit/ts_loader.js`; no browser/camera acceptance is claimed.

## Roboflow refresh and selection boundary

- Acne/post-acne/pigmentation NAS `5b632a5c12b76fcfe703`: finished, 89 children.
- Regional NAS `3485f8c67f957a1b850d`: finished, 75 provider records.
- No training or inference was started or duplicated.
- Acne NAS training summaries: highest displayed mAP50 child `929397` is 17.59 mAP50 / 4.44 mAP50:95 / 18.87 ms T4; highest displayed mAP50:95 child `754885` is 17.00 / 4.51 / 18.43 ms T4; lower-latency frontier child `e65132` is 17.04 / 4.36 / 12.55 ms T4. These are training summaries, not product acceptance.
- Existing frozen evaluation for `754885` remains rejected and the live exact-ID `a5e262` evaluation remains poor. No `recommended` flag was treated as an accuracy or hardware winner.

## Remaining acceptance work

This change closes one fail-closed integration defect only. It does not establish criterion accuracy, threshold calibration, raw-camera behaviour, temporal stability, expert truth, model acceptance, production merge or deployment. The next useful acceptance work remains consented raw-camera replay and expert-labelled validation/test evidence under the existing source/threshold/model gates.
