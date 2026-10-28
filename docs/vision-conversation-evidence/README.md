# Current PR #13 evidence

See [the engineering report](../vision-conversation-report.md) and
[validation.json](validation.json) for status and provenance. These files supersede
the historical simultaneous-speech snapshot in `../vision-evidence/`.

`conversation-browser-{tr,en,de}.json` are separate full production-browser runs;
`conversation-browser.json` combines them. Each has 24 valid answers, 12 per eye,
one recognized wrong answer, turn transcripts/confidence/follow-ups, 43 recognition
starts and native audio timing. Timings are collected before navigation, with
nonempty trace assertions; zero-length post-reload traces are not timing proof.

The real browser, approved audio playback, DOM, SVG, scoring and history are used.
Camera pixels/model states/ASR transcripts in the conversational runs are
**simulated**, including all positive closure/hand/object screenshots. They cannot
establish physical detector or microphone accuracy. Camera panels visibly identify
the fixture. The preparation illustration is the existing product asset.

`native-camera.json` uses actual fake-device capture and local MediaPipe; its
no-face rejection, denial and disconnection checks pass. `native-speech.json` keeps
the native SpeechRecognition implementation, which reports `audio-capture`; the
separate permission-denied probe reports `not-allowed`. No positive physical speech
or camera claim is made.

Desktop screenshots are 1440×1000; mobile screenshots are full-page captures of a
390×844 viewport in TR/EN/DE. All are from the actual production frontend with no
development overlay. The before-fix German image and reproduction JSON document
the orientation echo bug; they are intentionally labeled historical failure
evidence, separate from the current screenshots.
