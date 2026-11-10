# KOL B — Attune.more Mental with Qwen3.5-2B + LiteRT-LM (on-device prototype)

Independent prototype, separate from KOL A (PR #29, prepared A/B/C recordings). Branch base: the shared start commit
`4b3f596121f98333d766c24f64cbd2c799442e72`. **No product file is changed**: everything lives in
`prototypes/mental-qwen35-litert/`. The final choice between the two approaches is the owner's.

Results and the PASS/FAIL/BLOCKED table: [`results/REPORT-2026-11-10.md`](results/REPORT-2026-11-10.md).
Pre-registered test plan (committed before any evaluation run): [`eval/TEST-PLAN.md`](eval/TEST-PLAN.md).

## What is where

| Path | What |
| --- | --- |
| `MODEL-AND-RUNTIME.lock.json` | Every downloaded artefact: source URL, revision, SHA-256, size, license |
| `web/core/` | Session core shared by WEB and AAOS: prompts, reply checks, epoch/cancel, closing, extractive written summary (prompts locked: `eval/PROMPTS-LOCKED.sha256`) |
| `web/adapters/` | LLM adapters (`litertWebLlm.js` in-browser WebGPU, `androidLlm.js` native bridge, `hostLlm.js` evaluation only), product crisis check (`crisis.js`), product validator via Pyodide (`pyValidator.js`) |
| `web/speech/` → `web/dist/speech.js` | In-browser VAD (Silero v5), STT (Whisper q8 via transformers.js), TTS (Piper via ONNX Runtime Web) |
| `web/app/` | Prototype page (WEB, and the AAOS WebView) |
| `web/compat/`, `web/tools/run_probe.cjs` | Browser compatibility probe of the model/runtime |
| `web/bench/` | Speech benchmarks and the B5 chain driver |
| `web/generated/` | Product code compiled/copied unchanged (crisis detector, validator) with source SHA-256 |
| `android/` | Separate AAOS APK (`more.attune.prototype.mentalqwen`): WebView + native LiteRT-LM bridge + CarUxRestrictions park gate. Never replaces the product app |
| `host/` | HOST-linux-cpu tools (smoke, leak test, LLM adapter for evaluation) — **not on-device** |
| `eval/` | Test plan, synthetic corpora, dev set (prompt tuning only), scripts, author labels |
| `results/` | Report, computed metrics (`summary.json`), trimmed raw evidence |

## Setup (no automatic install on anyone's computer)

Requirements: Node 22, Python 3.12+, Chromium/Chrome 153+ (WebGPU for the in-browser LLM), ~7 GB disk for models.
Network is needed **once** for downloads (huggingface.co + its CDN `us.aws.cdn.hf.co`, npm, GitHub release assets for
nothing in this build). After that every run blocks all non-loopback requests.

```bash
cd prototypes/mental-qwen35-litert/web
npm ci
./tools/copy_product_files.sh
npx esbuild speech/speech.js --bundle --format=esm --platform=browser --outfile=dist/speech.js --external:sharp --external:onnxruntime-node --define:process.env.NODE_ENV='"production"'
npx esbuild ../../../packages/safety/crisisDetector.ts --bundle --format=esm --platform=neutral --outfile=generated/crisisDetector.js
```

Models (verify each SHA-256 against `MODEL-AND-RUNTIME.lock.json`) into one directory `MODELS`:

```bash
MODELS=$HOME/attune-kol-b-models
mkdir -p $MODELS/qwen35-2b $MODELS/piper $MODELS/stt
curl -L -o $MODELS/qwen35-2b/Qwen3.5-2B_int8.litertlm https://huggingface.co/litert-community/Qwen3.5-2B/resolve/f24013ba6844bd39be2d1f68e8d2421a77eed1f2/Qwen3.5-2B_int8.litertlm
sha256sum $MODELS/qwen35-2b/Qwen3.5-2B_int8.litertlm   # c2438cb9c050220e667366b4beeca4daac56e693b226420674f53fc40f007c49
```

Piper voices: `rhasspy/piper-voices@cf910fb59f1d79ab3b625a63993a108751c6c25d` files `tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx(.json)`,
`en/en_US/kristin/medium/en_US-kristin-medium.onnx(.json)`, `de/de_DE/kerstin/medium/de_DE-kerstin-medium.onnx(.json)` into `$MODELS/piper/`.
Whisper: `onnx-community/whisper-small@36050c46…` (and `whisper-base@27a07b4b…`) — `config.json`, `generation_config.json`,
`preprocessor_config.json`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`,
`normalizer.json`, `vocab.json`, `merges.txt`, `onnx/encoder_model_quantized.onnx`, `onnx/decoder_model_merged_quantized.onnx`
into `$MODELS/stt/onnx-community/<name>/`.

Run (loopback only):

```bash
node tools/serve.mjs . $MODELS 8731
```

Open `http://127.0.0.1:8731/app/index.html?llm=web` in Chrome on a machine with a real GPU. `?llm=host` exists only for
evaluation (needs `host/llm_host_server.py`) and is labelled “HOST — not on-device” on the page.

## AAOS (separate APK)

```bash
cd prototypes/mental-qwen35-litert/android
ANDROID_HOME=<sdk with platforms;android-35 and build-tools;35.0.0> ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb push $MODELS /data/local/tmp/attune-models
adb shell run-as more.attune.prototype.mentalqwen sh -c 'mkdir -p files/models && cp -r /data/local/tmp/attune-models/* files/models/'
```

The APK has **no INTERNET permission**. LLM: LiteRT-LM Android 0.19.1, CPU backend (model card recommendation for
Android), one Engine per conversation. Speech runs in the WebView (WASM). PARK gate: `CarUxRestrictionsManager`, unknown =
not parked (same rule as the product app). Runtime on an AAOS emulator/device was **not** possible in this environment
(no KVM, no device) — see the report for the required test window.

## Safety controls kept

Product `checkCrisisTrigger` (compiled unchanged) runs before any model call; crisis text is the product's fixed text in
the product translation; the model is never asked. PARK lost, consent withdrawn, page hidden/app backgrounded, mute and
cancel stop output; an epoch check discards any late model or speech result. The language is locked during a session.
The personal closing line is spoken only if the product validator (`validate_spoken_summary`, unchanged) accepts it,
plus the prototype's on-device verifier; otherwise nothing personal is spoken and the written summary stays.
