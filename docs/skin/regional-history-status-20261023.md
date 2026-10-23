# Regional history status contract — 2026-10-23

Task 13 already had source-bound regional parsing, categorical history, retained-photo replay and persistence validation. This increment closes a stale-fallback gap in the history UI: when an explicitly selected record cannot provide a comparable regional observation, the adapter no longer substitutes an older valid record.

## Behaviour implemented

`regionalObservationHistory` now returns an explicit state:

- `comparable`: at least two observations share the exact method, normalization, model hash and validation-evidence identity;
- `single-record`: one valid observation exists for the current identity;
- `method-changed`: older valid observations exist but belong to another evidence identity;
- `not-evaluated`: the selected result is absent or explicitly unknown; it is never interpreted as normal or negative;
- `record-unavailable`: the requested record is absent, has an invalid timestamp, or contains a malformed source-bound regional result.

The trend modal presents these states separately. Unknown and incompatible records remain visible as exclusion counts, while only exact-identity positive/negative observations enter a categorical sequence. No numeric regional severity or cross-method delta is created.

## Verification

Four real server-builder fixtures cross the browser adapter. The executable suite covers all five statuses, an explicitly selected unknown result, a missing selected result, a malformed source-bound map, method identity change, three source aspect ratios and the existing retained-photo storage gate. All 88 checks passed.

Evidence: `docs/skin/evidence/regional-history-status-checks-20261023-v1.json`.

This is an integration-contract increment, not method acceptance. The accepted regional-method registry remains authoritative and empty. Real browser/IndexedDB, full frontend typecheck and real-camera acceptance remain pending in an environment with a runnable browser and the application dependency tree.
