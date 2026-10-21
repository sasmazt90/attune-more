# AAOS #129: stale observer page after motion lock

Actual run: https://github.com/sasmazt90/attune-more/actions/runs/39642341108
(the supplied URL `3964234108` returns 404). Tested source:
`ad7d94f60c9857fea0e7f0dbf6488830d87193f6`.

## Confirmed failure

This is an observer lifecycle defect. The app correctly destroys its WebView
when motion admission closes. The harness then reused Playwright's cached
Android device/WebView page instead of detaching that observer before discovery.
`page.route` ran against the old closed page during reconnect, not against the
newly created renderer.

| Evidence | Observation |
| --- | --- |
| Full job log, job 119368833354, lines 2264–2269 | Original audio/localization, Hearing and TR/EN/DE neural playback passed. Only interruptions failed; crash/console and evidence gates subsequently passed. |
| `mental-neural-interruptions.json` | Mute, cancellation, consent withdrawal, language and session checks all PASS. Backend-motion and Car-UX-motion remain BLOCKED, not inferred passes. |
| `neural-active-backend.json` | Actual current-run EN WAV active, 4.92s, looping for the bounded motion observation; SHA-256 `7a37cb5c09ac5e01f57345fe170593dce8dc06713975154bb091254ded15712f`. |
| `mental-neural-interruptions-traceback.txt` | Failure at `validate_emulator.py:858`, `client.request('connect')`, then `webview_driver.cjs`'s `page.route`. Destruction/no-target assertions and Park restoration had already completed; no stale-output pass had yet been recorded. |
| `logcat.txt:7528` | 17:42:56.455: renderer PID 8537 killed as **isolated not needed**, after the intentional backend-motion gate. |
| `logcat.txt:7864,7945–7960` | Existing app Activity received launch at 17:43:00; new WebView renderer PID 18310 started at 17:43:01.445. App PID remained 3078. |
| Pinned Playwright 1.64.0 source | Android devices are cached by serial; WebViews by app socket. `AndroidWebView.page()` caches `_pagePromise`. Destroying a target does not necessarily replace the app PID/socket or invalidate that cached promise. `AndroidDevice.close()` removes the device from the observer cache and disconnects its transports. |

Official source inspected:
[client/android.ts](https://github.com/microsoft/playwright/blob/v1.64.0/packages/playwright-core/src/client/android.ts),
[server/android/android.ts](https://github.com/microsoft/playwright/blob/v1.64.0/packages/playwright-core/src/server/android/android.ts).
The artifact's `python-install.log` confirms Playwright 1.64.0.

There is no failure-time app crash, low-memory kill or job timeout evidence.
The renderer termination reason and ordered replacement explain the closed-page
error. Observer teardown occurs later, after crash/console and evidence checks;
it did not cause this reconnect failure. Earlier unrelated emulator audio/system
crash-buffer entries are not attributed to this later failure.

The artifact contains a Python traceback but **no Playwright trace ZIP/network
trace**; `webview-driver.log` is empty. Historical per-target Playwright events
therefore cannot be reconstructed. New content-free lifecycle events make future
attachment, close and renderer-crash observations explicit.

## Minimal correction

- `webview_driver.cjs`: before reconnect, close the previous **observer device
  handle**, then rediscover the exact emulator/package through the public Android
  API. Reject an absent/closed fresh page. Record target/context closure and
  attachment; renderer crashes remain failures in the existing console gate.
- Keep the RPC process alive. Its current-run WAV bytes remain available for
  both independent motion checks. Do not restart the app, relax a safety gate,
  retry a failing check, reinstall a driver or bypass resource routing.
- `test_webview_driver.cjs`: actual RPC process with explicit Android lifecycle
  fixtures reproduces the exact pre-fix error. Three attachments (initial plus
  both motion replacements) get distinct live pages after the correction;
  detach failures and closed fresh targets still fail.
- `test_automotive_contract.py`: runs these Node regressions in the existing
  automatic CI and AAOS host-preflight path. No workflow changes.

## Verification and remaining gate

- Before correction: new RPC regression failed with the same closed-page error.
- After correction: seven Node observer tests PASS, including reconnect and
  existing routing, locale, recording-policy and real-response-retention guards.
- 47 focused automotive harness/contract/acceptance tests and four subtests PASS.
- Existing Cloud Chromium corroboration: closing one page leaves the browser
  alive; routing on its cached closed page fails; a fresh context/page accepts
  routing on both replacement cycles. This is browser lifecycle evidence,
  **not an Android motion or audio acceptance result**.
- JavaScript syntax and Git whitespace checks PASS. Application/frontend,
  backend, neural model/runtime, all approved recordings, interruption assertions,
  safety policies and workflow cost/timeout/artifact limits are unchanged.

Artifact 12366942875: 14,931,541 bytes, ZIP CRC and SHA-256 verified:
`b47df7c7c6a18e2aaa4ede7ffaf317b175c927b2ad1d4308948ce2d3cc0bd9d2`.
All 334 members and the complete job log are retained in Cloud under
`/workspace/attune-aaos-interruptions-20261021/`.

Corrected Android attachment and the two motion/stale-output results remain
UNVERIFIED until one new owner-authorized AAOS run completes. All existing
assertions remain mandatory. No AAOS run, merge or deployment was launched here.
