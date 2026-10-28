# PR #13 — Mental versus Vision speech-turn audit

The owner's positive Mental Health experience is reported device evidence. Cloud
has not reproduced a successful native-microphone transcript for either module;
source differences below must not be mistaken for a physical ASR A/B benchmark.

| Area | Mental (`useMentalConversation.ts`) | Vision before this follow-up | Vision now |
| --- | --- | --- | --- |
| Recognition service | Browser SpeechRecognition / webkitSpeechRecognition | Same browser API; no backend transcription endpoint | Same provider/API, no model change |
| Recognition options | Selected locale, `continuous=false`, `interimResults=false` | Selected locale, continuous + interim | `continuous=false`; interim used only for activity, never scoring |
| Output ownership | Abort recognition before speaking; busy/voiceWaiting guards | `prompt()` spoke and immediately called `listen()` | Abort before every output; prompting stage plus output/controller guards |
| Next capture | Resume after output ends, with 350 ms teardown gap | Capture intentionally overlapped instruction | Native output completion, then 350 ms, then microphone |
| Final acceptance | One accepted final; abort recognizer | Multiple final fragments in a continuing recognizer | One accepted final per recognizer; abort before follow-up/evaluation |
| Interpretation | Free-form transcript forwarded to conversation handling | Letter + orientation needed; partial/ambiguous/noise could be confused | Preserve components across turns; ask only missing/ambiguous component; unknown speech cannot erase retained fields |
| Confidence | No Vision scoring/confidence admission | Per-component uncertainty flags from native final confidence | Independent retained letter/rotation/mirror confidence; a new component cannot confirm another |
| Camera/stimulus | No camera/stimulus admission dependency | Fresh camera, correct anatomical eye, actual visible stimulus and geometry required | Same automatic verification and score gates |
| Failure | Explicit cancellation for errors other than no-speech | Bounded retries already implemented in PR #13 | Bounded retries retained; silence gets one reminder per stimulus/component, then quiet restart |
| Cancellation | Session epoch, audio epoch, recognizer identity | Session/presentation/stage identity | Those guards retained for all follow-up output and capture turns |

## Confirmed defects and evidence

1. **Overlapping channels:** the old `prompt()` called `speak()` and `listen()` in
   the same operation. Its previous browser regression explicitly asserted an
   answer during playback. This violated the now-authoritative sequential flow
   and exposed instruction capture/echo and audio-device contention paths. The
   new controller test asserts exclusivity in both directions; the production
   browser records native playing/ended and recognizer-start events.
2. **Wrong retry question after unknown speech:** unrecognized tokens could become
   a letter ambiguity and overwrite an already retained letter. Parsing now marks
   no-component input separately; memory retains recognized components. The next
   prompt is based on actual missing information, including ambiguity.
3. **Turn restart races:** a recognizer could stay alive during a clarification,
   or restart from `inspect()` while a response was pending. Single acceptance,
   abort-before-output, pending-response/output guards, and presentation identity
   prevent these cases. Interrupted prompts are retained until they finish.
4. **Silence handling:** silent recognition ends previously restarted capture
   without a conversational reminder. One short approved reminder per missing
   component/stimulus is now bounded; repeated silent ends do not loop speech.
5. **Valid orientation rejected as echo:** the old substring filter classified
   German “auf dem Kopf” as instruction echo, even during an answer turn. The
   actual browser run stalled on that valid orientation. Unambiguous semantic
   letter/orientation answers now take priority over phrase overlap with prompts.
6. **Confidence mixing inside a final event:** distinct native letter and
   orientation result segments were pooled by minimum confidence. The controller
   now preserves confidence for the semantic fields supplied by each result.
   Native confidence remains per result, not per word; none is invented.
7. **Response timing:** playback, output teardown and final settlement are now
   excluded from the response clock. Recognition start begins timing; final/end
   suspends it. Vision adaptation/scoring formulas are unchanged.

A native `audio-capture` error in Cloud is a separate observed environmental
limitation. Controller fixes cannot establish physical microphone availability,
provider transcription accuracy or AAOS WebView support. Unsupported/failed native
recognition remains explicit and never becomes a wrong Vision response.

## Gaze audit

The worker reads face/hand landmarks and eye-blink coefficients. It does not read
`eyeLook*` blendshapes or require iris center/position. Bounding/head/eye geometry
uses landmarks below 468; iris landmarks 468–477 do not establish alignment,
closure or coverage. Head framing, lighting, usable eye pixels and relative scale
still gate automatic verification.

The added actual-tracker regression moves iris coordinates and a source-pixel pupil
left/right/above/below while keeping head/lid evidence independently valid, for
both test eyes. All eight cases pass without relaxing a camera threshold. Natural
physical gaze/coverage accuracy remains blocked pending real-device evidence.

## Scope / UI

No provider/model change, answer buttons, input selector, manual confirmation,
camera override, extra UI widget or redesign. The existing preparation instruction
now correctly says to wait for Listening after the instruction ends. Existing
status slots reflect output, processing and capture. All follow-ups reuse approved
TR/EN/DE `letter`, `orientation`, `reverse`, `repeat` and `next1` recordings. The
immutable old `first` recording contains a barge-in invitation, is preserved as an
approved asset, and is not dispatched by the active sequential flow.
