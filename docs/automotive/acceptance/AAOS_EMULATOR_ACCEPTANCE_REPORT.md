# AAOS emulator acceptance report

Attune.more is an **AAOS emulator-validated prototype** at `a3943b6c62e6f0282ff021e1de2f73a5c3c43e18`. The original run reports **17 PASS, 0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, with nine routes exercised. Acceptance is limited to the recorded debug APK and virtual automotive environment below. This report preserves an existing execution; no application tests, builds or emulator runs were performed while creating these documents.

## Provenance and execution

| Field | Evidence-backed value |
| --- | --- |
| Repository | https://github.com/sasmazt90/attune-more |
| Feature branch | `feature/aaos-oem-agnostic-prototype-20261019` |
| Validated source | [`a3943b6c62e6f0282ff021e1de2f73a5c3c43e18`](https://github.com/sasmazt90/attune-more/commit/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18) |
| Run | [#122, ID 39321125673, attempt 1](https://github.com/sasmazt90/attune-more/actions/runs/39321125673) |
| Executing job | [118295153003](https://github.com/sasmazt90/attune-more/actions/runs/39321125673/job/118295153003) |
| Routing | Manual `e2e-audit.yml` entry invokes `aaos-emulator-validation.yml` at the selected feature ref; unrelated browser-audit job skipped |
| GitHub conclusion | completed / success |
| Job duration | 10m51s reported by owner from GitHub UI; job timestamp fields unavailable through the connector |
| Preserved log interval | 2026-10-19 20:39:32.9473543–20:50:18.9654449 UTC; approximately 10m46s of emitted logs, not a billing duration |
| Source receipt | `source-commit.txt` exactly matches validated source; `checkout-status.txt` empty |
| Setup/build result | `execution.json`: assets, SDK, image, KVM, build, preflight, emulator all success; no first failed/blocked stage |

Original host preflight log records **45 passed, 4 subtests passed in 2.53s**. The original Next.js production build, debug APK build and read-only probe build succeeded. These are historical execution receipts, not newly reproduced checks. Expected BLOCKED/UNVERIFIED strings printed by negative host-test fixtures are not emulator failures; the 17 actual runtime results are separately recorded in `results.json`, `results.xml` and executing-job log lines 1604–1620.

## Exact tested environment

| Component | Observed configuration | Evidence |
| --- | --- | --- |
| Host | Standard GitHub-hosted `ubuntu-24.04`; Ubuntu 24.04.5 LTS; runner image 20261012.334.1; agent 2.337.0 | Executing-job log; `runtime-sdk.json` |
| Kernel / libc | 6.17.0-1022-azure / glibc 2.39; KVM required and available | `runtime-sdk.json`, `acceleration.txt` |
| Android image | `system-images;android-35-ext15;android-automotive;x86_64`, revision 4; API 35 extension 15; Automotive + Google APIs | `runtime-image.json`, `system-image-package.txt` |
| Fingerprint | `google/sdk_gcar_x86_64/emulator_car64_x86_64:15/AAI5.260516.001.A6/16618942:userdebug/test-keys` | `system-image.txt` |
| SDK / emulator / ADB | Command-line tools 22.0/build 15859902; emulator 37.2.12.0/build 16428233; platform-tools 37.0.1-15733141 | `runtime-sdk.json`, `host-preflight.json` |
| Android build | compile/target API 35; build-tools 35.0.0; AGP 8.9.2; Gradle 8.11.1; Java Temurin 21.0.12.1+1 | `apk-build.log`, immutable Gradle source, `runtime-sdk.json` |
| Web / Python tooling | Node 22.20.0, Python 3.11.17, Playwright 1.64.0 | `runtime-tools.json` |
| WebView | `com.google.android.webview` 147.0.7727.137 | `webview-provider.txt` |
| Virtual device | `attune-aaos`, `emulator-5554`, driver user 10; 2 virtual cores, 3072 MiB RAM, 4096 MiB data partition | `avd-config.ini`, `display-and-user.txt` |
| Actual display | 1280×800, density 160; all 25 original PNG IHDR dimensions independently verified | `emulator-command.json`, `display-and-user.txt`, PNGs |
| Launch | Headless, KVM, SwiftShader, no snapshot, no boot animation, no audio output, front/back camera disabled by CLI | `emulator-command.json` |
| Boot | Single launch; boot observed after 36.625 seconds | `boot.json` |

The preserved AVD file includes template defaults (including smaller LCD values and an emulated back camera). Actual launch overrides and runtime observations establish the tested display and camera absence. Configuration templates alone are not hardware evidence. Native preflight inspected 631 host ELF objects at the tools stage, with no required errors and five documented optional warnings: one unused TIFF plugin needing libtiff.so.5 and four unused RenderScript objects needing obsolete ncurses/tinfo5. Four SwiftShader/Vulkan load probes exited zero. This does not claim every optional SDK binary is compatible with Noble.

## APK identity

`app-debug.apk`: **56,158 bytes**, SHA-256 `2c49c1bc6b899ba547bf16349c569f4d3afd0a8a9781c54674e71f1de3732005`.

Application ID `more.attune.automotive.prototype.debug`, Activity `more.attune.automotive.MainActivity`, versionCode 1, versionName `0.1-prototype`, minimum API 29, target API 35. API 29 is a declaration, not evidence of API 29 runtime compatibility. `debug-package.txt` confirms the installed package. A separate self-targeted test-only probe (`more.attune.validation`) independently read public Car UX and PackageManager state; its build/install is logged, but its APK was not included in the original artifact. Do not manufacture a replacement artifact.

## Individual behavioral results

Every filename below is relative to the **flat root of the original ZIP**. The [manifest](AAOS_ACCEPTANCE_MANIFEST.json) inventories every referenced file with size and SHA-256. `results.json` supplies the original status/detail text.

| Check | Original status | Observed scope / original detail | Evidence members |
| --- | --- | --- | --- |
| aaos-runtime | PASS | API 35 real automotive emulator with WebView feature; fingerprint/provider recorded. | `system-image.txt`, `system-features.txt`, `webview-provider.txt`, `boot.json` |
| platform-compatibility | PASS | Boot-classpath Car jar, automotive/WebView features, Car UX service, enabled platform Activity blocking and unlocked driver user observed. PM android.car shared registration=False; public API connectivity remains a separate post-install check. | `platform-compatibility.json`, `platform-bootclasspath.txt`, `platform-libraries.txt`, `platform-car-service.txt`, `platform-user-state.txt` |
| apk-install | PASS | Debug app and separate self-targeted read-only Car API probe installed. | `debug-package.txt`, `host-preflight.json`, `app-debug.apk` |
| activity-start | PASS | am start -W succeeded; process and Activity observed. App-private callbacks checked separately. | `activity-start-launch.txt`, `activity-start.xml`, `activity-start-activities.txt`, `activity-start.png` |
| platform-parked | PASS | Real Car UX unrestricted AND fresh backend simulation Park; no UX override. | `platform-parked-car-api.txt`, `platform-parked.xml`, `platform-parked.png` |
| webview-backend | PASS | Actual Android WebView rendered Attune.more and fetched existing API via adb reverse. | `webview-backend.xml`, `webview-backend.png`, `backend.log`, `frontend.log`, `webview-driver.log` |
| navigation | PASS | Nine real WebView routes, visible headings, overflow check, native Back/Home; screenshots recorded. One AAOS viewport only. | `navigation.json`, `navigation.xml`, `navigation.png` |
| backend-moving-lock | PASS | Backend-only simulated 75 km/h removed WebView while real Car UX remained unrestricted. | `backend-moving-lock-car-api.txt`, `backend-moving-lock.xml`, `backend-moving-lock.png`, `backend.log` |
| platform-moving-lock | PASS | Emulator VHAL speed=10 m/s, Drive, parking brake off; actual Car UX restricted with backend still Park; no visible health WebView. | `platform-moving-lock-car-api.txt`, `platform-moving-lock.xml`, `platform-moving-lock.png`, `logcat.txt` |
| background-lifecycle | PASS | Home backgrounded app; fresh native pause AND stop receipts and absence of trusted WebView debug target observed; foreground Park restored. No active capture session was started. | `lifecycle-events.txt`, `background-lifecycle.xml`, `background-lifecycle.png`, `logcat.txt` |
| backend-offline | PASS | Stopped owned backend and verified connection refusal; native offline/stale gate removed WebView; same isolated backend restart restored fresh Park. | `backend-offline-fault.json`, `backend-offline-locked.xml`, `backend-offline-locked.png`, `backend-offline.png`, `backend.log` |
| web-load-error-recovery | PASS | Real WebView main-frame connection failure showed native retry state; retry restored existing web app. | `web-load-failed.xml`, `web-load-failed.png`, `web-load-error-recovery.png`, `webview-console.json` |
| permissions-initial | PASS | Camera and microphone Android runtime permissions both denied; no grants or privileged vehicle permissions. | `permissions-initial-car-api.txt`, `permissions-initial.xml`, `permissions-initial.png` |
| permissions-denial | PASS | Actual OS permission dialog observed; its denial control clicked; dialog dismissed and camera/microphone permissions remained denied. No physical media involved. | `permissions-denial-observation.json`, `permissions-denial-observed.xml`, `permissions-denial-prompt.png`, `permissions-denial-car-api.txt`, `permissions-denial.png` |
| unsupported-hardware | PASS | PackageManager reports absent camera; native status labels agree. Physical hardware is unverified. | `unsupported-hardware-car-api.txt`, `unsupported-hardware.xml`, `unsupported-hardware.png` |
| crashes-console | PASS | No app crash receipt or unexpected observed WebView JS/console error; intentional network fault phases logged separately. | `crash-buffer.txt`, `webview-console.json`, `logcat.txt`, `crashes-console.png` |
| evidence-capture | PASS | Valid framebuffer PNGs, fresh UI/activity evidence and matching acquisition hashes for nine routes and every passed behavioral check. | `evidence-index.json`, `results.json`, `results.xml` |

These statuses describe the assertions actually executed. `platform-compatibility.json` was written before APK installation and therefore says public Car API access is UNVERIFIED until the later probe succeeds. The subsequent per-scenario `*-car-api.txt` receipts establish that API access; preserve the earlier stage record unchanged. Similarly, `permissions-denial-observation.json` retains a pre-click `state: pending` alongside `denial_clicked: true`; post-click UI/probe observations and the final result establish dismissal and continued denial.

## Nine route baseline

| Route | Observed visible heading | Status | CSS viewport / document width | Original screenshot |
| --- | --- | --- | --- | --- |
| `/` | Attune.more | PASS | 1280 / 1280 | `route-dashboard.png` |
| `/skin` | Cilt Sağlığı | PASS | 1280 / 1280 | `route-skin.png` |
| `/dental` | Diş Sağlığı | PASS | 1280 / 1280 | `route-dental.png` |
| `/vision` | Göz Sağlığı | PASS | 1280 / 1280 | `route-vision.png` |
| `/hearing` | İşitme Sağlığı | PASS | 1280 / 1280 | `route-hearing.png` |
| `/mental` | Ruh Sağlığı | PASS | 1280 / 1280 | `route-mental.png` |
| `/care` | Sizin için uygun uzmanlar | PASS | 1280 / 1280 | `route-care.png` |
| `/profile` | Sağlık Geçmişim | PASS | 1280 / 1280 | `route-profile.png` |
| `/privacy` | Verileriniz sizin kontrolünüzde. | PASS | 1280 / 1280 | `route-privacy.png` |

Each screenshot has corresponding `.xml` and `-activities.txt` members, listed in the manifest. The native Back button returned from privacy to profile and native Home returned to `/`. Width equality is the harness's horizontal-overflow assertion, not a full visual or usability acceptance. This run does not cover 375/768/1440px layouts, actual 200% browser zoom, every form control or all content below the captured fold.

## Independent fail-closed safety architecture

The native gate requires all of: foreground Activity, public Android Car UX state UNRESTRICTED, and a backend snapshot no older than **2500ms** indicating Park, gear P, zero speed and no movement. Unknown, disconnected, stale, restricted or background states close the gate. Source: immutable `GatePolicy.java`, `CarRestrictionSource.java` and `MainActivity.java` references below.

1. **Backend gate independently exercised:** a debug-only backend simulation supplied 75km/h while the read-only Car API probe still reported `doRequired=false`, restriction flags 0. Native UI observation required the movement lock and absence of WebView. Backend returned to Park in cleanup.
2. **Platform gate independently exercised:** emulator VHAL speed 10m/s, Drive, parking brake off caused the real Car UX probe to report `doRequired=true`, flags 255, while the independent backend remained Park. The platform's normal Activity blocking remained enabled; health WebView was absent. VHAL was restored to Park and Activity relaunched afterward. Emulator input injection is not a certified physical signal source.
3. **Car API integration:** `android.car.jar` exists on the boot classpath, while `pm list libraries` does not register `android.car` as an installable shared library. Gradle retains compile-time `useLibrary 'android.car'`; the manifest has no erroneous install-time shared-library requirement. Runtime connection failures/LinkageError resolve to UNKNOWN. No distraction-optimized Activity declaration or UX policy override was added.
4. **Background:** fresh native pause and stop event receipts plus disappearance of the trusted WebView debug target were asserted, followed by fresh foreground Park recovery. No active recording/capture session was started; interruption of such a session is not established by this test.

## Permissions, missing hardware and fault recovery

- Camera and microphone OS permissions started denied and remained denied. The actual automotive microphone permission dialog was observed, its “Don't allow” control clicked, and dismissal/denial verified. This is not an actual camera dialog test: the image reported no camera.
- PackageManager reported `camera=false`, `microphone=true`, matching native unsupported-camera labels. No physical camera, microphone input, audible output, vehicle device or Windows execution was involved.
- Offline injection stopped only the harness-owned isolated backend, retained ADB reverse mappings, verified host connection refusal, observed native offline/stale lock and no WebView, then restarted that same backend and observed fresh Park plus WebView recovery. `backend-offline-fault.json` records locked/recovered true. Its approximately 2.462s stop-to-observation interval includes orchestration and is not an enforced latency SLA.
- Removing only the frontend reverse mapping produced an actual WebView main-frame connection failure and native retry state (`web-load-failed.png/.xml`). Restoring it and selecting retry restored the web app. Backend remained available. Backend and frontend faults were distinct.
- Debug web/API traffic used localhost ports 3000/8000 through ADB reverse and fresh isolated test data. External requests were blocked by the harness, API keys blanked and local env loading disabled. This does not establish production TLS, external provider availability, a production backend, or zero total billed infrastructure cost.
- Original guidance-asset preflight records 33 approved asset checks passing, including the approved mental-entry recording. Console check observed no unexpected WebView error; deliberate network-fault errors and blocked external resources are classified separately. Crash buffer contained no app crash. This is a finite observation interval, not exhaustive crash/security certification.

## Evidence integrity, privacy and retention

Original artifact ID **12220138469**, name `aaos-39321125673-1`, ZIP **5,475,596 bytes**, SHA-256 **`664c8bd56f13d9d59940290cbd6bb21e4b6ced48ba4033cdf3f9c44161f19171`**, matching GitHub's digest. ZIP CRC checks pass. **172 files**, **11,316,421 uncompressed bytes**, flat directory root, no directory entries, duplicate paths, traversal or symlinks. Retained unchanged in Cloud at `/workspace/attune-aaos-evidence-archive/39321125673/aaos-39321125673-1.zip` with extracted byte-identical copies under `/workspace/attune-aaos-evidence-archive/39321125673/extracted`.

The original `evidence-index.json` contains 25 capture groups / 75 PNG, UI and Activity receipts with matching acquisition size/hash and no capture errors. All 25 PNGs have valid chunk CRCs and 1280×800 dimensions; all 16 JSON and 27 XML files parse, including JUnit totals 17 tests/0 failures/0 skipped. Every ZIP member was compared to its extracted copy and SHA-256 inventory. No original evidence was edited or regenerated.

Screenshot integrity proves acquisition and preservation, not that every frame depicts the instant asserted. Captures run after each scenario returns, sometimes after its `finally` restoration. `platform-moving-lock.png` and `background-lifecycle.png` show a restored Park screen; `backend-moving-lock.png` shows the dashboard although the captured XML has the native lock. The latter is a visual/UI state mismatch whose exact timing cause is not established by the archive. Do not use these PNGs alone as proof of the locked interval. The runtime assertions, independent probe, fresh UI/lifecycle receipts and source control flow provide the behavioral evidence. Explicit intermediate captures do show backend-offline lock, web-load failure and the OS permission dialog. Pixel-level transition timing and compositor synchronization remain unverified; this preservation task makes no code change or new test to resolve them.

Complete executing-job log exported through the GitHub connector is saved separately as `job-118295153003.log`: **169,234 bytes**, SHA-256 **`73ca5a08bbe03051e9817665aa30b0e74c328ef24f9e466268c72d077d908c20`**, 1,753 lines. It preserves the connector's UTF-8/BOM text; it is not claimed to be the original raw GitHub log-download ZIP. The unrelated job was skipped. Original run metadata is retained privately alongside the archive.

Privacy review covered all 25 original screenshots, 188 distinct XML text labels, text-pattern checks and source/packaging review. No real user health records or credentials were found. Visible portraits match the existing approved preparation illustrations in `HealthStartCard.tsx`; no test participant photos were captured. Generic driver/local-user/demo fields are not real patient observations. Raw dependency logs contain public package-maintainer contact metadata, and emulator logs include diagnostic identifiers. **No raw binary evidence or full logs were published.** Keep the original private pending approval; this bounded review is not a blanket privacy, security or asset-rights certification. These lightweight documents contain no raw personal data or credentials.

The original artifact expires **2026-10-20 20:50:15 UTC**. The workspace copy is independent of that expiration but is **not a permanent archive guarantee**. Permanent binary location is **PENDING OWNER APPROVAL**, `stable_url: null` in the manifest. The [archive publication plan](ARCHIVE_PUBLICATION_PLAN.md) is ready for review. Never substitute the expiring Actions URL for durable storage.

## Reproduction protocol and acceptance criteria

No reproduction is authorized or performed by this preservation task. For a separately approved future execution:

1. Preserve/check out exact source `a3943b6c62e6f0282ff021e1de2f73a5c3c43e18` in an isolated Cloud checkout, retain the approved audio/assets and hashes, and consult the immutable source inventory. An installed APK's SHA identifies this run's exact debug binary; debug signing, runner image, packages, system image/WebView availability and action major tags can change, so source identity alone does not guarantee a byte-identical rebuild.
2. Use the registered **Attune browser audit** manual entry selecting this feature branch, which routes to the reusable AAOS workflow. If the branch has advanced, first review the source diff; a branch dispatch cannot be represented as testing the old SHA merely because this document exists. No default-branch merge is needed.
3. Retain standard `ubuntu-24.04`, initial attempt only, 40-minute timeout, KVM requirement, one emulator launch, no automatic retry, original runtime policy/constraints, one-day artifact retention and 50MiB cap. Record any availability/version drift as a blocker or explicit reviewed change. Do not turn policy unknown/restricted states into Park to get a pass.
4. Follow the existing workflow's asset, SDK/library, image, build/import and host checks before the single boot. Use isolated disposable data and no external paid services, real user data or physical capture. Runtime expectations are defined by `validate_emulator.py` and `webview_driver.cjs`, not inferred from screenshots alone.
5. Acceptance requires all 17 named checks PASS, all nine route rows PASS, independent safety-gate evidence, actual OS denial observation, complete fresh UI/Activity/PNG evidence, no unexpected observed console/native crash, no failed stage and artifact integrity within bounds. A failed prerequisite leaves dependent observations BLOCKED; absent capability is UNVERIFIED, never a fabricated PASS.
6. Download the original bytes before expiry, verify hosted digest/ZIP CRC/member hashes, save full executing-job logs and metadata, and record a separately approved durable location. Keep any future execution results separate from this immutable baseline.

## Immutable source references

The [manifest](AAOS_ACCEPTANCE_MANIFEST.json) includes size/SHA-256 for these source files at the validated commit, plus package lock, backend requirements and static-illustration component. References are pinned to the validated source, not the later documentation commit.

- [.github/workflows/e2e-audit.yml](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/.github/workflows/e2e-audit.yml)
- [.github/workflows/aaos-emulator-validation.yml](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/.github/workflows/aaos-emulator-validation.yml)
- [.github/actions/setup-automotive-sdk/action.yml](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/.github/actions/setup-automotive-sdk/action.yml)
- [scripts/automotive/install_linux_runtime.sh](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/scripts/automotive/install_linux_runtime.sh)
- [tests/automotive/runtime_policy.json](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/runtime_policy.json)
- [tests/automotive/runtime-constraints.txt](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/runtime-constraints.txt)
- [tests/automotive/runtime_preflight.py](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/runtime_preflight.py)
- [tests/automotive/run_emulator.py](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/run_emulator.py)
- [tests/automotive/validate_emulator.py](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/validate_emulator.py)
- [tests/automotive/webview_driver.cjs](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/webview_driver.cjs)
- [tests/automotive/validate_assets.py](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/validate_assets.py)
- [tests/automotive/emulator-probe/src/main/java/more/attune/validation/RestrictionProbe.java](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/tests/automotive/emulator-probe/src/main/java/more/attune/validation/RestrictionProbe.java)
- [apps/automotive/app/build.gradle](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/app/build.gradle)
- [apps/automotive/build.gradle](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/build.gradle)
- [apps/automotive/gradle/wrapper/gradle-wrapper.properties](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/gradle/wrapper/gradle-wrapper.properties)
- [apps/automotive/app/src/main/AndroidManifest.xml](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/app/src/main/AndroidManifest.xml)
- [apps/automotive/app/src/main/java/more/attune/automotive/GatePolicy.java](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/app/src/main/java/more/attune/automotive/GatePolicy.java)
- [apps/automotive/app/src/main/java/more/attune/automotive/CarRestrictionSource.java](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/app/src/main/java/more/attune/automotive/CarRestrictionSource.java)
- [apps/automotive/app/src/main/java/more/attune/automotive/MainActivity.java](https://github.com/sasmazt90/attune-more/blob/a3943b6c62e6f0282ff021e1de2f73a5c3c43e18/apps/automotive/app/src/main/java/more/attune/automotive/MainActivity.java)

See [limitations](AAOS_ACCEPTANCE_LIMITATIONS.md) for unverified scope and the [OEM summary](OEM_TECHNICAL_VALIDATION_SUMMARY.md) for the bounded external-facing designation.
