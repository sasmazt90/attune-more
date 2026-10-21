# Run #121 consolidated readiness after approved audio publication

**Offline/Cloud readiness: PASS. Actual corrected AAOS scenarios: UNVERIFIED until a separately approved manual run. No Actions run was started.** This supersedes the missing-asset readiness blocker in `AAOS_ACCEPTANCE_AUDIT_20261019.md`; its original #121 findings remain historical evidence.

## Synchronization and independent asset verification

The clean Cloud checkout on `feature/aaos-oem-agnostic-prototype-20261019` was fast-forwarded from `eefe6a7aa63988492baeaf997db914e8a2ec6fb9` to the published commit **`de703d95b0d1bf779ced4918e7d5e2e447da34e4`**. That commit adds exactly one file and preserves the consolidated #121 harness fixes. No other audio, manifest, health module or safety control changed.

| Check | Verified result |
|---|---|
| Path | `apps/vehicle-app/public/audio/guidance/mental-entry-voice-only-v1.mp3` |
| Git tracking / source | Actual binary blob in `de703d95`, byte-for-byte equal to the synchronized workspace file |
| Size | **57,168 bytes** |
| SHA-256 | **`9bdfd42f81d5488ff21d6ad8e47bd0ee2db4a95d9f60e971ee70532d2f2b8e93`**, matching both the supplied identity and unchanged manifest |
| Manifest | `mental-entry` URL is `/audio/guidance/mental-entry-voice-only-v1.mp3`; expected voice `tr-TR-EmelNeural`, rate `-10%`, pitch `-10Hz`, version `guidance-20261009-v1` remain compatible with the existing loader contract |
| Real production-server response | **HTTP 200**, `Content-Type: audio/mpeg`, `Content-Length: 57168`; response body has the same SHA-256 as the approved Git blob |
| Media range request | **HTTP 206**, `Content-Range: bytes 0-1023/57168`, exact first 1,024 approved bytes |
| Real browser decode | Existing Cloud Chrome **155.0.8059.84** decoded the exact served bytes with OfflineAudioContext: **9.528 seconds**, **24,000 Hz**, **one channel**. `canPlayType('audio/mpeg')` reports `probably` |
| All guidance assets | **33/33** present, with hashes matching the approved manifest; the packaging preflight now exits successfully |

The decoder test called no `play()` method, requested no camera/microphone, and generated no audible output. It establishes desktop decoder compatibility, not physical or Android Automotive playback acceptance. The original console 404 was not filtered, replaced with another recording or hidden behind a fixture response: the actual Next production server now serves the approved bytes.

## Every remaining #121 issue

Original source/log evidence and A/B/C/D classifications remain in the [root-cause matrix](AAOS_ACCEPTANCE_AUDIT_20261019.md). The historical run remains **12 PASS / 3 FAIL / 2 BLOCKED**; these new host results do not rewrite its statuses.

| #121 issue | Consolidated correction and current Cloud evidence | Remaining AAOS check |
|---|---|---|
| `backend-offline` timeout — B/D | Re-reviewed owned backend shutdown/restart and labeled native observations. A real Cloud test established keep-alive, stopped only the owned backend, confirmed new and existing connections failed, then restarted the same isolated command and observed fresh synthetic Park. Backend reversal removal is no longer treated as proof of an outage | Native stale/unknown lock must actually remove WebView during the verified outage and recover only after fresh backend state. #121 did not identify its exact timed-out predicate; no claim that this is already proved on Android |
| `unsupported-hardware` timeout — B/D | Recorded #121 XML shows an outstanding OS permission modal. Strict denial selection, final cancellation and explicit modal obstruction detection remain covered by focused tests; no simulation or vehicle policy is changed | Actual independent hardware-label check must run after the modal is dismissed. Advertised absent camera can be checked; physical camera/microphone acceptance remains outside this task |
| `crashes-console` missing MP3 — A/D source packaging | Exact approved asset independently verified above. Actual URL is now 200, byte ranges work, browser decode succeeds, all manifest hashes pass. Manifest and recording contents unchanged | The new AAOS WebView navigation/console observation must confirm absence of the prior 404 and any other unexpected errors. Desktop decoding is not an AAOS or audible-playback pass |
| `permissions-denial` blocked — B/D | Re-reviewed recognized permission-controller/app-title checks, AAOS denial-row interceptor, observation after WebView closure, denial proof and cleanup. Recorded-XML replay selects deny at (640,518), not allow at (640,402); unknown/spoofed dialogs remain blocked. Pause/destroy safety is unchanged | Observe the actual OS denial control being clicked, dialog disappearance and both permissions remaining denied; cancellation alone cannot pass the scenario |
| `evidence-capture` incomplete — B/D | Fresh UI polling, real framebuffer PNG validation, XML/activity capture and acquisition hashes retained. Added a positive contract test for all nine route triplets plus a passed behavioral check; modifying its Activity receipt correctly makes evidence acceptance BLOCKED | Actual first-frame UI acquisition and every successful-check/route triplet must be acquired in the new run. No old XML, rendered HTML or fixture image is accepted as emulator evidence |

The timeouts share a previously weak observation mechanism, but one common runtime cause is not established. The hardware modal appeared after the earlier backend timeout. The backend injection and observation corrections remain necessary independently of the MP3 restoration.

## Additional verified harness correction

Review found a diagnostic gap in `tests/automotive/validate_emulator.py:357`: a wait whose final error was `Blocked` raised before saving its phase label, error and timeout receipt. This could obscure another permission/readiness blocker even after the #121 synchronization fixes.

A focused regression first reproduced the missing JSON receipt (`blocked-wait-before-fix.log`). The correction writes the same-phase diagnostic receipt before raising a labeled **BLOCKED**, preserving the original cause and classification. No failure is converted to PASS or silently skipped. The second added regression verifies complete evidence succeeds and a modified Activity receipt blocks acceptance.

Files changed in this continuation, beyond the already-published audio commit:

- `tests/automotive/validate_emulator.py` — retain timeout diagnostics for BLOCKED waits; no behavioral gate changes.
- `tests/automotive/test_acceptance_regressions.py` — blocked-wait diagnostic and complete/tampered evidence regressions.
- This readiness report, `AAOS_ACCEPTANCE_AUDIT_20261019.md`, `EMULATOR_VALIDATION.md` — current status and preserved historical findings.

## Executed Cloud validation

The existing isolated Ubuntu **24.04.5** container and pinned setup were reused: Python **3.11.17**, Node **22.20.0**, Java **21.0.12.1+1**, Gradle **8.11.1**, AGP **8.9.2**, SDK/build tools **35 / 35.0.0**. Browser decoding used the existing managed Cloud Chrome separately. No Windows/local tools, dependency reinstall, new paid service, full 783-test suite or emulator launch.

| Validation | Result |
|---|---|
| Asset preflight | **PASS**, 33 approved recordings and matching hashes |
| Focused Python tests | **PASS**, **57 tests + 10 subtests**; includes 69 policy assertions, 22 Car-source assertions and actual class-absence safety execution, plus recorded UI/host fixtures explicitly identified as such |
| WebView harness Node tests | **PASS**, three tests |
| Native debug/release assembly and lint | **PASS**, 91 Gradle tasks; observer assembly/lint **PASS**, 43 tasks; existing warnings remain, zero lint errors |
| Production web build | **PASS**, compilation, lint/type validation and 13 static pages; existing warnings retained |
| SDK/native dependency preflight | **PASS**, **625 host ELF objects**, six Android guest payloads excluded, zero required errors; six previously documented unused optional-library warnings |
| Actual APK/tool/import preflight | **PASS**, packaged identities, SDK tools, compiler, documented Node Android API and isolated keyless backend import; `pip check` clean |
| Owned backend failure/recovery | **PASS**, actual Cloud HTTP/process observations, not mocked device results |
| Approved audio serving and decode | **PASS**, real HTTP 200/206, exact served-byte hash and desktop Chrome decoder |
| Workflow/static checks | **PASS**, actionlint 1.7.12 on all four workflows, Python compilation, existing installer Bash syntax and Git whitespace checks |

Evidence is outside tracked product paths at `/workspace/attune-aaos-resumed-verification-20261019/`: `asset-identity.json`, `source-packaging/asset-preflight.json`, `http-service-results.json`, `browser-audio-decode.json`, `ubuntu-focused-tests.log`, `ubuntu-node-tests.log`, native/probe/web build logs, `host-preflight/`, `blocked-wait-before-fix.log`, and `evidence-sha256.json`. Private synthetic service data is excluded from the evidence inventory. `served-approved.mp3` is an audit copy of the exact approved HTTP response, not a replacement asset.

## Remaining risks and approval boundary

1. **UNVERIFIED:** corrected native offline lock/recovery, actual denial-button interaction/cleanup, independent unsupported-hardware behavior and complete live capture on AAOS. This Cloud executor has no `/dev/kvm`; no software-emulation fallback was used.
2. Unknown permission-controller layouts/locales or inaccessible UI roots remain BLOCKED with diagnostics. Commands retain individual timeouts and the workflow retains its 40-minute limit. Actual scheduling, VHAL inputs and WebView/CDP behavior remain platform-dependent.
3. The image/SDK version and package-revision guards still reject unexpected drift. The pinned image and APIs already passed real #121 installation and moving-lock checks; this continuation changes none of them.
4. Valid MP3 serving/decoding does not establish audible output, user interaction/autoplay behavior, physical microphone/camera capability, OEM/vehicle integration, clinical accuracy or production readiness.
5. Next run must use only standard GitHub-hosted `ubuntu-24.04`, exactly one initial manual dispatch, **40-minute** timeout, **50 MiB** artifact limit (49 MiB source plus ZIP margin), **one-day** retention and the existing 256-file ceiling. No automatic retries, larger/premium runners, extra paid services, main changes, merge or deployment. The previously accepted limited artifact-billing risk remains; exact remaining free storage and a zero-charge outcome are not newly claimed.

**No known source-packaging blocker remains. Request approval for one manual validation of the final consolidated feature commit; do not dispatch before that approval.**
