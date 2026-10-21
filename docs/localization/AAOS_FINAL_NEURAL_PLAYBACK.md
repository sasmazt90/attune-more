# Final neural playback blocker — run 39632276829

Scope: Mental neural output and its existing acceptance observer only. Failed
source: `9cadcf9bf4fd1a5533f5fe1ccd19405890c485fb`. No emulator run, merge or
deployment was launched during this correction.

## Evidence and root causes

The complete job log (job 119333411589) and 298-member evidence artifact were
inspected. Artifact `aaos-39632276829-1`, ID 12361074433, is 12,396,809 bytes;
SHA-256 `ad83bf0d90d64c9d131bc8d9c91aa730ed797ecaa8f8664917526fca494865dc`.
ZIP CRC passed. Original evidence is retained outside Git in
`/workspace/attune-aaos-neural-final-20261021/evidence`.

| Finding | Evidence / source | Cause and correction |
| --- | --- | --- |
| TR/DE returned valid HTTP 200 but zero playback starts | `mental-neural-audio.json`; `backend.log:2024–2025,2656–2657`. TR worker 152.701s, DE 134.714s, both exit 0. Original client created a new Audio after fetch; original `fixedFileSpeech.ts:36` swallowed play rejection. `MainActivity.java:232` requires a media gesture. | The harness clicked a heading **before** long synthesis, losing transient activation. Strict Cloud Chromium reproduced `NotAllowedError`, zero starts after 6s; immediate playback passed. Add a visible, localized user play action when autoplay rejects, keeping the same WAV and live guards. The historical AAOS rejection name was not logged; the mechanism is source-supported and reproduced, not a directly captured AAOS exception. New stage evidence distinguishes it. |
| EN 504 | `backend.log:2385–2386`: last phase inference at 36.611s; parent deadline 180.278s; worker killed/reaped with -9. `mental_neural_tts.py:212–213,235–237`. | Backend worker deadline expired **during inference**, after initialization. Proxy propagated it; no EN WAV reached the browser. Requests were sequential (`validate_emulator.py`, Mental neural loop). The EN-only fixture had 51 words/269 characters including the interruption instructions; TR/DE were short single utterances. Use a comparable short EN utterance for this finite transport/playback check; keep actual interruption assertions against its current-run generated WAV. No worker/proxy/client timeout increase or model change. Long-form CPU capacity remains unverified and can still time out safely. |
| Conflicting application deadline (also review 4339112774) | Original `useMentalConversation.ts:159` aborted every ordinary speech call at 100s, despite shared 180/185/190s worker/proxy/client budgets. The observer calls the client directly. | This was **not** the cause of the run's 180s EN request, but would abort legitimate long responses in the actual conversation. Remove only the neural path's competing outer timer; retain existing finite generation and playback deadlines, fixed-clip/browser/crisis limits and live cancellation. |
| Delayed response-body evidence read | Focused corrected Cloud run returned 200 and completed playback, then CDP `Network.getResponseBody` reported no data. Original observer read bytes only after playback. | Capture the response body immediately on the response event. If unavailable, preserve observed playback/stages and report evidence BLOCKED. Clear retained EN bytes before every new EN attempt; never substitute a prior response. |
| Interruption/console downstream results | Run `results.json:88–100`: interruptions BLOCKED by neural failure; console contained this same EN 504. | These are downstream results, not additional proven Car, Hearing, navigation, decoder or lifecycle defects. Retain the existing interruption and console gates. |

Worker phase durations in the failed run:

| Language | Model construction | Inference | Outcome |
| --- | ---: | ---: | --- |
| TR | 22.061s | 114.961s | HTTP 200, no browser start |
| EN | 19.162s | at least 143.389s of available inference time, incomplete | HTTP 504 |
| DE | 19.163s | 101.117s | HTTP 200, no browser start |

No retained evidence proves an independent OOM, worker crash before the deadline,
or exact CPU contention contribution. Cold model initialization completed for
all three. Initialization overhead contributes to the budget but does not explain
the entire EN overrun. The short corrected EN check does not prove that the old
269-character utterance now fits.

## Changes

- `fixedFileSpeech.ts`: optional real-user gesture callback only on native
  `NotAllowedError`; bounded wait; live admission rechecked synchronously at each
  click; UI removed and source cleared on finish/abort. A stale callback cannot
  restart cancelled output. Other decoding/play errors still fail.
- `mentalNeuralSpeech.ts`: passes that callback through and reports content-free
  response/gesture/playing/ended stages. No extra synthesis on the play action.
- `useMentalConversation.ts`, Mental page, message catalog: TR/EN/DE play-response
  button and removal of the conflicting neural-only 100s timer. UI cleanup follows
  the existing audio epoch/controller lifecycle.
- `localized_webview.cjs`: same callback contract with a visible observer button
  and trusted Playwright click outside the microphone conversation; short EN
  fixture, stage timings and early current-run response retention. No native
  autoplay-policy changes, mocked inference, fabricated media events or retries.
- Focused client/conversation/playback and observer regressions cover the change.

## Executed Cloud verification

- 75 focused frontend/API/worker/acceptance tests passed; one existing third-party
  Python deprecation warning. The new actual playback lifecycle test executes 11
  explicitly synthetic media/time cases: gesture, decoding, timeout, abort, mute,
  background, consent, motion, locale, session and no-UI fallback behavior.
- Six Node observer policy/evidence tests passed, including body-read ordering,
  unavailable evidence preservation and rejection of stale retained EN output.
- Zero frontend ESLint warnings/errors; typecheck and isolated production build
  passed. Localization consistency and focused frontend follow-up checks passed.
- Strict-policy Chromium probe: retained real TR WAV, controlled 0/6s HTTP latency.
  Before: 6s + `user-gesture-required` => `NotAllowedError`, false, zero starts.
  After: same bytes/policy => trusted play click, true, exactly one start.
  These latency fixtures are explicitly **not new inference**.
- **Actual pinned V3 inference, default conditioning, EN** through the isolated
  authenticated backend → same-origin production proxy → current observer:
  HTTP 200 at 58.731s, response-ready 58.728s, gesture-required 58.733s,
  playing 58.799s, ended 63.720s. `played=true`, `starts=1`.
  Strict `user-gesture-required` policy; no autoplay bypass flag.
- New WAV: 238,124 bytes; mono PCM16/24kHz, 4.96s; valid decoding/nonzero PCM;
  SHA-256 `85899ab01b21770d94bda560b2395e5e5ef93380439dedb21f0f56ac046fd59c`.
  Path: `/workspace/attune-aaos-neural-final-20261021/real-strict-browser-ready/en.wav`.
- Actual current observer mute, cancellation, language switch and consent
  withdrawal: PASS with that same new WAV, exactly one initial start, paused/source
  cleared, no restart after restoring conditions (1.5s observation).
  Zero page errors/capture attempts. Owned services stopped; unrelated processes
  untouched. Full microphone/LLM conversation was not exercised.

Cloud logs, JSON observations, the original/updated gesture probe, screenshot and
WAV are retained under `/workspace/attune-aaos-neural-final-20261021/`.

## Acceptance boundary and next gate

Corrected-source AAOS playback and native motion/session interruption remain
UNVERIFIED until one owner-authorized run completes. Historical automotive,
Hearing and original-audio passes remain historical evidence. Neither Cloud
Chromium nor media fixtures establish AAOS or physical listening acceptance.

The change is prepared for the existing finite **short-utterance** acceptance, not
unbounded long-form synthesis or guaranteed inference latency on every CPU load.
No claim that the original long EN request is repaired is made. The hard worker
deadline and unavailable/error path remain enforced. Do not silently broaden
that claim or retry a failed run automatically.

Use `e2e-audit.yml`, branch `feature/localization-en-de-tr-20261020`,
`expected_source_sha` equal to the final verified PR HEAD, only after owner
authorization. Existing standard Ubuntu, 40-minute, 50 MiB, one-day retention,
no paid service and no automatic retry limits are unchanged. All 194 approved
recordings, health/Hearing scoring, crisis policy, data/consent formats, Android
gesture rule and production configuration are unchanged.
