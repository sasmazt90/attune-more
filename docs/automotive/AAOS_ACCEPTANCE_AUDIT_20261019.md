# AAOS partial acceptance audit — run #121

> Historical findings before approved audio commit `de703d95`. The exact asset
> has now been independently verified; current consolidated readiness, all five
> remaining scenarios and risks are in [AAOS_RUN121_READINESS_20261019.md](AAOS_RUN121_READINESS_20261019.md).

**Actions remains stopped.** At this audit snapshot another emulator run was blocked by the missing approved audio asset. No corrected-scenario emulator passes are claimed by this historical report.

## Evidence examined

[Run #121](https://github.com/sasmazt90/attune-more/actions/runs/39309014352), job `118253481813`, source `805371677c98154aecd3d6879df141ad23c256c9`. Complete 1,719-line job log and the complete artifact archive were downloaded. Artifact `12214359909` contains **161 files**, 3,943,318 compressed bytes; SHA-256 `e3da8ef7d2ac5a607bc01e919826c78e64de47ffbc2f102eb3c5c87ccc6a6f35`.

Actual results remain **12 PASS / 3 FAIL / 2 BLOCKED**. APK installation, Car API observation, Activity launch, WebView/backend connectivity, nine routes, both independent moving locks, background lifecycle and web-load recovery passed. All nine route PNG/XML/Activity triplets were independently decoded/parsed and checked. There are **23 valid PNGs**, **22 native UI XML files**, plus JUnit XML. The crash buffer is empty; the reported console failure is the missing MP3 request, not an observed native application crash.

Raw logs use UTC. Times below are displayed in **Europe/Berlin, CEST (UTC+2)** on 19 October 2026. Logs and artifacts are preserved outside tracked product paths at `/workspace/attune-aaos-acceptance-audit-20261019/`.

## Root-cause matrix

Classification: **A** application/source-package defect, **B** harness defect, **C** unsupported emulator capability, **D** missing/incorrect evidence. Original source locations below refer to commit `8053716`; corrected locations refer to this consolidated patch.

| Scenario / classification / severity | Exact evidence and original source | Root cause and correction | Verification and limits |
|---|---|---|---|
| **backend-offline: B/D; high** | Full job log **1586**, 21:20:56.029 CEST: generic 30s timeout. `tests/automotive/validate_emulator.py:648` removed only `adb reverse tcp:8000`; `:289` lost the identity of the timed-out wait. Failure screenshot/XML were acquired after the `finally` block restored connectivity. `backend.log` records extensive connection reuse, including 274 GETs on client port 36147 | Deleting a reverse listener is not a verified outage of existing HTTP streams. #121 contains neither a connection-refusal receipt nor per-wait traceback: the exact timed-out predicate and native offline behavior **cannot be established** from this evidence. Replace injection with shutdown of only the harness-owned backend, wait for process exit and actual connection refusal, then assert the native unknown/stale gate and absent WebView. Restart the same keyless isolated service and verify fresh Park recovery. Preserve both backend log segments | **PASS, real Cloud HTTP/process check:** established keep-alive; owned shutdown broke existing and new connections; restart restored fresh synthetic Park. Corrected Android offline lock/recovery **UNVERIFIED**. No claim that #121 proved an application safety defect or that its exact timeout location is known |
| **unsupported-hardware: B/D; high** | Job log **1590**, 21:22:25.605 CEST. `unsupported-hardware-launch.txt` explicitly reports `GrantPermissionsActivity`; its screenshot/XML still display the audio permission prompt. Original `validate_emulator.py:708` called `parked_ready(:434)`, waiting for native Park behind that modal | Prior permission check left an OS modal open. Its native Park observation was obstructed, not a demonstrated hardware-label defect. Correct denial handling/cleanup; explicitly classify a remaining permission modal as BLOCKED before polling native Park. Preserve the independent hardware test after successful cleanup | Real #121 probe reports camera=false, microphone=true; other real native snapshots show `Kamera: yok`. The formal standalone scenario still did not complete. Fixture replay verifies detection and non-mutation behind a modal. This is **not C**: absent camera is an advertised condition the test can inspect |
| **permissions-denial: B/D; high** | Job log **1589**, 21:21:53.219 CEST, state=`closed`. Actual `permissions-denial.png/.xml` shows **Allow Attune.more Prototype to record audio?** and **Don’t allow**. `logcat.txt:5808` starts the OS request; `:5894` installs its Car UI. Original `validate_emulator.py:695` searched only `permission_deny_button`; `:700` stopped observing when the WebView closed | AAOS uses nonclickable `car_ui_list_item_title` with a clickable sibling `car_ui_list_item_touch_interceptor`. Closing WebView on pause is the app's deliberate safety behavior (`MainActivity.java:124`), not proof the OS dialog failed to appear. Select only a recognized permission-controller dialog for this APK and its exact denial row; keep observing OS UI independently of page closure. Capture the prompt before tapping, verify dismissal and both denied permissions. Finally cancel any remaining modal; cancellation alone cannot pass denial acceptance | **PASS, recorded-XML replay:** denial coordinate (640,518), not allow coordinate (640,402); wrong package/app/unknown wording rejected; closed-page flow and cleanup regressions pass. **UNVERIFIED:** actual corrected denial click and its resulting Android lifecycle in a new emulator. No permission grants, relaxed origin policy or lifecycle weakening |
| **crashes-console: A/D, source packaging; high** | Job log **1591**, 21:22:27.662 CEST; `webview-console.json` requests `/audio/guidance/mental-entry-voice-only-v1.mp3` and gets 404. `apps/vehicle-app/public/audio/guidance/manifest.json:312` specifies exactly this URL. `.gitignore:148` at `8053716` explicitly excluded the file | URL matches the approved manifest; recording is absent from Git and Cloud. Required SHA-256 is **9bdfd42f81d5488ff21d6ad8e47bd0ee2db4a95d9f60e971ee70532d2f2b8e93**. The tracked contract-named MP3 hashes to **92f143f29631a1deb3555adbcd551a03218f21c4f7eb81946dba2ca5df2ea943**, so changing the URL would substitute different audio. Remove the ignore override so the exact approved recording can be included. Add read-only manifest/file/hash preflight before SDK downloads/builds; preserve the console error until asset restoration | **404 reproduced on real Cloud Next production server.** All 67 repository MP3 files were checked; none matches the approved hash. All other guidance entries match their files. New preflight correctly returns **69 / BLOCKED**, naming the missing URL/hash; finalizer leaves all emulator scenarios BLOCKED. **UNRESOLVED:** approved bytes must be supplied via an authorized Cloud/GitHub location. Manifest/hash unchanged; no synthesis, substitute, paid speech call, or console filtering. This does not prove the existing Windows delivery or deployed production instance lacks its local asset |
| **evidence-capture: B/D; medium** | Job log **1592**, 21:22:27.664 CEST. `activity-start-evidence-error.txt`: null UI root; Activity launch itself passed, and its PNG and Activity dump are retained. Original `validate_emulator.py:347` tried UI dump once; `:736` correctly rejected the resulting warning. All nine route triplets are intact; artifact upload passed | First resumed Activity preceded its accessible application frame. Poll fresh UI within a bounded window; require an application UI node for initial Activity evidence, then capture a real framebuffer PNG and Activity dump. Retain partial components on failure, validate PNG/XML, and index acquisition timestamps, byte counts and SHA-256. Evidence acceptance verifies every passed behavioral check and all nine route triplets, including file hashes | **PASS, focused tests:** transient root followed by fresh app UI produces complete evidence; PNG alone does not pass; missing/changed components remain BLOCKED. **No upload-loss evidence:** all 161 archived files were downloaded and inspected. Future real captures remain **UNVERIFIED**; no HTML screenshots or old XML substitute |

### Do the timeouts have a common cause?

They share the generic `wait()` reporting defect, but **one common runtime cause is not proven**. The hardware timeout is conclusively obstructed by the undismissed permission dialog. The backend timeout occurred earlier, before the media request, so that dialog cannot explain it. Its reverse-rule fault injection was inadequate evidence of an outage; several 30-second waits existed and #121 retained no traceback identifying which expired. New wait labels, same-phase UI timestamps, timeout snapshots and exception tracebacks preserve that distinction in future evidence.

The ADB listener implementation was reviewed as corroborating source: [listener removal](https://github.com/LineageOS/android_packages_modules_adb/blob/lineage-22.2/adb_listeners.cpp#L146) erases the listener, whose destructor closes its listening fd. This is an Android 15 source mirror, not a claim of exact SDK 37 source equivalence or proof of the unrecorded #121 socket state. The replacement test establishes an actual disconnected service instead of depending on that inference.

## Exact changed files

| File | Change |
|---|---|
| `.github/workflows/aaos-emulator-validation.yml:56` | Early approved-asset gate, its finalizer outcome and focused acceptance regression tests |
| `.gitignore:147` | Allow the approved public guidance recording to accompany its manifest; no binary added without matching approved bytes |
| `tests/automotive/validate_assets.py:10` | Read-only guidance URL/file/hash inspection; explicit missing/mismatched asset report and exit 69 |
| `tests/automotive/validate_emulator.py:151` | Strict OS-dialog/denial-row recognition |
| `tests/automotive/validate_emulator.py:345` | Labeled waits, same-phase observation timestamps and timeout evidence; exception tracebacks |
| `tests/automotive/validate_emulator.py:412` | Bounded fresh UI acquisition, actual PNG validation and component receipts |
| `tests/automotive/validate_emulator.py:525` | Explicit permission-modal obstruction check |
| `tests/automotive/validate_emulator.py:642`, `:655`, `:777` | Owned service lifecycle, verified backend outage, capture while locked and recovery evidence |
| `tests/automotive/validate_emulator.py:828`, `:901` | Denial observation/cleanup independent of WebView; complete successful-check evidence validation |
| `tests/automotive/fixtures/aaos_permission_denial.xml` | Actual #121 OS hierarchy, formatted for review; synthetic test profile, no new observations |
| `tests/automotive/test_acceptance_regressions.py` | Eleven focused regression cases for the above contracts |
| This report, `EMULATOR_VALIDATION.md`, `AAOS_CAR_COMPATIBILITY_AUDIT_20261019.md` | Current acceptance status and historical cross-reference |

No files under `apps/` or `services/` changed. Native fail-closed Car UX, backend/provider behavior, WebView origin/media policy, health modules, approved manifest/hash and real data remain untouched. No main changes, merge, deployment, Windows/device checks, extra infrastructure or Actions trigger.

## Verification executed in Cloud

The existing isolated official **Ubuntu 24.04.5** container was reused with Python **3.11.17**, Node **22.20.0**, Java **21.0.12.1+1**, Gradle **8.11.1**, AGP **8.9.2**, SDK/build tools **35 / 35.0.0** and existing pinned dependencies. Host ports were already occupied, so real service checks ran inside this audit's Docker namespace; existing host listeners were not stopped or reused.

The early asset gate and its failure finalizer were also executed with Noble's system Python 3.12, since the workflow intentionally performs this read-only check before setup-python. Finalization and the artifact cap explicitly use `python3`, so they remain available on that early failure path.

- **PASS:** 55 focused Python tests + 10 subtests, including 69 existing policy assertions, 22 existing Car-source assertions, actual missing-class safety execution, and eleven new acceptance regressions. XML replay and mocked device responses are explicitly host tests.
- **PASS:** three existing Node WebView harness tests; no protocol/media behavior changed.
- **PASS:** actual Cloud backend keep-alive, owned shutdown, new/existing connection failure and restart; real Next server confirms approved URL 404 and different hash at the legacy URL. No audible playback, capture or paid provider call.
- **PASS:** offline debug/release APK assembly and Android lint (91 Gradle tasks); observer assembly/lint (43 tasks). Existing warnings remain; no lint errors. These do not establish corrected Android harness behavior.
- **PASS:** all four workflows validated with actionlint 1.7.12; Python compilation, existing installer Bash syntax and Git whitespace checks.
- **BLOCKED as intended:** source-asset preflight identifies exactly the missing approved mental-entry recording. Its offline finalizer reports all emulator scenarios BLOCKED, with `first_failed_stage=assets`; it does not invent native failures or passes.
- Reused #121's successful web build, SDK/native dependency audit and actual AAOS successes. No 783-test rerun, dependency reinstall, model work or emulator launch.

Evidence: `ubuntu-focused-tests.log`, `ubuntu-node-tests.log`, `ubuntu-android-build.log`, `ubuntu-probe-build.log`, `host-service-validation.log`, `host-services/host-service-results.json`, `asset-preflight.log`, `source-packaging/`, complete `run-121.log`, `run121-artifacts/`, `evidence-summary.json` and `evidence-sha256.json`, all under `/workspace/attune-aaos-acceptance-audit-20261019/`.

## Remaining limits and next step

1. **Required external prerequisite:** restore only the approved mental-entry recording matching the manifest SHA-256. Its Cloud/GitHub location has been requested. No substitute recording or altered hash is justified. Until then the workflow intentionally stops before SDK downloads/builds and no new run is requested.
2. **UNVERIFIED:** corrected Android offline lock/recovery, actual AAOS denial action and cleanup, independent absent-hardware scenario, first-frame capture and full evidence indexing on a new emulator. This Cloud workspace has no KVM; no software-emulation fallback was attempted.
3. Unknown permission-controller layouts/locales remain BLOCKED with UI evidence and cancellation; cancellation is never treated as a denial-button pass. Media hardware advertisement does not establish physical capture, audible playback or device acceptance.
4. Every new behavioral/evidence failure remains visible. Successful #121 checks stay historical PASS; failed or blocked scenarios are not retroactively changed.
5. Standard GitHub-hosted Ubuntu only, **40-minute** timeout, **50 MiB** artifact ceiling (49 MiB source plus ZIP margin), **one-day** retention, 256-file ceiling, feature-only routing and no automatic retry remain intact. Artifact capacity and a zero-billing outcome are not newly claimed.

After the exact asset is available, validate its hash, source tracking and served response, then request approval for one bounded manual run. **Current readiness: consolidated harness checks pass; source package and remaining AAOS acceptance are still partial.**
