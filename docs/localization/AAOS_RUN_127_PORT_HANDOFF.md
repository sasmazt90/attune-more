# Run #127: readiness service cleanup and port handoff

2026-10-21. PR #5, feature/localization-en-de-tr-20261020.
Failed [run 39604781078](https://github.com/sasmazt90/attune-more/actions/runs/39604781078)
tested `0b5db27ca174700d445c6afbc379d2fc62959936`.

## Evidence and limits

The complete job log and artifact were inspected. The artifact is 133,011 bytes,
SHA-256 `e7dc26a918a414909246162ca20dc7a74b85f82b57d8a6a2a324bff80448a9bd`,
matching GitHub's digest. Copies remain outside Git in
`/workspace/attune-aaos-run127-audit-20261021/`.

At 13:11:30.071 UTC neural readiness reported PASS with real backend 401,
no-consent 403 and authenticated frontend proxy/moving 409 observations. Model
provisioning, native dependencies, SDK, builds and host preflight passed. At
13:11:33.874 UTC the runner stopped before AVD/emulator creation:

```text
BLOCKED: Port 8000 unavailable: [Errno 98] Address already in use
```

`boot-blockers.json` contains only that blocker. No runtime AAOS acceptance was
executed in #127. Negative-fixture BLOCKED messages earlier in the passing host
test step are not additional real emulator failures.

**The exact historical port owner/PID is UNVERIFIED.** Neither the job log nor
artifact records a listener snapshot, PID or readiness process exit record.
`EADDRINUSE` alone cannot identify a live owner. Do not infer an orphaned backend
from it. The old readiness code waited for both direct children, but did not
verify child groups or port reusability.

## Confirmed defect and reproduction

The failed-source `tests/automotive/run_emulator.py:39-41` used a plain bind to
test availability. Uvicorn/asyncio server sockets use `SO_REUSEADDR`; a plain probe
can fail while a closed server's connections remain in kernel `TIME_WAIT`, with
no owning PID. The same plain check occurred at
`neural_readiness.py:31-33` and `validate_emulator.py:633-637`.

This was reproduced using the **actual existing backend, Next proxy and
readiness function**, with only an extra task-owned keep-alive socket controlling
close order. No neural inference, browser capture or emulator was involved:

| Observation | Before correction | After correction |
|---|---|---|
| Readiness auth / consent / proxy-motion checks | 401 / 403 / 409 | 401 / 403 / 409 |
| Owned backend / frontend PIDs | 226229 / 226230 | 226471 / 226472 |
| Both direct children exited/reaped | Yes, exit -15 / 0; neither PID existed | Yes, exit -15 / 0; neither PID existed |
| TCP state after client close | Port 8000 TIME_WAIT, PID null | Port 8000 TIME_WAIT, PID null |
| Plain bind | Errno 98 | Errno 98, deliberately retained as a negative control |
| Server-compatible bind/listen | Available | Available; readiness explicitly records released ports |
| Actual harness-owned backend starts on 8000 | PID 226252, HTTP 200 | PID 226492, HTTP 200 |
| Harness backend cleanup | Exited | Exited; owned group verified stopped |

Receipts and logs are in `actual-time-wait-before/` and
`actual-time-wait-after/`. These observations confirm the faulty probe and a real
readiness-to-harness failure mode. They do not reconstruct #127's missing kernel
snapshot or establish that an unrelated listener was impossible in that run.

## Correction

Only workflow/harness preparation files changed; no product code or TTS settings:

- `tests/automotive/service_lifecycle.py`: shared bind **and listen** probe with
  address reuse for HTTP ports only; no `SO_REUSEPORT`. A genuine listener still
  blocks. Bounded five-second port-release polling; read-only PID/socket-state
  observations without command lines, environment, tokens or private IDs.
  Cleanup signals only recorded task-owned session/process groups, checks live
  descendants even after a leader exits, escalates TERM to KILL if necessary,
  reaps owned direct children and verifies groups have no running members.
- `tests/automotive/neural_readiness.py`: use the shared probe and cleanup in
  `finally`, wait for released ports, then report success with PID/exit/group
  receipts. SIGTERM raises through cleanup. Existing auth, consent, proxy,
  model/dependency, memory and remaining-time gates remain intact.
- `tests/automotive/run_emulator.py`: require the successful cleanup receipt,
  repeat the live port check before any AVD/emulator creation, and preserve
  `port-preflight.json` for future owner/state attribution. Console/ADB ports
  5554/5555 retain their strict original bind semantics.
- `tests/automotive/validate_emulator.py`: use the same HTTP-port probe and
  bounded owned-group cleanup for backend restarts and final service shutdown.
- `tests/automotive/test_service_lifecycle.py`: real socket/process regressions
  with explicitly labelled lightweight HTTP fixtures; these are not model or
  Android acceptance results.
- `.github/workflows/aaos-emulator-validation.yml`: include the focused lifecycle
  regressions in the existing pre-emulator host test step.
- This report.

## Verification and readiness

79 focused tests plus 21 subtests passed: readiness/harness lifecycle, actual
port 8000 handoff, TIME_WAIT versus live-listener discrimination, bounded waits,
untouched unrelated listener, consent-check and partial-spawn failures,
termination unwinding, a live child surviving its leader, missing cleanup receipt,
and existing runtime/harness/automotive host contracts. Python compilation,
actionlint and diff checks passed. The actual backend/proxy handoff above also
passed after the correction. No model download, provisioning, inference, app
build, broad suite or emulator run was repeated manually.

All 194 original recordings, Chatterbox V3, Hearing TR/EN/DE scoring, the five
health modules, user data, consent/crisis/motion restrictions and prior successful
AAOS evidence remain unchanged. Standard Ubuntu, 40 minutes, 50 MiB artifacts,
one-day retention and no retries remain unchanged. GitHub automatic CI and final
SHA are recorded in the Cloud receipt/PR handoff.

A new exact-source AAOS run still requires separate owner authorization.
Its emulator result remains UNVERIFIED. #127 was not retried; main, merge and
production deployment were not touched.
