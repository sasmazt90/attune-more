# Mental speech timing investigation — 2026-11-05

This reuses the completed audit's five English turns on WEB and five on AAOS. It does not rerun conversations or claim listening approval. Original recordings/reports remain private. The [numeric summary](mental-timing-20261105.json) contains timings only, without conversation content or evidence access links.

## Measured pipeline

Seconds: median (range), five observations per platform. These are sample summaries, not population percentiles.

| Stage | WEB | AAOS |
|---|---:|---:|
| Participant speech end → transcript | 1.9 (1.4–2.1) | 1.6 (1.5–1.7) |
| Chat send → complete reply text | 0.869 (0.787–1.011) | 0.888 (0.752–1.016) |
| TTS request → first complete audio ready | 11.679 (9.814–14.415) | 10.182 (8.299–12.778) |
| Ready audio → playback event | 0.006 (0.006–0.007) | 0.008 (0.007–0.009) |
| Participant speech end → first sound | 14.6 (12.6–17.0) | 12.5 (10.9–15.2) |
| First ready part → second ready part | 13.516 (12.533–17.304) | 13.276 (10.594–17.564) |
| First part playback duration | 3.140 (2.417–4.082) | 2.682 (1.955–3.866) |
| First part ended → second part playing | 11.098 (9.205–13.368) | 10.596 (8.307–14.412) |

First/end-to-end figures come from the saved turn timing report. Other intervals use original `browserTimings`: group by turn; subtract `send` from `chat-response`, `tts-request` from first `response-ready`; pair each ready event with the next playing event. Duplicate playing notifications are not extra segments. Gap is second playing minus first ended. Rounding/event boundaries explain small differences between turn-level and browser-level figures.

## What the evidence establishes

1. **API processing is not the dominant wait in these samples.** Reply text arrives about 0.9 s after send. Transcription contributes roughly 1.5–2 s. Reducing conversation quality or truncating content to optimize the chat API is not justified by this evidence.
2. **The dominant wait is local TTS preparation/generation.** The deployed baseline uses a resident CPU worker and four threads. Earlier experiments cited in the master tracker found no gain from eight threads or a second worker. Browser timing includes configuration verification, warm-up wait if any, inference, WAV encoding and transfer; it does not isolate each share. Do not label the entire 8–14 s as measured inference time.
3. **There is no audio-sample streaming.** `mental_neural_worker.synthesize()` calls whole-utterance `model.generate`, encodes a complete WAV, and the resident protocol returns complete-file base64. API, Next proxy and browser await complete bytes. Reading HTTP chunks does not make synthesis streaming; a proxy-only edit cannot make the model emit earlier samples.
4. **The gap has a concrete scheduling explanation.** `mentalNeuralSpeech` splits at a sentence boundary (at least six words), requests part two when part one is ready, and plays part one while part two generates. Playback lasts about 2–4 s; part two takes another 11–18 s to become ready, leaving the observed 8–14 s gap. Backend admission allows one generation; concurrent fetches can receive 429 rather than improve throughput.
5. **Playback dispatch is small:** 6–9 ms in these samples. This is not physical-speaker latency or subjective intelligibility. No listening session took place in this follow-up.

Source: `apps/vehicle-app/src/utils/mentalNeuralSpeech.ts`, `apps/vehicle-app/src/app/api/mental-neural-speech/route.ts`, `services/core-api/mental_neural_tts.py`, `mental_neural_resident.py`, `mental_neural_worker.py`. The parent receives resident worker phase measurements but retains only total generation time and warm/cold status, limiting historical inference/verification attribution.

## Measurable proposals

These are experiments for a justified targeted runtime session, **not deployed changes**. Preserve pinned source/model/reference voice, approved files, formal TR/DE address, multilingual meaning, safety cancellation and no-advice behavior.

| Priority | Proposal | Measurement / decision rule |
|---|---|---|
| 1 | Expose bounded numerical resident phase telemetry; add parent verification/warm-wait, proxy transfer and per-segment request/ready events. Never log text, tokens or raw worker output. | Account for total time within 100 ms; record cold/warm separately, inference real-time factor, busy count, bytes and decode/play delay. Attribute cost before optimizing. |
| 2 | Benchmark warm-up readiness and verification overhead with the existing worker. Investigate duplicate verification only if material. | At least 20 fixed synthetic turns per EN/TR/DE, warm and cold separately. Target ≥20% lower median first sound with no p95 regression. Verification reuse must retain asset identity and invalidation, never bypass checks. |
| 3 | Compare approved two-part scheduling with complete-utterance buffering, using identical text/voice. This trades first-sound wait for no inter-part gap. | Report first sound, completion, gap and abort latency together. Full buffering should have zero inter-part gaps but must disclose added initial wait. Choose only after actual EN/TR/DE listening and owner acceptance; retain current segmentation meanwhile. |
| 4 | Evaluate genuine incremental synthesis only if the pinned runtime supports it without model/voice changes. The current `model.generate` contract does not. | Proposed usability target: median first sound ≤5 s, p95 ≤8 s, p95 inter-part gap ≤0.5 s. These are not achieved results or promises under current CPU limits. Preserve every word/meaning and verify no audio after mute, consent loss, DRIVE or background. |

Chat token streaming alone can remove only a fraction of the observed ~0.9 s API wait unless generation safely starts sooner; sentence boundaries, later corrections and safety classification make speculative speech risky. Do not speak unvalidated partial text or introduce a new model/GPU here. Buffers shift waiting rather than remove it; extra workers lack evidence of benefit. Approved fixed clips remain byte-identical and must not substitute for contextual live responses.

Accept a future optimization only with matched text/language/voice/settings/hardware; objective timing and content completeness; actual listening evidence for clarity/prosody/continuity; and existing interruption/consent/PARK/DRIVE regressions. This establishes a baseline and priorities, not subjective audio approval.

## Follow-up instrumentation

See [the performance follow-up](PERFORMANCE-FOLLOWUP-20261105.md) for measured token/decoder costs and the bounded timing instrumentation. This does not supersede the original recordings or establish subjective listening acceptance.
