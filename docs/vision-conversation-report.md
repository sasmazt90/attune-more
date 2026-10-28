# Vision Health PR #13 — sequential voice validation

28 October 2026. [PR #13](https://github.com/sasmazt90/attune-more/pull/13)
remains draft, unmerged and undeployed. Implementation tested by the current
production-browser runs: `6e3269a2f64fadd570f0883a591c9ab84cd5c90c`.
The evidence/report delivery commit is the PR head; machine-readable results and
implementation CI are in [validation.json](vision-conversation-evidence/validation.json).
Earlier `vision-evidence/` results are historical and do not establish the current
sequential requirement.

## Mental Health comparison and confirmed fixes

[The source comparison](vision-asr-comparison.md) covers configuration, permissions,
capture ownership, retries, transcript acceptance, timing, scoring gates and
browser/AAOS limits. Both modules use browser SpeechRecognition; there is no
new provider or model. Mental uses a single recognition turn after output. Vision
previously overlapped output and continuous recognition, and had stimulus/camera
and structured-answer dependencies that Mental does not have. This establishes
code defects, not a physical microphone A/B comparison.

Vision now aborts recognition before output, waits for native playback completion
and a 350 ms teardown gap, then listens. One final result is accepted per
recognizer. Interim text indicates activity only. The existing approved short
TR/EN/DE recordings ask for only missing/ambiguous fields. Letter, rotation and
mirror information remain bound to the current session, eye and stimulus.
Unknown speech cannot erase recognized fields or enter the score denominator.
Corrections in a listening turn replace only the supplied component; complete
answers settle once without inviting speech while the microphone is closed.

Confidence remains independent per component and native result segment. Unknown
native confidence is not invented, and a confident direction cannot confirm an
earlier low-confidence letter. The response clock excludes output, teardown and
final settlement. Silence gets one reminder per stimulus/component, then quiet
restarts. Existing bounded transport retries and cancellation guards remain.

An actual German browser run exposed an additional failure: “auf dem Kopf” was
discarded by the instruction-substring echo filter. Valid semantic partial answers
now take priority. [Before/after source reproduction](vision-conversation-evidence/de-echo-reproduction.json)
records the initial **FAIL** and corrected **PASS**; the before-fix screenshot is
retained as failure evidence. No failing physical scenario has been converted into
a pass by a manual interaction.

## Stage matrix

| Stage | Status | Observed evidence and limits |
| --- | --- | --- |
| Preparation, eye instructions and visible SVG | PASS | Production build, loaded fonts/assets, native approved audio; camera/model fixture |
| Output completes before recognition; no overlap | PASS | 43 recognition starts per locale, minimum 350.6 ms after native output, zero overlap violations; events retained before history reload |
| Partial answers, unknown speech, ambiguity, independent confidence, corrections | PASS | Actual-source controller: 15 scenarios per language; production-browser turn logs linked below |
| Deterministic natural transcript interpretation | PASS | 39 TR + 31 EN + 30 DE cases, including spelling words, numeric rotations, mirror/axis variants, colloquial forms and explicit corrections; unrelated/incorrect words rejected. This is not ASR accuracy |
| Automatic correct/wrong eye, hand/object, camera-loss admission | PASS | 42 gate/geometry checks, actual-tracker generated pixels and controlled production browser, both anatomical sides |
| Closure at small eye size and slow fresh frames | PASS | Stable eye-corner pixel regions; sustained samples within camera freshness; spatially distinct head anchors; generated tracker evidence |
| Gaze left/right/up/down, both sides | PASS | Actual tracker with independently moved source-pixel pupils and iris landmarks, eight conditions; no pupil-centering or eyeLook gate added |
| Native camera/model lifecycle | PASS | Actual fake-device capture and local MediaPipe GPU: no-face pattern rejected; permission denial and disconnection clean up |
| Natural physical closure / hand / opaque object / off-axis gaze | BLOCKED | Cloud has no participant camera media; generated pixels and injected model states cannot establish physical accuracy |
| Native microphone permission denial | PASS | Native SpeechRecognition reports `not-allowed`; zero scored trials |
| Native microphone transcription in TR/EN/DE | BLOCKED | API exists, but native probe reports `audio-capture`; physical microphone unavailable, no utterance accuracy tested |
| Both eyes, completion, score and history reload | PASS | 24 valid responses per locale, 12 per eye, 23 combined correct / one recognized wrong; results and history reload pass |
| Retry, pause/output interruption, spoken resume | PASS | Production browser/native audio, controlled ASR/model in all three locales; retained component and retry limit checked |
| Exit/restart, stale final, camera/microphone consent withdrawal | PASS | Owned media/output/recognition stop; incomplete history absent; current presentation cannot accept an old callback |
| Desktop and 390×844 mobile rendering | PASS | Actual production screenshots in all three languages, loaded assets, no horizontal overflow; simulated camera content labeled |
| Frontend checks and localization | PASS | Typecheck, lint (no warnings/errors), production build; inventory/translation IDs and placeholders valid |
| Regression suite | PASS | 1,796 passed / 44 skipped; final copy/timing-log delta: 57 Vision tests passed |
| AAOS host policy / Java syntax | PASS | 69 host checks; nine source files parse; not Android runtime proof |
| Android assembly/lint and AAOS WebView speech | BLOCKED | Full JDK 21 available; Android SDK missing. Workflow dispatch also returns GitHub HTTP 403. No runtime/device evidence |

## Per-language turns and score

The test drives actual production UI, score logic, SVG, native approved recordings
and results/history integration. Camera video, model output and ASR transcripts
are explicitly simulated. Each language runs 24 valid answers, 12 per eye, with
one intentionally recognized wrong letter. Expected combined correctness is
23/24; the existing letter/orientation result formulas remain unchanged.

| Language | Turn-by-turn log | Conversational scenarios | Complete session |
| --- | --- | --- | --- |
| TR | [Turkish](vision-conversation-evidence/conversation-browser-tr.json) | 12 | PASS: 24 valid, 23 combined correct |
| EN | [English](vision-conversation-evidence/conversation-browser-en.json) | 12 | PASS: 24 valid, 23 combined correct |
| DE | [German](vision-conversation-evidence/conversation-browser-de.json) | 12 | PASS: 24 valid, 23 combined correct |

Each log contains the supplied transcript and confidence, score count before the
turn, requested follow-up, whether the turn scored, native output/recognition
events, and overlap violations. The 12 cases are letter only, orientation only,
both, neither, ambiguous letter, ambiguous orientation, low letter confidence,
low orientation confidence, letter correction, orientation correction, bounded
silence and stale callback. Results include both eyes and history after reload.

Additional evidence: [controller](vision-conversation-evidence/controller-turns.json),
[transcript matrix](vision-conversation-evidence/transcript-matrix.json),
[retry/pause/resume](vision-conversation-evidence/lifecycle-browser.json),
[exit/restart/cleanup](vision-conversation-evidence/cleanup-browser.json),
[native camera](vision-conversation-evidence/native-camera.json), and
[native speech](vision-conversation-evidence/native-speech.json).

## Native limitations and reproduction

With the production frontend on `http://127.0.0.1:3306`, the existing local API and
approved speech assets available, and installed Chrome/Playwright:

```sh
export VISION_TEST_URL=http://127.0.0.1:3306
export CHROME_PATH=/path/to/google-chrome
python tests/e2e/vision_native_camera.py
python tests/e2e/vision_native_speech.py
VISION_TEST_LANGUAGES=tr python tests/e2e/vision_conversation.py
VISION_TEST_LANGUAGES=en python tests/e2e/vision_conversation.py
VISION_TEST_LANGUAGES=de python tests/e2e/vision_conversation.py
python tests/e2e/vision_conversation_lifecycle.py
python tests/e2e/vision_conversation_cleanup.py
```

The camera probe uses Chrome's fake-device input with unchanged local model
weights. It detects zero faces and both eyes uncertain; rejection passes, positive
natural-face accuracy remains unverified. The speech probe keeps the actual native
recognizer and fake microphone, while controlling camera/model admission. Its
observed sequence is native instruction playing/ended, visible letter,
question playing/ended, listening, `asr-error:audio-capture`; zero trials score.
The separate microphone-denied context reports `asr-error:not-allowed`.
Neither is a successful transcription.

The Android command `bash scripts/automotive/build.sh` with a verified complete
Temurin 21 JDK reaches `:app:compileDebugJavaWithJavac` dependency resolution, then
fails: `SDK location not found. Define a valid SDK location with an ANDROID_HOME
environment variable or by setting the sdk.dir path`. The former missing
JAVA_COMPILER blocker was resolved; the SDK remains missing.
`gh workflow run automotive.yml --repo sasmazt90/attune-more --ref
feat/vision-live-test-resolution` returned `HTTP 403: Forbidden`.

For the remaining natural-media and AAOS scenarios, follow the
[real-device procedure](vision-physical-validation.md): no injected recognition or
landmarks, both anatomical sides, natural gaze in four directions, microphone
permission grant/denial, each locale, 24 questions, and separate transcription,
interpretation, score and lifecycle outcomes. Valid actions that stall are failed
acceptance cases, never manually overridden passes.

## Original defects

| Reported defect | Status | What is established |
| --- | --- | --- |
| Spoken answers unreliable | PARTIALLY FIXED | Sequential capture, valid orientation echo, turn races and confidence mixing fixed in code; positive real microphone transcription blocked |
| Natural TR/EN/DE interpretation | FIXED for tested transcripts | 100 deterministic cases and conversational fixtures pass; real accent/noise/transcription accuracy remains UNVERIFIED |
| Repeated guidance / stale playback | FIXED in controlled integrations | Short per-component follow-ups, bounded silence, output ownership and cancellation verified; no physical acoustic acceptance claim |
| Automatic closure / hand / object detection stalls | PARTIALLY FIXED | ROI collapse, slow-frame holds and inadequate head-anchor distribution fixed; natural camera acceptance UNVERIFIED |
| Gaze-to-camera alignment | UNVERIFIED physically | Source audit finds no pupil-centering gate; eight generated gaze conditions pass without threshold relaxation |
| Wrong progression / scoring / session state | FIXED in automated coverage | Per-target memory, one commit, unscored unknown/invalid speech, stale-event rejection and existing scoring formulas verified |
| UI consistency | PARTIALLY FIXED / presented for review | Shared preparation, cockpit tokens, camera/history/result components retained; differences below are reported without redesign |

## Scope and UI review

Removed from the initial PR implementation: letter/orientation answer buttons,
speech/buttons mode selector, manual closure/coverage confirmation, its camera
condition override, related state/fallback/result metadata/copy/tests, and the
added replay button. Existing start, pause/resume, retry, restart and finish
controls remain; spoken repeat remains. No alternative answer path, confirmation,
user-confirmed gate or new provider/model was introduced in this follow-up.
Approved audio manifests and scoring/adaptation formulas are preserved. Skin,
Dental, Hearing and Mental behavior is unchanged.

Comparison with Skin/Dental/Hearing: Vision uses the shared HealthStartCard,
CameraPreview, RecordHistory, accessible dialogs, dark cockpit surfaces, turquoise
accent and localization system. Passive eye stages/progress follow the existing
module journey pattern. The production screenshots show loaded assets, readable
text, no development overlay and no horizontal overflow at 390 px.

Existing differences for owner review, without redesign: the shared mobile header
takes substantial vertical space; Vision puts the optotype before camera status
on mobile, requiring scrolling for condition details; its active section is wider
than the preparation card; the previous heard fragment can remain visible during
an eye-switch instruction until the next target binds, though it cannot score for
the new target; Hearing/Dental have more specialized panel hierarchy. No additional
control or workflow is proposed or implemented here.

Current screenshots (camera panels are visibly labeled **CONTROLLED CAMERA / Not
physical acceptance**): [preparation](vision-conversation-evidence/desktop-preparation.png),
[active/listening](vision-conversation-evidence/desktop-listening.png),
[closure instruction](vision-conversation-evidence/desktop-eye-closure-instruction.png),
[coverage instruction](vision-conversation-evidence/desktop-eye-coverage-instruction.png),
[hand](vision-conversation-evidence/desktop-hand-coverage.png),
[object](vision-conversation-evidence/desktop-object-coverage.png),
[retained spoken letter](vision-conversation-evidence/desktop-recognized-letter.png),
[response processing](vision-conversation-evidence/desktop-spoken-response.png),
[results](vision-conversation-evidence/desktop-results.png),
[history](vision-conversation-evidence/desktop-history.png),
[mobile TR](vision-conversation-evidence/mobile-tr.png),
[mobile EN](vision-conversation-evidence/mobile-en.png),
[mobile DE](vision-conversation-evidence/mobile-de.png).
