# Source-bound Attune / Roboflow comparison gate

Date: 2026-10-24

## Outcome

The current merged product flow was rechecked before adding comparison work.
`main` still resolves to commit
`7463eef112c5a40f7cd01192b6d1f4e9fa6ab285`; that implementation already
returns regional skin results, a nine-criterion FRONT overview, separate skin
type, maps/contours, and persistence receipts through
`/api/local-health/skin`. This work does not replace or rename that flow.

The connected Railway account exposes three unrelated projects (Adatif-AI,
Sasmaz-Digital, and mygamebookai) and no Attune service. The current product
endpoint therefore could not be executed remotely in this run. No Railway
resource, variable, deployment, or domain was changed.

Added `scripts/skin-research/build_attune_roboflow_comparison.py`. It accepts a
captured Attune response bundle plus the existing generated triplet manifest
and immutable Roboflow FRONT evidence. It emits JSON and Markdown only when all
of the following are true:

- all six generated FRONT identities match the 18-image triplet manifest;
- the Attune bundle is pinned to the current merged commit and product endpoint;
- each input JPEG hash matches, and its separately recorded decoded-RGBA hash
  equals the response `photoId`;
- source dimensions, volatile analyzer storage receipt, all six anatomical
  regions, maps/contours, all nine current criteria, and separate skin type are
  present and internally consistent;
- the Roboflow result uses `ciltanalizi-rfa8m/12` at the 8% review floor and
  immutable package `7ee34fce76456d9ff4cfe6e7049aad1e`;
- every per-image and aggregate threshold count is recomputed from the one
  stored prediction response rather than trusted as a copied total.

The output retains Attune quality/limitation receipts and Roboflow proposal
counts side by side. It explicitly states that neither output is ground truth
for the other and that no precision, recall, F1, calibration, real-camera
acceptance, or production activation follows from the comparison.

## Verification

`python -m unittest scripts/skin-research/tests/test_build_attune_roboflow_comparison.py`
passes six tests. They cover a complete source-bound bundle and fail-closed
behavior for a missing Attune subject, decoded-photo identity mismatch,
tampered Roboflow threshold totals, wrong product commit, and CLI failure with
no output artifacts. Both changed Python files also compile with `py_compile`.

## Remaining acceptance boundary

The six real Attune responses have not been captured. The production UI is a
camera/MediaPipe flow rather than a file-upload endpoint, the local scratch
runtime lacks the product's OpenCV/MediaPipe/ONNX/FastAPI dependencies, and no
Attune Railway service is connected. The gate is therefore ready but no
comparison receipt was fabricated. Real-camera evidence, expert labels,
class-specific threshold calibration, and product activation remain pending.

No model training, inference, deployment, model selection, facial-image commit,
or production merge was performed.
