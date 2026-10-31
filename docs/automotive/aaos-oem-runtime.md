# AAOS OEM demonstration runtime

These switches support the existing Android Automotive prototype on devices
without a native browser speech-recognition implementation. They do not certify
an OEM vehicle, physical camera, calibrated hearing device, or clinical model.

## Opt-in microphone transcription

The default remains the existing native speech provider. To explicitly enable
the cloud provider in an isolated demonstration build, build the frontend with
`NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER=openai` and run the loopback API with
`ATTUNE_CLOUD_ASR_ENABLED=1`. Supply the existing OpenAI credential through the
deployment environment; never embed it in the frontend, APK, or evidence.

Vision and Mental then require the additional `cloud-asr-openai-v1` consent.
An earlier service grant cannot silently authorize this new processing purpose.
Real Android microphone capture is encoded by MediaRecorder and sent to
`POST /api/speech/transcribe`. The route requires an explicit trusted Origin,
strict consent, an allowed service/language, and bounded WebM/WAV input. It uses
the existing bounded OpenAI client, one in-flight transcription, and memory-only
payloads. Provider exceptions are sanitized. Returned recognition confidence is
unknown (`0`), never a fabricated certainty. Cancellation and consent revocation
stop capture and reject late responses.

The debug shell declares Android's normal `MODIFY_AUDIO_SETTINGS` permission so
WebView can route microphone audio. Camera and microphone runtime consent and
the existing native PARK/background restrictions remain in force.

## Isolated CPU Skin analysis profile

The standard backend deadline remains 90 seconds and the frontend transport
deadline remains 95 seconds. On a deliberately selected slow CPU demonstration
runtime, set both:

```text
ATTUNE_SKIN_ANALYSIS_PROFILE=extended-cpu
NEXT_PUBLIC_ATTUNE_SKIN_ANALYSIS_PROFILE=extended-cpu
```

This gives the same worker up to 180 seconds and its transport 185 seconds.
The frontend setting is a build-time setting. Request parameters cannot select
the profile. Model math, image quality thresholds, inference order, and worker
cancellation on movement, consent loss, disconnect, or timeout are unchanged.
Do not enable this profile to conceal a stalled worker. Keep stage timing and
real AAOS response evidence. Experimental acne-v5 remains explicitly experimental.

## Loopback origins

The Android debug build accepts `attuneDebugWebOrigin` and `attuneDebugApiOrigin`
Gradle properties, validated as local HTTP origins. Defaults are unchanged.
The test deployment bridges the existing app through restricted SSH tunnels;
LXD and AMS administration are never exposed publicly. Use the actual property
names in `apps/automotive/app/build.gradle` when reproducing a build.

## Complete structured session summaries

The structured Mental session analyzer requests a strict JSON schema derived
from its existing `SessionAnalysis` contract. Plain JSON mode allowed a real
provider response to omit `spokenSummary`, which correctly prevented saving a
successful session but interrupted the spoken closing. Every schema field is
required (nullable fields can still return null), and theme values use the
existing stable vocabulary. Server validation remains authoritative and no
missing content is fabricated or silently retried. The ordinary non-structured
analyzer retains its previous JSON mode. The selected provider/model must support
strict structured outputs; the real demonstration verified `gpt-4o-mini`.

The provider contract follows the official
[Structured Outputs guidance](https://developers.openai.com/api/docs/guides/structured-outputs).

## Validation boundary

`tests/unit/cloud_speech_runtime.cjs` exercises cancellation, consent renewal,
pending-capture cleanup, and late-response rejection with deterministic media
and provider doubles. Backend transcription and Skin lifecycle tests are in
`tests/unit`. These unit checks do not replace real AAOS media/E2E acceptance.
`tests/automotive/oem_e2e_spec.json` specifies the five real journeys; its
NOT_TESTED template is not a success certificate. Final recordings and evidence
must independently demonstrate real Android execution, all applicable result
controls, and cost-safe shutdown.
