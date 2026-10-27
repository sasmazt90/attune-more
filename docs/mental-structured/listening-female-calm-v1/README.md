# Female voice review — approval pending

This separate review set uses the existing pinned official Chatterbox Multilingual V3 model, with one public-domain LJ Speech reference (`LJ001-0001`, 9.655 seconds). The [profile](../../../shared/mental/voices/female-calm-v1.json) pins the recording hash and synthesis settings. [License evidence](../female-reference-license.md) identifies the source corpus and its public-domain status. This is a generated review voice, with no endorsement by the reference speaker.

Exactly nine speech clips and six lossless joined previews are provided. The [official-default recordings](../listening/README.md) remain unchanged for comparison. No samples are approved; no mass production, merge or deployment is authorized.

| Language | A acknowledgment | B01 opening focus | B02 event emotion |
| --- | --- | --- | --- |
| TR | [A-V01](../../../apps/vehicle-app/public/audio/mental/v1/tr/female-calm-v1/A/A-V01.wav) | [B01-V01](../../../apps/vehicle-app/public/audio/mental/v1/tr/female-calm-v1/B01/B01-V01.wav) | [B02-V01](../../../apps/vehicle-app/public/audio/mental/v1/tr/female-calm-v1/B02/B02-V01.wav) |
| EN | [A-V01](../../../apps/vehicle-app/public/audio/mental/v1/en/female-calm-v1/A/A-V01.wav) | [B01-V01](../../../apps/vehicle-app/public/audio/mental/v1/en/female-calm-v1/B01/B01-V01.wav) | [B02-V01](../../../apps/vehicle-app/public/audio/mental/v1/en/female-calm-v1/B02/B02-V01.wav) |
| DE | [A-V01](../../../apps/vehicle-app/public/audio/mental/v1/de/female-calm-v1/A/A-V01.wav) | [B01-V01](../../../apps/vehicle-app/public/audio/mental/v1/de/female-calm-v1/B01/B01-V01.wav) | [B02-V01](../../../apps/vehicle-app/public/audio/mental/v1/de/female-calm-v1/B02/B02-V01.wav) |

The six previews concatenate those PCM bytes with the existing provisional 120 ms join; they create no additional speech.

| Language | A + opening focus | A + event emotion |
| --- | --- | --- | --- |
| TR | [Listen](tr-A-V01-B01-V01.wav) | [Listen](tr-A-V01-B02-V01.wav) |
| EN | [Listen](en-A-V01-B01-V01.wav) | [Listen](en-A-V01-B02-V01.wav) |
| DE | [Listen](de-A-V01-B01-V01.wav) | [Listen](de-A-V01-B02-V01.wav) |

## Conditioning and style

The pinned upstream `prepare_conditionals` uses the reference waveform for voice-encoder embedding, speech prompt tokens and acoustic conditioning. Each clip uses the exact same 425,830-byte reference (SHA-256 `4d2bd83ff0f7fe33491b03193abdf623f1b4cc2d8103972b33638d3607d86dc5`). It supplies `audio_prompt_path` to upstream `generate`; it does not modify the model or upstream source.

The intended style is warm, calm, attentive and professionally empathetic. `exaggeration=0.35`, `cfg_weight=0.0`, `temperature=0.8` reduce expression and use upstream’s suggested mitigation for reference-language accent transfer. Upstream associates lower CFG with more deliberate pacing, but has no gender, explicit speech-rate or breathing control. There is no pitch shift, time stretching, artificial breath insertion or post-processing beyond PCM16 encoding; the upstream watermark is retained. Perceived female presentation, warmth, speed, breathing and intonation must be assessed by listening.

All sample texts are identical to the original comparison set. Turkish uses formal verb forms (`istersiniz`, `hissettiniz`); German uses `Sie`. The English reference can influence TR/DE accent even at zero CFG. Please assess pronunciation and naturalness in each language.

## Measured checks

All nine recordings are mono 24 kHz PCM16 with zero clipped samples. Generation took 532.934 seconds in total, with peak worker RSS 6,906,356 KiB. All 18 original comparison files (nine clips, six previews, manifest, index and listening sheet) retain their original hashes. B questions are 8–45% longer than their default counterparts; this is a comparison against the old recordings, not evidence of a normal conversational rate. The acknowledgment durations vary.

## Verification and remaining limits

The [measurements](measurements.json) report exact durations versus the original recordings and descriptive upstream-encoder cosines for the reference, samples and cross-language question pairs. The [index](index.json) and [manifest](../../../apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json) record scripts, hashes, metrics and recipes. An uncalibrated cosine, especially from the generator’s own encoder on short clips, is not independent speaker verification. A-V01 acknowledgments are too short to support a reliable identity judgment. **Cross-language speaker consistency is not verified; native-language listening and owner approval are pending.**

The dynamic closing API accepts the profile ID and refuses a mismatched reference/settings or absent approval. An omitted profile cannot bypass the female approval gate. Tests verify the same conditioning adapter and hash contract for TR/EN/DE. The current frontend selection remains `official-default`; this voice has not been activated. No dynamic closing audio was synthesized because this authorization covers only nine representative clips. Its perceived consistency on a longer personalized summary therefore remains untested. After approval, activation must bind both prepared speech and closing to this profile, followed by an approved closing listening test.

The female CLI rejects `--all` even if a manifest is later marked approved. Full production requires a subsequent authorized change. Existing consent, crisis, driving, storage, cancellation, mute and audio-disposal protections remain in place.

To reproduce locally, download the reference from the immutable URL in the profile, verify its SHA-256, copy the existing runtime config into the same directory, set `conditioning` to `female-calm-v1`, and add `referenceAudio: {path, sha256}` using a path inside that config directory. Use the isolated runtime, unchanged pinned model/source and existing offline segmenter cache. The reference is a small public-domain test fixture in Coqui’s source repository; no replacement model or network-restriction workaround is involved.

```sh
python scripts/mental_audio_batch.py --profile female-calm-v1 --generate --config /absolute/runtime/config-female-calm-v1.json --python /absolute/runtime/venv/bin/python
python scripts/mental_audio_review_bundle.py --profile female-calm-v1
/absolute/runtime/venv/bin/python scripts/mental_voice_review.py --config /absolute/runtime/config-female-calm-v1.json
```
