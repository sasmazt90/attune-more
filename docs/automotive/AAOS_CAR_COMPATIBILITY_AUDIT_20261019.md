# AAOS Car API compatibility audit after run #120

> Historical audit: run #121 subsequently passed installation, public Car API
> observation, nine routes and independent moving locks. Remaining acceptance
> is documented in [AAOS_ACCEPTANCE_AUDIT_20261019.md](AAOS_ACCEPTANCE_AUDIT_20261019.md).

Actions remains stopped. This audit used managed Cloud only and launched no new emulator guest or GitHub Actions job. The correction retains AAOS 35-ext15 and the public Car UX APIs. Installation and application acceptance of the corrected APKs remain unverified.

## First actual failure

[Run #120](https://github.com/sasmazt90/attune-more/actions/runs/39284151482), job `118165231682`, ran source `800c234b68b8d66af0fdf764ec7c8358d0241aa6`. Its complete 1,658-line job log was retrieved, together with all 39 files in artifact `12201623789` (375,049-byte ZIP, SHA-256 `fedc9c9aad0fd85dcc5464980a35a73052389b4ed093b49d47b50b876d2cf395`).

At **16:21:42.1194333 UTC**, log line **1515**, Package Manager rejected the application:

```text
INSTALL_FAILED_MISSING_SHARED_LIBRARY: ... Package more.attune.automotive.prototype.debug
requires unavailable shared library android.car; failing!
```

Linux ABI checks, SDK/image setup, web build, both APK builds and host preflight had passed. The emulator booted once in **34.548 seconds**. `aaos-runtime` passed; `apk-install` failed; the other **14 checks and all nine routes were BLOCKED**. No product Activity, WebView, application permission check or independent safety scenario executed. Startup screenshot/UI warnings are separate from the install failure.

## Exact platform evidence

| Observation | Evidence / conclusion |
|---|---|
| SDK package | `system-images;android-35-ext15;android-automotive;x86_64`, revision **4**, API **35**, extension **15**, ABI **x86_64**, tag `android-automotive,google_apis`; run artifact `system-image-package.txt` and `runtime-image.json` agree |
| Guest identity | `google/sdk_gcar_x86_64/emulator_car64_x86_64:15/AAI5.260516.001.A6/16618942:userdebug/test-keys` (`system-image.txt`); independently installed official package has the same fingerprint in `build.prop` |
| Driver/display | Current user **10**, display **1280×800**, density **160** (`display-and-user.txt`) |
| Car Service | Actual `car-service.txt:505` contains `CarUxRestrictionsManagerService`; line **510** reports driver display 0 `DO: false UxR: 0`; line **561** confirms `mEnableActivityBlocking:true`; display 3 remains restricted |
| Features | Actual `system-features.txt` advertises automotive and WebView, microphone, and no `camera.any` |
| WebView | Actual provider `com.google.android.webview` **147.0.7727.137**, installed/enabled for all users |
| Runtime Car implementation | Read-only inspection of the matching official image extracted `/system/framework/android.car.jar`, `/system/framework/android.car.builtin.jar` directory entries and `/system/etc/classpaths/bootclasspath.pb`. The classpath protobuf includes both jars. DEX inspection confirms `Car`, `CarUxRestrictionsManager`, `CarUxRestrictions` and the exact signatures of all seven used methods are PUBLIC/SDK APIs |
| PM shared-library registration | The real installation error proves PM could not resolve required shared library `android.car`. **`pm list libraries` was not captured in #120**; neither were full package/feature queries beyond the saved feature list, nor live `BOOTCLASSPATH`. Their output is not reconstructed or claimed as executed |

The official image was inspected without booting, remounting, patching or replacing it. Its GPT super partition was decoded using the AOSP liblp metadata layout; geometry/header/table SHA-256 checks were verified. Logical partition extents were copied into isolated audit files and read using default read-only `debugfs`. The runtime jar was inspected with SDK 35 `dexdump`. This proves image contents; live public API connectivity from this app remains a separate emulator check.

The original manifest conflated **SDK compile-time use** with **PM shared-library loading**. `useLibrary 'android.car'` supplies compile-time SDK stubs. This image supplies the implementation on the boot classpath, rather than a PM library named `android.car` that an APK can require. The correct fix is removing the erroneous manifest shared-library requirement in both APKs while retaining the compile-time library and runtime safety dependency. No `android:required="false"` substitution, framework injection, privileged grant or UX override is introduced.

## Root-cause and correction matrix

Locations below refer to the corrected files; original manifest requirements were at application line 18 and probe line 7 in source `800c234`.

| Issue / severity | Exact source location | Evidence / root cause | Correction and validation before another run |
|---|---|---|---|
| **First failure — blocking** | `apps/automotive/app/src/main/AndroidManifest.xml:18`; `apps/automotive/app/build.gradle:7` retained | #120 log 1515 + actual image boot-classpath entries: manifest requires a PM shared library absent from this image | Remove only the manifest library entry; retain SDK `useLibrary`, automotive/WebView features and existing permissions. Rebuilt debug/release `aapt dump badging` confirms no required or optional `android.car` PM dependency |
| **Next predictable install failure — blocking** | `tests/automotive/emulator-probe/src/main/AndroidManifest.xml:7` | Probe has the identical manifest requirement; it was never installed in #120 | Apply the same correction; actual observer APK build/lint and packaged identity/declaration checks pass |
| **False host acceptance — high** | `tests/automotive/validate_emulator.py:132` | Old host preflight asserted that the defective manifest dependency existed, without comparing to the guest integration | Packaged checks now reject that dependency; require actual compiler availability for safety tests; both real APK identities verified |
| **Missing platform compatibility gate — high** | `tests/automotive/validate_emulator.py:149`, `:472`, `:751` | Automotive feature and boot-complete alone did not establish Car library visibility or Car UX service readiness | New aggregate pre-install gate records properties, PM libraries/features/packages, Car package, binder/service, live boot classpath and driver state. Requires supported boot-classpath jar and file, Car UX manager, enabled Activity blocking and unlocked driver user. Failure is BLOCKED and prevents APK installation; parser/negative orchestration tests pass |
| **Missing API/linkage failure handling — high, latent** | `apps/automotive/app/src/main/java/more/attune/automotive/CarRestrictionSource.java:12`, `:47`, `:84` | Old class directly held Car types and caught RuntimeException only. Missing classes/methods could abort startup; asynchronous conversion and disconnect errors were not guarded | Isolate Car types behind a lazy connection, catch linkage/runtime failures to UNKNOWN, invalidate stale callbacks before cleanup, safely disconnect. Actual source executed with all Car classes physically removed from the host classpath; gate/media stay locked. 22 additional behavioral assertions cover errors, positive/restricted observations, disconnect, stale callbacks and restart |
| **Observer error reporting gap — medium, latent** | `tests/automotive/emulator-probe/src/main/java/more/attune/validation/RestrictionProbe.java:46` | Observer did not report LinkageError and could lose its result on disconnect failure | Record such failures as observer errors; still no invented unrestricted state. Actual probe build/lint passes; Android execution pending |
| **Premature UI evidence — medium** | `tests/automotive/validate_emulator.py:748` | Both actual #120 startup PNGs show system user Loading; `uiautomator` returned null root. These are not product UI defects | Installation/runtime infrastructure checks no longer demand product UI capture before an Activity exists. Product captures remain required from activity-start; all nine route PNGs and UI/activity evidence still required. Driver-unlocked wait is bounded; missing PNG/evidence tests still block acceptance |
| **Blocked root diagnosis — medium** | `tests/automotive/validate_emulator.py:248` | An incompatible platform should not be misreported as an application installation failure | New `execution.json.first_blocked_check` records the first blocker separately from actual FAIL; regression verifies downstream installation stays BLOCKED |

## Official image alternatives

Google's SDK catalog and [AAOS emulator documentation](https://developer.android.com/training/cars/testing/emulator) were reviewed. The catalog snapshot is saved as evidence; no alternative image was downloaded or booted in this audit.

| Official x86_64 option | Catalog revision | Compatibility assessment |
|---|---|---|
| API 35-ext15, Google APIs (current) | 4 | Boot-classpath implementation and real Car UX service established above. Retain it; actual app API access still pending |
| API 35-ext15, Google Play | 4 | Same API family, different distribution. PM/boot-classpath visibility and exact Car UX behavior not independently verified; no evidence that switching fixes the declaration |
| API 34-ext9, Google APIs / Google Play | 5 / 4 | Official AAOS alternatives within the app's declared minSdk range. Requires intentional policy/API/device preflight changes and separate runtime acceptance; not a verified drop-in fix |
| API 33, Google APIs | 5 | Official older AAOS option; exact shared-library/classpath registration and behavior unverified |
| API 32 / 30, Google Play | 2 / 2 | Legacy official options within declared minSdk range. Older platform/provider behavior and hardware profiles require independent acceptance; not selected |

The exact image has the necessary public APIs and an operating restriction service, so switching platforms or replacing native restrictions with simulated speed is unjustified. The Android for Cars App Library is a different host/template integration; it does not replace this parked Activity's native Car UX and application safety gates.

References: [manifest library semantics](https://developer.android.com/guide/topics/manifest/uses-library-element), [public Car API](https://developer.android.com/reference/android/car/Car), [official image catalog](https://dl.google.com/android/repository/sys-img/android-automotive/sys-img2-5.xml), [AOSP super metadata layout](https://github.com/aosp-mirror/platform_system_core/blob/android-15.0.0_r1/fs_mgr/liblp/include/liblp/metadata_format.h). The SDK catalog's `35x`/`34x` schema labels are not used as guest API levels; installed source properties and actual runtime identify API 35.

## Exact changed files

1. `.github/workflows/aaos-emulator-validation.yml` — run focused safety/compatibility tests and retain their output before boot.
2. `apps/automotive/app/src/main/AndroidManifest.xml` — remove PM shared-library requirement; preserve features, permissions and parked Activity.
3. `apps/automotive/app/src/main/java/more/attune/automotive/CarRestrictionSource.java` — guarded, fail-closed Car connection and cleanup.
4. `tests/automotive/emulator-probe/src/main/AndroidManifest.xml` — matching declaration correction.
5. `tests/automotive/emulator-probe/src/main/java/more/attune/validation/RestrictionProbe.java` — explicit API/cleanup error evidence.
6. `tests/automotive/test_car_restriction_source.py` — real-source JVM execution with failure fixtures and with all Car classes absent; fixtures never enter an APK.
7. `tests/automotive/test_emulator_harness.py` — compatibility negative cases, exact matching, aggregate diagnostics, blocked installation/reporting.
8. `tests/automotive/validate_emulator.py` — packaged contract correction, early compatibility gate, first blocker reporting and correctly scoped UI capture.
9. `tests/unit/test_automotive_contract.py` — lock the boot-classpath manifest contract alongside existing safety/distribution tests.
10. This audit report.
11. `docs/automotive/EMULATOR_VALIDATION.md` — current status/reference.
12. `docs/automotive/AAOS_LINUX_RUNTIME_AUDIT_20261019.md` — historical report cross-reference.

## Executed verification

All execution was in Cloud. Native/tool checks used the existing official **Ubuntu 24.04.5** container, command-line tools **22.0 / 15859902**, emulator **37.2.12 / 16428233**, ADB **37.0.1**, SDK/build tools **35 / 35.0.0**, AGP **8.9.2**, Gradle **8.11.1**, Temurin **21.0.12.1+1**, Python **3.11.17**, Node **22.20.0**, Playwright **1.64.0**. These match the observed #120 versions (including its Java patch).

| Check | Result / evidence |
|---|---|
| Actual Android builds | **PASS** — offline debug + release APK assembly and lint, 91 Gradle tasks; observer assembly/lint, 43 tasks. Lint has 0 errors; existing JS-enabled warning and observer's two packaging warnings remain |
| Actual packaged contracts | **PASS** — debug, release and observer APK badging inspected; no PM `android.car` dependency; automotive feature and existing distribution boundaries preserved |
| Safety/harness/runtime unit checks | **PASS** — 44 Python tests + 10 subtests; includes actual 69 existing JVM policy assertions/9 Java syntax parses, 22 new source behavioral assertions and real class-absence execution. Host fixtures do not establish Android/ART results |
| WebView harness checks | **PASS** — three Node tests |
| SDK/native dependency preflight | **PASS** — 625 host ELF objects checked, six Android guest payloads excluded from host ldd; zero required errors. Six documented unused optional-object warnings remain; emulator normal/headless version reporting and renderer loads pass |
| APK/host import preflight | **PASS** — actual SDK tools, Java compiler, APK identities, documented Node Android API, keyless isolated backend import, initial simulation Park; `pip check` clean |
| Workflow/static checks | **PASS** — actionlint 1.7.12 on all four workflows, Python compilation, installer Bash syntax, `git diff --check` |
| Existing web build / 783 tests | Reused #120 successful web build and historical setup evidence. No full web suite or 783-test rerun |

An audit-container-only `/tmp/android-unknown` directory left root-owned by earlier inspection caused nonfatal crash-reporter permission messages during version reporting. Ownership was corrected only inside that isolated Cloud container; rerun startup checks are clean. No hosted-runner or application permission was loosened.

Raw evidence is outside tracked product paths: `/workspace/attune-aaos-car-compat-audit-20261019/`. Key files: `run-120.log`, `run120-artifacts/`, `partition-metadata.json`, `bootclasspath-decoded.json`, `image-public-car-api.json`, `official-image-alternatives.json`, `ubuntu-tests.log`, `ubuntu-android-build.log`, `ubuntu-probe-build.log`, `ubuntu-preflight/`, `evidence-sha256.json`. Runtime jar SHA-256: `f1d5c067d74c5e6ceb618d4cf08f605737e123b953a0172156d93ea73248249d`; classpath protobuf SHA-256: `07f2f6a761dfe65f9d72d37af9104954d4bc990a7733b1d49c2010b8444c19c1`.

## Remaining risks and readiness

- **UNVERIFIED:** live `pm list libraries`, package queries, shell boot classpath and driver readiness commands were not captured by #120. The new preflight deliberately blocks if any required evidence cannot be established, before product installation.
- **UNVERIFIED:** corrected APK installation/launch and public Car UX observer on ART. Host class-absence tests are failure-path evidence, not a substitute for emulator class loading and Binder behavior. No KVM is available in this Cloud workspace; no software-acceleration fallback or guest launch was attempted.
- **BLOCKED by #120 install failure:** all nine routes, actual WebView/backend networking, permissions, parked/moving independence, background lifecycle, fault recovery and product screenshots. First successful installation may still expose a genuine product/harness issue; no passes are predicted.
- Platform-dependent VHAL commands, user loading screens, access to a useful UI root, media advertisement and CDP availability remain possible blockers. Their existing safety checks stay enabled. SDK component versions/revision drift remains guarded, rather than silently accepted.
- Standard `ubuntu-24.04`, **40-minute** timeout, **50 MiB** artifact ceiling (49 MiB source plus ZIP margin), **one-day** retention, first-attempt-only execution, no automatic retries and feature-branch-only routing remain unchanged. No exact remaining artifact allowance or new billing outcome is claimed.

**Readiness: offline checks pass; ready for one separately approved manual validation, not accepted AAOS compatibility or production readiness.** No main modification, merge, deployment, web/backend/health implementation change, real data change, Windows/device work or Actions trigger is part of this audit.
