# Vision Health PR #13 — historical engineering report

This snapshot predates the owner's sequential-speech requirement. Current code,
results and screenshots are in [the conversational flow report](vision-conversation-report.md).
The earlier simultaneous-playback expectation is superseded.

Date: 28 October 2026. [Draft PR #13](https://github.com/sasmazt90/attune-more/pull/13).
Starting commit: `bb6088f8826e473e986a9f40e7f901ff11026030`.
The final implementation commit is recorded in `vision-evidence/validation.json`;
subsequent evidence/report commits are identified in the PR. No merge or deployment.

## Scope correction

Removed the newly added letter/orientation buttons, speech/buttons selector,
manual eye-cover confirmation, camera-gate override, related state/result fields,
copy, and tests. Reverted the result component to main. Removed the added replay
button too; the existing spoken repeat command remains. There is no alternative
answer workflow or manual camera verification. The remaining UI changes are the
requested passive progress/eye-stage indicators, cockpit panel styling, concise
status/guidance and localized detection feedback.

## Defects fixed in code

| Failure path | Change |
| --- | --- |
| Closing a small eye collapses the pixel ROI below the sampler's four-pixel minimum | Sample an eye-corner-based region of stable dimensions across lid movement. Preserve personal EAR/blink baselines, surrounding appearance checks and sustained evidence. Test both anatomical sides. |
| Fresh 400 ms model frames never complete preparation/eye or distance holds because every interval exceeds a 300 ms reset | Use the existing 750 ms camera freshness deadline; require at least three eye samples. A sudden stall relative to established cadence still resets the eye hold. Closure and distance thresholds are unchanged. |
| Lost face tracking can depend on several adjacent nose patches | Require three spatially distinct head anchors. Missing head/pixels still produce uncertain eyes. Hand overlap and opaque replacement remain separate evidence methods; pupil absence never proves closure. |
| Natural answers lose numbers/foreign grammar or accept arbitrary words by initials | Deterministic native TR/EN/DE interpretation, explicit spelling syntax and bounded code-word vocabulary; preserve Unicode and digits. Parse rotations, axes, combined mirror/rotation, corrections and ambiguity. No expected-letter fallback or unrestricted fuzzy matching. |
| Guidance speaks until ASR final, repeats on successive questions, or corrections arrive after scoring | Meaningful interim speech cancels obsolete playback. A 750 ms final-settlement window admits corrections, with current presentation/eye/condition checks at commit. Clarification is bounded per missing component; later questions listen without repeating guidance. |
| Transient ASR failure ends usable speech interaction | Up to two bounded transport/capture retries, without replay or scoring. Persistent/permission/unsupported failures remain explicit and use the existing retry action. No answer replacement path. |
| Duplicate/stale results, pause/unmount/permission races | Preserve recognizer/session/presentation identity, deduplication, confidence-per-component memory and clean cancellation. Hidden-page pause and microphone-consent withdrawal stop owned resources. |

## Evidence and limits

- `vision-evidence/transcript-matrix.json`: 39 TR, 31 EN and 30 DE deterministic
  transcript cases passed. Includes Elma/Edirne, spelling words, possessive
  spelling, explicit EN/DE spelling syntax, incorrect/unrelated words, corrections,
  colloquial “aşaa”, numeric rotations, mirror axes and ambiguous reverse terms.
  **These are interpretation results, not ASR transcription accuracy.**
- Six letters × eight transforms, wrong letter/direction scoring, confidence
  conflicts and 42 automatic eye gate/geometry checks passed. Five actual-tracker
  tests use explicitly generated pixels/geometry for baseline, small closed eye,
  hand/object classification, independent test eye, camera loss and slow frames.
  They do not establish natural-face detection accuracy.
- `vision-evidence/browser-results.json`: production browser, native approved
  audio/SVG/UI/API/history with controlled camera/model/ASR events. All 24 spoken
  responses, 12 per eye, automatic cover-state admission, correction, prompt
  interruption, duplicate final, retry limit, pause/resume, history and TR/EN/DE
  mobile/consent cleanup checks passed. No manual-answer/confirmation path exists.
- `vision-evidence/native-camera.json`: real local MediaPipe GPU worker with
  native browser fake-device capture rejects a no-face pattern; native permission
  denial and track disconnection produce no completed result.
- `vision-evidence/native-speech.json`: Chrome exposes native SpeechRecognition,
  but the fake-microphone probe reports `audio-capture`; no native transcription
  succeeded and zero trials were scored. Real microphone/ASR accuracy is unverified.
- Full unit suite, typecheck, lint, production build, localization inventory,
  AAOS host checks and CI observations are recorded in `validation.json`.
  AAOS host policy: 69 checks, syntax of nine Java files. Full Android assembly
  is blocked locally because the installed Java toolchain lacks `JAVA_COMPILER`.

Approved TR/EN/DE audio files/manifests, scoring/adaptation formulas, consent,
retention, parked-vehicle policy and the other four health modules are preserved.
No new speech model, dynamic voice production, provider cost or backend service.

## Remaining acceptance work

Natural left/right closure, hands, paper/objects, glasses, lighting and movement
have not been physically validated in this environment. Neither real TR/EN/DE
microphone transcription nor AAOS WebView speech capture has positive evidence.
The source fixes and automated checks cannot certify the owner's original live
scenarios. PR #13 stays draft for that reason. Use
[the physical acceptance procedure](vision-physical-validation.md), recording ASR,
interpretation, scoring and UI outcomes separately; valid actions that still stall
remain defects, never passes produced by a manual override.

Screenshots (controlled camera banner visible):
[desktop](vision-evidence/desktop-active.png),
[results](vision-evidence/desktop-result.png),
[history](vision-evidence/history.png),
[TR](vision-evidence/mobile-tr.png), [EN](vision-evidence/mobile-en.png),
[DE](vision-evidence/mobile-de.png).
