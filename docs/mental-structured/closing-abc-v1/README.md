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

Server contract (`validate_spoken_summary` in `services/core-api/mental_analysis.py`, enforced on every response). These are **formal** checks: one sentence, ≤ 12 words, ≤ 100 characters; the session language (letters, and no function words exclusive to another language); the address of the recorded closing (Turkish *sen*, German *Sie*); none of the A/B/C bridge phrases; none of the listed advice, suggestion, reassurance or evaluation markers; the recap form (“… söz ettin.” / “You talked about …” / “Sie sprachen über …”); in Turkish the ablative before the verb; no first person (a copied “my …” / “kiramı”; Turkish words ending in vowel + m are read as “my …” unless they are on a closed list of nouns such as *durum*, *eğitim*); lexical grounding — at least one content word the user said, at most one content word the user did not say (only next to two that they did, and only describing a word the user said: never right after an article, possessive or preposition unless a word the user said follows it, never a possessor such as “manager's” or Turkish “patronunun”), and every coordinated part of the line (“… and …”, “… ve …”, “… und …”) resting on a word the user said (English inflections “moved/moving” and, for German, a closed list of strong-verb nouns and stems — “Umzug”/“ziehe”, “Gespräch”/“spreche”, “hohen”/“hoch” — count as the same word); Turkish possessed nouns keep their role (the user's *annem* who acts may not become *anneni* who is acted on); negation parity per coordinated part — a negation in the user's words covers its whole clause, a part built only from negated words needs a negation of its own, a part that negates may only use words the user said in a negated clause, and the line may not negate when the user never did. English contractions count as negations only with an apostrophe or from a closed list (“dont”), so “recent” or “different” are not negations. NFC and whitespace are normalised; nothing is ever cut. A failing line is returned as `spokenSummary: null` with `spokenSummaryStatus` (`missing`, `too-many-words`, `wrong-language`, `address-mismatch`, `not-recap-form`, `tr-ablative-required`, `first-person`, `adds-unsaid-content`, `not-grounded-in-user-words`, `role-changed`, `negation-not-kept`, `negation-moved`, `negation-added`, `advice-or-evaluation`, …); the client then speaks nothing (it re-checks the bounds before speaking).

**Not guaranteed: meaning.** All of these are word-level checks; word overlap is not a check of meaning. Round 2 accepted **six** lines with wrong content (the round-2 text said four): `tr-negation-flip`, `en-negation-flip`, `de-negation-flip`, `en-one-added-word`, `de-one-added-word` and `tr-live-first-person`. Round 3 refuses those six (negation parity, coordinated parts, first person). Round 4 refuses the five that round 3 still accepted (`en-added-word-inside-part`, `en-negation-wrong-target`, `de-negation-wrong-target`, `en-negation-out-of-reach`, `tr-role-reversal`) and accepts the German paraphrases round 3 refused (“Umzug” for “ich ziehe”, “hohen Druck” for “Tempo … sehr hoch”). What is still accepted although wrong is listed in `tests/unit/fixtures/mental_spoken_summary_cases.json` as `knownLimitation` — five synthetic counter-examples written in round 4 to show the remaining shapes: an unsaid noun used as a modifier of a word the user said (“manager pressure”), an added part inside a German compound (“Chefstress”), a stem from the closed German list with another meaning (“Zug” as train for “ziehe”), a negation said without a negation word (“hardly”), and swapped roles in English word order. The checks still err towards rejection: correct paraphrases outside the listed forms, such as “odaklanma zorluğu” for “odaklanamıyorum” or the synonym “Sorge” for “Angst”, are refused (`conservativeReject`, 2 cases) — then nothing personal is spoken, the written summary stays, and the long text is never spoken instead. The fixture (80 synthetic TR/EN/DE cases, the reviewers' counter-examples included) keeps formal acceptance and content labels apart; tests fail unless every accepted-but-wrong line and every refused-but-correct line is declared.

Effect on the recorded real-provider lines of round 2 with the round-3 validator (re-validated offline, no new provider call; 72 lines per prompt; round 4 below): current prompt TR 24/24, EN 24/24, DE 18/24 formally valid (before: 24, 24, 21 — the three additional German refusals are the correct line “… den Umzug und das Telefonieren mit einer Freundin”); earlier prompt TR 22/24 (the two live “Kiramı …” lines are now refused), EN 24/24, DE 16/24. A stricter variant (no unsaid content word at all) was evaluated and not adopted: it would keep 53 of the 72 current lines (TR 21, EN 15, DE 17), refusing mostly correct paraphrases.

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

**Short line validator.** The four reviewer counter-examples (German line in English, an added fact, an imperative, Turkish address) were reproduced as accepted by the old checks and are now rejected or, for Turkish *sen*, accepted by design (`Baskılardan bahsettin.`; the *siz* variant is rejected). The 44-case synthetic corpus (TR/EN/DE, different topics, negations, added facts) passes formally; **6** cases were declared known limitations (three negation flips, two added words, a copied first person in Turkish). *(Round 3 correction: this text first said 4; the fixture always listed six. Those six are refused since round 3 — see “Short spoken summary” above for what remains.)*

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

## Review 2026-11-10, round 3: the same model on a GPU

Details, every row and the logs: [review-20261110-round3.json](review-20261110-round3.json); fixed texts: [gpu-benchmark-texts.json](gpu-benchmark-texts.json); tool: `scripts/mental_closing_abc/tts_device_benchmark.py`. Speed only: no listening review was done, and nothing here approves audio quality. The feature stays off; nothing was merged or deployed.

**What ran.** One temporary `g5.xlarge` (NVIDIA A10G 24 GB, 4 vCPU; eu-central-1b, because eu-central-1c had no capacity for the same type) for 92 minutes, with a separate CUDA environment: `torch 2.6.0+cu124`, FP32, TF32 off for matmul and cuDNN, the other packages at the WEB host's versions. The model files, the reference voice, the license evidence, the installed `chatterbox` sources, the Perth watermark package (22 files, weights included) and the segmenter cache hashed identical to WEB before any run. CPU baseline: the WEB host (`r7i.2xlarge`, Xeon 8488C, 4 inference threads as in the service), same tool, same texts, same seeds. Python was 3.11.18 on the GPU machine and 3.11.17 on WEB.

**Same texts and seeds, warm, product worker** (median, min–max; 9 short lines and 6 long parts, 5 seeds each on both devices; the GPU ran 5 more seeds, shown as “all”):

| | CPU | GPU, same seeds | Faster by | GPU, all seeds |
| --- | --- | --- | --- | --- |
| Short lines (6–11 words, ≈ 3.8 s audio) | 15.57 s (13.55–18.93), n = 45 | 3.14 s (2.45–3.85), n = 45 | 4.96× | 3.06 s (2.45–4.14), n = 90, p95 3.80 s |
| — Turkish / English / German | 16.21 / 15.09 / 14.40 s | 3.37 / 2.94 / 2.92 s | 4.8× / 5.1× / 4.9× | n = 30 each |
| Long parts (12–28 words, ≈ 9 s audio) | 28.18 s (18.62–39.33), n = 30 | 6.65 s (4.03–8.94), n = 30 | 4.24× | 6.64 s (4.03–9.05), n = 60, p95 8.81 s |
| Real-time factor, short / long | 4.02 / 3.15 | 0.82 / 0.72 | | |

Where the time goes for a short line (medians; every step timer synchronizes CUDA at both ends):

| Step | CPU | GPU | Faster by |
| --- | --- | --- | --- |
| Conditioning from the reference voice | 0.37 s | 0.06 s | 5.9× |
| Speech-token generation (T3) | 6.13 s (16 tokens/s) | 2.46 s (40 tokens/s) | 2.5× |
| Waveform decoding (S3Gen) | 9.05 s | 0.57 s | 16× |
| Watermark | 0.015 s | 0.026 s | — |

On the GPU the token loop is what remains (one decoding step at a time, bound by one CPU core). No failures in 181 GPU and 76 CPU rows. All 257 outputs are 24 kHz mono PCM16 with matching length; 3 CPU rows and 1 GPU row (German long parts) contain 1–7 full-scale samples. The same seed gives different audio on the two devices (75 of 75 pairs) and is not bit-reproducible on the GPU either (same length, different bytes; CPU repeats are identical). Timers cost nothing measurable (real-time factor 0.788 with and 0.792 without them, n = 30). Host memory: 5.0 GB resident on CPU, 3.1 GB on the GPU machine plus 3.2–3.4 GB of GPU memory for one model (the service holds two: default and female; that case was not measured).

**Cold.** A fresh process's first request took 29.9 and 28.4 s on CPU (n = 2) and 42.3, 23.7 and 24.4 s on the GPU (n = 3; imports ≈ 5 s, model to the device ≈ 12–13 s, first inference 4–21 s). In the service order (default model warmed at start, then the first female request) the GPU needed 19.1–22.1 s (n = 3), the CPU 25.9 s (n = 1; 26.2–27.7 s over HTTP, n = 3). A GPU does not fix the first closing after a service start.

**Service path** (the product's `verify_speaker` and resident worker subprocess, no seed; the seven lines the live analysis returned on WEB in this window with the current prompt and validator — German conversations 1 and 2 were refused, the third gave a line):

| | CPU | GPU |
| --- | --- | --- |
| Warm request | 16.59 s (15.38–20.22), n = 13 | 5.16 s (4.60–6.33), n = 60, p95 6.25 s |
| — of which bundle verification | 2.35 s | 2.32 s |
| — of which worker | 14.27 s | 2.84 s |

The service path has no HTTP layer. On CPU the same lines over the real HTTP endpoint took 15.13–19.17 s (n = 6) and its own timing header puts the HTTP part at ≈ 2 ms; the endpoint itself was not run on the GPU machine. Per-request verification (re-hashing 3.2 GB) is now 45 % of a GPU request.

**Closing in a browser and in the AAOS WebView — replays, not live.** The analysis responses are the ones measured live on WEB (1.8–4.2 s); the speech responses are the GPU service-path results for the same lines, delivered after their measured request time. Chromium (this branch's production build) and the AAOS 15 emulator's WebView played the real A/B/C recordings and ran the real closing code.

| | CPU speech (HTTP, this run) | GPU speech (service path) |
| --- | --- | --- |
| Browser, warm: personal audio ready | 18.1–21.7 s after the end tap | 6.7–9.0 s — before C ends in 6 of 7 closings |
| Browser, warm: C ends → personal audio | 9.7–11.4 s (n = 6) | 0.13–0.14 s, the configured pause (n = 7; same under strict autoplay) |
| Browser, first female request after a service start | 18.4–21.7 s after C (n = 3) | 10.2–15.9 s after C (n = 3) |
| AAOS WebView, warm: C ends → personal audio | 9.2–20.5 s in round 2 (product chain, CPU) | 0.13 s in 6 complete closings (3 by CDP click, 3 by calibrated real touch; TR/EN/DE) |
| AAOS WebView, first female request | — | 15.1 s after C (n = 1) |

A started 27–128 ms after the end tap in the browser and 188–226 ms in the WebView; A→B and B→C 128–133 ms (one transition 215 ms in the strict-autoplay run); no overlap; the summary text was ready at 1.8–4.4 s. The margin is thin for English, whose A+B+C can be as short as 7.5 s: with the slowest measured analysis (4.2 s) and GPU request (6.3 s) the personal audio would come up to ≈ 3 s after C; that combination did not occur in the 13 warm replays (7 browser, 6 AAOS).

AAOS interruptions with the same replay set (48 checks, 47 passed): cancel (+ new conversation), cancel during the summary and mute stopped the app's player 116–139 ms after the action; driving 63–286 ms (the web saw it after 22–232 ms); background 54–71 ms; nothing of the closing played later, also after the late speech response and after returning to the app; no sound and no failure notice after any of the 6 complete-closing cases. **One check failed and is not counted as passed:** for consent withdrawal during A the stop time could not be measured — in 3 of 3 samples the Android player had not yet reached `started` when consent was withdrawn (the page paused the element 19–42 ms later and the player never started; nothing played afterwards). The frame counter's ≈ 3 s tail after every stop is the mixer's silent standby, as in round 2, not audible output.

**Not done, and why.** A fully live closing against the GPU (browser or AAOS → test API → provider and GPU speech in one request chain) needs either an inbound rule on the GPU machine's security group or the provider key on that machine; neither was in the approved scope. The HTTP endpoint was not run on the GPU machine. No real speaker, no OEM audio focus, no physical vehicle signal. The emulator runs are not an OEM safety approval.

**Before this could be used in the product.** Listening review of GPU audio (it is different audio, not bit-reproducible); a decision on running a GPU host (≈ 1.26 USD/h on demand for this type) and its capacity (one zone had none); the cold start (19–22 s) — for example warming the female profile at service start, not tried here; the per-request bundle verification (2.3 s); measuring two resident models and concurrent requests on the GPU; a live end-to-end run through the HTTP endpoint; German lines (both closing conversations refused by the stricter validator); and the open items of the earlier rounds (owner listening approval of the 45 recordings, Turkish *sen* in the normal closing vs. *siz* in structured-v1).

**AWS.** WEB 09:40–10:52, 11:04–11:15 and 11:20–11:47 UTC; AAOS 09:57–10:49 and 11:15–11:47; GPU 09:44:03–11:16:13 (limit 150 min; OS timer at 12:10 and a local guard). The session was paused by a usage limit from about 10:06 to 11:02: the OS timers stopped WEB and AAOS on their own, and the GPU, whose jobs had finished at 10:14, stayed up inside its limit until the results were pulled. Final state by API at 11:48 UTC: GPU terminated, its volume and security group gone, WEB and AAOS stopped, product configuration hashes unchanged. Calculated cost 3.88 USD of the approved 5 (not yet on a bill; taxes excluded).

## Review 2026-11-10, round 4 (local work before the live run)

Raw data: [review-20261110-round4-local.json](review-20261110-round4-local.json); plan, costs and fixed criteria of the
live GPU run: [GPU-E2E-PLAN-20261110-round4.md](GPU-E2E-PLAN-20261110-round4.md). Nothing in this section was measured
on AWS; no instance was started. The feature stays off.

**Correction of a goal statement.** The handoff of round 3 called “≈ 8–9 s after C” the target for the personal line.
That was wrong: about 8–9 s is roughly how long A+B+C play, i.e. the time the line can be prepared while the user
listens. The goal is that the personal line follows C fluently, with as little waiting as possible. Measured from the
45 WAVs: A+B+C audio lasts 7.28–9.56 s in English (median 8.48 s), 8.64–12.56 s in Turkish (10.56 s) and
8.52–11.40 s in German (10.20 s) over the 125 combinations per language, plus two ≈ 0.13 s pauses — not a fixed time.
(Round 3's “English A+B+C can be as short as 7.5 s” included the pauses: 7.28 s of audio.)

**Validator.** The five lines that round 3 still accepted with wrong content are refused: an unsaid noun after
“your” (“… from your manager” → `adds-unsaid-content`), a negation moved to another topic (“not being worried about
your job” → `negation-moved`; German “…, nicht vor dem Ergebnis” → `negation-not-kept`), a negation further than four
words away (“I do not believe my manager will really support me” → “your manager's support” → `negation-not-kept`; a
negation now covers its whole clause), and swapped Turkish roles (“Annem beni hiç dinlemiyor” → “Anneni hiç
dinlemediğinden” → `role-changed`). The German paraphrases refused in round 3 are accepted: “Umzug” is grounded in
“ziehe” and “hohen” in “hoch” through a closed list of German strong-verb nouns and stems; English inflections
(“moved”/“moving”) count as the same word. Evaluating the change exposed an older bug that the four-word reach had
hidden: any English word ending in “-nt” (“recent”, “different”, “want”) counted as a negation; contractions now need
the apostrophe or come from a closed list. No threshold was widened and no expectation relaxed: the corpus grew from 61
to 80 synthetic cases, and five new counter-examples that are still accepted although wrong are declared as
`knownLimitation` (an unsaid noun used as a modifier, an added part inside a German compound, a listed German stem with
another meaning, a negation without a negation word, swapped roles in English word order). Two correct paraphrases stay
refused (`conservativeReject`: “odaklanma zorluğu”, the synonym “Sorge” for “Angst”).

All 144 recorded real-provider lines (round 2's acceptance runs, 72 per prompt; round 3 re-validated the same rows,
so they are counted once), re-validated offline (no provider call; formal acceptance only, not meaning; tool
`scripts/mental_closing_abc/validator_recorded_lines_eval.py --baseline e71f39c`):

| Lines (24 per language) | Round-3 validator (e71f39c), TR / EN / DE | Round-4 validator, TR / EN / DE |
| --- | --- | --- |
| Current prompt (“6–10 words”) | 24 / 24 / 18 | 24 / 24 / **24** |
| Earlier prompt (*sen*) | 22 / 24 / 16 | 22 / 24 / 20 |

The only changes are 10 German lines, all from refused to accepted (“den Umzug und das Telefonieren mit einer
Freundin” ×6, “hohen Druck bei der Arbeit …” ×4; content labels by the assistant: correct). No line accepted before is
refused now. Still refused, all from the earlier prompt: four German lines of 13 words (two distinct texts; the 12-word contract
is kept) and two Turkish “Kiramı …” lines (first person). These are recorded lines; a new live acceptance run with the real provider is part of the plan (P9).

**AAOS consent case.** Round 3's “consent withdrawn during A” acted on the page's `closing-A-playing` event, ≈ 1.3 s
after A's `play()`, when Android had not reported the app's player as `started` in 3 of 3 runs. The harness now
measures a stop only from a player Android reports as `started`: it polls `dumpsys audio` after the stage and acts at
once when the player is started; if that is not observed within 5 s, the precondition check fails and the case is
reported blocked, never passed. A separate case withdraws consent at the closing's first stage, before any player
starts, and requires that the player is not started at that moment and never starts afterwards. The decisions are in
`scripts/qa/aaos/closing_stop_verdict.cjs` and unit-tested with the player series recorded in round 3
(`tests/unit/aaos_closing_stop_verdict_runtime.cjs`); the emulator run itself needs WEB and AAOS and is part of the plan.

**Closing voice prepared at service start (opt-in, not measured yet).** At start the service warms only its default
model; the first closing then loads the `female-calm-v1` configuration's model (19–22 s on the GPU, 25.9–27.7 s on CPU
in round 3). With `ATTUNE_MENTAL_TTS_WARM_PROFILES=female-calm-v1` the start-up warm-up prepares that configuration too,
after the default model, in the same resident worker. Without the variable the service starts exactly as before; no
product setting was changed. Each warm-up step is logged with its own time (`Resident speech warm-up {...}`, numbers
only) and kept in `warm_log`; a request that arrives during it records the wait as `warm-wait` in its Server-Timing, so
the preparation is never hidden in warm request times. The live run measures cold, prepared and warm closings
separately (P2/P3), and the memory of two resident models (P6).

**Live GPU run: prepared here, run later the same day (next section).** Tools: `remote_resident_bridge.py` / `remote_resident_server.py` (the resident
worker's unchanged line protocol over one private TCP connection; the API, gates, verification and cancellation stay on
WEB), `closing_live_probe.py` (cold / prepared / warm closings per language, warm-up rows, concurrency pairs) and an
optional live mode of the AAOS harness (`CLOSING_LIVE_API`). Scope, costs (≈ 4.2 USD expected, ≈ 5.05 USD at the hard
limits) and criteria: see the plan.

## Review 2026-11-10, round 4: live run (WEB, GPU, AAOS emulator)

Raw data: [review-20261110-round4-live.json](review-20261110-round4-live.json); the raw files (timelines, server and
GPU logs with the 1 s memory series, AAOS assertions, personal-line WAVs, listening samples, cost, read-back hashes)
are in the owner's Drive folder named there. Criteria and limits were fixed before the run in
[GPU-E2E-PLAN-20261110-round4.md](GPU-E2E-PLAN-20261110-round4.md) section 6 and were not changed afterwards; the
numbers below come from `scripts/mental_closing_abc/closing_live_report.py`. Live, replay (round 3) and unit results are
kept apart. The test servers were built from this branch; product services were not touched and the feature stays off.

Path (WEB): system Chrome → the branch's Next test server → test API (product API environment, one-off bearer) → real
provider analysis → GPU synthesis over a private connection (g5.xlarge, only WEB → TCP 8191) → playback in Chrome.
Only the microphone is replaced, by one synthetic non-personal utterance per closing. Same model, weights, reference
voice, FP32 with TF32 off, settings and watermark; hashes verified on the GPU before the server started.

| Criterion | Result |
| --- | --- |
| P1 warm, C ends → personal line ≤ 1.0 s, 8 of 8 per language, ≥ 22 of 24 | **not met**: TR 8/8, EN 8/8, **DE 7/8**, overall 23/24. In de-warm-5 the validator refused the provider's line (`adds-unsaid-content`): written summary kept, nothing spoken |
| P2 prepared start (9 fresh processes) | met, 9/9, C → personal 125–127 ms |
| P3 cold (report only) | 1 process per language instead of the planned 3 (time); C → personal 11.6 / 13.7 / 13.9 s (DE/TR/EN); an earlier stopped attempt's TR cold closing: 23.5 s |
| P4 ready vs played | warm 23/24, prepared 9/9, cold 3/3 |
| P5 errors | 36 analyses and 107 speech responses, all 200; one refused line counted on its own |
| P6 memory, two resident models | met: GPU at most 7,123 MiB of 23,028 MiB; host RSS 7.27–7.48 GiB per worker (first worker 11.15 GiB peak, host has 16 GiB) |
| P7 two simultaneous requests ×3 | met: one 200 (4.45–4.53 s) and one 429 (0.002 s) per pair; no overlapping worker |
| P8 AAOS | timing 5 of 6 (≥ 5 needed); stop criterion **not fully met**: 1 of 11 stop cases not measurable, 1 extra in-flight check failed (below) |
| P9 live provider, 24 per language | TR 20, EN 23, DE 23 accepted (round-3 validator on the same lines: DE 18) |

Warm closings: 24 attempts; P1 failed. Median (min–max) in ms: end tap → A 19; A → B and B → C 126 (n = 24);
C → personal **126 (125–128, p95 128) over the 23 warm closings that produced a personal line** — de-warm-5 had none
(its line was refused) and is not in this number; analysis 2,697 (1,818–3,158; n = 24); speech request 5,516
(4,610–6,330; n = 23), of which speaker verification 2,170 and GPU worker 3,363; `warm-wait` ≤ 0.003. In those 23
warm closings and in all 9 prepared ones the personal line was ready before C ended, by 145–3,588 ms (warm) and
530–2,657 ms (prepared); the margin is smallest in English (warm median 880 ms, minimum 145 ms in en-warm-8, whose
A+B+C was among the shortest), so a slower request or a shorter A/B/C selection there would add waiting. All times
are page media events in the browser (the element's `playing` and `ended` events and the app's timing stages), not
an acoustic measurement of silence at a speaker; the ≈ 0.13 s gap after C is the configured join. Personal-line
WAVs: 35 from the measured run (attempt 3: warm TR 8, EN 8, DE 7, prepared 3 per language, cold 1 per language) and
1 from the stopped attempt 1 (tr-cold-1), kept apart in the archive.
Warm-up rows (never inside a closing's numbers): default 22.7–23.3 s,
female-calm-v1 15.8–16.0 s; process start → warm ≈ 24 s (cold) and ≈ 39.4 s (prepared). Cold female request
19.6–20.6 s: verification 2.2 s, model load 11.7–12.4 s, inference 3.3–3.9 s.

GPU step diagnostic (separate run; its timers synchronize the GPU, so it is not mixed into P1–P8), warm medians:
speech-token generation 2.19 (EN) – 2.87 s (DE), about 75–79 % of synthesis; waveform decoding 0.61–0.63 s;
conditioning 0.065 s; ≈ 25.6 ms per speech token; real-time factor 0.82–0.88. Per-request speaker verification
(bundle re-hash + manifest + approval) is about 40 % of a warm request on WEB; it was kept unchanged. When a closing is
cancelled or refused mid-request the worker is killed and the API re-warms a new one with female-calm-v1 (23.3–23.5 s,
three times in the AAOS run); a closing starting inside that window would wait.

AAOS emulator, live: the WebView's own request went to the branch's real `/api/mental-neural-speech` route on the AAOS
host, then to the test API on WEB (only AAOS → TCP 8190) and the GPU. **Not the product deployment** (no web-aaos on
WEB, no mTLS hop, one-off bearer, park gate fed by a harness mirror); no product-security or OEM conclusion. 18 cases,
71 checks, 69 passed. Complete closings, C → personal: 1,604 / 129 / 128 / 128 / 127 / 127 ms. In the first case the
emulator played every element about twice as fast (personal line over in 1.95 s of 3.84 s audio; Android mixer 82,944
frames per 1 s window against 49,536–50,688 in every other case), which shortened A+B+C to 5.8 s; the sample is kept,
cause not determined. Stops, measured from a player Android reported `started`: 74–221 ms in 9 cases. Failed:
`de-consent-revoked-during-A` — the player was seen started 30 ms after the stage but not at the consent (−2 ms), so the
stop time is not measurable and the case is not passed; `tr-drive-during-C` — the speech request in flight was answered
by the test API's park gate with 409 after 90 ms instead of being aborted (no audio played; the check is kept as
defined). Consent before start: the player never started. No case played closing audio afterwards.

Open: P1 German 7/8; the five declared `knownLimitation` lines; conservative rejects (“odaklanma zorluğu”, “Sorge”,
“worn out”, “Yorgunluktan …”, and “das Vermissen von Freunden”, which round 3 accepted but the user never said); cold
closings without preparation; per-request verification cost; the AAOS consent-during-A stop time; owner listening
approval. Cost of the run (list prices × API timestamps, taxes excluded): AWS ≈ 3.11 USD (GPU 83.5 min, WEB 89.5 min,
AAOS 43.1 min) + provider ≈ 0.1 USD estimated, within the 5.50 USD cap. Final state read from the API: AAOS stopped
first, then WEB; GPU terminated with its volume and security group; the temporary WEB group detached and deleted and
the WEB and AAOS group rules equal to the pre-run snapshot; no extra volume, address or running instance.

## Review 2026-11-10, round 5: open issues closed with the round-4 evidence (no new live run)

Raw data: [review-20261110-round5-followup.json](review-20261110-round5-followup.json); the only plan for further live
work is [LIVE-CHECK-PLAN-20261110-round5.md](LIVE-CHECK-PLAN-20261110-round5.md) (awaiting approval). No GPU or AAOS
was started; WEB ran 19 s to copy the AAOS-phase test API files (verified 10-minute shutdown limit, stopped again,
state read from the API). The round-4 results stand; wording corrections are listed in
`review-20261110-round4-live.json` → `corrections`. The feature stays off; no listening approval.

**Validator** (`services/core-api/mental_analysis.py`; contract unchanged: ≤ 12 words, ≤ 100 characters, no trimming,
the long summary is never spoken). Classes used: *false accept* = accepted although it adds to or contradicts the
user's words; *conservative reject* = refused although faithful, because the rules cannot verify it lexically;
*erroneous reject* = refused although the rules as specified should accept it; *correct reject* = refused and the line
does add, move or change something. Changes, each a closed list or a narrow rule:

- a person the user did not mention is refused, also as a modifier or inside a German compound
  (“manager pressure”, “Chefstress”, “patron baskısı”, “… and your son”);
- negation without a negation word counts (EN *hardly, barely, scarcely, rarely, rare, seldom*; DE *kaum, selten*);
- capitalized three-letter German nouns are content words (round 4 ignored “Zug”, so “den Zug am Abend” passed;
  bare *Zug/Gang* also need a prefix to be grounded in *ziehen/gehen*), and a coordinated part with only a
  three-letter word must rest on a word the user said (“… and the car”);
- irregular English verb forms (“worn” for “wearing”) and Turkish *yorgun/yorul*, *üzgün/üzül* are the same word.

Of the five round-4 limitations four are refused now; swapped roles in English word order stays open, and an unsaid
non-person noun as a modifier (“deadline pressure”, “Terminstress”, “zaman baskısı”) is declared as a remaining
`knownLimitation`. Three further false-accept shapes found on the way (the “Tod”, “car” and “kaum” cases) are refused.
Live rejects of round 4: “worn out” and “Yorgunluktan …” were conservative and are accepted now (content correct);
“… toplantılardan sonra söz ettin” (breaks the recap form) and the two “Kiramı …” lines (first person) are correct
rejects; “das Vermissen von Freunden” is a correct reject of an inference the user never stated; de-warm-5 gets no
meaning label because its line was not returned. No erroneous reject was found. Corpus 80 → 94 cases. Offline
re-validation against the round-4 validator: 144 recorded lines 0 changed, 72 live P9 lines 2 changed (both correct
lines now accepted), 35 WEB live lines 0, 14 AAOS live lines 0 (and the round-4 validator agrees with the API on all
14). Accepting more lines is not the measure; the changes remove wrong-content acceptances without new refusals of
recorded correct lines.

**AAOS, with the round-4 evidence (FAILs unchanged).** *Consent during A:* a harness sampling race. The app paused the
media 22 ms after the consent; the sampler's first `dumpsys audio` (issued 2 ms before, 30 ms long) most likely saw
that pause and read “not started at the action”. Click actions pause after 108–250 ms, so their first sample still saw
the player started. The harness now takes the at-action state from the last snapshot completed before the action and
measures the stop as the completion of the first later snapshot without a started player (an upper bound, stricter
than before); re-analysed this way the round-4 data bound the stop at ≤ 80 ms, which is reported, not counted as a
pass. *Driving during C:* the API's park gate (checked every 100 ms during synthesis) answered 409 90 ms after the
drive, killed the worker and re-warmed; the page saw the motion only at 232 ms (250 ms polling) and closed at 294 ms;
no audio played. That is the server half of the stop chain arriving first. A changed check for driving only (aborted
by the page or refused 409 by the park gate; any 2xx fails) is implemented and unit-tested but needs the owner's
acceptance before it is used. *First case at 2× speed:* page, guest and host clocks agree; the media elements ended
at their true end after half the wall time and the Android mixer wrote 82,944 frames per second-window against about
50,700 in every other case; round 3's first case was normal; the app sets no playback rate. Cause not determined. Every
complete closing now checks its media clock (within 10 %) and an off-clock closing's timing is blocked.

**After a cancelled request.** Any cancel or refusal during synthesis kills the resident worker; the API re-warms only
that request's profile (recovered API rows: 23.98 / 23.86 / 23.61 s for female-calm-v1). A new closing in that window
waits for it; and because conversation replies use the default profile in the same worker, the next reply after a
cancelled closing waits for the re-warm and then loads the default model cold — estimated, not measured, at roughly
40 s for the first spoken reply. Proposed, not implemented: drain the pending reply (bounded, audio discarded, guards
unchanged) instead of killing, or at least re-warm the start-up set after a kill. Speaker hash verification is not
cached.

**Wording corrections to round 4.** C → personal 126 ms (125–128) is over the 23 warm closings that produced a
personal line, out of 24 attempts (P1 failed); the line was ready before C in those 23 and in all 9 prepared ones,
with the smallest margin in English (145 ms); all times are browser media events, not acoustic measurements; the
WAV archive holds 35 lines of the measured run and 1 of the stopped first attempt, in separate folders.

## Review 2026-11-10, round 6 (track A): catalog closing line, checked against the user's own words

Raw data: [review-20261110-round6.json](review-20261110-round6.json); comparison inputs and results in
[comparison/](comparison/).

**What changed.** The personal line after C is no longer generated text or generated speech. The same single analysis
call returns up to three candidates from a reviewed catalog of 33 general meanings
([shared/mental/closing-catalog/v1/catalog.json](../../../shared/mental/closing-catalog/v1/catalog.json)), each with
the index of the user message it rests on and the user's exact words. The server
([mental_closing_catalog.py](../../../services/core-api/mental_closing_catalog.py)) checks every candidate and speaks
only a line that passes; the page then plays that line's prepared recording on the same element as A/B/C. Without a
checked line nothing is spoken and the written summary (unchanged, still personal) is shown. Opt-in per request
(`spokenCatalog`, with `spokenSummary`, legacy engine) and only when the page holds all 33 recordings of the language;
the feature stays off.

**The checks (server side; a quote or one keyword is never taken as proof of meaning).** Known catalog id; the message
is a user message (an assistant suggestion is not the user's statement); the quote occurs verbatim in it; the line's
cue occurs in the quote; no negation of the cue in its clause, including a negation inside the cue's own words ("uykum
hiç bölünmüyor", "my sleep is not disrupted") — a cue that is negative by itself ("uyuyamıyorum", "I can't sleep",
"kimse beni anlamıyor") stays valid; the clause is about the user (first person, or impersonal without another person;
a possessed person — "my mother", "annem", "meine Frau" — is a third person, and after a third person only a subject
pronoun makes the user the experiencer: "My mother is worried about me" is not the user's worry); line-specific
exclusions (pride in someone else is not the user's pride); not past ("eskiden", "used to", "früher") and not "no
longer"; not corrected by a later user message. No inference: "Yalnız yaşıyorum" ≠ loneliness, "çok sorumluluğum var"
≠ strain, "annem beni dinlemiyor" ≠ difficulty expressing oneself; resting ≠ being listened to; a conversation about
good things gets a positive line. Among checked candidates the one the user stressed (emphasis words, repeated
support) wins, then the provider's order. Every line is ≤ 11 words and ≤ 76 characters, one address per language
(TR sen, EN you, DE Sie), and states no diagnosis, advice or evaluation.

**The four content errors of round 5 (free-text validator, kept as a reachable path) are refused, not declared as
known limitations:**

| Case | User | Line | 4b3f596 | now |
| --- | --- | --- | --- | --- |
| EN role reversal | My mother never listens to me. | You talked about never listening to your mother. | accepted | `role-changed` |
| EN added thing (modifier) | There is a lot of pressure at work. | You talked about deadline pressure at work. | accepted | `adds-unsaid-content` |
| DE added thing (compound) | Stress bei der Arbeit belastet mich. | Sie sprachen über Terminstress bei der Arbeit. | accepted | `adds-unsaid-content` |
| TR added thing (modifier) | İşte çok baskı var. | İşteki zaman baskısından söz ettin. | accepted | `adds-unsaid-content` |

On the 265 recorded and live provider lines, only 9 English lines changed (valid → refused), all with "missing …",
which the user had not said; no other line changed.

**Server check, fixed inputs (no provider; a candidate for every acceptable and forbidden line).** Tuning set 51/51
acceptable lines accepted, 54/54 forbidden refused (not independent: the rules were tuned on it). Holdout v1, first
run before any change: 6/18 accepted, **4/9 forbidden refused** — 5 false accepts (pride in someone else ×3, a spouse's
tiredness ×2); after general fixes 12/18 and 9/9 (not independent). Holdout v2, written afterwards and run once: 8/12
accepted, **29/30 refused** (one false accept: "My mother is very worried about my father's health" → worry); after the
third-person fix 30/30 (not independent for that fix). A negation inside the cue's own words ("uykum hiç bölünmüyor")
was found with the harness sentence and fixed; it changed no count above. The remaining misses are deliberate: no
pressure line without the word pressure, no "happy" line for pride in someone else, no goal line for "I want to …"
(too broad).

**Live comparison with the real provider (WEB, product API environment in memory; one analysis per input; 93
analyses).** The first attempt failed in a way that matters: the provider copied the template's placeholder id
("Cnn") in 27 of 28 candidates, so only 1 of 39 expected lines was spoken (kept as `attempt1-template-placeholder-*`).
With the template holding an empty list and the keys named only in the rule:

| Set | Content accuracy | Fitting personal line | Safe abstention | Forbidden spoken | Salience | Written summary topics |
| --- | --- | --- | --- | --- | --- | --- |
| Tuning (48) | 26/26 | 26/39 (TR 10/13, EN 8/13, DE 8/13) | 9/9 | 0 | 3/3 | 43/48 |
| Holdout v1 (18) | 9/9 | 9/15 | 3/3 | 0 | – | – |
| Holdout v2 (27) | 7/7 | 7/12 | 15/15 | 0 | 7/12 | – |

Every spoken line was an acceptable one; the misses are abstentions (the provider proposed nothing in 44 of 93; the
server refused 13 candidates). Of those 13, **8 were forbidden lines the provider proposed** and the server refused
them: an inference ("Ich habe viel Verantwortung, aber ich komme mit allem zurecht" → strain), an assistant suggestion taken as the user's
("Vielleicht fühlen Sie sich einsam?" → lonely), a past state ("eskiden…" → self-doubt), stress put as pressure, and
four statements the user corrected later (tired ×3, worry ×1). 3 acceptable candidates were refused (quote not
verbatim ×2, cue outside the quote ×1) and cost coverage; 2 fitted neither list. Analysis time: first
call of a process 2.7–3.2 s, then median 1.6–2.0 s (provider round trip; not the closing's critical path, which waits
only for C to end). One run per input: repeat runs were not made.

**Recordings.** 99 lines (33 × TR/EN/DE) synthesized once on WEB (`r7i.2xlarge`, CPU, 4 threads) with the A/B/C
profile, model files, reference and settings; one take per line, seeds from the asset id; integrity of the six model
files and the reference identical before and after; 1,184 s of synthesis (median 12.3 / 10.6 / 12.2 s per line for
TR / EN / DE; audio 1.9–5.1 s) plus a 21 s warm-up. Technical findings, recorded and not re-generated: DE_C21 has 3
full-scale samples. Every entry is `technical-preview-awaiting-owner-listening`; nobody has listened to them.

**AAOS emulator, live (WEB test API with the real provider and the CPU worker; branch build 7dcf505 in the real AAOS
WebView; three-state checks; plan fixed before the run: [LIVE-CHECK-PLAN-20261110-round6.md](LIVE-CHECK-PLAN-20261110-round6.md)).**
21 cases: **16 PASS, 4 FAIL, 1 BLOCKED**; plus 45 + 99 recordings byte-identical in the WebView (PASS) and the two
round-5 subjects that no longer exist reported NOT_APPLICABLE.

| Check | TR | EN | DE | Notes |
| --- | --- | --- | --- | --- |
| L1 consent withdrawn during A | PASS (≤ 86 ms) | PASS (≤ 76 ms) | PASS (≤ 103 ms) | fresh `started` snapshot ≤ 150 ms before the action; stop upper bound; no audio afterwards |
| L2a driving during C, analysis held in flight | PASS (≤ 133 ms) | PASS (≤ 162 ms) | PASS (≤ 160 ms) | C stopped; personal recording never started; the held analysis request (3.1–5.1 s) ended aborted by the page; nothing later |
| L2b driving while the reply speech is generated | PASS (page abort) | PASS (409 park gate) | PASS (409 park gate) | 409 with JSON and 0 audio bytes; no player started; nothing later |
| L3 four parts (recorded) | FAIL ×2 (cold, warm) | FAIL | FAIL | A's element duration read as null at `ended` (harness listener order, see below) |
| L3 recomputed offline (labelled) | PASS ×2 | PASS | PASS | A's duration from its `playing` event; elapsed/WAV 0.95–1.03 for all 16 parts; no overlap |
| C end → personal line | 129 ms (cold), 128 ms (warm) | 137 ms | 128 ms | page media events, not acoustics; A→B and B→C 126–131 ms |

Kept controls: cancel during A with the analysis in flight (≤ 191 ms, request aborted), cancel during the catalog line
(≤ 191 ms), mute during C (≤ 189 ms), background during B (≤ 145 ms) and during the catalog line (≤ 80 ms), cancel
during B then a new conversation (≤ 160 ms), language locked during B: PASS. Consent withdrawn at the closing trigger:
**BLOCKED** — a started player of the app was already reported 8 ms before the action, so the precondition "not yet
started" was not met; nothing of the closing played afterwards and the analysis request was aborted, but the case is
not counted as passed. Every complete closing spoke the server-checked line C09 (sleep) for the synthetic sentence and
sent no closing-voice request; the analysis took 2.4–3.2 s and was ready before C ended.

**Why L3 failed as recorded.** The closing plays A, B, C and the line on one shared element. For A, the product's own
`ended` handler (registered before the harness started watching the element) resets the source before the harness
listener reads `duration`, so A's duration was recorded as null and the rule reported "not the expected recording".
B, C and the line were read correctly. The rule now takes the element's duration from its `playing` event in that
case and reports a part with neither as BLOCKED, never as FAIL or PASS (commit 8cfbff8, unit-tested). The recorded
verdicts are kept; the recomputation above is labelled and uses only recorded events.

**Window and cost.** Before starting: no other instance running, no active remote session, no remote command on these
hosts since this tooling's last one, no foreign process or work directory (the other track did not use them). WEB
22:14–23:03 UTC (49 min of 75), AAOS 22:28–23:02 (34 min of 60), each with a verified OS shutdown timer and a local
guard; started WEB first, stopped AAOS first. Temporary group (TCP 8190 from the AAOS group only) 22:43–23:02, deleted,
WEB's groups restored and no 8190 rule left; product configuration hashes unchanged; both instances stopped (read by
API). Cost ≈ 0.52 + 0.29 USD for the instances plus ≈ 0.12 USD estimated provider calls ≈ **0.93 USD** of the
1.50 USD cap (list prices, taxes excluded, not yet on a bill).

**Not done.** Repeated live comparison runs (one analysis per input); listening approval (nobody has listened to the
99 lines); a live crisis conversation (crisis sessions never start the closing, unit-tested); the recorded L3 cases
were not re-run with the corrected rule. Track B is pending; the comparison stays open until it is measured on the
same inputs.

## Tests

`tests/unit/test_mental_closing_bridge.py` (assets, manifest, hashes, profile pins, approval state) runs `mental_closing_bridge_runtime.cjs` (gate, single selection without repeats with all 125 reachable, A→B→C order without overlap, overlap of preparation, next-part prefetch, honest waits, cancel/session/mute/hidden/language, altered/failed assets) and `mental_closing_finish_runtime.cjs` (real `finish()` for normal and structured paths, fallback, summary failure, consent withdrawal, cancel, failed/empty sessions). `tests/unit/test_mental_spoken_summary.py` covers the short line (bounds, language, address, grounding, bridge phrases, advice/evaluation, no truncation, one provider call, template and recap form, opt-in API flag). `scripts/qa/mental_closing_bridge_timeline.cjs` (replay or live mode, `mental_closing_bridge_scenarios.py` builds scenarios from measurement rows), `scripts/mental_closing_abc/closing_realpath_probe.py`, `closing_live_probe.py`, `spoken_summary_probe.py` and `scripts/qa/aaos/aaos-mental-closing.cjs` produced the 2026-11-10 measurements. Round 2 adds `tests/unit/fixtures/mental_spoken_summary_cases.json` (formal vs content), `tests/unit/vehicle_polling_runtime.cjs` and a page/hook check that the completion guidance is skipped after a spoken closing. Round 3 adds the negation, coordinated-part and first-person cases to that corpus (61 cases; accepted-but-wrong and refused-but-correct lines must both be declared) and `scripts/mental_closing_abc/tts_device_benchmark.py`, which produced the CPU/GPU comparison. Round 5 adds the round-4 recorded AAOS series to `tests/unit/aaos_closing_stop_verdict_runtime.cjs` (pre-action sampling rule, upper-bound stop, driving in-flight rule, media clock) and 14 validator cases (94). Round 4 adds `tests/unit/test_closing_live_probe.py` and `tests/unit/test_closing_live_report.py` (warm-up gate; the 8-of-8 rule and blocked samples), the five round-3 limitations as refused cases, the German stem cases and new declared limitations (80
cases), `tests/unit/aaos_closing_stop_verdict_runtime.cjs` (AAOS stop decisions on recorded player series),
`tests/unit/test_mental_remote_resident.py` (remote worker bridge with a stub model), warm-up tests in
`tests/unit/test_mental_neural_resident.py` and `scripts/mental_closing_abc/validator_recorded_lines_eval.py`.
