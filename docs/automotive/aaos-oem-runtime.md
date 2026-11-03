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

## Bounded Skin preparation and cold-start fix

Analysis keeps its 90-second server and 95-second transport deadline. The former
extended-cpu option has been removed. Preparation loads each unchanged checkpoint
once through bounded, cancellable steps and warms inference before user pixels.
The worker configures its CPU pools before imports, and the dryness memory guard
samples physical RAM at most every 100 ms without skipping cancellation checks.

Transformers import metadata is cached with exact export/backend parity and
validated against the installed distribution version, registry code and RECORD
hashes. A mismatch falls back to the original loader. When packaging a different
pinned environment, generate its metadata once with:

```sh
python services/core-api/native_import_cache.py
```

No frames, predictions, weights or credentials are stored in that metadata.
Three-angle fusion preserves an honestly insufficient regional classification
without inventing a type or discarding otherwise valid measurements.

## Skin deadline on a shared host

The 90-second budget assumes the analysis can get CPU time. On the 4-core, 15 W
development laptop, the HTTP 504 reproduces with ample free RAM and almost no
paging: three competing busy processes next to the AAOS emulator are enough, and
memory pressure alone is not. The native worker therefore runs at above-normal
priority on Windows, and its ONNX Runtime and OpenMP lanes sleep while waiting
instead of spinning. Neither changes a computed value; thread counts stay fixed in
`local_native_worker.py` because the Torch thread count does change numeric output.

Below 400 MiB of available RAM the dryness reserve guard stops the analysis with
HTTP 503 `LOCAL_MEMORY_RESERVE`, which the UI reports as a memory condition the user
can act on. Neither the deadline nor the reserve is an environment option.

`scripts/qa/README.md` holds the launcher, resource monitor and journeys used to
reproduce these measurements.

## AAOS Vision output lifecycle

Vision reuses the media element unlocked by the user's start interaction. This
prevents later prompts from being rejected by Android WebView's autoplay gate.
Cancellation, microphone/output exclusion and consent checks remain in place.
The controller regression exercises repeated prompts in TR/EN/DE; real English
AAOS validation completed two assessments with 48 valid responses. This is UI
and integration evidence, not a clinical accuracy or physical-audio claim.

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
