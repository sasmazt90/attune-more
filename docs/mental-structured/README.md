# Structured Mental Health experience

The new structured experience remains opt-in (`NEXT_PUBLIC_MENTAL_CONVERSATION_ENGINE=structured-v1`). The existing conversation mode remains the default. No merge or deployment is authorized.

## Voice and audio

The selected structured voice is `female-calm-v1`, including personalized closing narration. The owner explicitly approved all nine representative TR/EN/DE recordings and six joined previews, accepted their quality/pacing/tone/transitions, and authorized production and routine validation of the remaining 405 assets. Approval evidence and protected recording hashes are versioned in `female-approved-recordings.json` and the female audio manifest. Individual listening approval applies to those nine recordings; production authorization covers the rest without falsely attributing individual listening.

The 414-script catalog contains 138 scripts per language: 12 A acknowledgments, 120 B variants across 12 objectives, and six special/control utterances. `shared/mental/v1/content.json` maps exact scripts to the selected profile. The active manifest is `apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json`. The original `official-default` catalog/recordings remain archived byte-for-byte for comparison.

The official Chatterbox Multilingual V3 model/source remain pinned. Conditioning uses the approved LJ Speech reference SHA-256 `4d2bd83ff0f7fe33491b03193abdf623f1b4cc2d8103972b33638d3607d86dc5`, with `exaggeration=0.35`, `cfg_weight=0.0`, `temperature=0.8`. Reference provenance, public-domain evidence and settings are in `shared/mental/voices/female-calm-v1.json`. No pitch/rate shifting, substitute TTS model, paid inference or network inference is used; the upstream watermark is retained.

Batch production uses at most two resident offline workers, finite requests and per-clip deadlines. Existing recordings are hash/recipe-checked and never overwritten. Resident recipes seed after model initialization for reproducibility independent of worker assignment; the already approved one-shot recipes and bytes remain intact. Every new clip is checkpointed and validated. Resident workers are task-only; the live endpoint retains one bounded, cancellable subprocess.

```sh
python scripts/mental_audio_batch.py --profile female-calm-v1 --all --generate --resident-workers 2 --config /absolute/runtime/config-female-calm-v1.json --python /absolute/runtime/venv/bin/python
```

Set `ATTUNE_MENTAL_TTS_FEMALE_CONFIG` to that verified configuration for structured closing speech. `ATTUNE_MENTAL_TTS_CONFIG` remains the separate legacy/default configuration. The backend, same-origin proxy and client verify the requested profile and locale. The female reference/settings must match the approved manifest. Consent, parking/authentication, cancellation, mute, visibility, audio focus, deadlines, no-store responses and object disposal are retained.

[Approved representative recordings](listening-female-calm-v1/README.md) · [Original comparison](listening/README.md) · [Validation](validation.md)

## Conversation and session contract

Ordinary structured replies use local routing and prepared audio only, with zero conversational OpenAI calls or dynamic narration. One consent-gated completion analysis produces a personalized spoken summary; only that summary uses dynamic narration. The complete bounded transcript stays in browser memory, with saved summary/transcript/history access governed by the existing separate consents. No diagnostic or clinical efficacy claim is made.

The 12 B objectives cover focus, situation, emotion, impact, frequency, triggers, thoughts, behavior, prior resources, current needs, optional chosen steps and optional reflection. The flow specification defines prerequisites and positive/indecision paths. Already supplied, asked or skipped objectives are not repeated. Uncertainty proceeds through clarification and direction to listening; advice/action questions require explicit interest. A+B pairs use versioned compatibility rules and one language/profile. Formal Turkish and German wording is preserved.

The 39-turn and 100,000-character boundaries preserve the crossing user utterance and finish gracefully without another question, using a soft character threshold before the hard boundary. Crisis screening and existing vehicle/explicit controls take precedence. Full text analysis remains available when closing audio is muted, cancelled or reaches its finite deadline.

Interaction design draws on Rogers’ person-centered listening, SAMHSA TIP 35 OARS, Beck Institute’s situation/thought/emotion distinctions and WHO PM+ resource/needs concepts. The software does not implement psychotherapy or claim those methods’ efficacy. Engineering/editorial checks do not replace independent native-language or clinical evaluation.

## Classifier decision

The owner confirmed that the separate-task comparison is complete and the final decision is to retain the existing rule-based classifier. MiniLM/E5 provisioning, integration and further benchmarking are closed. No external-task measurements are invented or copied. Only the current classifier and relevant TR/EN/DE regression fixtures are retained; temporary evaluation output and candidate-model tooling are removed. Future classifier work should prioritize intent recognition while preserving crisis/consent/control precedence.
