# Mental closing bridge (A/B/C) — female-calm-v1, technical preview

When a Mental conversation ends, three prepared recordings play — **A** thanks, **B** closes the conversation, **C** says the summary is being prepared — while the existing context preparation, summary request and checks run, and while the personalised summary's speech is generated. The summary then plays in the same `female-calm-v1` voice.

**Status: off by default. The 45 recordings are technically verified but await the owner's listening approval.** The reference profile's earlier approval does not cover these recordings or their joins; the manifest says so (`technical-preview-awaiting-owner-listening`, `ownerApprovedAt: null`).

## How it is wired

| Path | Before | With the bridge enabled |
| --- | --- | --- |
| Normal conversation (live default) | Summary shown; no closing speech | A→B→C, then the validated `summaryText` spoken in `female-calm-v1` |
| Structured conversation (`structured-v1`) | Summary shown, then `spokenSummary` spoken | A→B→C, then `spokenSummary` |

`finish()` in `apps/vehicle-app/src/utils/useMentalConversation.ts`:

1. Existing preconditions first (failed, crisis or empty sessions never start the bridge). The closing guard is the same as the existing dynamic closing: session epoch, park, speech/cloud/service consent, voice on, language.
2. `startClosingFlow()` (`mentalClosingBridge.ts`) chooses one A, one B and one C of the user's language **once**, verifies all three files (size + SHA-256) and starts A. It does not wait for anything else.
3. Context preparation and `/analyze-session` run unchanged and in parallel. All existing validation applies.
4. As soon as the summary text passed those checks, `summaryReady()` starts generating its speech with `prepareMentalNeuralSpeech()` — during A/B/C. Playback is a separate step.
5. After history storage and `setSummary()`, `complete()` waits for C to end, then plays the prepared summary. If it is not ready yet the page shows an honest state (“Özetin sesi hazırlanıyor”) — no recording is replayed. The next summary part is still generated while the previous one plays.

One controller and one audio-focus owner cover the whole closing. Only one output plays at a time. `cleanup()` (cancel, PARK/driving, consent withdrawal, unmount, new conversation) aborts recordings and pending speech; a late result of an old closing cannot play. Mute, hidden page and language change stop output through the existing playback guards. Normal conversation turns, their `official-default` voice and other modules are unchanged.

`mentalNeuralSpeech()` is now `prepareMentalNeuralSpeech(...).play(...)`; for ordinary turns the request order, deadlines, guards and stage events are identical (existing tests unchanged).

## Enable, disable, fall back

Build-time flag `NEXT_PUBLIC_MENTAL_CLOSING_BRIDGE`:

| Value | Effect |
| --- | --- |
| unset / anything else | Off — existing closing (default; no deployment sets it) |
| `approved` | Only recordings with owner approval in the manifest (none today → existing closing) |
| `technical-preview` | Test environments only: also plays technically verified, unapproved recordings; the page shows “Teknik önizleme…” |

Falls back to the existing closing when: the flag is off; the browser-system voice is selected; any of the 15 recordings of the language is missing, altered, unapproved for the mode, or has another profile/reference/settings than the approved `female-calm-v1` library; or a recording fails verification before anything played. If playback fails midway, nothing further plays and the existing notice “Özet hazır; kapanış sesi oynatılamadı.” appears. No other voice, provider or model is ever substituted.

To approve after listening: set each entry's `approvalStatus` to `approved` with `ownerApprovedAt`, set `approval.status`/`ownerApprovedAt`, and build with `approved`.

## Assets

`apps/vehicle-app/public/audio/mental/closing-abc/v1/{tr,en,de}/female-calm-v1/{A,B,C}/{TR|EN|DE}_{A|B|C}{1..5}.wav` and `manifest.json` (served by the app itself; Drive is only the review archive). Texts: `shared/mental/closing-abc/v1/catalog.json` (verbatim; German uses *Sie*).

Each of the 45 files was synthesized once on the existing WEB host with the product worker (`mental_neural_worker.synthesize`, resident model, 4 threads): Chatterbox 0.1.7, source `5de7a54…`, model revision `5bb1f6e…`, reference SHA-256 `4d2bd83f…`, exaggeration 0.35, cfg_weight 0.0, temperature 0.8, watermark retained, PCM16 only — no pitch, rate or silence edits. Seed = first 32 bits of SHA-256(asset id), as for the prepared library. Model files and reference were hashed before and after; product files on the host were unchanged. Mono 24 kHz PCM16, 0 clipped samples, edge silence ≤ 160 ms leading / ≤ 540 ms trailing.

## Measurements (details: [evidence.json](evidence.json))

Clip durations and the 125 combinations per language (clip audio + two transitions of 120 ms configured pause + 9 ms measured browser overhead):

| Language | Clip audio | A+B+C min / median / max | Within 8–9 s |
| --- | --- | --- | --- |
| TR | 2.72–4.96 s | 8.90 / 10.82 / 12.82 s | 2 of 125 |
| EN | 1.96–3.48 s | 7.54 / 8.74 / 9.82 s | 69 of 125 |
| DE | 2.44–4.20 s | 8.78 / 10.46 / 11.66 s | 2 of 125 |

Summary speech on the host (product resident loop, synthetic non-personal two-sentence summaries; each request also pays ≈2.27 s of bundle verification):

| Request | Seconds | Audio |
| --- | --- | --- |
| official-default warm-up at boot | 19.8 | — |
| first female request (TR part 0, loads the female model) | 33.1 | 7.20 s |
| warm first parts TR / EN / DE | 20.1 / 17.2–19.1 / 19.5–22.7 | 4.7–7.1 s |
| second parts TR / EN / DE | 18.0 / 12.6 / 15.4 | 2.9–5.1 s |

Browser timeline (production build, real Chromium playback of the committed WAVs, real hook code; **all backend responses are fixtures**, the summary arrives after an assumed 3 s (12 s in one case), speech responses replay the host-measured delays — no provider call):

| Scenario | First prepared audio | C ends | First personalised audio | C→summary gap | Part gap | Closing audio ends |
| --- | --- | --- | --- | --- | --- | --- |
| TR warm | 26 ms | 12.7 s | 25.4 s | 12.7 s | 13.1 s | 50.8 s |
| TR first female request after boot | 30 ms | 11.7 s | 38.4 s | 26.7 s | 13.1 s | 63.8 s |
| EN warm (two samples) | 24–28 ms | 8.5–9.1 s | 22.5–24.4 s | 13.9–15.3 s | 9.1 s | 40.2–42.1 s |
| DE warm (two samples) | 26–30 ms | 11.1–11.3 s | 24.8–28.0 s | 13.7–16.7 s | 11.7 s | 46.5–49.7 s |
| TR warm, summary after 12 s | 25 ms | 11.1 s | 34.4 s | 23.3 s | 13.1 s | 59.8 s |

The summary request started 3–5 ms after the trigger (in parallel with A); speech generation started within 1 ms of the validated text; no output overlapped in any run (A→B and B→C 127–130 ms). The bridge hides part of the wait, not all of it: with this CPU host the first personalised audio still comes 13–27 s after C. **This feature does not make synthesis faster.**

Not measured: a live provider's summary latency, the first EN/DE female request after boot (only TR was cold in the probe), real network/ASR, AAOS, and any listening quality. The PR #28 conditioning-cache flag was not used.

## Tests

`tests/unit/test_mental_closing_bridge.py` (assets, manifest, hashes, profile pins, approval state) runs `mental_closing_bridge_runtime.cjs` (gate, single selection without repeats with all 125 reachable, A→B→C order without overlap, overlap of preparation, next-part prefetch, honest waits, cancel/session/mute/hidden/language, altered/failed assets) and `mental_closing_finish_runtime.cjs` (real `finish()` for normal and structured paths, fallback, summary failure, consent withdrawal, cancel, failed/empty sessions). `scripts/qa/mental_closing_bridge_timeline.cjs` produced the browser timeline.
