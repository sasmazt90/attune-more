# Genuine AAOS OEM E2E runners

These runners connect to the existing Android WebView over ADB and record the
actual Anbox video/audio stream. They are not browser-emulator acceptance tests.
Run one module at a time against a dedicated synthetic test session. They grant
and revoke test service consent through the UI, create results from real media,
and exercise deletion only for IDs produced by that same test run.

Prerequisites: current debug APK, frontend/API, the restricted Anbox stream client
at trusted `https://localhost:18443`, ADB at `127.0.0.1:15555`, and simulated PARK.
Do not point this suite at a personal health-history profile.

Set `ATTUNE_OEM_WORKSPACE` to the protected directory containing `fixtures/` and
`runtime/`. Set `ATTUNE_ADB` to the platform-tools adb executable. Optionally set
`ATTUNE_PLAYWRIGHT_PATH` and `ATTUNE_CHROME_EXECUTABLE` for existing approved
installations. The local media manifest and recovery evidence describe fixture
provenance and hashes; large/licensed media and credentials are not in Git.

Run from the repository root, for example:

```text
node tests/automotive/oem/vision-aaos.cjs
node tests/automotive/oem/skin-final-aaos.cjs
node tests/automotive/oem/dental-final-aaos.cjs
node tests/automotive/oem/hearing-final-aaos.cjs
node tests/automotive/oem/mental-aaos.cjs
```

Each run writes its actual input/response/state/action evidence and an uncut
`continuous-raw.webm`. A completed command alone is insufficient: inspect
`result`, `fullResultCoverage`, errors, all inventories, media integrity and
independent video QA. Unseen, failed, or intentionally disabled actions must not
be relabeled PASS. The transient touch ring follows genuine pointer events and
does not alter application state.

The camera harness sends approved prerecorded frames through the official SDK
into actual Android capture. The audio harness sends synthetic speech through
the microphone path into actual ASR. DIN observes the unchanged random seed to
enter controlled responses through the UI; it does not calibrate human hearing.
Vehicle state is simulated and experimental models remain labeled accordingly.

Keep the GPU active only for the real AAOS run. Stop the AAOS instance, temporary
bridges/accounts/tunnels and then fully power off the existing cloud Instance.
Verify billing inactive in the Console. Preserve the existing disk and VPC.
