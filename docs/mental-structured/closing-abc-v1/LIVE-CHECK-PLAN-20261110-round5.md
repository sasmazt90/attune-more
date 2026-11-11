# Targeted live checks after round 5 (plan only, awaiting approval)

Round 5 changed the validator, the AAOS harness's stop sampling and checks, and nothing in the product's speech or
playback path. Most open questions were settled with the round-4 evidence (see
[review-20261110-round5-followup.json](review-20261110-round5-followup.json)). This plan lists only the live checks
that local work cannot replace. Nothing here runs without the owner's explicit approval of scope, limits and cost; the
broad round-4 runs are **not** repeated.

## Not repeated, and why

| Round-4 check | Why no new run |
| --- | --- |
| P1/P2/P3 WEB closings | Speech and playback code unchanged. The validator change was evaluated offline on every recorded line (144 recorded, 72 live P9, 35 WEB live, 14 AAOS live): only 2 lines changed, both correct lines now accepted. P1's German 7/8 is a refused provider line, not timing; a re-run would only re-draw provider lines. |
| P6 memory, P7 concurrency | Unchanged code; met in round 4. |
| P9 provider acceptance | Recorded lines re-validated offline; no new provider calls needed for the validator change. |
| GPU diagnostic | Unchanged model and settings; no new GPU. |

## Needed live checks (no GPU)

Hosts: the existing AAOS emulator and WEB only. AAOS depends on WEB: WEB first, then AAOS; stop AAOS first, then WEB.

| # | What | Why it needs a live run | Samples | Criterion (fixed before the run) |
| --- | --- | --- | --- | --- |
| L1 | Consent withdrawn during A, with the round-5 sampling rule (at-action state from the last snapshot completed before the action; stop = completion of the first later snapshot without a started player, upper bound) | The round-4 stop time was not measurable because of the sampling race; only a new run can measure it | 3 (TR, EN, DE), replay speech (no GPU needed: A is a recorded clip) | Each: pre-action snapshot shows the app's player started (≤ 150 ms before the action), upper bound ≤ 1,000 ms, no closing audio afterwards. A case without that snapshot is blocked and counts as failed: 3 of 3 needed |
| L2 | Driving during C while the closing-voice request is in flight | Tests which half of the stop chain arrives first (page abort or the API's park gate 409) with the real route and API | 3 (TR, EN, DE). Live speech from a test API on WEB with the CPU worker (no GPU): synthesis is slower there, so the request is reliably in flight during C | Player leaves `started` ≤ 1,000 ms after the backend acknowledgement (upper bound); no closing audio later, also after returning to the app; every request in flight ends aborted by the page **or refused 409 by the park gate** — this second option is a proposed change of the round-4 check and applies only if the owner accepts it before the run; otherwise the round-4 check applies unchanged. Any 2xx answer fails. 3 of 3 needed |
| L3 | Media clock of the emulator | The 2× playback of round 4's first case happened once; the new per-element check must see a run | Built into every complete closing of the session (L1/L2 sessions start with one complete, unmeasured warm-up closing, then one measured complete closing per language) | Every element's `playing` → `ended` time within 10 % of its duration; otherwise that closing's timing is blocked (counted, not dropped) |

Optional, only after an owner decision on the post-cancel proposal ([review-20261110-round5-followup.json](review-20261110-round5-followup.json), `rewarmAfterCancel`):

| # | What | Samples | Criterion |
| --- | --- | --- | --- |
| L4 | “Drain instead of kill” after a cancelled closing: time until the next closing's personal line is ready, and the next conversation reply | Implemented and unit-tested first; then on WEB's CPU worker: 3 × (cancel during C, new closing 5 s later) and 3 × (cancel during C, conversation reply 5 s later), each against the current behaviour | Reported only (no pass/fail); no audio from the cancelled request ever plays; guards (park, consent, disconnect) keep refusing during the drain |

## Limits and cost (to be approved)

WEB r7i.2xlarge ≤ 75 min and AAOS m8i.2xlarge ≤ 60 min, each with a verified OS shutdown timer and a local stop
guard; no GPU, no new security group rule except, for L2 only, the round-4 temporary group on WEB that admits TCP 8190
from the AAOS group (removed afterwards, WEB's network configuration verified). List prices (eu-central-1): WEB
0.6384 USD/h, AAOS 0.50716 USD/h → at the limits ≈ 0.80 + 0.51 ≈ 1.31 USD plus provider calls (≈ 10 analyses,
≈ 0.01 USD); proposed cap 1.50 USD + tax. Evidence to a new Drive folder with read-back hashes; earlier evidence kept.
No listening approval is implied.
