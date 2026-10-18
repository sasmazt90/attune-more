# Clean-clone CI portability — 19 October 2026

This change is limited to CI and test harnesses. Production application,
launcher, model, threshold, consent and history sources are unchanged.

The baseline GitHub run 39172093363 reported 737 passed, 46 failed and 43
skipped. Its frontend production build passed. Backend failures fell into:

| Cause | Repair and preserved boundary |
| --- | --- |
| Five YOLOX graph tests imported a locally extracted repository | CI checks out Megvii-BaseDetection/YOLOX at the existing recorded revision `6ddff4824372906469a7fae2dc3206c7aa4bbaee` and exposes that source through PYTHONPATH. No pretrained weights, export or training job. |
| Two historical browser replay tests required ignored photo/payload evidence | Exact prerequisite `output/playwright/front-browser-api.json` is reported as an explicit skip when absent. The original replay/assertions still run when that archive is available. No invented replay or personal image is committed. Cancellation is tested separately without requiring a photo. |
| Old neutral/snapshot fixture loaded a sibling checkout | Explicit synthetic 478-point numeric geometry tests source copying, pose and expression gates. It is not MediaPipe/camera or natural-photo acceptance. |
| Photometric tests predated source-bound expression support | Explicit neutral-score fixtures supply the new prerequisite for the existing fold/edge tests. Missing/stale expression tests remain independent fail-closed controls; production thresholds and expected scores are unchanged. |
| Temp-transpiled TS modules omitted transitive source imports | The existing TS loader resolves the actual project dependencies. No application modules are replaced with successful fake results. |
| Numeric history test had no service consent | The isolated in-memory store receives explicit consent through the real production consent setter. The append guard remains active. |
| A purported unit test launched a live care browser | A deterministic blocked transport exercises the real provider's ACCESS_BLOCKED/public handoff. Assertions require source-only links, unknown time and no invented availability. |
| Old static checks expected a replaced UI call or removed text fallback | Assertions follow the current overview adapter delegation and microphone rejection branch. They still require real-result binding and cancellation before recognition. |
| Windows-only imports blocked pure ownership tests on Linux | Only the unused msvcrt locking surface is substituted on non-Windows and raises if called. Actual identity/descriptor functions and tamper assertions run. Native OS lifecycle acceptance is not claimed. URL tampering covers both app-mode and ordinary-window argv. |
| Lease identity tests measured the whole already-imported pytest/Torch process or launched an unrelated observer | Controlled RSS/live-RAM/observer fixtures isolate ownership semantics. A separate over-budget assertion still requires fail-closed rejection. No production resource bound is raised. |
| Hard-coded Windows Node path and obsolete speech fake signature | Resolve Node from the pinned environment; accept and assert the real positive connection/read timeout arguments in the fake provider. |

There is no blanket ignore, xfail, continue-on-error, assertion removal, model
activation or historical user-record rewrite. Existing optional model/data and
native-platform prerequisites remain explicit skips; `pytest -ra` records their
reasons. A green clean-clone unit suite does not reproduce local licensed-photo
replays, physical camera/audio, clinical, OEM/mobile or commercial-rights
acceptance. Those remain governed by their existing evidence records.

Final local and actual GitHub outcomes are recorded in
`cdc-progress/release-ci-portability-20261019/status.json` in the maintenance
workspace; that runtime status is not shipped as product data.

Local focused verification covered 163 distinct passing tests and five explicit
missing-local-data skips across the repaired files and the existing five YOLOX
graph contracts. The first grouped run exposed two incomplete fixture repairs;
both passed after correcting the public-handoff expectation and supplying the
synthetic eye axis. The speech fake's exact 5s/15s timeout contract also passed.
Repeated targeted cases are not added to the distinct count. This is focused
local evidence, not a substitute for the full clean-clone GitHub run.
