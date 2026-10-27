# Vision live-test repair

Starting point: `bb6088f8826e473e986a9f40e7f901ff11026030` (main, PR #12).

## Audit

The active `/vision` route exports `SpokenLetterPage`. It presents A/B/E/F/P/R
with all distinct mirror-then-clockwise-rotate transformations. There are 12
valid responses per anatomical eye, right then left. Two correct responses halve
the CSS-pixel size; two incorrect responses undo a step. Results distinguish
letter and orientation accuracy, technically invalid trials, and “cannot see”.
Absolute distance, dioptres and clinical acuity are deliberately not inferred.
The old continuous/Snellen utilities are retained but are not this route.

Camera frames run through the local MediaPipe Face/Hand worker, personal open-eye
templates, blink coefficients, lid geometry, pixel replacement, palm overlap,
head-anchor distance consensus and temporal holds. Pupil absence is not used as
proof of closure. Coverage can defeat face landmarks and patch correlation;
single-camera inference cannot guarantee physical occlusion. The UI previously
offered no alternative and could repeatedly pause or open a blocking dialog.
`covered` also lost the distinction between hand and object evidence.

ASR is exclusively browser SpeechRecognition (tr-TR/en-US/de-DE), not a backend
transcription endpoint. Backend `vision_speech.py` is TTS. No audio recording,
VAD pipeline, local ASR model or native AAOS recognizer is connected to this route.
The recognizer ignores interim results and alternatives, commits complete finals
immediately and treats unsupported/failed recognition as a blocking error. This
drops corrections, prevents usable WebView fallback and leaves TTS speaking until
a final. The parser discards digits, uses substring replacements for foreign
grammar and infers letters from arbitrary word initials. Most degree, mirror-axis,
counterclockwise and colloquial phrases therefore fail or become ambiguous.

The prompt set already has immutable approved TR/EN/DE assets, manifests and
SHA-256 playback verification. Preserve these recordings and speaker identity.
Repeated per-question instructions and automatic clarification need explicit
per-presentation bounds; new fixed recordings are unnecessary.

Reuse HealthStartCard, CameraPreview, InformationButton, RecordHistory,
LetterVisionResult, cockpit tokens, accessible dialog and consent/park gates.
Add the journey/progress and panel hierarchy used by Hearing, without changing
Skin, Dental, Hearing or Mental behavior.

## Validation policy

Keep parser, scoring, browser-controller and physical media evidence separate.
Existing historical closeout explicitly says physical acceptance was not done.
Synthetic camera/ASR events cannot establish real eye or microphone accuracy.
The delivery report records observed checks and any missing physical validation.
