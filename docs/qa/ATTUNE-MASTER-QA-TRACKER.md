# Attune.more master QA tracker

Live status of QA-01 to QA-34. Update the row in the same commit as the work.

**How to read status.** A build, an HTTP 200 or a results screen alone never makes an item DONE. "Final" stays
open until the item is verified on the final release candidate. Evidence is labelled:

- **Live AAOS:** the real Android 15 WebView on the emulator
- **Live WEB:** real Chrome against the deployed application
- **Viewport audit:** local Chrome resized to a vehicle size with the native stylesheet. Not the real WebView.
- **Static:** source change or unit test only

**Task IDs.** Master-task IDs are the ones named in the owner's instruction of 2026-11-04. The definition of all
21 master tasks was not found. Searched: this repository, and Drive (`Attune-more-FINAL-TASK-TRACKER.csv` is the
marketing-deck tracker, a different numbering). Task IDs are not reused or renumbered here.

**Priority.** The instruction gives no priority for QA-20, 26, 27, 28, 29, 30 and 31. Those marked `*` are proposed.

Baseline commit: `4503f2d`. All five CI jobs pass on it.

## Summary

| Status | Count | Items |
|---|---:|---|
| DONE (awaiting final candidate) | 1 | QA-29 |
| IN PROGRESS | 13 | QA-08, 09, 11, 12, 21, 22, 23, 24, 27, 30, 31, 32, 34 |
| NOT STARTED | 20 | QA-01, 02, 03, 04, 05, 06, 07, 10, 13, 14, 15, 16, 17, 18, 19, 20, 25, 26, 28, 33 |
| BLOCKED | 0 | |

## Items

| QA | Task | P | Status | Root cause or suspected cause | Files | Commit | Evidence | Remaining | Acceptance | Final |
|---|---|---|---|---|---|---|---|---|---|---|
| QA-01 | 11.1 | P0 | NOT STARTED | Suspected: Turkish mood labels reach the English summary ("feeling Gergin") | `mental_provider.py`, summary prompts, stored summaries | | | Trace and fix; verify TR, EN, DE separately | All generated text and labels match the selected language | Open |
| QA-02 | 11.2 | P0 | NOT STARTED | Chatterbox on CPU: 70.1 s for one short sentence, measured | `mental_neural_tts.py`, `useMentalConversation.ts` | | `restart-acceptance-20261104.json` | Instrument each stage; reduce latency without changing the voice | Separate repeatable timings for ASR, LLM, TTS, delivery, playback; cold and normal apart | Open |
| QA-03 | 11.3 | P2 | NOT STARTED | Unknown | Mental transcript UI | | | Fix wording | A transcript not saved by consent is not shown as a failure | Open |
| QA-04 | 19.1 | P0 | NOT STARTED | Consent copy leads with vendor names | `serviceConsent.ts`, `HealthConsentGate.tsx`, privacy page | | | Lead with Attune.more; keep third-party disclosure | Five modules and Privacy reviewed; actual data flows still disclosed | Open |
| QA-05 | 01, 19 | P1 | NOT STARTED | Callouts drifted from the approved design | `SkinFindingCallouts.tsx`, `SkinRegionOverlay.tsx` | | | Find references; restore | Before and after against approved references; no obstruction; anchoring kept | Open |
| QA-06 | 19.3 | P1 | NOT STARTED | Unknown; identity not yet checked | `HealthStartCard.tsx`, `public/assets` | | | Compare with latest approved files | Each portrait matches the approved file, or the missing source is documented | Open |
| QA-07 | 19.4 | P1 | NOT STARTED | Inconsistent hierarchy, technical labels | `app/care/page.tsx` | | | Redesign | Consistent type; no redundant text; status kept | Open |
| QA-08 | 19.6 | P0 | IN PROGRESS | Native insets exist; WebView measured between the bars | `MainActivity.java` | `a9b7919` | Live AAOS: `aaos-viewport-20261103.json` | Toolbar APK not yet on the emulator; verify controls on real screens | No control covered by native UI on the real emulator | Open |
| QA-09 | 19.7 | P1 | IN PROGRESS | Fixed-size dialogs; actions could scroll away | `AccessibleDialog.tsx`, `globals.css` | `a9b7919` | Viewport audit | Result dialogs with real data, keyboard and focus | Close and primary action reachable at every size | Open |
| QA-10 | 19.8 | P2 | NOT STARTED | `ⓘ` renders as an empty box on Chrome on the WEB host: a text glyph, not an icon | Components using the glyph | | Live WEB screenshot | Replace with an icon; sweep other glyphs | No empty boxes on WEB or AAOS | Open |
| QA-11 | 19.9 | P1 | IN PROGRESS | Plurals and percent format fixed; the rest not reviewed | `i18n/core.ts`, `messages.json` | `3852f94`, `4503f2d` | Static: localization check, unit tests | Review all TR, EN, DE text | Reviewed; findings fixed or listed | Open |
| QA-12 | 19.10 | P1 | IN PROGRESS | Overflow checks missed visual faults | `scripts/qa/ui/automotive-audit.cjs` | `4503f2d` | Viewport audit in EN and DE | Screenshots on the real WebView; confirm consent text no longer peeks below pinned buttons | Reviewed screenshots per the required state list | Open |
| QA-13 | 20.1 | P0 | NOT STARTED | Feature absent | `app/care/page.tsx` | | | Build | User confirms and saves; view, edit, delete; no false "booked" claim | Open |
| QA-14 | 20.2 | P0 | NOT STARTED | Hardcoded `preferredCity: "İstanbul"` | `app/care`, `main.py` care match | | | Remove; add region preference with fallback | Region independent of UI language; specialty and region match | Open |
| QA-15 | 20.3 | P1 | NOT STARTED | Unknown | `app/care/page.tsx` | | | Fix | User-local time; correct appointment type | Open |
| QA-16 | 10 | P1 | NOT STARTED | Suspected: per-origin storage; earlier tests delete their records; consent gates saving | `healthRecords.ts` | | | Investigate each cause | Causes distinguished with evidence | Open |
| QA-17 | 10 | P1 | NOT STARTED | Not yet tested | `healthRecords.ts`, `RecordHistory.tsx` | | | Run the full sequence | Save, history, refresh, re-entry, Stop/Start, history, delete; no duplicates or restored deletions | Open |
| QA-18 | 21 | P0 | NOT STARTED | Earlier videos cover digits-in-noise only | `app/hearing/page.tsx` | | | Validate pure-tone end to end | Completion, results, history on both platforms | Open |
| QA-19 | 19, 21 | P1 | NOT STARTED | Unclear raw numbers | `HearingToneResults.tsx`, `HearingStoredResult.tsx` | | | Redesign live and saved views | Understandable with real data; not presented as clinically calibrated; fits AAOS | Open |
| QA-20 | 21 | P0* | NOT STARTED | | | | | Record | Separate pure-tone videos on WEB and AAOS | Open |
| QA-21 | 09 | P0 | IN PROGRESS | The old test answered "can't see" every time; no limit existed | `spokenVision.ts`, `SpokenLetterPage.tsx`, `scripts/qa/realistic` | `3852f94`, `4503f2d` | Live WEB and Live AAOS full runs PASS on deployed `a9b7919`: 24 trials, one can't-see, real ASR | Rerun on the final candidate for the videos | Trial record has symbol, intended answer, transcript, parsed answer, correctness, eye, size and scores | Open |
| QA-22 | 09 | P1 | IN PROGRESS | Early stop was shown as complete | `LetterVisionResult.tsx` | `3852f94` | Live WEB and Live AAOS stop scenario PASS on `a9b7919` | Recheck on the final candidate | Stopped runs labelled; unmeasured letters shown; size tables reachable | Open |
| QA-23 | 08 | P0 | IN PROGRESS | Supplied BITE photo fails the contact gate | `dentalCapture.ts`, `dental_analysis.py` | `fc25c91` | Live AAOS: 4 views measured, HTTP 200, history reopened, but with the **substituted Male set**. Does not close this item | Run with the original female photos after QA-24 | Four valid views with the supplied photos on the real emulator, or honest PARTIAL | Open |
| QA-24 | 18 | P0 | IN PROGRESS | Closed bite with discoloured enamel: 419 of 488 excluded pixels read as pink-like, contact 47.06% against 60% | `dental_analysis.py`, `dentalCapture.ts` | | `dental-bite-gate-20261104.json` | Fix classification; validate on controls | Open, closed, discoloured, normal controls correct; threshold not simply lowered; uncertain when unsure | Open |
| QA-25 | 18.1 | P0 | NOT STARTED | A visible acne lesion was missed earlier | Skin pipeline | | | Test after QA-31 | False negatives and positives reported per image; "Unclassified spots" not a failure by itself | Open |
| QA-26 | 16 | P1* | NOT STARTED | | Recording pipeline | | | Set capture quality | Readable, adequate FPS, synchronized audio | Open |
| QA-27 | 16 | P0* | IN PROGRESS | Earlier deployment: older source plus patches. AAOS copy step nested folders, fixed in `4503f2d`, not yet redeployed | `deploy_release.py`, `deploy_host.py` | `4503f2d` | WEB ran `a9b7919` with recorded provenance | Deploy final candidate including the APK; verify all layers | Commit, frontend, backend, APK, models, config verified on both | Open |
| QA-28 | 16 | P2* | NOT STARTED | | | | | Remove diagnostic overlays from recordings | Clean presentation; honest disclosure in the report | Open |
| QA-29 | 17 | P1* | DONE | | `AttuneControl.ps1`, `stable_host.py` | `fc25c91` | Live: Stop, Start, READY, Stop. `restart-acceptance-20261104.json` | None unless operational code changes | Real cycle succeeds | Pending final candidate |
| QA-30 | 16 | P0* | IN PROGRESS | | CI | `4503f2d` | 5 of 5 CI jobs pass | Rerun all suites on the final candidate | All listed suites pass | Open |
| QA-31 | 18.9 | P0* | IN PROGRESS | | `docs/qa/SKIN-MODEL-CONTRACT.md` | | Started | Complete matrix and runtime proof | Every indicator rated with evidence; no invented decisions | Open |
| QA-32 | 19.11 | P1 | IN PROGRESS | Hero took over half the usable height with a redundant chip row | `app/page.tsx` | `4503f2d` | Viewport audit | Measure and screenshot on the real WebView; WEB and AAOS separately | Module cards visible with little scrolling; identity preserved | Open |
| QA-33 | 19.12 | P1 | NOT STARTED | Live preparation falls through to the saved-record placeholder in the face panel | `SkinFacePanel.tsx`, `SkinActiveScan.tsx` | | Viewport audit screenshot | Fix; test every camera state; confirm synthetic frames only in QA | Accurate message in each state on both platforms | Open |
| QA-34 | 19.13 | P1 | IN PROGRESS | Baseline at 1280x517: 3.2 screens, 46% preview visible | `dental.module.css`, `app/dental/page.tsx` | `4503f2d` | Baseline: Live WEB resized to 1280x517, not the real WebView | Measure on the real WebView; before and after | Preview fully visible; no detail lost; manual visual acceptance | Open |

## Acceptance evidence so far

| Run | Build | Input | Platform label | Result | Scope |
|---|---|---|---|---|---|
| Restart cycle | Host config before release deploy | n/a | Live | READY, all checks | Service availability only |
| Vision full | `a9b7919` frontend | Female-Vision set | Live WEB | PASS, 14 checks | Controlled speech and photos |
| Vision full | `a9b7919` frontend | Male-Vision set | Live AAOS | PASS, 14 checks | Android microphone path, real ASR, reference camera |
| Vision stop | `a9b7919` frontend | Same | Live WEB, Live AAOS | PASS | WEB's history step had a script error fixed before the full run |
| Dental | `a9b7919` frontend | Male-Dental, JPEG recompressed | Live WEB, Live AAOS | 4 views measured | Not the supplied female BITE photo |

Findings to carry into the report:

- ASR on the Android path misheard letters (B as D). Five attempts needed the code-word fallback in the AAOS full run.
- These runs predate the final candidate, so they are not the 12 acceptance videos.
