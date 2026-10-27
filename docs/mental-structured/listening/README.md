# Representative voice samples — approval pending

These are the nine actual recordings from the pinned official Chatterbox Multilingual V3 worker and the existing `official-default` conditioning. None is approved. No mass production has run. Scripts, exact hashes, durations and measured production phases are in the versioned audio manifest; [index.json](index.json) identifies this review set.

| Language | A-V01 acknowledgment | B01-V01 opening focus | B02-V01 event emotion |
| --- | --- | --- | --- |
| TR | [Peki.](../../../apps/vehicle-app/public/audio/mental/v1/tr/official-default/A/A-V01.wav) | [Bugün ne hakkında konuşmak istersiniz?](../../../apps/vehicle-app/public/audio/mental/v1/tr/official-default/B01/B01-V01.wav) | [O anda nasıl hissettiniz?](../../../apps/vehicle-app/public/audio/mental/v1/tr/official-default/B02/B02-V01.wav) |
| EN | [Okay.](../../../apps/vehicle-app/public/audio/mental/v1/en/official-default/A/A-V01.wav) | [What would you like to talk about today?](../../../apps/vehicle-app/public/audio/mental/v1/en/official-default/B01/B01-V01.wav) | [How did you feel at that moment?](../../../apps/vehicle-app/public/audio/mental/v1/en/official-default/B02/B02-V01.wav) |
| DE | [In Ordnung.](../../../apps/vehicle-app/public/audio/mental/v1/de/official-default/A/A-V01.wav) | [Worüber möchten Sie heute sprechen?](../../../apps/vehicle-app/public/audio/mental/v1/de/official-default/B01/B01-V01.wav) | [Wie haben Sie sich in dem Moment gefühlt?](../../../apps/vehicle-app/public/audio/mental/v1/de/official-default/B02/B02-V01.wav) |

These previews concatenate the original PCM with the provisional 120 ms join; they use no additional synthesis or lossy encoding:

| Language | A + opening | A + emotion question |
| --- | --- | --- |
| TR | [Listen](tr-A-V01-B01-V01.wav) | [Listen](tr-A-V01-B02-V01.wav) |
| EN | [Listen](en-A-V01-B01-V01.wav) | [Listen](en-A-V01-B02-V01.wav) |
| DE | [Listen](de-A-V01-B01-V01.wav) | [Listen](de-A-V01-B02-V01.wav) |

Please assess pronunciation and language, voice identity across A/B and languages, warmth/neutrality, loudness, truncated words, artifacts, pause length, breath and intonation at each join. Automated PCM checks found zero clipped samples; they do not establish auditory quality. Approval must be explicit and recorded before mass production; fixing a rejected recording must preserve its original bytes and use a new version.
