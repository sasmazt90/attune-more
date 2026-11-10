# Round 6 (track A): catalog closing — test plan, recording time and cost (fixed before any AWS resource is started)

Track A only. No GPU, no "drain instead of kill", no model change, no merge, no deployment; the feature stays off.
Hosts: the existing WEB (`r7i.2xlarge`) and AAOS (`m8i.2xlarge`) instances only. The other track does not run on them;
before the start the window checks that no other instance runs and that neither host shows another experiment
(processes, work directories, recent remote commands not from this window); if one does, the window is not opened and
nothing of that work is stopped.

## What changed and what must be measured anew

The personal closing line is no longer generated speech. The analysis call returns up to three catalog candidates
(line id, user message index, the user's exact words); the server checks each against the conversation and, if one
passes, returns the fixed line. The page plays that line's prepared recording after C on the same element. Without a
checked line nothing is spoken; the written summary is unchanged. Earlier GPU and round-4 timings are not results of
this path and are not reused.

## Order of work

1. Local (done before the window): code, catalog, unit tests, CI on the pushed commit.
2. WEB on: preflight (no other experiment), clone of the tested commit, **one-off synthesis of the 99 catalog lines**
   (`synthesize_closing_catalog.py`: same pinned Chatterbox source, model files, `female-calm-v1` reference and
   generation settings as the 45 A/B/C clips; one take per line; language by language; a deadline stops between clips
   and leaves whole languages). Nothing else measures on WEB while it runs.
3. After synthesis: pull the WAVs and the record to this container (hash-checked); live comparison of the catalog
   selection with the real provider on WEB (product API environment read in memory; content metrics; timing
   reported only from this run); then `build_closing_catalog_manifest.py`, unit tests, commit, push.
4. AAOS on (started so that its boot overlaps the end of synthesis); temporary security group on WEB that admits only
   the AAOS group on TCP 8190; test API on WEB (branch code, product API environment in memory, local CPU worker,
   default and closing voice warmed at start); branch build on AAOS; harness `CLOSING_ROUND=6`.
5. Close: AAOS results pulled, AAOS stopped; WEB logs pulled, temporary group removed and WEB's network configuration
   verified, WEB stopped; final state read by API. Evidence to Drive (new folder), read back and hash-checked.

## AAOS cases (TR/EN/DE) and criteria (fixed now)

Outcomes: PASS, FAIL, BLOCKED (precondition or evidence missing; counts against the criterion), NOT_APPLICABLE (the
subject no longer exists; never shown as PASS). Earlier FAIL records stay as recorded.

| # | Case | Criterion |
| --- | --- | --- |
| L1 | Consent withdrawn during A (×3) | Android reports the app's player `started` in a snapshot completed ≤ 150 ms before the action; stop upper bound ≤ 1,000 ms; no closing audio afterwards. No fresh `started` snapshot: BLOCKED |
| L2a | Driving during C, catalog closing (×3); the analysis answer is held by the harness (labelled) until 6 s after C starts, so it is in flight | C stops (upper bound ≤ 1,000 ms after the backend acknowledgement); the personal recording never starts; the held analysis request ends aborted by the page; nothing plays later, also in the returned app. No analysis request in flight: BLOCKED |
| L2b | Driving while the conversation reply's speech is generated live (dynamic speech path that remains; ×3) | The speech request ends aborted by the page, or with a 409 from the route **with evidence of the park gate** (JSON answer, no audio bytes; the route answers 409 only for its backend's park/authentication gate, a client cancel is 499 there); no player starts; nothing plays later. Only the analysis or nothing in flight: BLOCKED. A 409 without that evidence, or any audio: FAIL |
| L3 | Every complete closing (TR cold, TR/EN/DE warm) | A, B, C and the personal line: each exactly once, each with its own `playing`/`ended` stage matched by a media event of the closing element; elapsed time within ±10 % of the part's own WAV duration (manifest); each part starts after the previous one ended. Missing part, event or duration: BLOCKED (never filtered into a pass); another element's sound never stands in. Also: the personal line is the checked catalog recording, and no closing speech request is made |
| C→P | C end → personal line start, cold and warm reported separately | Reported (median, min, max per language); no pass criterion is attached to a new number |
| Kept | Mute during C; background during B and during the catalog line; cancel during A (analysis in flight), during the catalog line, during B then a new conversation; consent before start; language lock during B | As in round 5 (stop, nothing later, no extra sound); crisis sessions never start the closing (unit-tested; no live crisis text is sent) |
| N/A | Round-5 "drive during summary" (closing-voice request in flight) and its 409 check | No closing-voice request exists on the catalog path: NOT_APPLICABLE, replaced by L2a and L2b |

All 45 A/B/C and all 99 catalog recordings must reach the AAOS WebView byte-identical to their manifests.

## Comparison (shared starting corpus kept)

Fixed inputs in `comparison/`: the 48 tuning inputs, holdout v1 (first run recorded before any change), holdout v2
(written after the tuning, run once). Reported together: content accuracy, rate of a fitting personal line, rate of
safe abstention (a solution that refuses everything does not pass), written summary coverage, the line's grounding
(the server checks), the audio transition (L3, C→P) and cold/warm start. Track B: pending until its results exist.

## Time

Synthesis estimate from the A/B/C run on the same host (seconds of synthesis per character of text, 4 threads):
TR 503 s, EN 399 s, DE 519 s → **≈ 24 min** for 99 lines (+ ≈ 25 s warm-up); bound used for planning 30 min.

| Minute (from WEB start) | WEB | AAOS |
| --- | --- | --- |
| 0–5 | start, OS timer armed and verified, preflight, clone | off |
| 5–35 | synthesis (nothing else measured on WEB) | start ≈ 28, boot |
| 35–41 | pull WAVs ‖ live comparison (provider); local manifest, tests, commit, push | preflight |
| 41–45 | fetch commit, test API (warm-up), temporary group | fetch, build, serve |
| 45–63 | test API serves the AAOS cases | harness: 21 cases + asset parity (≈ 18 min) |
| 63–70 | logs pulled, group removed and verified, stop | results pulled, stop (≈ 42 min used) |

Limits (hard, from each instance's own start): **WEB ≤ 75 min, AAOS ≤ 60 min**, each with an OS shutdown timer at the
limit (verified after arming; if it cannot be verified the instance is stopped at once) and an independent local stop
guard. Closing margin: work that would end later than 5 min before a limit is not started; it is reported as not done.
No second window is opened on my own.

## Cost (list prices, eu-central-1, queried 2026-11-10)

| Item | Rate | At the limit | Expected |
| --- | --- | --- | --- |
| WEB r7i.2xlarge | 0.6384 USD/h | 75 min → 0.80 USD | ≈ 70 min → 0.74 USD |
| AAOS m8i.2xlarge | 0.50716 USD/h | 60 min → 0.51 USD | ≈ 42 min → 0.36 USD |
| Provider calls (≈ 93 comparison + ≈ 25 AAOS analyses, ≈ 4k input tokens each with the catalog) | gpt-4o-mini list price | ≈ 0.10 USD | ≈ 0.08 USD |
| Temporary security group, existing volumes | no extra charge for the group; volumes are billed whether on or off | — | — |
| **Total** | | **≈ 1.41 USD** | **≈ 1.18 USD** |

Cap: 1.50 USD plus tax, not transferable to the other track. Not on a bill yet when reported; taxes excluded.

## Not part of this round

GPU, "drain instead of kill", a model change, merge, deployment, enabling the feature, listening approval on the
owner's behalf (every new recording stays `technical-preview-awaiting-owner-listening`).
