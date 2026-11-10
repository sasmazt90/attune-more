# Mental closing bridge (A/B/C) — female-calm-v1, technical preview

When a Mental conversation ends, three prepared recordings play — **A** thanks, **B** closes the conversation, **C** says the summary is being prepared — while the existing context preparation, summary request and checks run, and while the personalised summary's speech is generated. The summary then plays in the same `female-calm-v1` voice.

**Status: off by default. The 45 recordings are technically verified but await the owner's listening approval.** The reference profile's earlier approval does not cover these recordings or their joins; the manifest says so (`technical-preview-awaiting-owner-listening`, `ownerApprovedAt: null`).

## How it is wired

| Path | Before | With the bridge enabled |
| --- | --- | --- |
| Normal conversation (live default) | Summary shown; no closing speech | A→B→C, then the short validated `spokenSummary` from the same analysis call, in `female-calm-v1`; `summaryText` stays on screen and in history |
| Structured conversation (`structured-v1`) | Summary shown, then `spokenSummary` spoken | A→B→C, then `spokenSummary` |

`finish()` in `apps/vehicle-app/src/utils/useMentalConversation.ts`:

1. Existing preconditions first (failed, crisis or empty sessions never start the bridge). The closing guard is the same as the existing dynamic closing: session epoch, park, speech/cloud/service consent, voice on, language.
2. `startClosingFlow()` (`mentalClosingBridge.ts`) chooses one A, one B and one C of the user's language **once**, verifies all three files (size + SHA-256) and starts A. It does not wait for anything else.
3. Context preparation and `/analyze-session` run in parallel. On the normal path the request adds `spokenSummary: true` (same single provider call, see below). All existing validation applies.
4. As soon as the analysis passed those checks, `summaryReady(spokenSummary)` starts generating its speech with `prepareMentalNeuralSpeech()` — during A/B/C. Playback is a separate step. If the short line is missing or invalid, `summaryUnavailable()` is called: the written summary is saved and shown, nothing longer is spoken instead, and the page says so (“Özet hazır; kısa sesli özet oluşturulamadı.”).
5. After history storage and `setSummary()`, `complete()` waits for C to end, then plays the prepared summary. If it is not ready yet the page shows an honest state (“Özetin sesi hazırlanıyor”) — no recording is replayed. A/B/C and the summary play on **one** media element, created in the user's “end conversation” gesture, so a WebView that requires a gesture per element (AAOS: `setMediaPlaybackRequiresUserGesture(true)`) needs no extra tap.

One controller and one audio-focus owner cover the whole closing. Only one output plays at a time. `cleanup()` (cancel, PARK/driving, consent withdrawal, unmount, new conversation) aborts recordings and pending speech; a late result of an old closing cannot play. Mute and a hidden page stop output through the existing playback guards; the language selector is locked while the closing runs (the language guard remains as a second layer). Normal conversation turns, their `official-default` voice and other modules are unchanged.

`mentalNeuralSpeech()` is now `prepareMentalNeuralSpeech(...).play(...)`; for ordinary turns the request order, deadlines, guards and stage events are identical (existing tests unchanged).

## Short spoken summary (normal closing)

The normal path used to speak the written `summaryText` (TR 19, EN 24, DE 22 words in the first probe; 25–42 words from the live provider on 2026-11-10). It now asks the **same** `/analyze-session` call for an additional `spokenSummary` (`spokenSummary: true`, legacy engine only; no second provider request). `summaryText` is unchanged and remains the screen/history text.

Server contract (`validate_spoken_summary` in `services/core-api/mental_analysis.py`, enforced on every response). These are **formal** checks: one sentence, ≤ 12 words, ≤ 100 characters; the session language (letters, and no function words exclusive to another language); the address of the recorded closing (Turkish *sen*, German *Sie*); none of the A/B/C bridge phrases; none of the listed advice, suggestion, reassurance or evaluation markers; the recap form (“… söz ettin.” / “You talked about …” / “Sie sprachen über …”); in Turkish the ablative before the verb; lexical grounding — at least one content word the user said, and at most one content word the user did not say (only next to two that they did). NFC and whitespace are normalised; nothing is ever cut. A failing line is returned as `spokenSummary: null` with `spokenSummaryStatus` (`missing`, `too-many-words`, `wrong-language`, `address-mismatch`, `not-recap-form`, `tr-ablative-required`, `adds-unsaid-content`, `not-grounded-in-user-words`, `advice-or-evaluation`, …); the client then speaks nothing (it re-checks the bounds before speaking).

**Not guaranteed: meaning.** A line made of the user's own words can still reverse a negation (“I am not worried about my health” → “You talked about worries about your health”) or add a single unsaid word (“… and your boss”). `tests/unit/fixtures/mental_spoken_summary_cases.json` keeps formal acceptance and content labels apart (42 synthetic TR/EN/DE cases, the reviewers' four counter-examples included); a test fails unless every formally accepted line with wrong content is declared there as a known limitation.

Turkish address: the recorded A/B/C closing (owner's verbatim texts) uses *sen* (“Paylaştıkların…”, “Seni…”), so the dynamic line in the normal closing now uses *sen* too. The structured-v1 library keeps its documented formal-address rule (*siz*); in that path A/B/C and the structured `spokenSummary` therefore still differ in address — an open decision for the owner (new *siz* recordings or a changed structured rule), not changed here. No recording was regenerated.

The prompt puts `spokenSummary` in the JSON template with the recap form, asks for the user's own words, kept negations and the address above. Earlier prompt versions were rejected by measurement with the live provider (`gpt-4o-mini` on WEB):

| Prompt | Result with the real provider |
| --- | --- |
| Rule appended after the conversation, key not in the template | No `spokenSummary` at all (`missing`, TR 2/2) |
| Key in the template, no recap form | Lines were reassurance/advice (“It's normal to feel anxious…”, “…destek almayı düşünebilirsiniz”, “…effectively”); DE 3 of 4 failed grounding |
| Recap form, Turkish *siz* (2026-11-10 morning) | 29 of 30 passed the then-current formal checks; one TR line had a grammar error (“…uzaklaşmak söz ettiniz”) |
| Recap form, Turkish *sen*, user's own words, kept negations (current) | see *Review 2026-11-10, round 2* |

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

**Superseded (kept as the original record):** the first browser timeline below paired the `part0-repeat` synthesis times with the `part0` WAVs (7.20/5.80/6.00 s audio instead of 6.32/4.68/7.12 s) and mislabelled EN/DE as first-after-boot. Corrected and new measurements: *Review 2026-11-10* below and [review-20261110.json](review-20261110.json).

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

## Review 2026-11-10: corrected and real-path measurements

All numbers are milliseconds/seconds from the closing trigger (“end conversation”). Sources are labelled; replays are never counted as live runs. Details and every row: [review-20261110.json](review-20261110.json).

**Corrected replay of the 2026-11-09 probe** (long written summary, as before; each part now plays the WAV of its own measurement row; the harness refuses mismatched duration, WAV hash, text hash, profile or run id, and fails a run whose requested text differs — the old pairing is rejected by that check): first personalised audio TR 25.4 s (repeat) / 38.4 s (first female request), EN 22.5/24.4 s and DE 24.8/28.0 s (two warm samples each); part gaps 9.1–14.0 s; no overlap. Same under `--autoplay-policy=user-gesture-required`.

**Real path on WEB (components).** A separate API process of this branch (loopback port 8190, the product API's own environment, fresh token; product services untouched) with the real provider and the real `/api/mental/neural-speech` endpoint, resident worker, `female-calm-v1`, 4 threads; synthetic conversations. *cold* = first female request of a freshly started process after its start-up warm-up.

| | TR | EN | DE |
| --- | --- | --- | --- |
| Analysis with `spokenSummary` (one call) | 2.7–2.8 s | 2.1 s | 2.4 s |
| Written summary / spoken line | 30–35 / 8–9 words | 30–42 / 9–11 words | 25–38 / 11 words |
| Short line speech, cold | 32.0 s (5.1 s audio) | 28.8 s (4.1 s) | 30.3 s (4.6 s) |
| Short line speech, warm | 21.0–21.8 s (5.0–5.3 s) | 17.5–18.0 s (3.8–3.9 s) | 18.9–21.5 s (4.3–5.2 s) |
| Long first part, cold / warm | 48.6 / 39.6–39.8 s (11.6–12.0 s) | 33.4 / 21.9–33.2 s (5.4–10.0 s) | 33.0 / 22.5–39.3 s (5.9–11.9 s) |

Each request pays ≈ 2.35 s bundle verification; inference runs at ≈ 3.1–4.1× the audio duration on this CPU host; the first female request of a process adds ≈ 10 s.

**Live on WEB (nothing replayed but the microphone).** System Chrome → a production build of this branch → the test API → real provider and real TTS; one synthetic utterance per conversation; per language a fresh API process, first closing cold, second warm:

| Closing | Summary text | C ends | First personal audio | C → personal | Closing audio ends |
| --- | --- | --- | --- | --- | --- |
| TR cold / warm | 3.2 / 2.7 s | 11.0 / 10.3 s | 32.8 / 22.9 s | 21.9 / 12.5 s | 37.1 / 27.4 s |
| EN cold / warm | 2.3 / 2.5 s | 9.2 / 8.6 s | 30.0 / 20.2 s | 20.8 / 11.5 s | 33.4 / 23.7 s |
| DE cold / warm | 2.3 / 2.5 s | 11.1 / 8.8 s | 30.9 / 20.8 s | 19.8 / 12.0 s | 34.8 / 24.6 s |

A started 17–19 ms after the trigger; A→B and B→C 126–129 ms; no overlap, no tap. (An earlier live run with the second prompt is kept in the evidence: one DE closing spoke nothing because its line was rejected, and showed the honest notice.)

**Short vs long on the same recordings** (replay in Chromium of the real-path analysis and speech responses with their measured delays; long = the previous behaviour, build 4872c6e; identical under default and strict autoplay):

| Conversation | First personal audio short / long | Closing audio ends short / long |
| --- | --- | --- |
| TR c1 cold | 34.8 / 51.4 s | 39.9 / 91.9 s |
| TR c1, c2 warm | 23.8, 24.5 / 42.6, 42.4 s | 28.8, 29.8 / 81.7, 73.6 s |
| EN c1 cold | 31.0 / 35.6 s | 35.2 / 65.4 s |
| EN c1, c2 warm | 19.7, 20.1 / 24.1, 35.4 s | 23.5, 24.1 / 50.4, 58.5 s |
| DE c1 cold | 32.8 / 35.4 s | 37.3 / 69.0 s |
| DE c1, c2 warm | 24.0, 21.4 / 24.9, 41.7 s | 29.1, 25.7 / 59.5, 66.4 s |

Why: speech time grows with the audio produced. The long path's first unit is the first sentence (12–28 words here), so the gain in time to the first personal audio is ≈ 1–5 s where that sentence was short (DE c1, EN c1) and 15–20 s where it was long; the long path's second part was generated only after the first and arrived 8–21 s after the first part ended. The short line removes the second part and that pause; the closing ends 27–53 s earlier. **It does not make synthesis faster**, and the 8–9 s target is not met: after C ends, the personal audio still comes ≈ 11–14 s later (warm) or ≈ 20–23 s later (first female request after a service start).

**AAOS (real WebView).** AAOS 15 emulator on the AAOS host, cloudDemo APK, native PARK/driving gate and background handling, Android audio mixer. The product web-aaos service was not changed: the WebView origin's page and asset requests were answered by a build of this branch on the AAOS host through CDP interception; vehicle state went to the real backend; recognizer scripted; reply, analysis and closing speech replayed from the WEB real-path recordings. Results: all 45 recordings reached the WebView byte-identical to the manifest; TR (cold) and EN (warm) complete closings played A→B→C→personal summary in order without overlap or tap prompt (A→B/B→C 126–128 ms; the app held Android audio focus; output frames during A and the summary); cancel during B followed by a new conversation, cancel during the summary, mute during C, consent withdrawal during A: output stopped (no frames in the following window), no closing stage or closing audio afterwards, including after the late speech response; the language selector is locked during the closing; driving during C and backgrounding during B: the last output frame came 3.5 s and 3.3 s after the action, then silence, and nothing of the closing played after returning (the WebView document was replaced). *(Round 2 correction: those 3.3–3.5 s include ≈ 3 s of silent mixer standby frames; the app's player stopped far earlier — see round 2.)* Not verified on AAOS: a real Android touch on “end conversation” (the `adb input tap` coordinate mapping missed the button; all taps were CDP input events), a German complete closing, live provider/TTS inside AAOS, real speakers/hearing, OEM audio focus with other car apps, and a physical vehicle signal. One observation: in one run the existing completion guidance clip failed once ≈ 10 s after a finished closing (notice “Seçilen ses oynatılamadı…”) and then played on retry; the closing's own audio was not involved; cause not determined. *(Round 2 correction: the “untagged play ≈ 10 s later” was the personal summary itself — two clocks had been mixed; the root cause of the extra sound and the notice is explained in round 2.)*

## Review 2026-11-10, round 2

Details, every row and the raw traces: [review-20261110-round2.json](review-20261110-round2.json). Sample sizes are given everywhere; none of the small samples is presented as a percentile.

**Short line validator.** The four reviewer counter-examples (German line in English, an added fact, an imperative, Turkish address) were reproduced as accepted by the old checks and are now rejected or, for Turkish *sen*, accepted by design (`Baskılardan bahsettin.`; the *siz* variant is rejected). The 44-case synthetic corpus (TR/EN/DE, different topics, negations, added facts) passes formally; 4 cases are declared known limitations (negation flips, one added word, a copied first person in Turkish).

**Real provider, formal acceptance** (`gpt-4o-mini` on WEB, same single analysis call; two synthetic closing conversations and six different-topic conversations per language, 3 repeats each = 72 analyses per prompt):

| Prompt | TR | EN | DE |
| --- | --- | --- | --- |
| Turkish *sen*, user's own words | 24/24 | 24/24 | 16/24 (4 × 13 words, 4 × unsaid word) |
| + “aim for 6–10 words”, German separable verbs grounded (current) | 24/24 | 24/24 | 21/24 (3 × the assistant's word “Druck”) |

Content of the 69 formally valid current lines, **labelled by the assistant (not a human review)**: 67 correct (some vague, e.g. “İşten ve uykudan söz ettin.”), 2 imprecise (“… and swimming” where the user only wished to swim); no negation flip, added fact, wrong address or wrong person was seen in this sample. The validator does not establish meaning; listening/reading review remains required.

**Live on WEB** (system Chrome → this branch → test API → real provider and real TTS; 1 cold + 3 warm closings per language, earlier prompt version of this round):

| Language | First personal audio (warm) | C → personal (warm) | Cold | Notes |
| --- | --- | --- | --- | --- |
| TR | 21.5 / 22.2 / 22.9 s | 11.2 / 11.9 / 12.4 s | 31.0 s | n = 3 warm |
| EN | 17.9 / 19.4 / 20.3 s | 9.6 / 10.2 / 11.4 s | 29.4 s | n = 3 warm |
| DE | — | — | 32.8 s | 3 of 4 closings had no valid line (spoke nothing, honest notice); the one line came on the first female request |

The ≈ 8–9 s target is not met; the remaining wait is synthesis time on the CPU host (short line: 14–20 s warm, 25–28 s for the first female request after a service start; inference ≈ 3–4× the audio). A/B/C are not lengthened or repeated to hide it. A GPU comparison is planned, not started: [GPU-PLAN-20261110.md](GPU-PLAN-20261110.md).

**AAOS stop latency.** No repository or OEM criterion exists; the proposed criterion (fixed before the runs) is: the app's Android player leaves `started` within 1000 ms of the stop condition. Measured per stage (host clock; guest events converted with a measured offset; player states sampled every ≈ 38 ms):

| Case | Before (web polls vehicle state every 1 s) | After (250 ms while app audio owns output) |
| --- | --- | --- |
| Driving during the closing | backend ack 12 ms, web never saw it before the native gate closed the WebView at 666 ms, player stopped 685 ms (n = 1) | ack 6–13 ms, web saw driving 23–248 ms, media pause 38–274 ms, player stopped 62–255 ms (n = 3) |
| Background (HOME) | player stopped 67 ms (n = 1) | 75–91 ms (n = 2) |
| Cancel, mute, consent withdrawal | — | 77–153 ms (n = 4) |

In every case the output frame counter kept rising for 2.9–3.1 s after the player stopped: AudioFlinger's standby period (property unset, platform default), writing silence. The earlier 3.3–3.5 s were this tail, not audible closing audio. The native gate (1 s poll, WebView destroyed) is unchanged. After every interruption nothing of the closing played later, including when the replayed speech response arrived afterwards and after returning to the app.

**Extra sound after the closing — root cause.** When a closing ends, the page's phase becomes `completed` and the existing `mental-complete` guidance (another voice: “Görüşme tamamlandı…”) starts on a new media element ≈ 55 ms after the closing released audio focus. On the pre-fix build it either played (a second completion message, 5.7 s) or, in the language-lock run, `play()` was rejected with `NotAllowedError` (Android WebView's gesture rule for a new element), the guidance reported `gesture-required` and the page showed “Seçilen ses oynatılamadı…”. Fix: after a spoken (or user-stopped) closing the page does not start that guidance; with the bridge off or on fallback it still plays. On the fixed build no sound followed the closing in 9 complete closings (TR/EN/DE × CDP click, real touch, product-chain speech; from the raw play events), and no failure notice appeared; the language-lock case showed no notice either. Both pre-fix complete closings played the guidance afterwards.

**AAOS coverage.** Real calibrated Android touches (`adb input tap`, mapping measured with two swallowed probe taps) started the closing in TR, EN and DE, and those closings completed A→B→C→personal summary without a tap prompt; CDP clicks likewise in TR, EN and DE. With `CLOSING_TTS=product` the closing speech was generated live through the existing product AAOS chain (WebView → AAOS Caddy → WEB Caddy mTLS → `web-aaos` → `api-aaos`, nothing reconfigured): TR first request 24.8 s, EN 12.2 s, DE 15.8 s server time, personal audio 9.2–20.5 s after C; the analysis stayed replayed because the deployed AAOS backend runs `main`, which has no `spokenSummary`. A fully live path to a test API from AAOS is not possible without a configuration change: the AAOS security group reaches WEB only on 8443 (Caddy mTLS to product services); opening 8190 or adding a route needs approval.

## Tests

`tests/unit/test_mental_closing_bridge.py` (assets, manifest, hashes, profile pins, approval state) runs `mental_closing_bridge_runtime.cjs` (gate, single selection without repeats with all 125 reachable, A→B→C order without overlap, overlap of preparation, next-part prefetch, honest waits, cancel/session/mute/hidden/language, altered/failed assets) and `mental_closing_finish_runtime.cjs` (real `finish()` for normal and structured paths, fallback, summary failure, consent withdrawal, cancel, failed/empty sessions). `tests/unit/test_mental_spoken_summary.py` covers the short line (bounds, language, address, grounding, bridge phrases, advice/evaluation, no truncation, one provider call, template and recap form, opt-in API flag). `scripts/qa/mental_closing_bridge_timeline.cjs` (replay or live mode, `mental_closing_bridge_scenarios.py` builds scenarios from measurement rows), `scripts/mental_closing_abc/closing_realpath_probe.py`, `closing_live_probe.py`, `spoken_summary_probe.py` and `scripts/qa/aaos/aaos-mental-closing.cjs` produced the 2026-11-10 measurements. Round 2 adds `tests/unit/fixtures/mental_spoken_summary_cases.json` (formal vs content), `tests/unit/vehicle_polling_runtime.cjs` and a page/hook check that the completion guidance is skipped after a spoken closing.
