# Attune.more master QA tracker

Status of QA-01 to QA-35 on release candidate `4bb51b3fe1b02ad5e2c97b91fc242ea51ff0f151`.

**How to read status.** DONE means verified on the release candidate, for the scope written in the last column. A build,
an HTTP 200 or a results screen alone never makes an item DONE. Evidence is labelled:

- **Live AAOS:** the real Android 15 WebView on the emulator
- **Live WEB:** real Chrome against the deployed application
- **Static:** source change or unit test only

Passing means the flow and the checks hold. **It says nothing about clinical or detection accuracy**, which stays NOT
VERIFIED wherever no labelled ground truth exists. Independent review by Antigravity has not happened yet.

**Task IDs.** Master-task IDs are the ones named in the owner's instruction of 2026-11-04. The definition of all 21 master
tasks was not found in this repository or on Drive (`Attune-more-FINAL-TASK-TRACKER.csv` is the marketing-deck tracker, a
different numbering). Task IDs are not reused or renumbered here.

**Priority.** The instruction gives no priority for QA-20, 26, 27, 28, 29, 30 and 31. Those marked `*` are proposed.

## Summary

| Status | Count | Items |
|---|---:|---|
| DONE | 33 | QA-01, QA-02, QA-03, QA-04, QA-05, QA-06, QA-07, QA-08, QA-09, QA-10, QA-11, QA-12, QA-13, QA-14, QA-15, QA-16, QA-17, QA-18, QA-19, QA-20, QA-21, QA-22, QA-23, QA-24, QA-26, QA-27, QA-28, QA-29, QA-30, QA-32, QA-33, QA-34, QA-35 |
| IN PROGRESS | 2 | QA-25, QA-31 |
| BLOCKED | 0 |  |
| NOT STARTED | 0 |  |

## Items

| QA | Task | P | Status | Root cause | Files | Commit | Evidence | Remaining | Acceptance on the release candidate |
|---|---|---|---|---|---|---|---|---|---|
| QA-01 | 11.1 | P0 | DONE | Turkish mood labels were placed into translated summaries ("feeling Gergin") | `utils/mentalHistory.ts`, `MentalSessionRows.tsx` | `46403ea`, `2da0a41` | Live: `rc-web-language/language.json`, Mental videos, `mental-performance.md` |  | PASS for language: TR, EN and DE clean through the API; English journeys clean on both platforms. Full translation review not done |
| QA-02 | 11.2 | P0 | DONE | Chatterbox loaded per request on 2 threads: 77 s for 4.6 s of audio. Kept resident on 4 threads, same voice and weights. Replies limited in the prompt | `mental_neural_tts.py`, `mental_neural_resident.py`, `deploy_host.py`, `mental_provider.py` | `fed84d7`, `2da0a41` | Live: `mental-performance.md`, `tts-distribution.json` | Sentence streaming or a GPU for a further gain | PASS for reduction: 18.6 to 24.9 s from speech end to reply, from about 70 s. Normal median 9.1 s (n=14), cold 28.3 s. Same voice. Still slow for conversation |
| QA-03 | 11.3 | P2 | DONE | A transcript not saved by consent read as a failure | `MentalSessionRows.tsx`, `RecordHistory.tsx` | `46403ea` | Static: unit tests. Live: Mental saved record |  | PASS |
| QA-04 | 19.1 | P0 | DONE | Consent copy led with vendor names | `serviceConsent.ts`, `speechProvider.ts`, `HealthConsentGate.tsx`, privacy page | `46403ea`, `76b160d` | Live: consent screenshots in EN, DE, TR on both platforms |  | PASS: Attune.more leads; OpenAI still disclosed |
| QA-05 | 01, 19 | P1 | DONE | Numbered markers and long lines replaced the approved callouts. Rebuilt to the owner's two references: see QA-35 | `SkinFindingCallouts.tsx`, `skinCalloutLayout.ts` | `ea9d2b4`, `9f04710`, `b7fe187` | Live: `skin-label-evidence.md`, screenshots |  | PASS, superseded by QA-35 |
| QA-06 | 19.3 | P1 | DONE | Three portraits differed from the owner's files. Now byte-identical; Skin and Dental already were | `HealthStartCard.tsx`, `public/assets` | `46403ea` | Byte comparison with the owner's files; Live: preparation screenshots |  | PASS: all five identical |
| QA-07 | 19.4 | P1 | DONE | Inconsistent hierarchy and technical labels | `app/care/page.tsx` | `46403ea` | Live: `care` journey and screenshots |  | PASS |
| QA-08 | 19.6 | P0 | DONE | Native toolbar and system bars reduce the WebView to 1280x564. Layout now measured there | `MainActivity.java`, `run.sh` | `a9b7919`, `0091399` | Live AAOS: `rc-aaos-ui`, 1280x564 |  | PASS on the emulator: no control covered |
| QA-09 | 19.7 | P1 | DONE | Fixed-size dialogs; sticky actions left a gap where text showed through | `AccessibleDialog.tsx`, `globals.css` | `a9b7919`, `41d9593` | Live: `rc-*-ui`, 62 states per platform |  | PASS |
| QA-10 | 19.8 | P2 | DONE | `ⓘ` rendered as an empty box; replaced with an icon | Components using the glyph | `46403ea` | Live: `rc-*-ui` |  | PASS: no font-dependent glyphs |
| QA-11 | 19.9 | P1 | DONE | Plurals, percent format, mixed-language text. "Last 1 scans" found late | `i18n/core.ts`, `messages.json` | `3852f94`, `46403ea`, `705eb07` | Static: localization check. Live: screens in EN, DE, TR | A professional translation review, if wanted | PARTIAL: mechanical check clean; read-through limited to recorded screens |
| QA-12 | 19.10 | P1 | DONE | Overflow checks missed visual faults, and an earlier run measured a 404 page for one state | `scripts/qa/realistic/e2e_modules.py` | `2da0a41`, `14a65ff`, `41d9593` | Live: `rc-*-ui`, 3 languages, dialogs opened and scrolled |  | PASS: includes the consent text below pinned buttons, fixed in `41d9593` |
| QA-13 | 20.1 | P0 | DONE | Feature absent | `app/care/page.tsx`, `careAppointments.ts`, `CareAppointments.tsx` | `46403ea`, `66a0551` | Live: `rc-*-care`, 19 checks per platform |  | PASS |
| QA-14 | 20.2 | P0 | DONE | Hardcoded `preferredCity: "İstanbul"` | `app/care`, `main.py`, `care_provider.py` | `46403ea` | Live: `rc-*-care` |  | PASS: no default city; region independent of language |
| QA-15 | 20.3 | P1 | DONE | Times shown in UTC | `careAppointments.ts` | `46403ea` | Live: `rc-*-care` |  | PASS: local time, no UTC |
| QA-16 | 10 | P1 | DONE | Proven live: with saving at its default, a full Skin scan saves nothing. Records are per browser profile and origin. The Skin result gave no sign of it; it now says so | `app/skin/page.tsx`, `SkinResultView.tsx` | `ea9d2b4` | Live: `rc-web-qa16-default-saving`, `persistence-evidence.md` |  | PASS: causes separated; default saving proven live |
| QA-17 | 10 | P1 | DONE | Not previously tested as a whole sequence | `scripts/qa/realistic/persistence_check.py` | `76b160d` | Live: `persistence-evidence.md`, real Stop and Start |  | PASS: 11 of 11 on each platform |
| QA-18 | 21 | P0 | DONE | Earlier videos covered digits-in-noise only | `app/hearing/page.tsx` | `46403ea` | Live: pure-tone videos, `hearing-evidence.md` |  | PASS with a scripted listener; not a measure of hearing |
| QA-19 | 19, 21 | P1 | DONE | Raw numbers without context | `HearingDinResult.tsx`, `HearingToneResults.tsx`, `HearingStoredResult.tsx` | `46403ea` | Live: Hearing videos and screenshots |  | PASS: no clinical claim |
| QA-20 | 21 | P0* | DONE | Dedicated pure-tone evidence on each platform | Recordings | n/a | Two pure-tone videos |  | PASS |
| QA-21 | 09 | P0 | DONE | The old test answered "can't see" every time; no limit existed | `spokenVision.ts`, `SpokenLetterPage.tsx` | `3852f94`, `4503f2d` | Live: `vision-scoring-matrix.md`, read back from stored records |  | PASS: 24 valid trials per platform, one can't-see, real recognition |
| QA-22 | 09 | P1 | DONE | Early stop was shown as complete | `LetterVisionResult.tsx` | `3852f94` | Live: stop scenario on `a9b7919`; Results-by-size opened in both videos |  | PARTIAL: the stop scenario was not rerun on this commit; that code is unchanged |
| QA-23 | 08 | P0 | DONE | The supplied BITE photo failed the contact gate | `dentalCapture.ts`, `dental_analysis.py` | `d0759ad` | Live AAOS: original female set, video and record |  | PASS: four views measured |
| QA-24 | 18 | P0 | DONE | Discoloured enamel was read as a gap. New check uses joined contact only under a low opening; thresholds .04, .60 and .50 unchanged | `dental_analysis.py`, `dentalCapture.ts` | `d0759ad` | `dental-bite-findings.md`, `dental-bite-gate-v2-20261104.json` |  | PASS on the controls; thresholds unchanged |
| QA-25 | 18.1 | P0 | IN PROGRESS | Accuracy cannot be established from single scans. Finding register per image is in the report | Skin pipeline, no change | n/a | Report: findings register | Labelled ground truth | NOT VERIFIED: likely misses recorded, no accuracy claimed |
| QA-26 | 16 | P1* | DONE | Recording at 80% scale and browser notices over the page | `run_e2e.sh`, `run.sh` | `76b160d`, `16f8f6e` | `coverage.json`, frames reviewed |  | PASS: 1280x800, 12 fps, audio present |
| QA-27 | 16 | P0* | DONE | Earlier deployment mixed older source and patches | `deploy_release.py`, `deploy_host.py` | `4503f2d` | `rc-provenance`, `RELEASE-CANDIDATE.md` |  | PASS: commit, build, APK, models, config verified |
| QA-28 | 16 | P2* | DONE | Diagnostic overlays in recordings; the pairing key is masked | `e2e_modules.py`, `videoPoster.ts` | `76b160d`, `b4d65cd` | Frames reviewed; report discloses the test toolbar |  | PASS |
| QA-29 | 17 | P1* | DONE | Restart reported PARTIAL over two restored V5 files, then READY hid an empty OpenAI account | `deploy_host.py`, `host_ready.py` | `ea9d2b4`, `8939fa7` | Live: real Stop and Start, reports `141005` and `141037` |  | PASS: STOPPED 31 s, READY 84 s |
| QA-30 | 16 | P0* | DONE | Mood test pinned old text; prompt exemption had to follow the wording | CI | `2da0a41`, `c4016db` | CI `41808646146`, `41808646311`, `41808646456` |  | PASS: 3 of 3 workflows |
| QA-31 | 18.9 | P0* | IN PROGRESS | V5 never ran on AWS (converted line endings); Python MediaPipe was missing. Both fixed. Most model decisions have no approval record | `.gitattributes`, `deploy_host.py`, `SKIN-MODEL-CONTRACT.md` | `16f8f6e`, `9e415eb` | `SKIN-MODEL-CONTRACT.md`, `skin-contract-runtime.json` per platform | Owner decisions on V5, `regional.pt` and approvals | Runtime proven; contract NOT VERIFIED until decided |
| QA-32 | 19.11 | P1 | DONE | Hero took half the usable height; a saved hearing record pushed every Start action off the first screen | `app/page.tsx`, `HealthHistoryOverview.tsx`, `CockpitHeader.tsx` | `0091399`, `ea9d2b4`, `705eb07` | Live: `rc-*-ui`, before and after screenshots |  | PASS: 5 of 5 Start actions in the first screen at 1280x564; not at 517 px and below |
| QA-33 | 19.12 | P1 | DONE | Live preparation fell through to the saved-record placeholder | `SkinFacePanel.tsx` | `46403ea`, `c4016db` | Live: `rc-*-camera`, `rc-*-skin` |  | PASS on both platforms |
| QA-34 | 19.13 | P1 | DONE | Baseline at 1280x517: 3.2 screens, 46% preview visible | `dental.module.css`, `app/dental/page.tsx` | `4503f2d`, `b4d65cd` | Live AAOS: `rc-aaos-dental` |  | PASS: 1.46 screens, 100% preview visible, from 3.2 and 46% |
| QA-35 | 01, 19 | P1 | DONE | Owner's brief of 2026-11-04: all located findings by default, one when selected, labels fitted per language. Also arrows beside the photo, one-row header | `SkinFindingCallouts.tsx`, `skinCalloutLayout.ts`, `skinCalloutModel.ts`, `SkinResultView.tsx`, `SkinFacePanel.tsx`, `HealthResultNavigation.tsx`, `CockpitHeader.tsx` | `ea9d2b4`, `9f04710`, `b7fe187` | Live: `skin-label-evidence.md`, WEB 594 and AAOS 396 states | Independent visual review by AG | PASS on real results; photos with fewer labels than the references where a finding was measured on another photo |
