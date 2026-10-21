# AAOS Run #126: neural deadline audit

2026-10-21. PR #5, feature/localization-en-de-tr-20261020. Failed source:
`d9dfeee877cddd257143c40219cca08d35fa545c`.
[Run 39595768569](https://github.com/sasmazt90/attune-more/actions/runs/39595768569),
job 119207565385. No emulator dispatch, merge or deployment was performed for this correction.

## Evidence and first failure

The complete job log and evidence ZIP were inspected. The downloaded artifact is
12,190,073 bytes, SHA-256
`9db50e3ab2aca5b07b034476cdcf6b3330d8b6f56b3c409890f6a28fc660ffb2`, matching GitHub's digest.
Cloud evidence is retained outside Git at
`/workspace/attune-aaos-run126-audit-20261021/`.

Provisioning passed in 116.089 seconds; the exact private ZIP and all 117 bundle
files passed. SDK, APK installation, actual Activity/WebView/backend, all nine
routes, independent backend/Car UX moving locks, lifecycle, permissions, 194
approved audio decodes, 15 module/language playbacks, 27 localized route visits
and three scored Hearing workflows passed. The report contains 18 PASS, two
BLOCKED and one FAIL rows. These historical emulator observations remain valid
for that tested source; they are not a new-source AAOS acceptance claim.

The first neural request, Turkish, returned HTTP 504 after 90.545 seconds.
English and German then returned 504 after 90.526 seconds each. `starts=0` in
all three observations. `backend.log` lines 1936, 2120 and 2303 contain the
corresponding backend POST **504** access records. `frontend.log` contains normal
startup, without a proxy crash. `mental-neural-interruptions` is downstream
BLOCKED; the final `crashes-console` FAIL consists of these same three HTTP 504s.
It is not evidence of an Android process crash.

## Root-cause matrix

Line references below identify the failed source unless marked corrected.

| Finding | Source and runtime evidence | Cause and correction | Focused validation |
|---|---|---|---|
| Backend generated the 504 | `services/core-api/mental_neural_tts.py:179-180` raises `NEURAL_TTS_DEADLINE` at 90 seconds; backend itself logged all three 504s at approximately 90.5 seconds | The bounded worker deadline expired before valid WAV delivery. The proxy's 95-second timer had not expired. Set a measured, finite 180-second worker budget | Virtual 120-second success, deadline kill/reap at 180 seconds, actual constrained-CPU V3 profile and production-path check |
| Sequential cold workers, not three concurrent models | `tests/automotive/validate_emulator.py:786-788` awaits each blocking observer RPC before the next language. `mental_neural_tts.py:149-150` rejects a second active generation with 429; a new child loads the model for each request | Preserve sequential requests, one child, source/asset verification and kill-on-cancel. No warm service, model replacement, cache or architectural redesign | Existing cleanup/source/routing tests; observer behavior remains sequential |
| Incompatible client/proxy deadlines after correcting the worker | `apps/vehicle-app/src/app/api/mental-neural-speech/route.ts:39` and `src/utils/mentalNeuralSpeech.ts:27` both used 95 seconds | Shared policy now specifies worker 180 s, proxy 185 s, client generation 190 s; five-second transport/cleanup spacing | Actual proxy/client tests exercise expiry, request abort, timer cleanup, response validation and safety cancellation |
| Generation timer also covered playback | `apps/vehicle-app/src/utils/mentalNeuralSpeech.ts:39` awaited full playback before clearing the same 95-second timer | Latent premature playback cancellation after a slow successful response. Clear only the generation timer once the full bounded WAV is received. Keep live cancellation/validity polling and the existing 60-second audio duration limit/playback deadline | Actual client control-flow fixture checks timer handoff and mute/cancel/language observation; generated-WAV browser checks |
| Observer's 110-second RPC budget was too small | `tests/automotive/validate_emulator.py:788` | Derive the observation budget from generation + maximum audio duration + 15 seconds: 265 seconds. Preserve all scenarios and their assertions | Existing observer regressions; no ignored 504s or fabricated observations |
| Worker phase evidence was discarded | `services/core-api/mental_neural_tts.py:170` directed worker stderr to DEVNULL | Raw ML stderr remains suppressed because it can include input text. Optional task-owned scratch telemetry records only seven allowlisted phase names, wall/CPU seconds, peak RSS and final outcome/return code; parent filters and logs numerical fields and deletes scratch on every exit. Enabled only in the AAOS job | Privacy filtering tests, real child cleanup tests, phase-order fixtures and actual worker timing log |

The exact Run #126 split among asset verification, imports, model load and
inference is **UNVERIFIED**: no phase or per-request CPU/RSS record survived.
The worker was still unfinished when the application deadline fired; an earlier
worker exit would take the 503 path. There is no retained evidence establishing
an OOM kill, CPU starvation, deadlock or a specific model-loading failure.
Pre-boot available memory was 15,372,828,672 bytes, which cannot establish memory
availability during inference. The parent deadline cleanup terminates an
unfinished worker; that is distinct from an independently observed worker crash.

## Measured basis for the bounded correction

The same pinned source, V3 checkpoint, default `conds.pt`, two Torch/OMP threads
and exact observer texts were profiled in the existing Cloud runtime. No model
transfer, new engine or reference recording was involved.

| Focused real inference | Model loading | Generation | Total | Valid output |
|---|---:|---:|---:|---|
| Exact Turkish observer text, normal Cloud CPU allocation | 12.243 s | 21.308 s | 41.574 s | 4.0 s, PCM16 mono 24 kHz |
| Exact longer English observer text, worker affinity restricted to one CPU | 9.314 s | 136.778 s | 152.910 s | 15.2 s, PCM16 mono 24 kHz |

English user CPU time was 148.650 seconds; peak RSS was 6,880,540 KiB. This directly
demonstrates CPU inference exceeding the former 90-second request budget without
an emulator or worker crash. It does **not** retroactively establish Run #126's
CPU contention or exact phase timings. 180 seconds is the next whole-minute
ceiling above this measured cold request, with approximately 27 seconds margin;
it is not an unlimited or arbitrary-length inference guarantee. The unchanged
4096-character input cap can still produce a request that exceeds this bound and
must fail safely. No prompt was shortened, sampling changed or output substituted.

The Cloud machine is Debian 13, not the actual Ubuntu 24.04 AAOS runner. Shared
runner performance, stochastic output length and simultaneous emulator memory/
CPU use remain unverified for the corrected commit. The job still has a hard
40-minute timeout, standard Ubuntu runner, 50 MiB artifact ceiling, one-day
retention, one initial attempt and no automatic retry. No limit was increased
except the specifically measured request/observer deadlines above.

## Verification and preservation

Focused verification passed 87 tests plus 11 subtests (one existing third-party
Python deprecation warning), including real non-ML child-process cleanup and
virtual deadline tests. The four extended-budget tests were rerun after requiring
motion/disconnect observation after the old 90-second boundary; all passed.
Zero-warning frontend lint, typecheck, production build, actionlint, Python/Node
syntax, 69 Android host policy checks and Java syntax checks passed. These are
explicitly host/Cloud checks, not a new emulator run.

The actual production backend → same-origin proxy → Cloud Chromium path then
generated the exact longer English request with the worker restricted to one
CPU. Backend worker elapsed time was **153.620 seconds**, HTTP **200**, and full
browser request plus playback was **168.445 seconds**, with one observed start
and source cleared on completion. The retained safe worker phases show 2.705 s
asset verification, 0.008 s source verification, 4.218 s imports, 10.616 s model
load and 134.888 s inference. Peak RSS was 6,879,968 KiB. The actual 14.72-second
PCM16 mono 24 kHz output is 706,604 bytes, SHA-256
`9ac5057b68efcdabad5cf7d5c1f75ee563b9aa8b65656e1799a6545dc03ed645`.

Playback of that newly generated WAV passed mute, cancellation, language change,
session validity change and consent withdrawal checks using the production
shared playback path. Backend no-consent and moving-state admission returned
403 and 409. There were no browser page errors or capture attempts. The two owned
Cloud services stopped; unrelated services were untouched. Evidence is in
`real-proxy-browser-correct-port/` under the Cloud audit directory. This is actual
Cloud inference/browser evidence, not emulator or physical listening acceptance;
the full LLM/microphone conversation was not started.

The final commit is recorded in the Cloud audit receipt and PR handoff. The original failed Cloud test
attempts remain available: TestClient needed Cloud local IPC permission; the
first isolated browser build targeted port 8000 instead of the owned 8155
backend, so its Park gate correctly prevented inference. The corrected isolated
build uses `NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT=8155`; no product gate was bypassed.

All 194 approved recordings, Hearing banks/scoring, Cilt/Göz/Diş WebView modules,
consent/crisis rules, native Car UX and backend vehicle admission are outside the
changed paths. Prior unaffected successful evidence is reused. No weights, WAVs,
private IDs or credentials are committed. Final AAOS acceptance on the corrected
exact SHA requires a separately owner-authorized manual run; #126 was not retried.
