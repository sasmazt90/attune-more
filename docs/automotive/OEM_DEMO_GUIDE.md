# Parked OEM demonstration guide

Current implementation and limits: [28 October audit](DEMO_READINESS_20261028.md).
Use the **debug APK** for this isolated demonstration. The unsigned release build
deliberately has no simulated or authorized real vehicle provider and cannot
unlock the health experience. Neither build is a production integration or an
approved Google Play for Cars category.

## Prerequisites and build

Use a developer-controlled AAOS emulator host with JDK 21, Android SDK platform
35 including `android.car`, build tools 35.0.0 and ADB. The wrapper pins Gradle
8.11.1. Install existing Node/Python dependencies using the repository's pinned
versions; retain approved audio/models. Do not copy real health data or provider
keys into the demonstration. Use the existing approved network/proxy and CA setup.

From repository root:

```bash
export JAVA_HOME=/absolute/path/to/jdk-21
export ANDROID_HOME=/absolute/path/to/android-sdk
export ANDROID_USER_HOME=/tmp/attune-android-user
export GRADLE_USER_HOME=/tmp/attune-gradle-cache
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
python3 tests/automotive/run_checks.py
bash scripts/automotive/build.sh
```

Debug artifact: `apps/automotive/app/build/outputs/apk/debug/app-debug.apk`.
The APK requires the existing frontend and backend; it does not contain them.

## Launch on the emulator's host

Terminal 1, repository root, with installed Python dependencies:

```bash
export ATTUNE_LOAD_LOCAL_ENV=0 OPENAI_API_KEY=''
export ATTUNE_ROBOFLOW_API_KEY='' ROBOFLOW_API_KEY=''
export ATTUNE_DATA_DIR=/tmp/attune-aaos-demo-data
.venv/bin/python -m uvicorn main:app --app-dir services/core-api --host 127.0.0.1 --port 8000
```

Terminal 2, repository root, Node 22.20.0/npm 10.9.3:

```bash
export ATTUNE_LOAD_LOCAL_ENV=0 NEXT_TELEMETRY_DISABLED=1
npm run build
npm start
```

Terminal 3, with an already running **Automotive** AVD selected. Follow the
[official emulator setup](https://developer.android.com/training/cars/testing/emulator)
and select a package actually available in SDK Manager. Use an image without
compatibility mode as part of independent distraction acceptance. Do not use a
phone image, UX override or privileged car permission to make the gate pass.

```bash
curl --fail http://localhost:8000/api/health
curl --fail http://localhost:3000/
adb devices
# With multiple devices, add the selected device's -s SERIAL to every adb call.
adb reverse tcp:3000 tcp:3000
adb reverse tcp:8000 tcp:8000
adb install -r apps/automotive/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n more.attune.automotive.prototype.debug/more.attune.automotive.MainActivity
```

Both servers must run on that emulator host or use separately reviewed explicit
forwarding. The APK's `localhost` means ADB-reversed host ports; it is not a
Windows workstation dependency. Keep the backend bound to loopback. Remote
deployment needs a reviewed HTTPS/authentication/origin configuration, not a LAN
URL substituted into this debug demo. Never ignore certificate errors.

## Demonstration and native acceptance still required

1. Confirm the native label explicitly identifies **backend simulation**, Android
   policy is independently unrestricted, and fresh simulated Park opens the web
   page. Missing Car services must stay locked. Grant only existing product
   consents for the capabilities actually demonstrated.
2. Visit Skin, Dental, Vision, Hearing and Mental, then care, profile/history and
   privacy, in TR/EN/DE. Announce unavailable camera/recognition/output capabilities
   explicitly. Do not substitute fake results, answers or new speech providers.
3. Use the native simulation control for Park → move → Park. Separately activate
   platform driving restrictions while backend simulation remains Park. The web
   surface and active media must stop; fresh Park opens a new page. Background and
   reopen the app; no active workflow may resume automatically.
4. Stop only the demo-owned backend: the gate must close after disconnect/staleness.
   Restore it and confirm fresh Park. Stop the frontend separately and check native
   Retry. Open a nonexistent same-origin document and check the same Retry behavior;
   a missing subresource alone must retain the module's existing error handling.
5. Check denied/absent camera and microphone behavior. An Android permission dialog
   may pause and destroy the web session; restart the workflow explicitly afterward.
   The external Dental file picker remains unavailable in this native shell.
6. Test portrait/landscape, OEM bars at all edges, cutouts, keyboard open/close and
   focused field scrolling. Check Android 15+ and the API 29 fallback. The 800×480
   and 1024×400 **browser** checks do not verify native IME behavior.

The existing `tests/automotive/validate_emulator.py`/`webview_driver.cjs` harness
now includes main-document HTTP 404 recovery. Its current workflow has historical
source/branch/runner authorization guards: this new branch is not allowlisted.
Do not assume dispatching it would execute this source. A future hosted run needs
reviewed authorization/configuration; no such run was dispatched for this delivery.

## Repeat the deterministic browser evidence

With the isolated servers running, Playwright installed and a compatible Chrome:

```bash
export ATTUNE_AAOS_EVIDENCE=/tmp/attune-aaos-web-evidence
# Set only when Chrome is installed at a nonstandard path:
# export ATTUNE_CHROME_EXECUTABLE=/absolute/path/to/chrome
.venv/bin/python tests/e2e/automotive_web_smoke.py
.venv/bin/python tests/e2e/automotive_asset_smoke.py
```

These create 162 full-page browser PNGs, 216 layout/simulation observations and
235 asset checks. They block external requests and never capture media or call a
paid provider. They are not AAOS runtime or five-module hardware acceptance.
