# TR / EN / DE localization implementation and acceptance

**Current approved-recording integration:** see [194-recording acceptance report](APPROVED_AUDIO_INTEGRATION.md). It supersedes the historical eSpeak/global voice-selection and scored EN/DE digit-bank behavior described below. PR #5 remains draft. The following original implementation evidence belongs to `bb27283d` and is retained as history.

**Engineering implementation verified in Cloud; draft integration pending platform speech/listening acceptance.** No merge or deployment is authorized by this report.

Repository: `sasmazt90/attune-more`. Branch: `feature/localization-en-de-tr-20261020`. Integration base: `7ba4dfbad8b4916de1411e1a6e2980b814a3658c`. Current main was rechecked at `1ee2386efd3dc30fe8d5b0d2bbf336ac7f03c98e`; the integration base contains ten already-pushed AAOS commits beyond main. All eight observed remote branch tips are ancestors of that integration base. The PR therefore includes that previously unmerged AAOS history as well as the new localization commit.

## Delivered

- Persisted, accessible TR/EN/DE header selector; TR default. Language/voice settings are locked during active assessments and whenever the existing backend parked state is unavailable. No health/consent/progress reset or locale-keyed remount.
- Central source catalogs across all nine routes, five modules, shared results/history/care/privacy, dialogs, guidance, backend messages, safety/crisis wording, metadata and formatting. Known display text is translated; machine IDs, raw measurements, units and user-authored quotations retain their meanings. Previously saved free-text content retains its original language.
- Exact `tr-TR` / `en-US` / `de-DE` recognition configuration, target-independent letter/control parsing, explicit unsupported states, transient Unicode-safe parsing and unchanged scoring algorithms.
- Actual system/browser voice discovery without guessed genders or cross-language substitution; separately persisted choices; free Microsoft metadata discovery; new EN/DE local synthesis and male/female fixed guidance. Unavailable voices/processing produce an accurate failure state. Pending old-language speech is cancelled explicitly while conversation data remains; crisis cancellation keeps the emergency stop/112 path.
- Thirty translatable native AAOS strings per language, with unchanged product identity strings and independent gate/lifecycle/origin policy. Native labels follow a guarded, one-way preference read from the trusted ready foreground WebView.
- Automated catalog/placeholder/hardcoded display checks, backend/Unicode/voice/audio/safety tests, and a reusable finite Cloud browser assessment in `tests/localization/`.

See [architecture](ARCHITECTURE.md), [voice/audio provenance and bounded local checks](VOICE_AND_AUDIO.md), and [actual screenshots](EVIDENCE.md).

## Executed validation

| Check | Result | Evidence / scope |
| --- | --- | --- |
| Full relevant unit + automotive suite | **PASS** | **854 passed, 45 skipped, 0 failed; 10 passed subtests**. The skips require Windows/retained licensed or optional evidence; one existing AnyIO deprecation warning. |
| Catalog coverage and placeholders | **PASS** | 1437 complete catalog entries; 1485 inventoried sources; no missing coverage/placeholder mismatch. 65 explicit internal/identity exemptions are documented. Runtime/private/provider prose still needs appropriate review. |
| TypeScript, lint, production build | **PASS** | Cached pinned Node 22.20.0/npm 10.9.3; actual Next production build. Lint retains the same six pre-existing hook/img warnings. |
| Native debug/release build and lint | **PASS** | Actual offline Gradle 8.11.1 / Java 21 / compile SDK 35 builds and both lint variants in Ubuntu 24.04. Resource key/printf placeholder parity passed; unchanged gate/Car restriction classes passed host checks. |
| Desktop/tablet/mobile UI | **PASS** | All **81** route/language/width combinations: nine routes × TR/EN/DE × **1440, 768, 375 px**. Zero console/page errors, broken images, page overflow, overlapping controls, clipped visible leaf text or capture attempts. Assistive offscreen content and intentional carousel scrolling are distinguished. |
| Actual browser zoom | **PASS** | **27** route/language cases at Chrome **200%**. Native setting 2, outer width 1440, inner width 720, DPR 2, CSS zoom 1, visual scale 1. Viewport resizing was not used as a zoom substitute. |
| Result/history screens and Unicode | **PASS with synthetic fixtures** | **30** actual result dialogs across five modules, all three languages, 1440/375 widths. German/Turkish transcript characters and original record/consent bytes survived language changes. These are explicitly synthetic records, not camera/model/human assessment results. |
| Actual app guidance playback | **PASS, digital events** | Real app HTML audio `playing`/`ended` events for all four EN/DE male/female profiles. Headless Cloud audio is not a physical listening acceptance. |
| Optional free-text local synthesis | **PASS, Cloud codec/probe** | Real metadata/synthesis/MP3 decoding for all four profiles; no paid service or personal text. Actual Cloud browser system voice list was empty and displayed honestly. Web Speech event/provider tests use explicitly labelled fixtures. |
| Asset preservation and references | **PASS** | All **83 pre-existing audio files** retain their sizes and SHA-256. All **267** new assets are present in Git: 244 MP3, 20 digit WAV, 3 JSON; **12,004,852 bytes**. New assets are marked new synthesis, with auditory acceptance pending. |
| Moving/offline/consent gates | **PASS, isolated backend simulation** | Three locale cases: selector/voice settings lock while moving or backend state is unverified; speech endpoints reject moving requests/missing consent; verified parked recovery restores access. No real vehicle state is asserted or bypassed. |
| Locale changes, appointment display and manifest | **PASS** | Repeated TR/EN/DE selection, navigation/reload persistence, actual localized installation metadata with one head link, and refreshed date formatting in explicit synthetic DEMO appointment cards. No live availability or booking claim. |
| Archived AAOS #122 evidence | **PRESERVED** | Acceptance documentation and source/audio baseline were not rewritten. Its runtime result applies to `a3943b6`, not this localized build. |

Routes: `/`, `/vision`, `/skin`, `/dental`, `/mental`, `/hearing`, `/care`, `/profile`, `/privacy`. Viewports were 1440×1000, 768×1000 and 375×844. All execution/screenshots occurred in Cloud, using isolated ports 3200/8100, new browser profiles and synthetic storage with paid keys blank. Existing Windows/local processes and user data were not accessed.

The input audit found native date/number/file/checkbox controls and the existing numeric hearing keypad, with no alphabetic on-screen keyboard to add. Unicode transcript/storage round trips passed. Physical keyboard/IME behavior is a separate platform check.

## Resolved acceptance findings

The implementation/real-browser checks covered assembled history headings and specialty labels, translated safety templates taking precedence over generic templates, locale-reactive appointment/chat times, decimal values beside hearing units, preserved raw Unicode/user text, stale speech cancellation across preferences/tabs, and single ownership of the installation manifest. The default manifest URL/body and app identity remain available through explicit routes; its factory was moved out of Next’s automatic metadata-file registration.

## Remaining acceptance and merge decision

- **UNVERIFIED:** actual installed Windows SAPI/OneCore/browser voice availability, supported male/female metadata, real recognition and physical audible output. The app enumerates voices exposed by Web Speech; it does not claim an OS-wide inventory. Local free-text synthesis accurately reports unavailable if its optional tools are absent.
- **UNVERIFIED/BLOCKED here:** new-build AAOS recognition, WebView/system voice availability, native language UI, audible output, OS permission denial and lifecycle behavior. This Cloud runtime has no `/dev/kvm`. No new emulator Actions run was triggered. The existing manual workflow is deliberately restricted to the old AAOS feature ref; any future authorized run must validate a reviewed ref containing these changes while retaining the existing cost/artifact/timeout controls.
- **UNVERIFIED:** live paid-provider generation and online voice service behavior; no paid API requests were made. Existing provider consent/safety restrictions are retained.
- **PENDING:** listening/pronunciation/linguistic review of new synthesis and translations. EN/DE hearing digit banks are separate/versioned and explicitly not established as acoustically or clinically equivalent; the warning is visible and scoring/calibration restrictions remain unchanged. No clinical or OEM/production certification is asserted.

Keep the PR **draft and unmerged** until the required platform speech and listening acceptance is resolved. The bounded CDC Local and AAOS checks are specified in [VOICE_AND_AUDIO.md](VOICE_AND_AUDIO.md); no repeated broad health/device QA, training, new model, deployment or automatic Actions retry is requested.

## Evidence retention

Selected actual screenshots and compact machine receipts are committed under `docs/localization/evidence/`. Full screenshots, raw test/geometry/audio evidence, source-change checksums, harnesses and a ZIP are retained under `/workspace/attune-localization-20261020/`. Earlier failed diagnostic iterations remain separately retained and are not counted as passing acceptance. Original AAOS archives and their private Drive preservation remain untouched.
