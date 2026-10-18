# Reproducing local skin research

Run from the repository root. These are offline development tools, not product
diagnostic endpoints. No model weights, photographs or case-level manifests belong
in Git. All generated outputs must remain under ignored `audit-results/`.
Exact source revisions and license hashes are in
`third-party/skin-research/sources.json`; full notices are retained separately.
The research environment uses the exact versions in
`scripts/skin-research/requirements.txt`, plus the existing repository Node and
MediaPipe dependencies and Python Playwright with Chrome. It does not change the
shipped API dependencies. Verify applicable package notices before provisioning
another environment; no paid training or provider is required.

## Public sources and acne candidate evaluation

```powershell
python scripts/skin-research/download_sources.py
# Downloads the complete public SCIN release, about 12.7 GB in this run.
python scripts/skin-research/prepare_scin.py --download-images --all-images --analysis-workers 4
python scripts/skin-research/verify_scin_faces.py
python scripts/skin-research/train_acne.py
```

The default training input is the whole-face geometry manifest. Geometry is not
expert image annotation. The current seven eligible cases fail the minimum split
requirements, so default training refuses without creating deployment weights.
SCIN case differential labels are not lesion counts, severity, image-specific
acne truth or confirmed negative faces. Expert image review and a separate camera
domain remain mandatory even if numerical metrics later pass.

The failed ear/macro/Haar candidate diagnostic can be reproduced explicitly:

```powershell
python scripts/skin-research/train_acne.py --manifest audit-results/skin-capabilities-20261008/scin/manifest.json --candidate-diagnostic-only --out audit-results/skin-capabilities-20261008/acne-reproduction
```

Its metrics must never be presented as facial acne performance. Case and near-image
duplicate components share one partition; checkpoint, threshold and temperature
use validation only. `acceptance.json` records project admission targets, not
clinical standards. The default deployment gate remains closed. See
`acne-annotation-protocol.json` for separate image-classification, local lesion and
expert severity targets. Nothing converts class probability or attention into a
regional severity map.

## Dryness and sagging

Follow `annotation-protocol.json` before collecting rights-cleared standardized
captures. Obtain two independent expert grades, third-expert adjudication when
necessary, real consent and license records, region boxes and source-coordinate
annotations. No synthetic clinical targets are accepted. With no supplied data:

```powershell
python scripts/skin-research/prepare_annotations.py --target dry
python scripts/skin-research/prepare_annotations.py --target sag
python scripts/skin-research/train_ordinal.py --target dry --manifest audit-results/skin-capabilities-20261008/annotations/dry-manifest.json
python scripts/skin-research/train_ordinal.py --target sag --manifest audit-results/skin-capabilities-20261008/annotations/sag-manifest.json
```

Both preparations report zero cases and both training runs refuse. Once real data
exists, pass `--manifest <private-annotation-json>` to preparation first. Preparation
checks rights, exact/near duplicate leakage and case partitions; do not bypass it
with a manually split manifest. Training validates expert targets again and reports
held-out confusion, MAE and weighted kappa. Expert agreement, sufficient independent
test cases and camera-domain review remain separate product admission conditions.
Visible flaking is not physiological moisture; contour laxity is not elasticity.
Regional ordinal grades do not supply a local map.

## Product maps and surface shine research

Build the production application, then run the owned-process harness with ports
3000 and 8000 free. It uses disposable history and disables paid providers:

```powershell
$env:SKIN_RESULT_AUDIT_DIR = 'audit-results/skin-capabilities-20261008/final-product'
python scripts/run-followup-checks.py tests/e2e/postmeeting_skin_contract.py tests/e2e/skin_cabin_preview.py
python scripts/run-followup-checks.py tests/e2e/skin_local_map_runtime.py
python scripts/skin-research/evaluate_surface.py --captures audit-results/skin-capabilities-20261008/final-product --out audit-results/skin-capabilities-20261008/final-surface
python scripts/skin-research/verify_rendered_maps.py
```

The native Chrome 200% capture records actual zoom geometry. Controlled video
fixtures are engineering evidence, never new physical user acceptance. The ordinary
product generates only source-bound redness index maps. The fixed local surface
shine method and MIT baseline run only in research; surface candidate area is not
sebum or validated oil severity. Software exposure challenges do not replace actual
sweat, cream, makeup, tone and repeat-capture evaluation.

`evaluate_existing_front.py` additionally requires the existing licensed NASA
front-only sources and recorded landmark evidence under prior ignored audit paths.
It reuses native source pixels and the current mesh; it is not a downloadable new
fixture or three-pose acceptance substitute.

See `delivery-20261008.md` and `aggregate-evidence.json` for measured failures,
remaining scientific gates, runtime limits, exact build and security results.
After committing a clean source tree, the normal Windows shortcut verifier records
the served chunk hashes and delivered SHA in the ignored delivery proof:

```powershell
python scripts/verify-postmeeting-delivery.py --output audit-results/skin-capabilities-20261008/delivery.json
```
