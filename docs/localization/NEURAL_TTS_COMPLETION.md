# Zero-warning frontend and opt-in Chatterbox V3 integration

2026-10-21. PR #5, `feature/localization-en-de-tr-20261020`, starting at `45d6b3778144cd1c7322314b16f5ee0d21f93cd5`. This report supersedes the browser-only dynamic speech architecture in FUNCTIONAL_COMPLETION.md. Historical Hearing/fixed-recording evidence remains applicable.

## Actual status

| Check | Result |
|---|---|
| Six original frontend warnings | PASS: stable handlers/current refs, no suppressions |
| Initial lint, typecheck, production build | PASS, zero frontend warnings |
| Initial affected Skin/Vision/Mental checks | PASS, 31 tests |
| Consolidated auth/config/process/proxy/client/locale/original-audio/observer checks | PASS, 86 focused tests and four subtests; explicit model/HTTP/audio fixtures |
| Chatterbox source identity and code license | PASS, official pinned source and MIT text |
| Exact V3 weight snapshot/hash/model license evidence | BLOCKED: official Hugging Face endpoint returned proxy `403 Forbidden` |
| Approved natural female reference profiles | BLOCKED: no verified reference recording/profile established. Owner authorized autonomous selection; no further voice-selection approval is required. Official VCTK corpus page also returned proxy `403 Forbidden`; upstream source tree contains no reference WAV/MP3. No rights are inferred from Clipchamp approval. |
| Real model inference, voice identity/naturalness, TR/EN/DE speech samples and synthesis latency | NOT EXECUTED; unavailable weights/profiles/runtime. No fixture is presented as neural output. |
| New Android neural transport/playback | NOT EXECUTED; explicit required observer scenario added |
| Final AAOS and merge | BLOCKED by neural runtime acceptance; no dispatch, merge or deployment |

Real production browser transport passed for TR/EN/DE using an explicitly labelled synthetic PCM tone, including cancellation before playback and during playback; one unchanged DE approved M4A passed the shared lifecycle. These are transport/output tests, not neural speech samples or synthesis latency measurements. The real browser check exposed and corrected NextURL loopback-host normalization in the same-origin guard.

Final focused/browser/build/CI receipts are retained in `/workspace/attune-neural-completion-20261021/`. Counts above describe distinct bounded runs, not an additive full-suite count. Initial failed fixture/type/catalog logs are retained alongside corrected results.

## Warning corrections

Skin uses its memoized guidance controller in the privacy effect's dependencies. Region navigation uses stable callbacks with functional selection updates and current result order. Vision's stage transition callback is stable, so the mute listener observes it without being repeatedly torn down. The header uses Next Image with explicit 20×20 geometry for the same decorative SVG. Mental's phase ref is updated synchronously by a stable setter, preserving cancellation during asynchronous summary completion; consent events call the latest action through the existing ref. No effect suppressions or lint rule changes were introduced.

The additional cross-tab review finding is corrected in the locale core and provider: all locale/API/audio consumers retain the assessment's language for the lifetime of local locks. Storage-driven language changes do not cancel active assessments or notify the provider until the last local lock releases. The latest external preference then applies without rewriting other tabs' settings, records or consent.

## Model identity and licenses

Official [Resemble AI source](https://github.com/resemble-ai/chatterbox/tree/5de7a54aa4e5e2baadb0182dde554908b48b85c2), package version 0.1.7. [Code license](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/LICENSE): MIT, Copyright 2025 Resemble AI; unchanged notice in `third-party/CHATTERBOX_LICENSE.txt`.

The pinned `mtl_tts.py` exposes `t3_model='v3'` → `t3_mtl23ls_v3.safetensors`, with TR/EN/DE support. **Its default is V2**, so both `from_local` and the file manifest explicitly require V3. Weight repository: [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox). No exact weight revision/hash or weight-license verification is claimed from the source code license alone.

`requirements-mental-tts.txt` is an optional isolated environment, never part of app startup, normal CI or unit installation. Official constraints require Python ≥3.10 (use 3.11), torch/torchaudio 2.6.0, transformers 5.2.0 and safetensors 0.5.3. Runtime checks enforce these versions and the installed VCS source commit. The current application venv is incompatible/missing these packages; it was preserved. Cloud currently has CPU only, approximately 15 GiB available RAM and 6 GiB free disk. CPU execution is supported by upstream, but sufficient end-to-end resources/latency have not been proven. No GPU or paid compute was provisioned.

## Runtime boundaries

Dynamic ordinary Mental reply → same-origin `/api/mental-neural-speech` → bearer-authenticated loopback `/api/mental/neural-speech` → bounded offline worker → validated PCM16 mono 24 kHz WAV → existing application output lifecycle.

The server-held `ATTUNE_MENTAL_TTS_TOKEN` must be at least 32 characters and identical in Next/server and API. Never prefix it with `NEXT_PUBLIC_`, put it in a bundle, commit it or include it in artifacts. The proxy rejects missing/foreign Origin, oversized/non-JSON requests, invalid consent/language and non-loopback backend URLs. Existing CORS origins/headers are unchanged. This is service authentication, not a new user identity system. Backend also requires authenticated-driver state and verified Park.

Inference is off until `ATTUNE_MENTAL_TTS_CONFIG` exists. No model downloads, ML imports or model construction happen at API startup. Each request runs a separate, single-concurrency subprocess; loading cost is included in its 90-second deadline. Concurrent requests return 429 rather than building an unbounded queue. Text travels over stdin, audio over stdout; no response text/audio cache or temporary health files are created. Worker logging is suppressed; provider credentials are removed from its environment. Offline flags and disabled Python socket connections prohibit implicit network fetches. The tokenizer's auxiliary Cangjie mapping is supplied from the hash-verified local bundle. Upstream audio watermarking remains enabled. Subprocess loading is deliberately bounded; low-latency suitability remains unverified.

The manifest verifies the exact model files, model-repository license evidence, female profile metadata, explicit cloning rights evidence and per-language reference hashes. Builtin `conds.pt` is prohibited because its gender/reference authorization was not established. References must be mono PCM16 WAV, 3–15 seconds. The checked-in example is intentionally **unconfigured** and cannot produce output. Attestation fields do not themselves establish rights: an operator must first verify the actual license/consent evidence covering commercial synthetic voice generation and identity use.

Motion, lost driver state, disconnect, deadline or cancellation kills the inference child and discards output. Frontend also gates language, mute, visibility, permissions/session identity, navigation and Hearing focus. It validates source/locale/MIME/size before creating an audio element. Native `playing` plus completed `ended` are required; generated audio uses the same cleanup/meter/playback lifecycle as fixed files. No overlapping fixed guidance is allowed during generation/playback. Existing recordings/hashes and Hearing banks/scoring are unchanged.

Chatterbox is the new ordinary dynamic default. Browser/system speech remains an **explicitly selected** alternative under Voice options → Dynamic speech engine, with its existing female identity and online-consent rules. There is no automatic provider switch after failure. The separate nonpersonal preview still tests browser speech only and remains Cockpit-only. Emergency classification/display and the local 112 route run before provider/context work; optional neural generation never receives crisis text or delays its emergency response. Approved fixed emergency clips can still play; if unavailable, the visible emergency notice remains.

## Reproducible completion in an accessible free Cloud runtime

1. Do not alter the main application venv. Create a separate Python 3.11 environment outside tracked paths and install `services/core-api/requirements-mental-tts.txt` only when enough disk is available. Resolve/retain transitive package versions in a runtime receipt; no installation was performed here.
2. In an environment permitted to access the official Hugging Face repository, verify its V3 revision and model license/card. Download only `t3_mtl23ls_v3.safetensors`, `ve.pt`, `s3gen.pt`, `grapheme_mtl_merged_expanded_v1.json`, `Cangjie5_TC.json` and exact license evidence at that revision. Compute SHA-256 independently. Do not obtain a model via an unofficial mirror to evade a network restriction.
3. Select female references with documented commercial cloning/generation and identity-use rights. Preserve original source/license/consent and hashes; prepare separate derived mono PCM16 3–15s references. Never use the approved Clipchamp files without explicit cloning rights. Complete the config template in a private runtime directory, with all referenced files inside that directory. User authorization to select voices is not evidence of a third party's rights.
4. Run `python scripts/mental_tts/preflight.py --config /ABS/runtime/config.json --output /ABS/preflight.json` using the isolated environment. It validates dependencies/files/rights evidence without model loading or inference. Exit 69 means BLOCKED.
5. Set `ATTUNE_MENTAL_TTS_PYTHON=/ABS/isolated/bin/python`; run `python scripts/mental_tts/probe.py --config /ABS/runtime/config.json --output /ABS/NEW-evidence-directory`. This runs exactly three nonpersonal examples, reports actual synthesis latency/output hashes and never claims browser playback/naturalness from successful generation alone.
6. Verify those actual outputs in browser and confirm language, female voice/naturalness, complete playback and cancellation. Start the existing API and web app with the same randomly generated server token, the config path and worker Python. Set `ATTUNE_MENTAL_TTS_BACKEND_URL=http://127.0.0.1:PORT` only on the Next server. Use nonpersonal generated AI replies; capture no microphone or health data for this output check.
7. Only after required inference/playback acceptance and final CI/review pass, prepare one owner UI AAOS run on the new final SHA. Existing Attune browser audit routing, standard Ubuntu, 40 min, 50 MiB incl ZIP, one-day retention/no retries/paid services remain unchanged. The new `mental-neural-audio` observer attempts all three languages and reports unavailable runtime as BLOCKED; no silent skip. The ordinary workflow currently provisions no neural weights/profiles/runtime/token, so **do not launch it expecting this new gate to pass**. Provide verified assets/config in the same disposable free runtime first; do not commit weights/secrets/references or upload them to a paid service.
8. Await actual AAOS evidence and review/merge requirements. Keep PR #5 unmerged while a required acceptance remains BLOCKED. No deployment is authorized.
