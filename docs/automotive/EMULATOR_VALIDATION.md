# Controlled Cloud AAOS validation — one run authorized

> Current status (2026-10-19): manual runs #117 and #118 failed before any
> application acceptance. The complete root-cause audit, consolidated corrections,
> current Cloud verification and remaining runtime limitations are in
> [AAOS_PIPELINE_AUDIT_20261019.md](AAOS_PIPELINE_AUDIT_20261019.md).
> Earlier preparation/run-authorization statements below are historical. No new
> Actions execution is authorized by this audit; request approval after its verified
> feature-only commit/push. Use a new manual run, not a rerun attempt.

Prepared 2026-10-19 in managed Linux Cloud, `/workspace/attune-more`, from
`32b0f5278c94e2c1a1b91d01b52b9fdc439099ab` on
`feature/aaos-oem-agnostic-prototype-20261019`. No push, Actions dispatch, emulator
run, deployment, or Windows execution was authorized by preparation alone.

The owner subsequently authorized committing and pushing this feature branch and
exactly one manually dispatched standard-Ubuntu validation run. The owner accepts
limited possible artifact billing despite unverifiable remaining storage/pending
usage. No automatic retry, main merge, deployment, larger/premium runner, external
paid infrastructure or additional paid service is authorized. The runtime results
remain unverified until that single run actually executes.

## Verified feasibility and cost

- GitHub repository metadata identifies `sasmazt90/attune-more` as **public**, default
  branch `main`, not archived. Existing successful Actions runs were inspected:
  main CI `39188207275`; manual browser workflow `36955786226`, registered workflow
  ID `370615037`. These are historical evidence, not a new run or proof that current
  third-party-action policy accepts the emulator action.
- Existing app: AGP 8.9.2, Gradle 8.11.1 with distribution checksum, Java 17 bytecode,
  minSdk 29, compile/target SDK 35, build tools 35.0.0, required `android.car`,
  automotive and WebView features. Minimum SDK is a declared compatibility floor,
  not proof of acceptance on every API 29–35 system image.
- Google's stable SDK catalog contains
  `system-images;android-35-ext15;android-automotive;x86_64`, revision 4,
  download 1,402,295,681 bytes, SHA-1 `0ddb2dd3cf225407000c32e5d73a3f3529c6e94c`.
  It requires emulator >=36.3.1. Other catalog entries include API 29/30/32
  Automotive Play Store images, API 33 Automotive, and API 34-ext9 Automotive.
  Only **API 35-ext15 x86_64** is proposed for this finite run. SDK manager resolves
  the current stable image/emulator; installed versions and fingerprint are saved.
  This is not a claim that SDK manager pins image revision 4 forever.
- `ReactiveCircus/android-emulator-runner` accepts `android-automotive` and separate
  `system-image-api-level`. Its v2 tag resolved to commit
  `a421e43855164a8197daf9d8d40fe71c6996bb0d`; the new workflow pins that commit.
- GitHub documents hardware acceleration on standard hosted Linux runners. Use
  **standard `ubuntu-24.04`**, two emulator cores, 3 GiB emulator RAM, one job,
  1280×800 nominal landscape screen at 160 dpi (actual metrics saved),
  40-minute total timeout and 10-minute boot timeout. No larger, self-hosted, paid,
  Windows, or macOS runner. `/dev/kvm` is verified at run time; its absence blocks
  the run instead of falling back to slow emulation or paid capacity. The current
  managed Cloud workspace itself has no `/dev/kvm`; it is used only to prepare.
- Expected compute cost: **$0 while this repository remains public and the job uses
  the standard runner**. Cold dependency downloads/build/boot/checks are estimated
  at 15–35 minutes, not a measured runtime. Downloaded SDKs/dependencies stay on
  the disposable runner, with no uploaded AVD or persistent cache.
- Artifact storage is separate. Owner-provided billing evidence: GitHub Free,
  2,000 included minutes/month, 0.5 GB included storage, $0 billed, $50/month Actions
  budget, stop-at-budget and alerts enabled. The $50 budget is **not** a zero-spend
  guarantee. Current pooled storage and pending/accrued usage remain unavailable;
  the owner explicitly accepts that limited risk for this one run. The obsolete
  zero-cost-attestation variable is not required or set. No billing settings are
  changed. Evidence source files are limited to 49 MiB, 256 files and 200-byte
  relative paths, reserving 1 MiB for ZIP overhead under the **50 MiB artifact
  ceiling**, with **one-day retention**. Oversize evidence is not uploaded. No
  billable storage from other work is removed or certified. Rerun attempts stop
  before checkout/setup; no automatic job or workflow retry is configured.

## Manual dispatch without changing main

GitHub requires a manually dispatched workflow to be registered on the default
branch. The new dedicated file is not there. The **existing** registered
`e2e-audit.yml` is therefore the manual entry point: on this exact feature ref its
browser job is skipped and it calls the dedicated AAOS reusable workflow from
the same feature commit. Other refs retain the original browser workflow.
No changes to main and no broad test-suite run are required.

Under the owner's single-run approval, review/commit these files on this branch,
confirm the remote ref still permits a normal fast-forward push, push only this
branch, and dispatch **one** run using:

```bash
gh workflow run e2e-audit.yml --repo sasmazt90/attune-more \
  --ref feature/aaos-oem-agnostic-prototype-20261019
```

The new file also declares `workflow_dispatch` for future registration, but do not
assume it can be directly dispatched while absent from main. This preparation
does not authorize adding it to main or creating a PR. Current Actions allowlists,
SDK downloads, image boot and KVM are checked by the actual run; failures remain
BLOCKED/FAIL with evidence, never substituted with a phone emulator.

## Finite validation scope

1. Verify API 35, QEMU, automotive/WebView features and record system fingerprint,
   WebView provider, emulator version, source SHA and clean checkout status.
2. Assemble existing debug APK and separate test-only observer APK; install both.
   The observer instruments **itself**, calls public `CarUxRestrictionsManager`
   APIs and reports advertised camera/microphone features. It neither instruments
   the product nor writes vehicle state or restrictions.
3. Launch the actual product Activity. Verify process, foreground Activity, Park
   gate, WebView and existing FastAPI connectivity through `adb reverse`.
4. Open nine existing routes (`/`, `/skin`, `/dental`, `/vision`, `/hearing`,
   `/mental`, `/care`, `/profile`, `/privacy`), check visible headings and horizontal
   overflow, capture screenshots, exercise native Back/Home. Any consent clicks
   are explicit UI actions in a fresh disposable CI profile. No human profile,
   saved human consent, health analysis, photo, payment or appointment is used.
5. Separately exercise backend debug simulation at 75 km/h and Park, then emulator
   VHAL speed/Drive/parking-brake events while backend remains Park. Require real
   platform restriction observations and absence of visible health WebView. Do
   not set distraction-optimized metadata, policy overrides or allowlists.
6. Send Home and return: require a fresh native pause/stop event receipt and removal
   of the trusted WebView debug target. Active capture cancellation and process
   death/recreation are outside this finite smoke test.
7. Remove/restore backend and frontend reverse tunnels independently. Require
   fail-closed missing/stale data behavior, native page-load error, retry/recovery.
8. Verify initial Android camera/mic denial. Request media through a temporary
   trusted-page test button and deny any actual Android prompt. No Android grants
   are made. Missing hardware/request cancellation may BLOCK prompt coverage.
   Media comes only from the emulator; no physical device or audible check.
9. Compare genuinely absent PackageManager hardware features with native labels;
   if the image advertises both features, mark absence behavior UNVERIFIED rather
   than treating `-camera-* none` or muted audio as proof.
10. Capture UI hierarchy, screenshots, Activity/Car service dumps, lifecycle,
    crash/logcat and WebView errors; export JSON, JUnit XML and Markdown report.
    Intentional connectivity failures and blocked remote requests are recorded
    separately. JavaScript runtime errors still fail the console check.

Actual web/backend sources and production configuration are unchanged. All API
keys are blank, local env loading is off, data is isolated under runner temp,
remote browser requests are blocked, no secrets are inherited by the reusable
workflow, and no camera/mic stream is retained. Only bounded evidence is uploaded;
never API data directories, WebView profiles, weights, caches, keys or AVD images.

## Evidence semantics and limitations

`PASS` = named runtime observation established; `FAIL` = unexpected behavior or
assertion failure; `BLOCKED` = dependency/infrastructure/observation unavailable;
`UNVERIFIED` = an acceptance layer that the image cannot establish. BLOCKED and
UNVERIFIED are JUnit skipped entries with distinct reasons, and cause the harness
to return nonzero; an incomplete run cannot become a full pass. Missing results
after setup/boot failure are explicitly filled as BLOCKED. Failed setup/build may
only have hosted job logs and a blocked report, not emulator screenshots.

Debuggable WebView CDP must be available in the installed image. This harness
connects to the real Android WebView and never launches desktop Chrome. If CDP
or lifecycle receipts are absent, relevant checks are BLOCKED. Cold image boot,
first-run system screens, VHAL shell compatibility, WebView versions, and permission
prompt lifecycle behavior remain runtime uncertainties. This is one virtual car
configuration, not a matrix of API levels/screens/OEMs, a physical media check,
Google Play approval, production readiness or clinical acceptance. Unsupported
speech recognition, external picker restrictions and release fail-closed behavior
remain as documented in the prototype; this run does not replace them.

Prior host policy, Android build/lint, web smoke and 783-test setup evidence remain
historical. This preparation does not repeat those suites. Offline harness tests
and probe compilation validate only the new validation tooling, never AAOS behavior.

Preparation checks on 2026-10-19: **7/7 offline reporting/dependency tests passed**;
the observer debug APK **assembled successfully against real SDK 35** using cached
AGP/Gradle dependencies in Cloud (13 seconds); **actionlint 1.7.12 passed both
affected workflows**, with external shellcheck/pyflakes integrations disabled.
No product rebuild, full-suite rerun, emulator launch or Actions run was performed.
The feature branch was absent in a read-only GitHub branch search at preparation.
After the single-run authorization, the seven offline tests and workflow/Bash
checks passed again; the observer with public PackageManager permission reads
compiled successfully in 14 seconds. Manual dispatch currently needs Cloud API
access to `api.github.com`; a repository GET from the Cloud CLI returned
`Forbidden`, while Git transport succeeded. This is an access blocker, not an
artifact-quota blocker. Do not work around the destination policy or change the
manual event into an automatic push/PR trigger.

## Exact prepared file changes

All paths below are relative to `/workspace/attune-more`. These changes are
prepared for the authorized feature-branch commit; generated probe builds/caches
are ignored.

| Path | Change |
|---|---|
| `.github/workflows/e2e-audit.yml` | Modified: feature-only manual routing; original browser job skipped on this feature ref |
| `.github/workflows/aaos-emulator-validation.yml` | Added: dedicated manual/reusable AAOS job, single-attempt guard and evidence limits |
| `tests/automotive/validate_emulator.py` | Added: finite runtime harness and evidence finalizer |
| `tests/automotive/test_emulator_harness.py` | Added: seven offline reporting/dependency tests |
| `tests/automotive/emulator-probe/.gitignore` | Added: exclude generated builds/caches/local keys |
| `tests/automotive/emulator-probe/settings.gradle` | Added: isolated test-only build settings |
| `tests/automotive/emulator-probe/build.gradle` | Added: isolated observer APK build |
| `tests/automotive/emulator-probe/src/main/AndroidManifest.xml` | Added: self-targeted instrumentation, no extra privileges |
| `tests/automotive/emulator-probe/src/main/java/more/attune/validation/RestrictionProbe.java` | Added: public Car UX/feature observer |
| `docs/automotive/EMULATOR_VALIDATION.md` | Added: feasibility, cost, scope, limitations and approval instructions |

GitHub Actions currently provides a documented free standard-runner path, so an
alternative service is not needed. If the approved run cannot obtain KVM or an
AAOS image, report the concrete blocker first. No other service has been verified
here to offer a genuinely free accelerated AAOS environment; do not substitute
Colab, Codespaces, a phone-only device farm, or a free trial as equivalent evidence.

## Primary references

- [GitHub runner acceleration](https://github.blog/changelog/2024-04-02-github-actions-hardware-accelerated-android-virtualization-now-available/)
- [GitHub billing and artifact storage](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Manual dispatch registration](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)
- [Emulator runner inputs and AAOS example](https://github.com/ReactiveCircus/android-emulator-runner/tree/a421e43855164a8197daf9d8d40fe71c6996bb0d)
- [Google stable Automotive SDK catalog](https://dl.google.com/android/repository/sys-img/android-automotive/sys-img2-3.xml)
- [AAOS emulator testing](https://developer.android.com/training/cars/testing/emulator)
- [Documented VHAL adb examples](https://developer.android.com/training/cars/testing/aaos-on-pixel)
