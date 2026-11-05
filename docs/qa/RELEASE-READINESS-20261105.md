# Engineering release follow-up — 2026-11-05

This source-release assessment follows the completed Independent QA audit of 2026-11-05. Its private recordings, photographs and integrity receipts remain in their original archive. No primary journey was repeated and no preserved installation was modified.

**Release scope:** the existing WEB/AAOS cloud demonstration and fresh installations of the same prototype package. This is not production signing, physical-vehicle acceptance, clinical validation, or authorization to migrate a legacy-signed device. The preserved AAOS installation already has the pinned certificate.

## Baseline and traceability

| Reference | Meaning |
|---|---|
| `00efaf3cb24f988fbe65604a862ec57964a1569e` | Main at the completed audit and start of this review |
| `9a938b4e3dfe1e18704d3c64dfaf421bc2a06e11` | Original provider-return candidate; existing real AAOS return-flow evidence belongs to this revision |
| `f8909991d8715f9046d6715995a5fa2230e19e31` | Review correction: privacy wipe, exact 24-hour boundary, corrupt-state cleanup |
| [PR #24](https://github.com/sasmazt90/attune-more/pull/24), merge `366920c6dfba1dd4f777264ee188e5a2cdabd21a` | Provider-return change merged after review and all three CI workflows passed |
| `a656f2f` | CQ-02, CQ-03 and OPS-01 implementation and targeted tests in the follow-up change |
| [PR #25](https://github.com/sasmazt90/attune-more/pull/25) | Follow-up fixes, including the template guard in both legacy and structured API modes, and this release assessment |

The source baseline consists of PR #24 plus the follow-up containing this report. Its merge is conditional on passing review and applicable CI; consult its PR for the final head and merge SHA. Stopped hosts still contain the audited `9a938b4` candidate (AAOS versionCode 1061), **not** these privacy/API/tooling corrections. A source merge is not deployment evidence.

## Findings and disposition

| Finding | Impact and disposition | Evidence / remaining condition |
|---|---|---|
| CQ-05 / PR #24, P1 | Resolved and merged. Confirmed external handoff remembers an internal return route; pending question survives WebView recreation. | Existing AAOS runtime evidence plus 14 targeted tests and TypeScript on the reviewed head. No automatic booking: confirmation opens a draft; saving requires explicit input. |
| PR #24 privacy review, P2 | Resolved. Delete all data removes the pending handoff. Corrupt/future state is discarded; age **at least** 24 hours expires on read. | Regression executes the actual wipe handler, verifies deletion and PARTIAL when storage refuses removal, and preserves an unrelated preference. |
| CQ-02, P2 latent API defect | Resolved in source. Prompt example uses JSON null; both legacy and structured analysis reject the exact leaked Turkish template literal through the existing provider-failure path. | TR/EN/DE fixtures preserve legitimate reasons and null, reject the placeholder without retry or invented output. No live recurrence or frontend consumer was found in the completed audit. This is not a general language detector. Historical records are unchanged. |
| CQ-03, P2 evidence reliability | Resolved in source. Both harness entry points propagate nonzero exit for caught ERROR, FAIL, empty checks and page errors. Saved status agrees with exit result. | Actual harness finalization tested with synthetic browser I/O, including target closure. Separate report/video validation remains necessary; exit zero alone does not prove a valid recording. |
| OPS-01, P3 operational display | Resolved in source. AWS login output goes to the host display rather than the function result; error preference is restored in finally. | Extracted real Connect-Aws function tested with fake login success/failure in PowerShell CI. DNS/startup/readiness sequencing unchanged. Owner Windows shortcut copy has not been updated or exercised by this task. |
| CQ-04, P1 **for legacy rollout only** | Not required for this baseline. Already migrated devices use signed in-place upgrade; fresh installs need no migration. Legacy rollout remains blocked. | Release-path decision below. No destructive migration or disposable environment was necessary for the selected path. |
| CQ-06, P2 conversation usability | Open improvement / listening acceptance. Long initial waits and segment gaps remain. | [Timing investigation and proposals](MENTAL-LATENCY-20261105.md). Approved voice/assets/segmentation unchanged. No subjective listening approval claimed. |
| OPS-03 AAOS Skin retry, P2 test reliability | Open; not proven to be a product crash. Keep failed attempt and successful identical retry. | Screenshot at Overview failed with target closed; subsequent probe found native PID and resumed activity. R2 passed. No contemporaneous renderer/gate trace establishes the cause. |

## Native review and data boundaries

`OriginPolicy.contains` parses a URI and compares exact scheme, host and effective port; it rejects userinfo and invalid ports. Debug loopback remains explicitly restricted. The route is validated before remembering and loading, then consumed once. External navigation still needs a main-frame user gesture, valid HTTPS, native confirmation and a fresh `ready()` check. `openWeb()` remains readiness-gated. Background/DRIVE destroys the WebView and stops capture through the existing architecture; there is no new bypass or vehicle state.

Pending storage contains only specialty, provider name, source type and timestamp, never external URL, appointment time or referral health payload. No/Yes acknowledgement clears it; Yes creates an editable draft. Storage failure leaves the in-page question usable. Route restoration is scoped to the surviving native Activity; process death may return home, with the valid pending question available upon visiting Care. Expiry is checked on restoration, not by a background deletion scheduler.

## CQ-04 release-path decision

`apk_upgrade_host.plan()` permits in-place update only with the pinned identity, permits fresh installation when no package exists, and refuses a mismatched installed certificate unless migration is explicitly selected. The one uninstall is confined to the named migration function. Normal deployment uses `adb install -r`.

The unchanged demo certificate SHA-256 is `2aacbb13bad91c2ef982d594a8d98b65f523a71fdc97772d50222fe9f9843876`. The completed audit verified same-certificate 1058 → 1061 installation and preserved existing records, preferences, consents and photographs. Earlier uninterrupted upgrades are in [QA-41](QA-41-APK-UPGRADE.md). No additional legacy-signed device has been identified.

If scope expands to such a device, **stop at SIGNATURE_MISMATCH**. Before offering migration, follow the [operations procedure](../aws/OPERATIONS-CONTROL.md) on an isolated disposable legacy installation: seed synthetic records/consents/preferences/photos for each Android user, retain the old APK and verified backup, run the corrected migration uninterrupted, compare every stored value/photo and permission, then exercise interrupted recovery separately. Never use the preserved AWS installation or real records as that fixture. Stand-in tests do not close device acceptance. The debug-enabled cloud-demo certificate is not a production release identity.

## Verification and remaining release gates

- PR #24 head `f890999`: 14 targeted Care/appointment/native tests and TypeScript passed. CI [41968872864](https://github.com/sasmazt90/attune-more/actions/runs/41968872864), Android [41968872885](https://github.com/sasmazt90/attune-more/actions/runs/41968872885), AWS preparation [41968872849](https://github.com/sasmazt90/attune-more/actions/runs/41968872849) passed. Preparation initially timed out; the same revision passed on retry. APK identity verification passed with the existing pin.
- Follow-up: `pytest tests/unit/test_mental_structured.py tests/unit/test_qa_exit_status.py tests/unit/test_ops_login_output.py tests/aws/test_apk_upgrade.py -q`: **79 passed, 3 skipped locally** (PowerShell runtime and optional cryptography). PowerShell behavior must pass in CI before merge.
- Both PowerShell login success/failure cases passed on the CI runner. The first follow-up CI found the internal prompt's localization inventory entry needed updating; its existing provider-instruction exemption was updated to the new exact text/hash. The localization suite then passed **10 tests locally**, including catalog/runtime behavior and approved-audio integrity. No user-facing translation was exempted or removed.
- Existing AWS/preview-origin suite: **92 passed, 27 skipped locally**; skipped Windows-only fixtures and optional dependency are not runtime acceptance. These tests make no remote AWS changes.
- AWS API readback at **2026-11-05 05:13:46 UTC** confirmed both existing instances **stopped**. This follow-up never started either host.
- No live provider call, audio generation, host deployment or broad E2E run was needed for these narrow fixes. Future deployment must retain signed in-place installation and use targeted pending-question/privacy/analysis-response checks, preserving records; do not repeat all twelve journeys.
- For the next justified Skin run, collect bounded timestamps for CDP disconnect/target destruction, renderer exits, native gate transitions and app PID/activity. Correlate with screenshot failure and keep the first attempt. Do not add blind retry or alter stable Skin inference without a reproduced cause.

The source fixes are separable from acceptance limits: legacy migration is blocked outside this scope; conversational audio needs measured optimization and actual listening; Skin closure remains unexplained. No infrastructure, IAM, security group, DNS, model asset, production credential or approved AAOS safety architecture was changed.
