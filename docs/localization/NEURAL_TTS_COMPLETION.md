# Zero-warning frontend and opt-in Chatterbox V3 integration

> Current results: [real V3 default-voice inference, source fingerprint verification and Cloud playback](DEFAULT_V3_COMPLETION.md). All unavailable-model/VCS-installer status and counts below describe the earlier pre-import checkpoint; they do not replace current runtime evidence. AAOS remains unverified.

2026-10-21. PR #5, `feature/localization-en-de-tr-20261020`, starting at `45d6b3778144cd1c7322314b16f5ee0d21f93cd5`. This report supersedes the browser-only dynamic speech architecture in FUNCTIONAL_COMPLETION.md. Historical Hearing/fixed-recording evidence remains applicable.

## Historical pre-import status

| Check | Result |
|---|---|
| Six original frontend warnings | PASS: stable handlers/current refs, no suppressions |
| Initial lint, typecheck, production build | PASS, zero frontend warnings |
| Initial affected Skin/Vision/Mental checks | PASS, 31 tests |
| Consolidated auth/config/process/proxy/client/locale/original-audio/observer checks | PASS, 87 focused tests and four subtests; explicit model/HTTP/audio fixtures |
| Chatterbox source identity and code license | PASS, official pinned source and MIT text |
| Exact V3 weight snapshot/hash/model license evidence | BLOCKED: official Hugging Face endpoint returned proxy `403 Forbidden` |
| Official default conditioning | Source behavior verified; required `conds.pt` is included in the new six-file hash manifest. External female reference requirement removed. Actual conditioning bytes remain unavailable. |
| Real model inference, TR/EN/DE speech samples and synthesis latency | NOT EXECUTED; unavailable weights/conditioning/runtime. No fixture is presented as neural output. |
| New Android neural transport/playback | NOT EXECUTED; explicit required observer scenario added |
| Final AAOS and merge | BLOCKED by neural runtime acceptance; no dispatch, merge or deployment |

Real production browser transport passed for TR/EN/DE using an explicitly labelled synthetic PCM tone, including cancellation before playback and during playback; one unchanged DE approved M4A passed the shared lifecycle. These are transport/output tests, not neural speech samples or synthesis latency measurements. The real browser check exposed and corrected NextURL loopback-host normalization in the same-origin guard.

Final focused/browser/build/CI receipts are retained in `/workspace/attune-neural-completion-20261021/`. Counts above describe distinct bounded runs, not an additive full-suite count. Initial failed fixture/type/catalog logs are retained alongside corrected results.

## Warning corrections

Skin uses its memoized guidance controller in the privacy effect's dependencies. Region navigation uses stable callbacks with functional selection updates and current result order. Vision's stage transition callback is stable, so the mute listener observes it without being repeatedly torn down. The header uses Next Image with explicit 20×20 geometry for the same decorative SVG. Mental's phase ref is updated synchronously by a stable setter, preserving cancellation during asynchronous summary completion; consent events call the latest action through the existing ref. No effect suppressions or lint rule changes were introduced.

The additional cross-tab review finding is corrected in the locale core and provider: all locale/API/audio consumers retain the assessment's language for the lifetime of local locks. Storage-driven language changes do not cancel active assessments or notify the provider until the last local lock releases. The latest external preference then applies without rewriting other tabs' settings, records or consent.

The related cross-tab speech-selection finding is also corrected. Engine and female voice identity are captured at the first local lock, before an utterance starts, and remain stable through that assessment. Pending remote settings become effective after unlock and refresh the selector. Online-provider permission is deliberately not frozen: a live revocation still cancels remote browser output. Microphone/service permission and motion gates are unchanged. Focused tests exercise actual generation/browser adapter functions under foreign-tab writes and verify revocation still works; all voice/output observations in these tests are explicitly synthetic fixtures.

## Model identity and licenses

Official [Resemble AI source](https://github.com/resemble-ai/chatterbox/tree/5de7a54aa4e5e2baadb0182dde554908b48b85c2), package version 0.1.7. [Code license](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/LICENSE): MIT, Copyright 2025 Resemble AI; unchanged notice in `third-party/CHATTERBOX_LICENSE.txt`.

The pinned `mtl_tts.py` exposes `t3_model='v3'` → `t3_mtl23ls_v3.safetensors`, with TR/EN/DE support. **Its default is V2**, so both `from_local` and the file manifest explicitly require V3. Weight repository: [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox). No exact weight revision/hash or weight-license verification is claimed from the source code license alone.

`requirements-mental-tts.txt` is an optional isolated environment, never part of app startup, normal CI or unit installation. Official constraints require Python ≥3.10 (use 3.11), torch/torchaudio 2.6.0, transformers 5.2.0 and safetensors 0.5.3. Runtime checks enforce these versions and the installed VCS source commit. The current application venv is incompatible/missing these packages; it was preserved. Cloud currently has CPU only, approximately 15 GiB available RAM and 6 GiB free disk. CPU execution is supported by upstream, but sufficient end-to-end resources/latency have not been proven. No GPU or paid compute was provisioned.

## Runtime boundaries

Dynamic ordinary Mental reply → same-origin `/api/mental-neural-speech` → bearer-authenticated loopback `/api/mental/neural-speech` → bounded offline worker → validated PCM16 mono 24 kHz WAV → existing application output lifecycle.

The server-held `ATTUNE_MENTAL_TTS_TOKEN` must be at least 32 characters and identical in Next/server and API. Never prefix it with `NEXT_PUBLIC_`, put it in a bundle, commit it or include it in artifacts. The proxy rejects missing/foreign Origin, oversized/non-JSON requests, invalid consent/language and non-loopback backend URLs. Existing CORS origins/headers are unchanged. This is service authentication, not a new user identity system. Backend also requires authenticated-driver state and verified Park.

Inference is off until `ATTUNE_MENTAL_TTS_CONFIG` exists. No model downloads, ML imports or model construction happen at API startup. Each request runs a separate, single-concurrency subprocess; loading cost is included in its 90-second deadline. Concurrent requests return 429 rather than building an unbounded queue. Text travels over stdin, audio over stdout; no response text/audio cache or temporary health files are created. Worker logging is suppressed; provider credentials are removed from its environment. Offline flags and disabled Python socket connections prohibit implicit network fetches. The tokenizer's auxiliary Cangjie mapping is supplied from the hash-verified local bundle. Upstream audio watermarking remains enabled. Subprocess loading is deliberately bounded; low-latency suitability remains unverified.

The manifest now verifies all six official model files, including required internal `conds.pt`, and model-repository license evidence. Generation explicitly selects V3 with `audio_prompt_path` omitted. No external reference or female-profile requirement remains. The checked-in example is intentionally **unconfigured** and cannot produce output. Exact official model metadata and bytes must first be verified; source code license evidence alone does not establish model-file integrity.

Motion, lost driver state, disconnect, deadline or cancellation kills the inference child and discards output. Frontend also gates language, mute, visibility, permissions/session identity, navigation and Hearing focus. It validates source/locale/MIME/size before creating an audio element. Native `playing` plus completed `ended` are required; generated audio uses the same cleanup/meter/playback lifecycle as fixed files. No overlapping fixed guidance is allowed during generation/playback. Existing recordings/hashes and Hearing banks/scoring are unchanged.

Chatterbox is the new ordinary dynamic default. Browser/system speech remains an **explicitly selected** alternative under Voice options → Dynamic speech engine, with its existing female identity and online-consent rules. There is no automatic provider switch after failure. The separate nonpersonal preview still tests browser speech only and remains Cockpit-only. Emergency classification/display and the local 112 route run before provider/context work; optional neural generation never receives crisis text or delays its emergency response. Approved fixed emergency clips can still play; if unavailable, the visible emergency notice remains.

## Reproducible completion in an accessible free Cloud runtime

The verified asset import and real speech generation have since completed. See
[DEFAULT_V3_COMPLETION.md](DEFAULT_V3_COMPLETION.md) for the measured results,
offline directory installation and actual-source fingerprint checks. The received
archive is an asset bundle, not a wheelhouse; do not repeat its transfer or model
verification without evidence of corruption. AAOS, merge and deployment were not
run in this recovery task.
