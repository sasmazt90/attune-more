# Vision physical acceptance procedure

Status: **not executed in Cloud**. This procedure uses the existing voice-first
product. It does not add any answer method, camera override or confirmation.
Obtain the participant's permission before recording test media; keep raw face
and voice recordings outside Git and remove them after the agreed review.

## Setup

Use the production build on desktop Chrome, mobile Chrome and the intended AAOS
WebView/host. Record OS/browser version, locale, microphone/camera model, glasses,
lighting and approximate viewing position. Keep the vehicle parked. Use the
existing consent flow, enable camera/microphone, start with both eyes open, and
wait for baseline preparation. Do not inject landmarks or recognition results.
Unsupported browser ASR must be reported as unavailable, not as a passed test.

## Automatic camera matrix

Run each condition separately for RIGHT-test-eye and LEFT-test-eye stages:

| Condition | Required behavior |
| --- | --- |
| Requested other eye physically closed | Stable closed evidence; test eye stays independently open |
| Other eye covered by palm | Stable local hand/appearance evidence; automatic continuation |
| Other eye covered by opaque paper/object | Stable replacement evidence; automatic continuation |
| Wrong eye covered | No response admission; guidance identifies test eye |
| Both eyes covered | No response admission |
| Entire camera covered / face leaves frame | No response admission; camera/face unavailable |
| Dim light, glare, glasses, head movement | Reject uncertain frames; recover when current evidence is valid |
| Brief blink / temporary landmark loss | No dialog loop or repeated prior instruction; invalid states cannot score |
| Slow but fresh 350–500 ms frames | Baseline/eye holds can complete; excessive frame age still rejects |
| Camera denied / disconnected | No saved incomplete result; owned tracks/worker close |
| Eye switch | New anatomical side evaluated; previous side cannot satisfy it |

Measure time from sustained correct action to admission, source frame age, model
frame intervals and oscillation count. Keep verified detection distinct from
uncertain inference. A stalled valid cover is a failed physical acceptance case;
there is no manual path that can turn it into a pass.

## Speech matrix

For each of TR/EN/DE, run at least 24 questions with actual microphone input.
Select the locale before starting or while paused using the existing controls.
Include direct letters, common spelling words, explicit spelling syntax, both
orders of letter/orientation, mirror + rotation, corrections, colloquial speech,
quiet/noisy rooms, silence, low volume, accents and delayed/repeated responses.
The deterministic examples in `vision-evidence/transcript-matrix.json` are a
starting corpus, not recordings or proof of ASR accuracy.

Record four independent outcomes for each utterance:

1. Actual ASR transcript/alternatives and reported confidence (unknown stays unknown).
2. Parsed letter/rotation/mirror/ambiguity.
3. Current stimulus ID, anatomical eye, admission conditions and scored answer.
4. User-facing progression, microphone state and guidance cancellation.

Include speech while the answer instruction is playing, a correction immediately
after a complete final, restart after silence, transport loss, repeated finals,
late results after a question changes, pause/resume, exit/restart and consent
withdrawal. Wrong but clearly recognized answers must score wrong; ASR/condition
failures must remain unscored. Repeat must be explicit. A correct response must
stop obsolete audio and advance once. Reopen completed history after reload.

Report per-language transcription accuracy separately from interpretation and
scoring accuracy; record unresolved cases instead of averaging them into success.
Do not mark PR #13 physically accepted until the natural camera and microphone
scenarios above have actual evidence.
