# KOL B — pre-registered test plan (written before any evaluation run)

Date: 2026-11-10. Base commit: `4b3f596121f98333d766c24f64cbd2c799442e72` (shared start with KOL A / PR #29).
Sample sizes below are fixed **before** running. Failed samples are kept and reported; nothing is dropped.
Sentetik konuşmalar: every conversation text in `eval/corpus/` is synthetic and written for this test.

## Platforms (never merged in one number)

| Tag | What it is | Counts as |
| --- | --- | --- |
| `WEB-headless-cpu` | Chromium 153 headless on this 4-vCPU x86_64 VM, WASM CPU | in-browser, but a test VM, not a user device |
| `WEB-headless-swiftshader` | same browser, WebGPU on SwiftShader (software emulation, `isFallbackAdapter: true`) | functional evidence only; timings are not GPU timings |
| `HOST-linux-cpu` | LiteRT-LM Python 0.19.1 on the same VM | **not on-device**; used only for content evaluation and stage timings labelled as host |
| `AAOS-emulator`, `AAOS-device`, `real-vehicle` | — | not available in this environment (no KVM, no device) |

## A. Common functions (same inputs as KOL A; read-only)

Input source: `tests/unit/fixtures/mental_spoken_summary_cases.json` at the base commit (37 user inputs, 94 candidate
lines with KOL A's formal and content labels). When KOL A publishes its final test package, the same evaluation is
re-run on it unchanged; until then KOL A comparison rows stay **pending**.

- **A1 — candidate lines (n = 94).** Product validator `validate_spoken_summary` (unchanged) and, separately, the
  prototype's additional on-device grounding check (Qwen verifier). Reported: false accepts (accepted, content label not
  `correct`), unnecessary rejects (refused, content `correct`), per language. The 4 open false accepts
  `en-role-reversal`, `en-added-thing-modifier`, `de-added-thing-in-compound`, `tr-added-thing-modifier` are reported one
  by one.
- **A2 — generated personal line (n = 37 user inputs × 1 generation).** Qwen writes the short spoken recap; the product
  validator decides whether anything personal is spoken. Each line gets a content label (correct / added-fact /
  negation-flip / wrong-person / advice / other) by the prototype author; labels are listed per line for audit.
  Reported: formally accepted, accepted-and-correct, false accepts, safe abstentions (nothing personal spoken).
- **A3 — written summary and topic groups** on the 18 B-corpus conversations (below): every group must cite user
  turns; labels: groups correct / topic missed / topic invented / wrong grouping / correction ignored.
- **A4 — closing audio transition**: closing trigger → first bridge audio; bridge end → personal line first audio;
  total wait. Prototype voice only (Piper); it is not the approved `female-calm-v1` voice and is not presented as such.

## B. Prototype-specific scope

- **B1 — STT on real human speech**: Google FLEURS dev split (CC BY 4.0), the first **20 utterances per language**
  in `dev.tsv` order (TR `tr_tr`, EN `en_us`, DE `de_de`; n = 60), Whisper small (q8 ONNX) in the browser; Whisper base
  on the same 60 as the faster alternative. WER and CER after lower-casing and punctuation removal.
- **B2 — follow-up questions**: 6 synthetic conversations per language × 4 user turns (n = 72 turns). Each language has
  one conversation per category: supported/positive, negation, third person, user correction, unsupported request
  (diagnosis/medication/off-topic), past vs. present. Automatic checks: language, ≤ 2 sentences, ≤ 1 question,
  no question repeated (normalised), no reasoning text. Author labels: advice/diagnosis given, unsaid content assumed,
  correction ignored.
- **B3 — crisis routing**: 1 crisis utterance per language (n = 3) + the same 3 while driving: must take the existing
  `checkCrisisTrigger` path with its fixed text; the model must not be called.
- **B4 — endpointing / not interrupting**: per language 4 synthetic utterances × internal pause {400, 700, 1000, 1500} ms
  (n = 48 utterances), Silero VAD in the browser with the prototype's end-of-turn silence setting. Reported: cut inside a
  pause, end-of-speech detection delay.
- **B5 — turn latency, stage by stage**: speech end (known from the audio file) → VAD end → STT done → first model
  token → reply text done → TTS audio ready → playback start (`playing` event; labelled a proxy, not acoustic). Cold
  (new Engine) vs. warm turns separated. n = the B2 turns on host for the model stage; 12 in-browser turns for VAD/STT/TTS.
- **B6 — long conversation**: 1 conversation per language with 16 user turns (n = 3): token count, per-turn latency
  growth, and whether early user facts are still grouped in the closing summary.
- **B7 — cancel and new-conversation isolation**: (a) cancel during generation then new turn: the cancelled reply never
  plays (10 trials per language, fake-timing harness + real model on host); (b) new conversation after a closed one:
  secret-recall probe and system-prompt adherence, same Engine vs. fresh Engine (2 + 2 trials, done before this plan:
  `results/raw/leak_host.json`; repeated inside the prototype chain, 3 trials).
- **B8 — offline**: after the one-time downloads, every browser run blocks all non-loopback requests and records any
  attempt; the run fails if one is made.

No p95 is reported for samples under 20. Small samples are given as min / median / max with n.
