# OEM-independent Android Automotive prototype

This implements a separate **AAOS parked application prototype**, using a native
Android Activity and a restricted WebView. It preserves the Next.js application,
FastAPI API, five health modules, consent/storage contracts, simulation and safety
checks. It is not Android Auto phone projection and is not approved for production
distribution, clinical use, or any OEM.

## Architecture and reuse

```text
Android AAOS parked Activity (apps/automotive)
  +-- CarRestrictionSource -> CarUxRestrictionsManager (display UX policy)
  +-- VehicleDataProvider  -> debug: existing FastAPI simulation
  |                        -> release: unavailable, fail closed
  +-- GatePolicy: foreground AND platform unrestricted AND fresh PARK observation
  +-- Hardened WebView -> existing Next.js -> existing FastAPI health/business APIs
```

`VehicleDataProvider` is a read-only Java adapter boundary (start/stop/observation).
It parallels the existing TypeScript `IVehicleProvider` without replacing it or
translating its demo identity fields into native authentication. A future adapter
must obtain authorization, validate source/units/consistency, timestamp observations
using a monotonic clock, and emit unavailable on disconnect. This prototype requests
no raw vehicle-speed/powertrain permission and does not implement that adapter.

`BackendSimulationVehicleProvider` reads `/api/vehicle/state` and invokes the
existing `/api/vehicle/speed` only on explicit debug simulation-button use. Native
status identifies the source as simulation. It retains only speed, park/move,
gear and local receipt time; no driver identity, location or health payload is needed.
Timeout, malformed data, transition or loss of connectivity invalidate eligibility.
Late results are rejected by lifecycle/mutation generations. The watchdog rejects
observations older than 2.5 seconds, even if the last value was PARK.

Android's `CarUxRestrictionsManager` independently controls the platform gate.
Missing/unready/disconnected services lock the app. Debug simulation does not
fabricate platform unrestricted state. Release excludes simulation controls and
uses `UnavailableVehicleProvider`, so it cannot enable health screens as shipped.

## Platform and distribution boundary

Official [Android for Cars categories](https://developer.android.com/training/cars)
do not list this health/wellness product as a standard supported category. Do not
label it a browser, navigation, media or IoT app to evade category rules. This is a
developer-installed prototype; official distribution requires a supported path or
separate platform/OEM engagement and review.

The [AAOS parked-app guide](https://developer.android.com/training/cars/parked/automotive-os)
requires lifecycle-aware interruption and use of platform UX policy. Accordingly,
the manifest requires automotive/WebView features, does not mark the Activity
`distractionOptimized`, avoids forced orientation/immersive UI, and leaves system
bars/cutouts under Android control. No custom template service/category is claimed.

## Lifecycle, UX and recovery

- Native Home/Back/Retry controls have 64dp minimum height and remain available
  without relying on a car's hardware back button. A small native-only CSS asset
  raises web navigation/form targets to 48 CSS px; no product redesign is applied.
  Android density and the existing responsive layouts provide scaling; landscape
  and portrait are both permitted. On-device insets/density behavior is unverified.
- The gate closes on backgrounding, Android restriction, stale/moving/unavailable
  vehicle data. Closing destroys the WebView, stopping capture/playback/JS/network
  and dropping unsaved activity state. Lifecycle/provider callbacks cannot restore
  an old session. Returning to eligible PARK creates a fresh page; existing
  consented records remain in the app's separate WebView storage.
- A main-page/TLS/renderer failure destroys the view and requires explicit Retry;
  invalid certificates are never accepted. Vehicle polling can recover after
  network return, but media/conversations are never restarted automatically.
- OS permission dialogs can pause the Activity. If that happens, the pending
  WebView request is denied and the page/session is discarded; after granting an
  OS permission the user must start again. This conservative behavior needs real
  Android runtime validation before improving continuity.

## Hardware, permissions and module compatibility

No camera or microphone is assumed. Native feature detection is independent of
the backend's demo hardware fields. WebView media requests require the exact
trusted web origin, a currently eligible foreground gate, real feature presence,
the corresponding Android runtime permission and only whitelisted audio/video
resources. Unknown resources are denied. Existing web service/data-transfer
consents still apply; native grants do not alter them. See Android's
[PermissionRequest contract](https://developer.android.com/reference/android/webkit/PermissionRequest).

| Existing module | Reused behavior | AAOS limitation / restriction |
| --- | --- | --- |
| Skin | MediaPipe alignment, eyewear checks, bounded local appearance pipeline, history and consent | PARK only; usable camera, models/WASM and WebView performance required. Many AAOS devices expose no app camera. Clinical accuracy not established. |
| Dental | Existing preparation/camera/multi-pose analysis and local ONNX backend | PARK only; camera path capability-dependent. External photo file picker is deliberately unavailable because leaving the Activity destroys the initiating session; web desktop upload remains unchanged. |
| Vision | Existing spoken letter/calibration/response logic and cancellation | PARK only; camera, recognition implementation and calibrated display assumptions required. Web Speech recognition is commonly absent in Android WebView; no fake or unapproved native replacement. Existing unavailable state applies. |
| Hearing | Existing headphone preparation, Web Audio and response protocol/history | PARK only; output routing, stereo/headphones, volume and actual audible behavior unverified. No clinical audiometry claim. |
| Mental | Existing service/cloud/recognition/speech consents, crisis and conversation logic | PARK only in this shell; Android WebView speech recognition may be unavailable. Backend key/network/TTS availability remains separate; no paid calls were authorized for prototype validation. |
| Care / history / privacy | Existing routes, consented records, handoff and deletion UI | PARK only. External HTTPS handoff needs a user confirmation and installed browser; the prototype does not book or pay. Browser/print/share behavior requires separate Android acceptance. |

## WebView and network boundary

There is no `addJavascriptInterface`, wildcard native message channel, native
vehicle-control bridge or embedded secret. Navigation and permission origins use
exact scheme/host/effective-port comparison. File/content URL navigation, mixed
content, automatic popups, geolocation and third-party cookies are disabled.
External HTTPS navigation with a user gesture requires confirmation and opens a
separate browser; unsupported schemes are blocked. Certificate errors are canceled.
The official [WebView bridge guidance](https://developer.android.com/privacy-and-security/risks/insecure-webview-native-bridges)
informs these boundaries.

Debug permits cleartext only to `localhost` / `127.0.0.1`, reached through explicit
adb reverse tunnels. This reuses current frontend API origins and FastAPI CORS
unchanged. Release disables cleartext and uses intentionally invalid placeholder
origins. It is locked until real integration exists. Do not expose the current
local API remotely: it has no remote multiuser authentication or tenant isolation.
Production needs HTTPS deployment, authentication, origin configuration, backend
provider authorization, endpoint hardening and a reviewed trust boundary.

## Build

Requires JDK 17+ (21 recommended), Gradle **8.11.1**, Android Gradle Plugin **8.9.2**,
SDK platform **35** (with `android.car` optional SDK library), build tools **35.0.0**.
App minimum API is 29, compile/target API 35. No runtime third-party Android
dependency is introduced. These are prototype pins, not a claim about current
store target-API eligibility. Install SDK/JDK tools through official distributions.
The standard wrapper includes a pinned distribution SHA-256 and downloads Gradle
and normal build dependencies on first use. The build script does not install the SDK.

```bash
# In a configured Android development environment:
sdkmanager 'platforms;android-35' 'build-tools;35.0.0'
export ANDROID_HOME=/absolute/path/to/android-sdk
export ANDROID_USER_HOME="${TMPDIR:-/tmp}/attune-android-user"
export PATH=/absolute/path/to/gradle-8.11.1/bin:$ANDROID_HOME/platform-tools:$PATH
python3 tests/automotive/run_checks.py
bash scripts/automotive/build.sh
# Expected artifact after a successful build:
# apps/automotive/app/build/outputs/apk/debug/app-debug.apk
```

The new `Automotive prototype` PR/manual workflow performs host checks, assemble
and lint; it does not run an emulator or deploy. A workflow file is not evidence
of a successful CI run. See [actual validation](VALIDATION.md).

With a read-only user home, set `GRADLE_USER_HOME` to a writable build cache and
keep `ANDROID_USER_HOME` outside product source. Use supported proxy and CA trust
for Java dependency downloads; do not disable certificate verification. The current
Cloud toolchain resides under `/workspace/.attune-tools/`; installing it did not
update/publish the environment's saved setup configuration.

## Reproducible AAOS emulator procedure (not yet executed)

Use the official [AAOS emulator guide](https://developer.android.com/training/cars/testing/emulator).
Select an actual available Automotive system image in Android Studio Device
Manager (or inspect `sdkmanager --list`), not a phone image. Include a supported
image without compatibility mode when validating native OS blocking. Do not
invent a system-image package ID; use the SDK's returned identifier.

1. Start an AAOS AVD with its normal vehicle UX restrictions. Do not grant
   distraction-optimization overrides, privileged car permissions or fake hardware.
2. Run the existing backend/frontend in separate host terminals, using isolated
   synthetic data and no provider keys. These commands must run on the emulator's
   host or through supported explicit host forwarding, not the Windows workstation
   merely because the prototype is built in Cloud:

```bash
# Backend terminal, from repository root (reuse installed dependencies):
export ATTUNE_LOAD_LOCAL_ENV=0 OPENAI_API_KEY=''
export ATTUNE_DATA_DIR="${TMPDIR:-/tmp}/attune-aaos-demo-data"
.venv/bin/uvicorn main:app --app-dir services/core-api --host 127.0.0.1 --port 8000
# Frontend terminal, same repository; production build first if absent:
npm run build
npm start
# Android terminal, same host with connected AAOS emulator:
adb reverse tcp:3000 tcp:3000
adb reverse tcp:8000 tcp:8000
adb install -r apps/automotive/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n more.attune.automotive.prototype.debug/more.attune.automotive.MainActivity
```

3. Verify native status explicitly says backend **simulation**, platform policy
   is independently unrestricted, and the existing web UI appears in parked state.
4. Use the debug native simulation control for 0 → 75 → 0 km/h. Moving must destroy
   the web surface; fresh simulated Park may restore a new page. Check the actual
   `/api/vehicle/state` response; do not substitute clinical/vehicle success fixtures.
5. Independently use the emulator's vehicle controls to activate driving UX
   restrictions while backend simulation remains PARK. Android must obscure/block
   the Activity and the web/media must stop. A simulated backend PARK never overrides
   that state. Repeat from the launcher and from an already open page.
6. Disconnect the backend/tunnel: after timeout/freshness expiry the app locks.
   Restore it and verify a fresh page can appear. Stop/restart the app and confirm
   no active capture/conversation resumes. Stop frontend/TLS access separately and
   verify explicit Retry behavior; never bypass a certificate warning.
7. Deny Android camera/microphone requests; test an image without those features.
   No success/result should be invented. Real physical media acceptance remains
   separate and was not performed by Cloud validation.
8. Capture the same routes at 1024×600, 1280×720, 1920×1080 and a portrait AVD,
   multiple densities and system-bar placements. Inspect navigation, 48/64 target
   sizing, reflow, clipping and readability; record image/API/device/build IDs.

## Repeat the host-browser smoke

The finite host-browser smoke can be rerun against the isolated servers above:

```bash
export ATTUNE_AAOS_EVIDENCE="${TMPDIR:-/tmp}/attune-aaos-web-smoke"
# If the existing Chrome is at a nonstandard path:
# export ATTUNE_CHROME_EXECUTABLE=/absolute/path/to/chrome
python tests/e2e/automotive_web_smoke.py
```

This checks web behavior with automotive CSS and the actual backend simulation;
it does not exercise native Android lifecycle, WebView or Car services.

## Production prerequisites

Separate acceptance levels: **source/host-tested prototype**, **APK successfully
built**, **AAOS emulator tested**, **eligible official distribution**, and
**OEM-approved production integration**. None implies the next. Current evidence
is recorded in VALIDATION.md. Before production: authorized actual vehicle adapter,
on-device UX/media/privacy validation, supported distribution category/path,
authenticated secure backend, release signing/update/recovery, model/asset support,
clinical/claims and independent TR/DE legal/compliance review as previously deferred.
No prior model-license/clinical decision is reopened or certified by this prototype.
