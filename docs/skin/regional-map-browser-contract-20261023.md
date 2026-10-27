# Regional summary browser and history boundary

The API already emits `general.regionalSkinMap`, but `overviewFromResponse`
previously discarded it. The browser now retains a validated, numeric-only
summary bound to the accepted front capture ID and source dimensions. Historical
overview records without this optional field remain readable and unchanged.

`regionalSkinMap.ts` checks the server contract version and anatomy, recomputes
the region states from the supplied observations, verifies colours and the
combination rule, and preserves independent redness. Unknown observations never
establish normal skin. Conflicting oil/dry aggregates remain unknown because they
do not establish local co-occurrence geometry. The parser does not accept pixel
masks, bounding boxes or a whole-face classification as regional evidence.

The API converter strips unrelated fields before binding the summary. The
numeric-history validator rejects a stale capture, changed dimensions, pose or
coordinate space, inconsistent result, and extra fields in an existing bound
record. It does not silently repair or rewrite historical records. No photo
upload, retention consent, storage adapter, deletion flow or archived source was
changed.

`comparableRegionalObservations` exposes only supported categorical pairs with
the same criterion, region, method version, normalization, model identity and
validation evidence. Unknown readings and changed evidence identities are
excluded; it produces no invented numerical change score. This helper has not
yet been wired into the trend presentation.

## Verification

Run `python -m pytest -q tests/unit/test_regional_map_frontend_contract.py`.
The Python test generates four actual server summaries using deliberately
synthetic policies: registry-empty unknown, supported combination, incomplete
coverage and contradictory aggregates. A Node VM executes the real browser
parser and overview converter. **48 assertions pass**, including history JSON
round-trip, old-record compatibility, source mismatch rejection, independent
redness, unknown-not-normal, extra-field rejection and incompatible-method
comparison. Stub modules supply labels and unrelated view-model exports only;
the server builder, map parser and converter execute their real code.

The test uses the repository's TypeScript dependency when installed, or Node's
native type stripping in the scheduled workspace. A full vehicle-app TypeScript
typecheck/build was not run because that workspace lacks the app dependencies.
These are contract tests, not learned-model accuracy, camera validation or UI
overlay acceptance.

## Remaining work

- Keep the server's accepted regional-method registry empty until acceptance
  evidence passes; this change does not enable a research model.
- Bind accepted anatomical support to the photo SVG, preserve original source
  coordinates and independent redness, and test crop/pose alignment in browser.
- Connect categorical compatibility to the trend/history presentation and test
  the complete camera → API → result → history flow.
- Continue the independently active regional segmentation evaluation rather than
  duplicate its hosted inferences or training job.
