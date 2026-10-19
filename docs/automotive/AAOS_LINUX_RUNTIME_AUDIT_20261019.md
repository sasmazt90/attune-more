# AAOS Linux runtime audit after run #119

**GitHub Actions remains stopped.** This task starts no job, emulator guest, retry, deployment or paid service. Consolidated infrastructure changes are verified in managed Cloud before feature-only commit/push. This report supersedes the earlier readiness conclusion in `AAOS_PIPELINE_AUDIT_20261019.md`.

## First actual failure and previous verification gap

[Run #119](https://github.com/sasmazt90/attune-more/actions/runs/39275187024), job `118137690093`, source `4a093f699d9d18f2d5d261898c3a6ecc2c78d5d2`, failed at **15:09:04.7059669 UTC**. Complete job log line 616 identifies:

```text
/usr/local/lib/android/sdk/emulator/qemu/linux-x86_64/qemu-system-x86_64:
error while loading shared libraries: libpulse.so.0: cannot open shared object file
Process completed with exit code 127.
```

At that source, `.github/actions/setup-automotive-sdk/action.yml:30` ran `emulator -version` without installing/checking Linux dependencies. The launcher executes the normal QEMU binary for this invocation, whose ELF DT_NEEDED includes `libpulse.so.0` and Qt libraries. A future `-noaudio` boot flag does not remove a dynamic loader dependency. Neither the SDK launcher path fix nor a successful version check in an already provisioned Debian environment establishes readiness on a fresh Ubuntu runner.

The previous Cloud audit used **Debian 13**, with shared libraries already present. That was insufficient Ubuntu 24.04 evidence. This audit uses a **clean official Ubuntu 24.04 userspace container inside managed Cloud**, not Windows. The missing Pulse library is confirmed in #119; other missing libraries below were measured in clean Noble, not falsely attributed to the hosted job.

KVM, Node, Python, Java and SDK download steps passed in #119. APK compilation, image boot and the application harness were skipped. All application checks remain **BLOCKED**, with no application compatibility failure or success established by that run. The earlier #117 missing sdkmanager and #118 missing emulator PATH are separate historical failures documented in the prior audit.

## Reproduction configuration and evidence

- Repository `sasmazt90/attune-more`, existing branch `feature/aaos-oem-agnostic-prototype-20261019`, baseline `4a093f699d9d18f2d5d261898c3a6ecc2c78d5d2`.
- Ubuntu image `ubuntu:24.04`, manifest digest `sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac`; observed Ubuntu 24.04.5, glibc2.39. Cloud host is Debian 13/Linux 6.18.55; container userspace is Noble. This does **not** reproduce Azure's kernel, VM image, KVM or device model.
- Official command-line tools build 15859902/version 22.0; emulator37.2.12/build16428233; ADB37.0.1; compile SDK35; build tools35.0.0; AGP8.9.2; actual Gradle wrapper8.11.1; Node22.20.0; Playwright1.64.0. SDK version changes now fail before boot rather than silently changing the audited runtime.
- **Exact Actions CPython 3.11.17 for Ubuntu 24.04** downloaded from the `actions/python-versions` manifest/release `3.11.17-36876195594`, with a fresh virtualenv and actual workflow requirements. This avoids relying on the earlier standalone-Python build or preinstalled extra packages.
- Java is still configured as Temurin 21. #119 used 21.0.12+1; the available Cloud JDK tested is 21.0.12.1+1. The historical exact-patch download returned404. **Exact historical JDK bytes were not reproduced.** Core JNI dependencies, actual wrapper and debug/release/lint builds were tested with the available Java 21 patch; future jobs record/check their resolved Java major and ELF dependencies. Java patch drift remains a stated risk.
- Exact official AAOS35-ext15/android-automotive/x86_64 revision4 archive:1,402,295,681 bytes, SHA-1 `0ddb2dd3cf225407000c32e5d73a3f3529c6e94c`. Independently downloaded and verified, then a real SDK-manager installation completed. Official SDK-generated metadata was retained unchanged. Source properties report API35, extension15 and tags `android-automotive,google_apis`. The archive has `vendor.img` and a `data/` seed, **not userdata.img**. The preflight checks this actual packaging.

Evidence is outside product paths at `/workspace/attune-aaos-runtime-audit-20261019/`: complete `run-119.log`, ELF inventories, full APT metadata/install logs, installed-package snapshot, `ubuntu-soname-packages.json`, `ubuntu-tool-evidence/runtime-tools.json`, image/AVD evidence, build logs, test output and SHA manifest. SDK images, Python environments, caches, raw job logs and binary assets are not committed or uploaded to Actions by this audit.

## Root-cause matrix

Old locations name their immutable source. Other paths/lines refer to the consolidated patch.

| Issue / severity | Evidence and source location | Correction | Verification / remaining limit |
|---|---|---|---|
| Missing native dependency ordering — High, #119 primary | `4a093f6:.github/actions/setup-automotive-sdk/action.yml:30`; log:616; normal QEMU DT_NEEDED `libpulse.so.0` | Composite line10 installs the audited Noble runtime list before SDK execution. `scripts/automotive/install_linux_runtime.sh:1` uses only runtime packages plus binutils, no recommended extras. | Actual installer executed successfully in clean Noble; dpkg confirms `libpulse0` owns the exact SONAME. Both normal and headless emulator version commands pass. |
| Checking only the launcher misses QEMU/plugin dependencies — High | Launcher DT_NEEDED lacks Pulse; normal QEMU and Qt contain further dependencies; clean-before inventory found multiple missing SONAMEs | `runtime_preflight.py:95` inventories launcher, all emulator ELF components, command-line tools, ADB/platform tools and build tools with `readelf` and `ldd`; collects every required failure before emulator startup. Also checks actual system dlopen targets. | Full clean-before/after inventories retained. Final tools audit:625 host ELF objects, zero required errors. Missing-library aggregation/no-emulator-execution regression passes. |
| Hidden Python/OpenCV runtime dependencies — High, latent | Existing requirements plus inference/supervision dependency tree install **both** OpenCV distributions; clean venv `cv2.abi3.so` needed `libGL.so.1`, `libglib-2.0.so.0`, `libgthread-2.0.so.0` | Runtime policy includes `libgl1` and `libglib2.0-0t64`; complete Python-native scan at `runtime_preflight.py:214`, real imports and `pip check`. Production requirements unchanged. | Actual cv2/numpy/scipy/skimage/onnxruntime/backend imports pass in fresh Actions-Python Noble venv; all native wheel/stdlib dependencies inspected. No camera, inference or provider call. |
| CPython standard native DBM libraries — Medium, latent | Exact Actions Python `_dbm`/`_gdbm` needed `libgdbm_compat.so.4`/`libgdbm.so.6`, absent in minimal Noble | Explicit Noble names `libgdbm-compat4t64`, `libgdbm6t64`, verified from package metadata. | Actual package install, dpkg ownership and native extension scan pass. Tk desktop dependencies remain explicitly optional/unneeded. |
| Optional components have incompatible legacy ABI requirements — Medium, scope boundary | Emulator Qt TIFF plugin needs `libtiff.so.5`; old build-tools RenderScript tools need `libncurses.so.5`/`libtinfo.so.5`; Noble has no matching package candidates | Explicit optional-object inventory in `runtime_policy.json`; do not substitute ABI6 libraries or import old distro packages. Reject RenderScript sources under this policy. | Six optional warnings recorded: TIFF, four unused RenderScript host tools, Tk. Current Java-only app builds/lints without them. TIFF, RenderScript and Tk functionality is **not supported/certified** by this assessment. No platform safety test is skipped to clear a library check. |
| Incorrect loader context can create false missing-library results — Medium, audit finding | Standalone wheel/JVM libraries lack the importing process's private library context; Actions Python needs inherited `libpython3.11.so.1.0` lookup | `runtime_preflight.py:47` retains inherited library paths; per-component SDK, JVM and individual wheel `.libs` contexts only. Six Android/Bionic payloads are identified without host ldd. | Exact Actions Python executes all four renderer dlopen probes; JVM core dependencies pass. Regression preserves the Actions Python lookup path. No global combination of unrelated wheel libraries, copied system libraries or ABI aliases. |
| Upstream SDK refresh invalidates preflight — High, latent | Pinned ReactiveCircus `src/sdk-installer.ts:55` installs latest emulator again; `src/main.ts:207` catches failed pre-launch hook, then line213 still calls launch | Replaced that job stage with `run_emulator.py`. SDK/image installation happens once before preflight/builds; no SDK mutation between the final audit and launch. Existing AAOS options retained. | Source/control-flow review plus SDK-failure/KVM/early-exit/deadline regressions. New launch orchestration is **not claimed boot-proven** without KVM. |
| AVD lookup/configuration mismatch — Medium, caught before execution | Actual SDK22 creation ignored a custom ANDROID_AVD_HOME and registered under default `.android/avd` | `run_emulator.py:50` preparation uses the same default directory as the old action and an explicit data path, refuses an existing AVD, writes only owned resource configuration. HOME is never repurposed. | Actual shared preparation function executed in Noble; exact `attune-aaos` AVD created/configured and discoverable by `emulator -list-avds`. No guest boot. |
| Floating dependency environment and incomplete setup reporting — Medium | Python requirements have ranges; a prior successful enriched environment did not reproduce a cold install | `runtime-constraints.txt` freezes the fresh validated AAOS environment only; Python3.11.17 pinned. Finalizer includes image-stage outcome and all dependency blockers, rather than inventing product failures. | Fresh install succeeds, constraints resolve, `pip check` clean. Tests verify all library diagnostics survive finalization while app checks stay BLOCKED. SDK stable-channel version/image revision gates intentionally refuse future unaudited versions. |

## Verified Noble package names

The following **17 explicit provider packages** and **20 SONAME mappings** were verified using Noble APT metadata and installed `dpkg-query -S` ownership, not inferred from Debian names. APT installs their necessary dependency closure; base glibc/libgcc/libstdc++ and other resolved system/transitive libraries also appear in native inspection and the installed-package snapshot. `binutils` is the inspection tool dependency.

| Ubuntu 24.04 package | Checked SONAME(s) | Observed package version |
|---|---|---|
| `libpulse0` | `libpulse.so.0` | `1:16.1+dfsg1-2ubuntu10.1` |
| `libnss3` | `libnss3.so`, `libnssutil3.so`, `libsmime3.so` | `2:3.98-1ubuntu0.2` |
| `libx11-6` | `libX11.so.6` | `2:1.8.7-1ubuntu0.1` |
| `libxcb1` | `libxcb.so.1` | `1.15-1ubuntu2` |
| `libxext6` | `libXext.so.6` | `2:1.3.4-1build2` |
| `libxi6` | `libXi.so.6` | `2:1.8.1-1build1` |
| `libxkbfile1` | `libxkbfile.so.1` | `1:1.1.0-1build4` |
| `libsm6` | `libSM.so.6` | `2:1.2.3-1build3` |
| `libice6` | `libICE.so.6` | `2:1.0.10-1build3` |
| `libdbus-1-3` | `libdbus-1.so.3` | `1.14.10-4ubuntu4.1` |
| `libdrm2` | `libdrm.so.2` | `2.4.125-1ubuntu0.1~24.04.2` |
| `libgbm1` | `libgbm.so.1` | `25.2.8-0ubuntu0.24.04.4` |
| `libpng16-16t64` | `libpng16.so.16` | `1.6.43-5ubuntu0.7` |
| `libgl1` | `libGL.so.1` | `1.7.0-1build1` |
| `libglib2.0-0t64` | `libglib-2.0.so.0`, `libgthread-2.0.so.0` | `2.80.0-6ubuntu3.9` |
| `libgdbm6t64` | `libgdbm.so.6` | `1.23-5.1build1` |
| `libgdbm-compat4t64` | `libgdbm_compat.so.4` | `1.23-5.1build1` |

No PulseAudio daemon, audio playback, `libpulse-dev`, X server, browser installation, GPU driver suite, i386 compatibility libraries, training package or paid service is added. In particular, `libasound2` is a virtual/renamed choice on Noble; `libasound2t64` is the real package name, but the audited no-audio path does not require it, so it is not installed speculatively. Playwright uses its Android WebView API, not a desktop Chromium process; `playwright install --with-deps` is unnecessary here.

## Checks actually executed

| Check | Result | Evidence |
|---|---|---|
| Full Noble runtime installer | PASS | `ubuntu-runtime-installer-full.log`;17 names/20 SONAME owners verified independently in `ubuntu-soname-packages.json`. |
| Native linkage and symbol checks | PASS |625 host ELF objects;6 Bionic guest payloads excluded from host ldd;0 required errors;6 explicit optional warnings. `ubuntu-tool-evidence/runtime-tools.json`. |
| Emulator startup/version | PASS | Normal and `-no-window -version`, emulator37.2.12/build16428233; actual ADB37.0.1, sdkmanager22.0. |
| Dynamic graphics libraries | PASS for loading only | RTLD_NOW loads for SDK SwiftShader EGL/GLESv2 and Vulkan loader/SwiftShader ICD. This does not establish rendered frames, surface initialization or AAOS graphics behavior. |
| Exact image archive and SDK installation | PASS | Official checksum verified; actual SDK-manager install completed; source metadata and real partition/data files validated. |
| Exact AVD preparation/discovery | PASS | Actual `prepare_avd` function created/configured `attune-aaos`; emulator lists the AVD. `ubuntu-exact-avd.log`, generated config evidence. |
| Missing-KVM gate | PASS negative check | Actual runner returned69, with missing KVM/acceleration diagnostics, **before any AVD/guest boot launch**. `ubuntu-avd-verify.log`, `boot-blockers.json`. No `-accel off` fallback. |
| Python environment | PASS | Fresh actual Actions CPython 3.11.17 Noble archive; constrained runtime install, native imports, real backend import/initial Park, `pip check`, packaged app/probe identities and Car library preflight. |
| Native Java/Android builds | PASS | Debug/release assemble + both lint variants, Gradle8.11.1/AGP8.9.2,12s; probe assemble/lint,8s; actual project wrapper version verified. Cached dependencies reused. Existing JS-enabled/test-probe warnings remain, no new native errors. |
| Frontend production build | PASS | Actual Node22.20.0 production build in Noble; existing hook/img warnings. Web/backend/health source unchanged. |
| Focused regressions | PASS |37 Python tests plus10 subtests;3 Node policy tests; includes69 actual JVM policy assertions and syntax parsing of9 Java classes. No repeat of the783-test historical suite. |
| Workflow/static checks | PASS | All4 workflow YAMLs via actionlint1.7.12, composite YAML/Bash syntax, Python compile and semantic branch/manual/standard-Ubuntu/timeout/keyless/artifact/no-retry guards. External shellcheck/pyflakes integrations unavailable and disabled; other language checks executed explicitly. |

## Remaining pipeline review and preserved restrictions

The existing default-branch-registered `e2e-audit.yml` entry still selects only the feature's AAOS reusable job and skips the broad browser audit. No main change or PR is required. The generic Android workflow and main CI triggers remain unchanged. The feature push must be a normal fast-forward, with no open feature PR and no matching push-triggered workflow, checked before push.

The controlled launcher preserves API35-ext15, x86_64,2 cores,3072M RAM,4096M writable disk,1280×800/160dpi, headless SwiftShader, camera-none, no-audio, no snapshots, `-accel on`,600-second boot deadline and40-minute job timeout. It launches **once**, polls online ADB plus `sys.boot_completed=1`, fails on premature exit, checks ports/KVM/acceleration/free space before AVD creation, and terminates only its own emulator process group. Readiness polling is not a job/emulator retry. It retains the original animation settings and runtime harness. SIGTERM cleanup is explicit.

Existing runtime checks still require actual APK installation/current AAOS user, foreground Activity, genuine Car UX observations independent of backend simulation, fail-closed missing/stale data, nine true Android WebView routes, native Back/Home, pause/stop receipts and WebView destruction, real permission denial, hardware feature observations, tunnel faults/recovery and app crash/console evidence. No Car UX override/allowlist, fake vehicle result, synthetic media grant or consent change to human data is introduced. The app manifest, native safety policies, WebView security and release fail-closed configuration are unchanged.

Evidence remains restricted to49MiB source plus1MiB ZIP margin,256 files,200-byte paths,one-day retention, no AVD/system-image/venv/cache upload. Dependency JSON and host startup log are included in the existing evidence directory; private API data remains separate. Oversize evidence refuses upload. The first-attempt guard, public-repo/feature/manual checks and standard `ubuntu-24.04` runner remain. No larger/premium/self-hosted/paid infrastructure, merge, deployment or Actions dispatch occurs.

## Exact changed files

1. `.github/actions/setup-automotive-sdk/action.yml` — dependency installer before SDK usage; aggregate SDK preflight before emulator execution.
2. `.github/workflows/aaos-emulator-validation.yml` — explicit image stage, exact Python, constrained dependencies, tool preflight, controlled single-launch stage, image outcome reporting; limits retained.
3. `scripts/automotive/install_linux_runtime.sh` — Noble-only minimal provider-package installer.
4. `tests/automotive/runtime_policy.json` — expected versions, verified package/SONAME mappings and narrowly named unused legacy components.
5. `tests/automotive/runtime_preflight.py` — ELF/ABI/linkage/dlopen/version/image/native-import audits and complete machine-readable blockers.
6. `tests/automotive/runtime-constraints.txt` — AAOS-only Python runtime constraints from fresh Noble installation.
7. `tests/automotive/run_emulator.py` — auditable one-launch control, explicit AVD preparation, strict acceleration/readiness, failure cleanup; no later SDK reinstall.
8. `tests/automotive/test_runtime_preflight.py` — aggregation, loader-context, image, launch-refusal, boot deadline and configuration regressions.
9. `tests/automotive/validate_emulator.py` — image-stage outcome and dependency diagnostics in final reports.
10. `tests/automotive/test_emulator_harness.py` — library-blocker reporting regression.
11. `docs/automotive/AAOS_LINUX_RUNTIME_AUDIT_20261019.md` — this evidence/matrix/risk report.
12. `docs/automotive/AAOS_PIPELINE_AUDIT_20261019.md` — superseded-readiness notice, historical evidence preserved.
13. `docs/automotive/EMULATOR_VALIDATION.md` — current stopped status and latest audit link.

## Explicit remaining risks / readiness

1. **No KVM in this Cloud executor.** No guest boot, APK install/launch, Android screenshot or in-emulator application acceptance was executed here. #118's earlier boot does not prove the new launcher or application now passes.
2. **New launch orchestration is host-validated, not guest-validated.** Emulator CLI/version probes executed; no guest booted. Actual SDK/AVD creation/discovery and refusal paths passed; Azure KVM, process startup, boot readiness and cleanup against a running AAOS guest remain unverified.
3. **Exact historical Java patch not reproduced.** Tested21.0.12.1+1 differs from #119's21.0.12+1; Java 21 is the configured family and actual native builds/lint pass, but no byte-identical old-JDK assertion is made.
4. **Graphics/screenshot/UI runtime remains unverified.** dlopen is not rendering. The legacy `swiftshader_indirect` alias was resolved to SwiftShader by #118, but is absent from current GPU help; it is retained only with the audited emulator version. Original guest screencap crashes are still distinct from product crashes; emulator framebuffer capture must yield genuine PNGs in a future authorized run. UI-idle, CDP availability and Android permission-dialog lifecycle may yield BLOCKED results.
5. **SDK and image availability can change.** Stable SDK-manager downloads are fenced by audited emulator/ADB versions and image revision4; an update or download failure stops before boot. This is a drift guard, not a claim of permanent archive availability or a successful future cold download.
6. **Optional legacy functionality is unavailable.** TIFF5, RenderScript/ncurses5 and Tk GUI are outside the current headless Java/backend workflow. Adding such use requires a new dependency review, not ABI aliases.
7. **Native safety and permissions are still acceptance work.** Park/motion restrictions, platform blocking UI, foreground/background teardown, permissions, all nine Android routes and network failure recovery require actual runtime evidence. The existing gates may correctly prevent observations; no bypass is authorized.
8. **Metering and artifacts.** The existing bounded billing-risk authorization is historical; no new run is authorized by this audit. Current pooled storage/billing cannot be certified as zero. A hard job timeout/cancellation may prevent final artifact upload despite always-finalizers.

**Host dependency audit complete for the recorded configuration; AAOS application acceptance remains BLOCKED/UNVERIFIED. Actions stays stopped.** This report does not request an immediate rerun or certify OEM/production/physical-device/clinical/commercial readiness. Any later run requires separate explicit approval after reviewing this report and these limits.

## Primary references

- [Android Linux/system requirements](https://developer.android.com/studio/install): general IDE guidance is not substituted for measured x86_64 SDK dependencies.
- [Android emulator troubleshooting](https://developer.android.com/studio/run/emulator-troubleshooting): native dependencies and free-space requirements.
- [Android command-line environment variables](https://developer.android.com/tools/variables)
- [Official Automotive image catalog](https://dl.google.com/android/repository/sys-img/android-automotive/sys-img2-5.xml)
- [Noble libpulse0](https://packages.ubuntu.com/noble/libpulse0), [libglib2.0-0t64](https://packages.ubuntu.com/noble/libglib2.0-0t64), [libpng16-16t64](https://packages.ubuntu.com/noble/libpng16-16t64), [libgdbm-compat4t64](https://packages.ubuntu.com/noble/libgdbm-compat4t64)
- [Pinned former runner SDK installer](https://github.com/ReactiveCircus/android-emulator-runner/blob/a421e43855164a8197daf9d8d40fe71c6996bb0d/src/sdk-installer.ts#L55) and [pre-launch failure control](https://github.com/ReactiveCircus/android-emulator-runner/blob/a421e43855164a8197daf9d8d40fe71c6996bb0d/src/main.ts#L207)
- [Actions Python version manifest](https://github.com/actions/python-versions/blob/main/versions-manifest.json)
