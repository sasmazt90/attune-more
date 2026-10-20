# Integrated AAOS + TR/EN/DE prototype acceptance

Assessment date: 2026-10-21 (Europe/Berlin). Repository: `sasmazt90/attune-more`; PR [#5](https://github.com/sasmazt90/attune-more/pull/5); branch `feature/localization-en-de-tr-20261020`. Reviewed starting HEAD `978e42cf4fb4ab641015564a82f69837e6325072` against merge base/main `1ee2386efd3dc30fe8d5b0d2bbf336ac7f03c98e`, including all twelve commits of AAOS and localization history. This report supersedes earlier instructions to keep the PR Draft solely for physical acceptance. No deployment or new emulator execution occurred.

## Decision

The remediated prototype is ready for review, with **one required runtime merge gate still open**: actual AAOS execution of the combined native locale synchronization and approved M4A paths. Desktop Chrome and an Android build cannot establish that behavior. Stop before merge until the separately approved bounded run establishes it and final HEAD/check/review requirements are rechecked.

Full arbitrary-response Mental live speech in all three exact voices is **outside the accepted prototype feature scope**. Fixed module guidance and literal Mental templates are supported; arbitrary German live speech remains accurately unavailable. This safely disabled capability is a production release blocker for multilingual live-conversation parity, rather than a claim of a completed live feature. If the release scope requires that experience, it must pass its own acceptance before release. Neither prerecorded audio nor local-demo replies establish live TTS/LLM parity.

| Classification | Requirement | Evidence / disposition |
| --- | --- | --- |
| MERGE BLOCKER | Combined AAOS locale/audio runtime | Fresh Android WebView/native observations required; prepared, **not dispatched**. Historical #122 is insufficient for these changed paths. |
| MERGE BLOCKER | Exact final source, automatic checks and repository rules | Must be successful/current before merge. At initial inspection, main branch summary reported `protected:false`, required contexts empty; rulesets, reviews and review threads were empty. Detailed protection endpoint returned 403, so no claim of admin-level visibility. Recheck at merge time. |
| PRODUCTION RELEASE BLOCKER | Exact live Emel/Ada/Katja and localized STT | No supported, authorized no-cost live provider verified. DE live speech fails closed; TR/EN contracts do not prove service availability. Latest localized physical microphone coverage unverified. |
| OEM / PHYSICAL VEHICLE GATE | Real VHAL/OEM approval, media and on-device behavior | Unverified; separate from prototype merge. No physical vehicle or Windows processes used. |
| CLINICAL / ACOUSTIC GATE | New scored hearing digits / clinical claims | Thirty new digits remain inactive; EN/DE scored digit-bank entry rejects before fetching. Existing TR scored bank, noise, SNR, gain, scoring, thresholds and timing preserved. No clinical equivalence claimed. |
| DOCUMENTED NON-BLOCKING LIMITATION | Actual desktop hidden-tab state | Existing supported visibility regression passes; headless tab switching did not produce `document.hidden`. Real hidden-tab acceptance remains unverified. |

## Full-PR impact review

The initial 689-file diff includes 160 source/config/test files, 24 documents, 459 audio files, 29 inventories/manifests and 17 prior synthetic screenshots. This is not a localization-only review. New corrections and tests in this report add to that reviewed starting scope.

| Area | Review result |
| --- | --- |
| Native Activity, manifest, Gradle and SDK | Reviewed Android 35/min29/Java21/Gradle8.11.1 configuration, pinned SDK/image, origin policy, media permission handling and lifecycle. Release default remains unavailable/HTTPS-only; debug loopback remains confined to debug. No privileged vehicle permissions or JavaScript bridge added. |
| Independent automotive safety | Car UX UNKNOWN/restricted, missing/stale/future backend state, moving/non-P, background and unavailable production provider remain fail-closed. GatePolicy, CarRestrictionSource, OriginPolicy, MediaPermissionPolicy, manifest and app Gradle match the historical #122 source byte-for-byte. MainActivity locale changes require fresh runtime evidence. |
| WebView | Trusted foreground/ready source guard remains around native preference reads. SSL errors cancel; file/content access, mixed content and third-party cookies stay restricted. External navigation remains an explicit gesture/confirmation path. No platform policy/permission bypass introduced. |
| Localization and persistence | Display translation and formatting leave raw records, IDs, health measurements and consent contracts intact. Compared changed TSX interactive attributes: handlers, values and consent controls unchanged except the additional disabling of unvalidated EN/DE scored hearing entry. Existing storage keys remain. |
| Five health modules / media | Module+language+event dispatch, exact-template matching and fixed female/male assignments retained. All 194 originals and 83 pre-existing preservation hashes rechecked by tests. No audio regenerated, replaced, trimmed or transcoded. |
| Backend and Mental | Locale is request-scoped, response presentation does not translate stored user text; moving and consent admission remain. German termination, urgent safety and emergency-priority corrections described below. No model replacement or new health computation. |
| Tests, workflows, evidence | Reviewed manual/reusable routing, pinning, independent safety observer and honest BLOCKED/UNVERIFIED reports. Added finite integrated observations and early original-file integrity checks. No manual dispatch on push. |
| Public-source hygiene | Full changed-file inventory, binary provenance and literal private-key/token pattern review found no such credentials or personal data in the reviewed changes. This is a scoped engineering review, not a formal security certification. No unrelated product changes identified. |

## Corrected findings

| Finding / source | Root cause | Correction / validation |
| --- | --- | --- |
| Natural German termination: `services/core-api/conversation_control.py` | Only short exact control phrases matched; requested full sentence produced an ordinary demo reply. | Anchored finite German termination grammar; negated/ambiguous examples rejected. Real API and actual UI completion pass. Existing approved termination reply unchanged. |
| Explicit urgent danger: `packages/safety/crisisDetector.ts`, `services/core-api/mental_provider.py` | Requested danger + urgent-help sentence did not contain an existing self-harm keyword. | Shared paired safety grammar in `shared/localization/urgent-safety.json`; frontend/backend agree. Routes to existing 112 wording before providers. Reports `URGENT_SAFETY` without falsely diagnosing self-harm. Existing self-harm cases retain IMMINENT handling. |
| Emergency priority: `apps/vehicle-app/src/utils/useMentalConversation.ts` | Optional context compaction ran before the already-detected local emergency result; a long-context/provider failure could delay safety routing. | Local crisis skips optional compaction. Actual send closure tested with 42 synthetic prior turns and failing context/network; emergency response and retained transcript verified. Ordinary compaction failure still pauses. |
| Unicode regression harness: `tests/unit/test_crisis_unicode.py` | Temporary standalone transpilation lost the detector's real shared JSON dependency. | Existing TypeScript loader resolves actual source dependencies; all original Unicode assertions preserved and pass. |
| Integrated emulator observer / artifacts: `tests/automotive/` and two manual workflow YAMLs | Historical observer assumed TR navigation and had no approved M4A/native-language checks; 27 extra captures would exceed the old file-count ceiling. | Finite TR/EN/DE navigation, native label observation, 194 actual decode receipts and 15 real media cases. Failed decodes retain evidence. Source size/hash/path gate before SDK work. File-count ceiling 512 while retaining 49 MiB source + 1 MiB ZIP headroom / 50 MiB maximum upload. |

## German synthetic driver scenarios

All inputs are nonpersonal, owner-supplied synthetic text. Tests use actual keyless API and application UI components. A recognizer adapter emits synthetic transcripts; it performs no recognition, capture or external provider request. Media observations are actual fixed-file `playing`/`ended` events in Cloud Chrome, not simulated successes or physical listening acceptance.

| Scenario | Transcript / behavior | Result |
| --- | --- | --- |
| A | `Ich hatte heute einen stressigen Arbeitstag und möchte kurz darüber sprechen.` — German work-stress theme and local-demo response; fixed Katja playback. | PASS within DEMO/transcript scope |
| B | `Ich bin heute müde und kann mich nicht besonders gut konzentrieren.` — German fatigue theme and local-demo response; fixed Katja playback. | PASS within DEMO/transcript scope |
| C | `Ich möchte das Gespräch jetzt beenden.` — actual termination control, fixed German reply, completed UI/session boundary. | PASS |
| D | `Ich fühle mich gerade nicht sicher und brauche dringend Hilfe.` — local emergency guard, German 112 wording, normal conversation stopped; fixed Katja crisis playback; no conversation/context/speech request. Benign keyless provider-status GET remains allowed. | PASS |

All recognizer instances requested `de-DE`; no TR/EN audio fallback, invented emergency call, physical capture or external request was observed. Negative wording, existing Turkish Unicode crisis handling, moving wording, consent withdrawal and session regressions pass. Prior Windows microphone success remains user-reported historical acceptance, not latest-commit verification. Live ASR and live LLM reasoning remain UNVERIFIED.

## Exact live TTS audit

Microsoft's [voice catalogue](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=text-to-speech) documents Emel `tr-TR-EmelNeural`, Ada `en-GB-AdaMultilingualNeural` and Katja `de-DE-KatjaNeural` as female voices. Ada's voice locale is en-GB while the app locale remains en-US. A catalogue identity does not prove that this project's Clipchamp export and a provisioned live service are interchangeable or currently available.

The [documented Azure speech REST API](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech) requires an authorized resource/credential and service entitlement. No such approved no-cost runtime was established; none was provisioned or invoked. Existing `edge-tts` uses Edge consumer read-aloud infrastructure; its third-party implementation is not proof of a documented authorized service API. No consumer endpoint/catalogue/synthesis probe was executed in this audit. The approved export manifest remains unchanged, including null DE provider IDs; the Azure catalogue identifier was not silently installed into that consumer integration.

Fixed Emel/Ada/Katja recordings remain available. DE arbitrary live speech stays blocked with an accurate unavailable state; TR/EN exact contracts and fixture tests do not establish live availability. No eSpeak, male, other-language or alternate-character substitution is permitted. A legitimate provider integration and free entitlement would need separate engineering/runtime acceptance; this report claims no live parity.

## Executed verification and reusable evidence

| Verification | Result / limits |
| --- | --- |
| Final product production build | PASS using pinned Node22.20 and cached dependencies in a new isolated Cloud source tree. |
| TypeScript / lint | PASS; six existing hook warnings remain. No new product dependency installation. |
| Broad meaningful unit + automotive run | 867 passed, 47 skipped, ten subtests passed; one Unicode harness failure subsequently corrected. |
| Post-correction focused run | 97 passed, two platform skips, ten subtests passed; includes the formerly failing Unicode test and German/API/automotive regressions. Overlaps broad suite; counts must not be added. |
| Final observer reporting tests | 15 passed, including retaining all 194 codec observations on failure and restoring the synthetic locale. |
| Original-file source preflight | All 227 required original/guidance files PASS (194 M4As + 33 existing guidance MP3s). No audio success inferred from packaging alone. |
| Actual German browser component flows | Four PASS observations, three from initial run plus one focused safety recheck. Initial safety observer incorrectly counted benign provider-status GET as a forbidden conversation call; preserved failure and corrected-filter recheck are retained. |
| Observer desktop rehearsal | 194 real fetch/hash/AAC decodes, 27 actual menu-driven localized route visits and real DE Katja playback PASS; no capture, external requests or page errors. This is **desktop**, not Android. |
| Offline workflow validation | All five YAML/action files parse; 45 embedded bash scripts syntax-check; exact-source/attempt guard tested for success, missing SHA, mismatched SHA and prohibited retry. Not an actionlint or hosted-execution claim. |
| Approved module regression reused | Previous 15 module/language real playback cases; mute, abort, navigation/language cancellation, missing/size/hash faults and narrow voice-assignment/storage preservation remain applicable to unchanged media code. Existing actual hidden-tab limitation retained. |
| Historical AAOS / Android CI | [#122](https://github.com/sasmazt90/attune-more/actions/runs/39321125673) at `a3943b6c62e6f0282ff021e1de2f73a5c3c43e18`: 17 PASS + nine routes. Starting HEAD automatic frontend/backend/Android assembly/lint passed. Exact new-head automatic CI is reported separately in PR/task receipt. |

Cloud receipts, logs, initial baseline failures, source hashes, screenshots and browser results are retained outside the product tree in `/workspace/attune-final-acceptance-20261021/`. Earlier original/codec/module evidence remains in `/workspace/attune-approved-audio-20261020/`; archived #122 originals remain unchanged.

## Proposed single AAOS run — separate approval required

Use registered manual `e2e-audit.yml` on **this feature branch**, routing only to the AAOS reusable workflow, with `expected_source_sha` equal to the explicitly approved final commit. Do not run the unrelated browser-audit job. No automatic dispatch or retry is permitted.

- One standard GitHub-hosted `ubuntu-24.04` runner; public-repository guard; 40-minute hard job timeout; no larger/premium runner, cache, paid API, deployment or outside service.
- Exact existing AAOS35-ext15 x86_64 revision4; emulator37.2.12/build16428233; command-line tools22.0/build15859902; ADB37.0.1; Java21/Gradle8.11.1; Python3.11.17; Node22.20; Playwright1.64.
- Keyless synthetic isolated backend; actual platform Car UX and backend gates remain independent. Only existing emulator VHAL inputs are used; never disable restrictions or grant media permissions.
- Require the historical 17 acceptance scenarios plus new `localized-webview-audio`: all 194 original AAC/M4A decodes, 15 module/language real playback cases, all nine routes in each locale, and native TR/EN/DE status changes. Retain real screenshot/UI/activity evidence and explicit FAIL/BLOCKED/UNVERIFIED results.
- Artifacts: maximum 50 MiB including ZIP overhead, one-day retention; retain diagnostics even for failed checks when within cap. No automatic retries or alternative-image trial runs.
- Resource budget is at most 40 standard runner minutes plus 50 MiB for one day. Standard public-repository runner compute is free under GitHub's published policy; remaining artifact allowance/account billing is not independently visible here. No guaranteed-zero-charge statement is made. Confirm applicable free artifact capacity/owner authorization before execution; do not allocate paid services.

Successful runtime evidence, current automatic CI and final repository-policy/HEAD checks permit the already conditionally authorized prototype merge. Physical OEM, clinical equivalence and arbitrary live speech production acceptance remain separate, explicitly documented gates. If runtime evidence fails, do not retry or merge; report the actual first failure and downstream blocked checks.
