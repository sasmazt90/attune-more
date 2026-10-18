# SAG-01: source-bound lower face and contour support

The existing MediaPipe scores already travel from the accepted landmark call
through the source snapshot to expressionObservation/photoId and backend
validation. Thresholds for jawOpen, smile/frown, puff/press and conditional
pucker remain unchanged. Static lip shape is not a verified smile. FRONT/RIGHT/
LEFT capture-angle thresholds and anatomical side mapping are retained.

Two concrete protections are added: absent expression support no longer counts
as confirmed neutral, and the normal product lower-face path checks the same
requested-angle yaw/pitch/roll limits as the capture function. Only affected
lower-face sag results become null; unrelated criteria stay available. Source
photoId/version mismatch is still rejected. Snapshots and observation payloads
copy coefficients/landmarks, preventing later object mutation from changing
the accepted frame's metadata. Lower-face expression scope is versioned
`source-bound-lower-face-expression-v3-observed-pose`; old records are untouched.

For the already recorded 29cc4ba7 source, current chin v9 tracing has full
sampling-band coverage and approximately70% jaw-boundary coverage. Nine local
fold samples form runs no longer than3, below the unchanged minimum5; no
supported run is trackable. `CONTOUR_TRACKING_INSUFFICIENT_SUPPORT/null` remains
correctly unknown. There is no reviewed positive sag target annotation here.
No coordinate/scale error was demonstrated. No band widening, threshold
relaxation, invented continuity or normal-jaw-as-sag label was introduced.
The separate staging external-contour branch is not the production method and
was not promoted or modified. This task does not establish clinical sagging
or severity accuracy.

## Explicit unfinished delivery item

The fixed neutral-mouth spoken instruction could not be generated: the existing
runtime Edge-TTS returned NoAudioReceived twice; the already installed standard
client then returned a403 handshake. No paid/fallback voice, placeholder,
unrelated dental clip or silent audio was substituted. Existing audio bank
bytes/manifest remain unchanged. The generator now writes atomically and
removes its partial file on failure; error output omits provider URLs.

The new neutral live-capture condition is deliberately INACTIVE until an actual
verified same-Ahmet/profile clip is admitted to the existing content-addressed
bank. Backend null protection IS ACTIVE. Therefore neutral capture/voice
guidance is NOT completed by this delivery. Existing pose instructions gain
the same rate-limited issue path, with no new visible text/control. Mute,
cancel, driving, permission and route lifecycles remain respected. No permanent
UI text or visual design was added. Future asset admission must retain the
same voice/rate/pitch and existing cancellation lifecycle.

Focused source/expression/pose/null-map/snapshot and voice-timer controls,
recorded-source before/after, one normal API/schema chain, protected hashes,
build/shortcut identity and owned temporary-process closure are recorded in
the workspace parent's `cdc-progress/skin-neutral-contour-20261017`. Synthetic
score/pose and fake-audio controls are engineering evidence, not natural
accuracy or physical acceptance. Visible browser/history/semantic-permission
acceptance remains open for FINAL-01 under the Computer Use URL boundary.
No fixture is written to user storage; other models/methods/records are retained.
