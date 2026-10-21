# Chatterbox Multilingual V3: real Cloud speech and runtime recovery

2026-10-21. PR #5, `feature/localization-en-de-tr-20261020`. This report supersedes
external female-reference requirements and the earlier unavailable-model status.
No external reference or voice cloning is used. AAOS, merge and deployment are
outside this recovery task.

## Verified assets and implementation

- Official Chatterbox source: `5de7a54aa4e5e2baadb0182dde554908b48b85c2`, version 0.1.7.
- Official model revision: `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`.
- Explicit checkpoint: `t3_mtl23ls_v3.safetensors`. The upstream default is V2, so
  the worker calls `from_local(..., t3_model='v3')` explicitly.
- All 98 transferred parts passed filename, sequence, size and SHA-256 checks.
  The reconstructed ZIP is 3,283,572,066 bytes, SHA-256
  `5e98c442627ad78ce22a9bff151b0badd2343f1392b590b42889a0beb679f3fc`.
  All 117 manifest-listed files passed size and SHA-256 verification.
- All six official model files, including internal `conds.pt`, remain outside Git
  in `/workspace/attune-tts-runtime/bundle-20261021-v1`. No V2 substitution, other
  TTS engine, external reference recording or prerecorded synthesis substitute.
- The original tokenizer cache layout is preserved. The included segmenter ZIP
  and its extracted features/weights are in a dedicated PKUSEG cache; all three
  Perth watermark assets are present and verified. Watermarking remains enabled.
- Authenticated official Hugging Face repository metadata declares MIT. It is
  recorded explicitly as repository-level evidence, separately from the pinned
  snapshot's file hashes. It is not labelled a downloaded snapshot README or
  inferred from the source-code license. Existing snapshot LICENSE/README
  evidence remains supported. No blanket commercial/clinical clearance is claimed.

## Recovery and pinned source installation

The existing managed Linux Cloud runtime reconnected without a restart. Inspection
found no remaining matching runaway installer/Git processes. No unrelated process,
Windows application or user record was touched.

The interrupted `pip install git+file://...` repeatedly spawned filtered local Git
clones. Its log is retained. The exact cause of the lost executor connection was
not established. Recovery used the already available official source directory
and already installed dependencies, with no Git or dependency resolution:

```bash
/workspace/attune-tts-runtime/venv/bin/python -m pip install \
  --no-index --no-deps --no-build-isolation \
  /workspace/attune-tts-runtime/chatterbox-source
```

The installed 50 Python source files match the approved immutable upstream tree.
`shared/localization/chatterbox-v3-source.json` records their hashes. Runtime and
preflight verify actual package version, exact Python file set, every source hash
and path containment. Edited/missing/extra source and wrong versions fail closed.
This supports an offline wheel/directory installation without inventing VCS
metadata or using Git to install the package. No ML import occurs at API startup.

The optional runtime is isolated from the main application venv. Verified versions:
Python 3.11, torch/torchaudio 2.6.0+cpu, transformers 5.2.0, safetensors 0.5.3,
s3tokenizer 0.3.0, spacy-pkuseg 1.0.1, and official Perth 1.1.0 at
`ff1c8ac55a976971245cdd53c18d6131ca00d993`. `pip check` passes.
The received archive contains model assets/source provenance, not a wheelhouse;
package dependencies were installed separately from authorized official sources.
An older uncommitted bundle-builder prototype using the failed local Git route
was preserved outside the repository in the Cloud recovery evidence directory.

Runtime settings for this private Cloud installation:

```text
ATTUNE_MENTAL_TTS_PYTHON=/workspace/attune-tts-runtime/venv/bin/python
ATTUNE_MENTAL_TTS_CONFIG=/workspace/attune-tts-runtime/config.json
PKUSEG_HOME=/workspace/attune-tts-runtime/pkuseg-cache
HF_HOME=/workspace/attune-tts-runtime/hf-cache
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

The shared server token is ephemeral/server-only, never a public variable or
artifact. The existing same-origin proxy and authenticated loopback backend remain.
Worker sockets are disabled, and model loading uses only the verified local files.
Do not repeat transfers/reconstruction or model verification absent corruption.

## Actual inference and playback

The official V3 model loaded on CPU in 10.12 seconds with `conds.pt` present.
`generate(text, language_id=...)` was called without `audio_prompt_path` for the
owner's exact three nonpersonal examples. Real PCM16 mono 24 kHz WAVs were created
and independently decoded:

| Language | Audio duration | Inference time, loaded model | SHA-256 |
|---|---:|---:|---|
| TR | 7.32 s | 42.67 s | `1c9d38e03e605dbe12158bd21a8d9ca08b7453220671a8fca38f44cc203d5143` |
| EN | 5.12 s | 24.72 s | `51281292597460644fe7396cd448009060162c2ae1a5269988f8ac23ac79842c` |
| DE | 5.76 s | 27.52 s | `04fa0b21a22cd96958c4e37646fe750fbfdaf66256b876a04ba24ee04aea5c2d` |

Samples and decoding receipt:
`/workspace/attune-v3-recovery-20261021/neural-samples/`.
No human listening, exact spoken-content/pronunciation, physical speaker,
microphone, vehicle or clinical acceptance is inferred from these results.

The actual production proxy, backend and inference worker also generated fresh
TR/EN/DE responses and played them through the existing application audio path in
Cloud Chromium. All returned HTTP 200, observed native playback and completed
with the source cleared. Total request-plus-playback times were TR 63.85 s,
EN 46.34 s and DE 50.06 s, within the existing 90-second backend/95-second frontend
deadlines. These are measured CPU results for three finite examples, not a
low-latency or arbitrary-length performance guarantee.

Actual newly generated audio passed mute, abort, language-change and session-change
interruption checks, with playback stopped and sources released. Backend consent
denial returned 403 and isolated DEMO moving-state denial returned 409. Fresh
browser storage and a dedicated data directory were used; capture attempts and
unexpected page errors were zero. The first harness switched language and started
a request before the page's locale cleanup completed; waiting for the locale
transition resolved this harness race. The successful TR check was reused;
only EN/DE were resumed. Original diagnostic/failure evidence is retained.

## Real in-flight cancellation correction

The final live check found that stopping browser playback did not promptly stop
an inference child. The same failure reproduced with a direct backend HTTP client,
isolating it from the proxy. Starlette's `Request.is_disconnected()` uses a
pre-cancelled receive probe; with the HTTP middleware's AnyIO stream that probe
missed the real disconnect. The endpoint now observes disconnects with one pending
ASGI receive task after validated JSON consumption. The existing generation loop
sees the event, kills/reaps the child and discards output; the watcher itself is
cancelled and reaped on success, error or handler cancellation. Auth, consent,
Park/driver checks and timeouts are unchanged. Receive errors fail closed.

Actual direct-backend and browser-through-proxy cancellation both now stop the
observed real worker. The browser reports no playback and no capture. Three new
regressions use real bounded sleeper subprocesses and explicitly labelled ASGI
fixtures to verify disconnect, receive failure and handler cancellation cleanup.
They are not model-inference evidence. Original live failures, the fix and the
passing live observations are retained in the Cloud recovery directory.

## Safety, reviews and verification

The existing auth/proxy/offline worker, single concurrency, deadlines, mute,
audio focus, session/language/visibility cancellation, consent and Park/driver
restrictions are preserved. The two outstanding review findings are corrected:
“I no longer want to live” reaches the existing emergency route in both shared
policy consumers; the new speech processor requires explicit `speech-output-v2`
consent. Old consent documents are not migrated or rewritten during reads.

283 focused source-integrity, backend/proxy/client, consent, crisis, localization,
original-audio, Hearing and Android host checks pass. All 194 original recordings
were rehashed unchanged. Existing Hearing scoring and health modules are unchanged.
After the disconnect correction, all 49 affected checks pass, including three new
real subprocess cleanup regressions (46 overlap the earlier run; 286 distinct
checks overall). There is one existing third-party Python deprecation warning; frontend source
retains zero ESLint warnings. The isolated production build, prior same-source
lint/typecheck evidence and new focused catalog checks pass. Broad unrelated
suites were not repeated in Cloud.

Actual browser evidence: `/workspace/attune-v3-final-import-20261021/real-browser/`
(TR); `/workspace/attune-v3-recovery-20261021/real-browser-en-de/` (EN/DE and
interruption/safety); recovery logs and focused-test XML are in
`/workspace/attune-v3-recovery-20261021/`.

AAOS runtime acceptance remains unverified for this final neural integration.
No AAOS workflow was launched; no merge or deployment was performed. Review and
CI status must refer to the final feature commit, not earlier successful CI.
