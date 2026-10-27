# Follow-up review for PR #12

## Chatterbox provisioning and representative recordings

The existing owner archive `Chatterbox-Multilingual-V3-offline-20261021-v1.zip` was retrieved through the authenticated Drive connector as 98 parts. Every part, the reconstructed 3,283,572,066-byte archive (`5e98c442627ad78ce22a9bff151b0badd2343f1392b590b42889a0beb679f3fc`), and all 117 members matched the existing repository policy. No mirror or replacement model was used. The isolated runtime installed with its existing hashed requirements and passed `pip check`.

The official source remains `5de7a54aa4e5e2baadb0182dde554908b48b85c2`, Chatterbox 0.1.7, model revision `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`, V3 model file, Torch/Torchaudio 2.6.0 CPU, Transformers 5.2.0 and Safetensors 0.5.3. Conditioning remains `official-default`, SHA-256 `6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e`. The worker verified model/source bytes and disabled network during inference. Watermark and segmenter assets came from the verified bundle.

**Nine representative clips are generated, zero approved.** A-V01, B01-V01 and B02-V01 in TR/EN/DE use the existing worker and deterministic recipe seeds. The manifest records exact scripts, actual duration, hashes, PCM metrics and measured worker phases. Total subprocess wall time was 440.297 seconds; individual clips took 39.985–62.355 seconds, including verification, imports, model loading, inference and encoding. Maximum observed worker peak RSS was 6,945,188 KiB. All nine clips are mono 24 kHz PCM16 WAV; automated inspection counted zero clipped samples. These observations do not establish pronunciation, loudness consistency, speaker similarity or natural joins.

The [listening sheet](listening/README.md) links all nine recordings and six lossless A+B previews, using the provisional 120 ms join. Previews reuse the same recorded PCM and perform no further synthesis. No source recording was overwritten. The remaining 405 scripts are ungenerated. Sample approval, join approval and full-library approval remain absent; `--all` stays blocked. Owner/native listening is required before any mass production.

## Separate female voice comparison

The [female profile listening sheet](listening-female-calm-v1/README.md) provides a second nine-clip/six-preview set from one hash-pinned public-domain reference, using the same official model and source. The original default files and manifest are byte-preserved by the comparison baseline. This profile is review-only and does not change the active application selection. Cross-language perceptual consistency, warmth, breathing and natural pacing await listening; a dynamic closing was not synthesized under the nine-clip cap. Its API contract requires the same profile/reference/settings and explicit sample approval, including when a request omits a profile. Female mass production remains blocked.

## Expanded classifier evaluation

[`tests/fixtures/mental-routing-v2.json`](../../tests/fixtures/mental-routing-v2.json) contains 180 new synthetic utterances in 60 scenario groups, with parallel TR/EN/DE versions and explicit dialogue context. It includes colloquial language, ASR errors, quoted/negated/complex emotions, corrections, short answers, uncertainty, lifecycle controls, topic changes, advice preferences and crisis precedence. It is authored evaluation material, **not real-user transcripts or independent expert validation**. All translations of a scenario stay together: 36 training, 36 development and 108 test utterances. Its SHA-256 is `a172b34ed42bd9788a7678503f527627a5556d85c6f6b015e699693824fb91f3`; the corpus was fixed before semantic-model comparison. Production classification rules were not fitted to these test labels.

Measured rule baseline on the 108 test utterances:

| Metric | Result |
| --- | --- |
| Objective precision / recall / F1 | 88.51% / 69.37% / 77.78% |
| Exact objective match | 77.78% |
| Intent accuracy | 61.11% |
| Joint objective + intent accuracy | 57.41% |
| False positive / missed objectives | 10 / 34 |
| Median / p95 classification + shared-control time | 0.643 / 0.972 ms |
| Whole-process peak RSS | 38,896 KiB |

Per-input results, including failures and per-language objective scores, are in [benchmark-rules-v2.json](benchmark-rules-v2.json). The latency is warmed CPU execution, not recognition, network or playback latency; process RSS is not isolated model memory. The joint result is substantially weaker than the original small probe set suggested. The rule classifier remains a development baseline behind the release gate.

Official MiniLM (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0) and multilingual E5 small (`intfloat/multilingual-e5-small`, MIT) were inspected through the connected Hugging Face plugin. Both are approximately 117.7M-parameter multilingual embedding models. The prepared local runner uses verified Safetensors snapshots, two CPU threads, mean pooling/normalization, the E5 query prefix, and 128-token benchmark inputs. Threshold selection uses development data only. It reports model initialization, measured routing quality, latency and process memory, and never calls a hosted inference API. This benchmark adapter is **not enabled in production** and does not establish long-input coverage.

**A measured MiniLM/E5 comparison and model selection remain blocked.** After the owner published the allowlist update, the running Cloud environment still reported bound/observed spec revision 1, an empty custom-host allowlist, and an enforced old policy. Both official model download retries failed at `huggingface.co` before redirects; no additional blocked download hostname was observed. Connecting/authenticating the Hugging Face plugin did not update executor egress. No remote paid job, inference service, mirror, proxy bypass or unverified substitute was used.

Use a restarted/recreated Cloud environment bound to the published policy; if the current chat cannot refresh its environment, a fresh Cloud task is required. The existing PR branch contains the corpus, official downloader and runner:

```sh
python scripts/provision_mental_semantic_models.py --root /absolute/local/model-cache
python scripts/mental_classifier_benchmark.py --model rules --output /tmp/rules.json
python scripts/mental_classifier_benchmark.py --model semantic --model-path /absolute/local/model-cache/minilm/IMMUTABLE_REVISION --output /tmp/minilm.json
python scripts/mental_classifier_benchmark.py --model semantic --model-path /absolute/local/model-cache/e5/IMMUTABLE_REVISION --output /tmp/e5.json
```

The downloader uses the existing proxy/policy, official Hub metadata, immutable revisions, Git-blob/LFS integrity checks and local manifests; it refuses a mismatched existing file. Run semantic candidates in an isolated environment with Torch, Transformers, NumPy and the official tokenizers; do not change the voice runtime to benchmark them. Complete both comparisons and review errors by language before selecting or integrating a model. No best semantic solution is claimed without those measurements.

## Question objectives and conversation flow

All 360 B scripts were reviewed against their stable objectives and temporal subtypes; all 36 global A scripts were checked for unsupported interpretation. Automated checks cover counts, unique variants, stable language-independent IDs/subtypes, one question per B, manifest exact-script alignment and compatible acknowledgment IDs. This is an engineering/editorial review, not clinical or independent native-language approval.

| Node | Objective and review outcome |
| --- | --- |
| B01 | User-selected focus. Already supplied focus can fulfill it; continuation invitations remain excluded at opening. One awkward Turkish variant was rewritten. |
| B02 | Emotion at the described event. Past-event wording is consistent across variants; a tautological Turkish variant was refined. The classifier still lacks validated temporal/coreference resolution. |
| B03 | Description of the situation. Assistant-centered clarification wording was replaced with user-led wording in TR/EN/DE. |
| B04 | Antecedents/triggers of a reported feeling. Now requires B02 fulfillment, avoiding reference to an unreported feeling. |
| B05 | Thoughts at the described event. Now requires B03 fulfillment, avoiding an assumed situation. |
| B06 | Recent frequency of the reported feeling. All TR/EN/DE variants now name the feeling explicitly, avoiding ambiguity with event frequency. Requires B02. |
| B07 | User-reported daily impact, with no severity scoring. Completed/previously supplied objectives remain excluded. |
| B08 | Usual behavioral response to a feeling. Now requires B02; it does not assert that the behavior is harmful. |
| B09 | Previously helpful coping/resources. Past helpfulness is consistent; the questions do not prescribe a strategy. |
| B10 | Current needs/support. Deficit-assuming wording was replaced with neutral wishes/needs wording in all three languages. |
| B11 | Optional user-chosen small step. Still requires explicit interest in steps/advice; listening-only mode does not enter action planning. |
| B12 | Optional user-defined takeaway. Continuation acknowledgments remain excluded at closure; explicit finish never requires reflection. |

Positive wellbeing uses the shorter needs/optional-takeaway path. Indecision now has a focused situation/thoughts/needs path instead of automatically exploring emotional triggers and frequency. Repeated uncertainty progresses C01 → C02 → listening and cannot restart a clarification loop. Repeated listening turns select varied neutral global A clips without asking another question. Pausing during clarification preserves the original objective. Repetition history, same-speaker mapping and safety/control precedence remain in effect.

Listening-based A+B compatibility and native pronunciation remain unapproved. The revised draft variants were ungenerated and unapproved; none of the nine representative scripts or recorded bytes was changed.

## Session limits and information preservation

The previous frontend guard discarded the utterance that crossed 39 turns/100,000 characters. It now preserves that utterance verbatim in the transcript and analyzes it directly without an extra ordinary generation request. The usual path asks for a prepared F01 closure on turn 39, or when an accepted turn reaches the 94,000-character soft threshold, rather than asking another question. The boundary fallback remains below the 200-message/120,000-character analysis contract for bounded normal turns.

Executed production-closure tests cover the 39th turn, an extra utterance at turn 39, crossing 100,000 characters, the soft close, preserved prior messages, final-user-only analysis, a pending turn at the boundary, crisis priority, duplicate finish and consent withdrawal. They assert one analysis/closing on the successful path and no late visible result/audio after withdrawal. These are mocked-service lifecycle tests, not paid analysis or physical microphone/audio tests.

## Remaining release blockers

1. Explicit owner listening approval of the nine representative clips and six joins; pronunciation/voice/prosody/level acceptance is pending.
2. Active Cloud egress for official semantic-model downloads, then measured MiniLM/E5 comparison, selection and broader multi-turn/native-language evaluation. The current rule baseline is inadequate for production acceptance.
3. Independent native-language/methodological review of the full draft catalog, then approved mass audio production and full compatibility listening review.
4. Physical browser/vehicle and end-to-end voice usability acceptance. Existing technical safety/consent/storage/audio regressions remain required; no merge or deployment is authorized.
