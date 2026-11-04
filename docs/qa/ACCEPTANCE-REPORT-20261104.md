# Attune.more release candidate: acceptance report

**Release candidate `4bb51b3`, 2026-11-04.** Written by Claude, who built and tested it, so this is not an independent
review. Antigravity's review is the next step, and nothing is merged.

## Result in short

All 12 English videos were recorded on one commit, and every journey's automated checks passed. All of this used reference
photos, synthesized speech, a scripted listener and an emulator with simulated vehicle data.

**A pass here means the flow works and the checks held. It says nothing about clinical or detection accuracy**, which stays
NOT VERIFIED everywhere because no labelled ground truth exists for these runs. On Skin and Dental, comparing the
photos with the results by eye found likely misses, listed under [Findings register](#findings-register).

Five things need the owner's decision. They are listed under [Decisions for the owner](#decisions-for-the-owner).

## Final acceptance matrix

| Module and platform | Functional E2E | Result completeness | Accuracy | Model contract | Responsive UI | Persistence and history | Audio and video | Physical | Recording |
|---|---|---|---|---|---|---|---|---|---|
| Skin WEB | PASS | PARTIAL | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Skin AAOS | PASS | PARTIAL | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Vision WEB | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PARTIAL |
| Vision AAOS | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PARTIAL |
| Dental WEB | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Dental AAOS | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Mental WEB | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Mental AAOS | PASS | PARTIAL | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing digits-in-noise WEB | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing digits-in-noise AAOS | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing pure-tone WEB | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing pure-tone AAOS | PASS | PASS | NOT VERIFIED | NOT VERIFIED | PASS | PASS | PASS | NOT RUN | PASS |

Why the cells that are not PASS say so:

- **Skin result completeness:** "Unclassified spots" reports `NOT_VALIDATED`, and pores are not executed. Both are stated on
  screen or in the contract, not hidden.
- **Vision recording:** "Specialist options" is on the result screen, but the recording does not open it.
- **Mental AAOS result completeness:** in turn 5, the app stopped listening at a pause and kept 9 of the clip's 27 words.
  See the findings register.
- **Model contract:** MATCH needs both an approval on record and runtime proof. Skin has the runtime proof but no approval
  records for most indicators. Only Skin was in scope for this audit.
- **Physical:** nothing here used a physical camera, microphone, person or vehicle.

## Videos

| Platform | Journey | File | Seconds | MB | Result | Link |
|---|---|---|---:|---:|---|---|
| WEB | Skin | WEB_Skin_EN_E2E.mp4 | 116 | 5.0 | PASS | [Open](https://drive.google.com/file/d/1AFoHasgULOZz4CYoXrVdD7or-6knAN9s/view) |
| WEB | Vision | WEB_Vision_EN_E2E.mp4 | 236 | 3.3 | PASS | [Open](https://drive.google.com/file/d/1RwACXmewfP9aB5tfbFM7qCu7qE2c84xS/view) |
| WEB | Dental | WEB_Dental_EN_E2E.mp4 | 73 | 2.3 | PASS | [Open](https://drive.google.com/file/d/1EOIi-GzwaI7eLVypTjmWbTrJWgjuSvGD/view) |
| WEB | Mental | WEB_Mental_EN_E2E.mp4 | 233 | 9.1 | PASS | [Open](https://drive.google.com/file/d/11OVM1JlBZMLVlzkP_36NoPbDFzZqOioK/view) |
| WEB | Hearing digits-in-noise | WEB_Hearing_digits_in_noise_EN_E2E.mp4 | 105 | 3.0 | PASS | [Open](https://drive.google.com/file/d/1jFZGapSyI9jgw03DILMHBMhrRgtx_sh4/view) |
| WEB | Hearing pure-tone | WEB_Hearing_pure_tone_EN_E2E.mp4 | 476 | 11.9 | PASS | [Open](https://drive.google.com/file/d/1Zdb7T1GHuYjpT_-8pAE5l6TWkfNBorOZ/view) |
| AAOS | Skin | AAOS_Skin_EN_E2E.mp4 | 140 | 8.3 | PASS | [Open](https://drive.google.com/file/d/1x49sIt8qHRwwY-4FJakY6mf_Qq6_8L6_/view) |
| AAOS | Vision | AAOS_Vision_EN_E2E.mp4 | 264 | 4.8 | PASS | [Open](https://drive.google.com/file/d/1vUjTWyH_BpHtDnwhJi0ZJt4BqZKG5tsB/view) |
| AAOS | Dental | AAOS_Dental_EN_E2E.mp4 | 93 | 5.2 | PASS | [Open](https://drive.google.com/file/d/1IqmIUINDqRozcM2aDq7nvz_X2MnuTiqD/view) |
| AAOS | Mental | AAOS_Mental_EN_E2E.mp4 | 216 | 11.6 | PASS | [Open](https://drive.google.com/file/d/1jpKXJUhx5g7G5zv3iFpM4eeRJknUsE1Y/view) |
| AAOS | Hearing digits-in-noise | AAOS_Hearing_digits_in_noise_EN_E2E.mp4 | 115 | 4.9 | PASS | [Open](https://drive.google.com/file/d/1F0W38aiERSUNTy1lFsuWi9oARVS8evQr/view) |
| AAOS | Hearing pure-tone | AAOS_Hearing_pure_tone_EN_E2E.mp4 | 489 | 14.5 | PASS | [Open](https://drive.google.com/file/d/1n5YBGmP2xWSBQ40Lxny1OhBLpIFsG8V7/view) |

All are 1280x800 at 12 fps, with audio present. AAOS videos show the emulator's whole display, including the test build's
toolbar. Its "Camera: unavailable" refers to the emulator's own camera; the reference photos arrive through the demo camera
bridge.

Recorded in two sittings on the same commit, because the AWS sign-in expired partway. No journey needed a second attempt on
this commit. The pure-tone videos do not show the consent dialog, because Hearing consent was given in the digits-in-noise
run on the same platform.

### How delivery was checked

Everything is in [the Drive folder](https://drive.google.com/drive/folders/1LsbiNKlGinJUD5_gFSa2-SpHbtjJkmQa). For all 12 videos:

- **Size on Drive's servers matches the local file, read through the Drive API.** Done.
- **SHA-256 of the copy on the Drive folder matches the source.** Done through Drive for desktop, which may serve its local copy.
- **A full download back from the cloud, hashed.** **Not done.** The files are private, and the browser here is not signed in to
  Google. Hashes are in `videos.md`, so anyone downloading them can compare, and Antigravity's review should.

The earlier ten videos were not touched.

## What each module showed

### Skin labels (the owner's brief of 2026-11-04)

Checked on real results, reading the live page: **WEB 594 states at 9 sizes, the real AAOS WebView 396 states at 6 sizes**,
each in EN, DE and TR. All checks passed:

| Check | Result |
|---|---|
| Every drawn finding and marker is in the stored result, on its own photo | PASS |
| Default overview: all located findings, nothing selected | PASS |
| Selecting shows only that finding and highlights its card; deselecting restores | PASS |
| No label overflow, overlap or off-screen placement in EN, DE or TR | PASS |
| Every size under test was really applied | PASS |
| Findings sit on a clean photo | PASS |
| Lines stay short | PASS |
| Stored results are unchanged by the labels | PASS |

Models, thresholds, scores and counts did not change. Coordinates come straight from the stored result, and the distance
between each ring and its stored coordinate was under 1 px in every state.

**One difference from the reference images, on purpose.** They show four labels on one photo. Real results often show three,
because a finding measured on a side photo is not moved onto the front photo. For example, Redness on Character 11 was
measured on the side photos. Its card still shows the value, a note under the photo names it, and selecting the card switches
to the photo it was measured on. The brief asks for exactly this: never transfer a finding onto the wrong photograph.

Layout requested by the owner: region arrows sit either side of the photo, the repeated title on the right is gone, finding
counts are proportional, and Dental follows the same pattern. The top bar is one row from 1024 px at any height. At 800 px it
cannot fit, so its controls wrap to a second row.

### Vision

Both platforms were read back from the stored records: **24 valid trials, 12 per eye, exactly one "can't see it"**. Speech went
through the real microphone path and real recognition, with 25 transcripts per run, all status 200. One trial per run needed a
second attempt with a code word.

Scores recomputed from the spoken answers match the result screen and saved history: right eye 83/83, left eye 83/92. The two
platforms show the same percentages because the pattern of correct and wrong answers is scripted the same way. The letters
shown differ. Every Results-by-size section was opened in the recording. Per-trial detail is in `vision-scoring-matrix.md`.

### Dental

**The original female photos, on the real AAOS WebView: all four views measured**, including the supplied BITE photo that used
to be rejected. It is accepted as a closed bite with the note "Discoloured teeth lowered the confidence of the bite check".
This is not a WEB emulation or a substituted photo: the viewport is the emulator's 1280x564, the input hashes match the supplied
files, and the woman in the reference photos is visible in the camera preview in the video.

The gate was not simply loosened. Thresholds .04, .60 and .50 are unchanged. Open-mouth controls and constructed gaps are still
rejected. Details are in `dental-bite-findings.md`.

### Mental

A whole five-turn conversation on each platform, with real recognition, language model and speech. Language was clean. From
the end of speech to the start of the reply:

| Stage | Before | Now |
|---|---|---|
| Speech recognition | | about 1 s |
| Language model | | about 1 s |
| Speech generation | about 70 s | 16 to 23 s for these replies |
| End of speech to reply starting | | 18.6 to 24.9 s, leaving out the turn cut at a pause |

Short sentences have a median of 9.1 s (n=14), and the first after a restart takes 28.3 s. The voice is the same, with the same
weights. This is much better and still slow for conversation. Going further needs sentence streaming or a GPU, neither of
which is provisioned.

Language was also checked through the API in TR, EN and DE: no mixed-language text, including the reported "feeling Gergin".

### Hearing

Both protocols completed on both platforms. Digits-in-noise: 24 trials, 50 of 72 digits, 13 of 24 triplets, -7 dB SNR.
Pure-tone: 14 levels across both ears with 0 catch-trial false positives. Leakage between channels stayed at -100 dB or lower. **The
responses come from a scripted listener, so this proves the flow and the audio path, not anyone's hearing.** Levels are
uncalibrated digital levels and are not presented as clinical thresholds.

### Appointments, persistence and camera states

- **Appointments:** no region is assumed, the region is independent of the UI language, and opening a provider saves nothing. The
  person confirms the booking. The form has no meeting link. Local time is shown, not UTC. Edit and delete hold, and deleting
  says the provider's booking is not cancelled.
- **Persistence:** save, history, refresh, re-entry, a real host Stop and Start, history, delete. No duplicates, and deletions
  stayed deleted. 11 of 11 checks on each platform.
- **Why records looked like zero (QA-16):** proven live. With saving left at its default, a complete Skin scan shows full results
  and saves nothing, and the screen did not say so. It now does. Records are also per browser profile and origin, so WEB and AAOS
  never share them.
- **Camera states (QA-33):** fresh entry, camera unavailable, retry, waiting and live, on Skin and Dental, on both platforms. The
  saved-record text never appeared in a live scan. The camera refusal is injected in that journey only, never in a recording.
- **PARK and DRIVE:** 7 of 7 native gates passed on the real Android app, against simulated vehicle data.

### Layout measurements

| Screen | Baseline | Release candidate |
|---|---|---|
| Cockpit, real WebView 1280x564 | 2.44 screens at the baseline's 1280x517; hero over half the usable height | 1.24 screens; hero 22% in EN and TR, 26% in DE; all 5 Start actions in the first screen |
| Dental camera, real WebView | 3.2 screens, 46% of the preview visible | 1.46 screens, 100% of the preview visible |
| Header at 1280x800 | Two rows, 122 px | One row, 57 px |

The baselines were measured in a browser resized to 1280x517, not on the real WebView, so they are not exact comparisons. In a local
check at heights of 517 px and below, the Cockpit's Start actions still need a scroll with saved records.

## Findings register

**These comparisons are Claude's reading of the photos, not ground truth, and they say nothing about accuracy in general.** No model
or threshold was changed in response to them.

| Input | Finding | Model said | The photo shows | Kind |
|---|---|---|---|---|
| Character 49 | Acne on the chin | Not seen | Several red lesions along the jaw and chin | Likely missed |
| Character 49 | Acne on the forehead | 1 | Three or four red lesions | Likely undercount |
| Character 49 | Eczema or psoriasis tendency on the forehead | Seen, 1.9% of area | No plaque visible; shiny skin | Possibly wrong |
| Character 11 | Acne on the chin | Not seen | Spots near the mouth and chin | Likely missed |
| Female dental set | Caries candidates | 0 on all four views | Brown marks between teeth | Possibly missed |
| Both Skin runs | Unclassified spots | `NOT_VALIDATED` | | Not an error: the model is withheld |
| Both Skin runs | Pores | Not executed | | Known gap |

Other limits a reader should know:

| Finding | Detail | Suggested next step |
|---|---|---|
| Speech can be cut at a pause | On AAOS turn 5, 9 of the clip's 27 words were kept and the rest lost. In the earlier candidate this happened on WEB instead, so it varies per run | Review how end of speech is detected |
| Replies exceed the word limit | The prompt asks for at most 25 words; final runs reached 31 | Decide whether to enforce it after generation |
| Recognition is imperfect | One Vision trial per run needed the code word, and "R" was once heard as "Are" and still parsed correctly | Accept, or review the fallback |
| Demo camera can drop | 1 of 5 AAOS Skin recording attempts today ended in "Camera closed". The bridge delivers about 1.7 frames per second against a 750 ms limit. Demo bridge only, not a real camera | Owner decision below |
| READY did not notice an empty OpenAI account | Fixed in `8939fa7`: it now makes a one-token call | None |

## Model contract (QA-31)

The full matrix is in `SKIN-MODEL-CONTRACT.md`. In short: **two real gaps were found and fixed.** The V5 acne chain had never run on
AWS, and Python MediaPipe was missing. Both now run: 27 models report hashes that match the files on disk, and V5 measured 9 tiles. Both fixes change Skin numbers compared with earlier AWS runs, because they restore what was configured.

## Source and build

The full record is in `RELEASE-CANDIDATE.md`. Commit `4bb51b3`, all three CI workflows pass. The APK hash was read back from the
emulator, and 52 of 52 model files match the verification record by SHA-256.

## AWS operations (Task 17, QA-29)

A real cycle on the release candidate: **STOPPED in 31 s, READY in 84 s**, with a real OpenAI call. Models, voice and the OpenAI key
all survived without any manual step, and the final state was verified through the AWS API.

| Item | State |
|---|---|
| Start and Stop tool, reports, recovery | Working, used all day |
| Service start after boot, Chatterbox, mTLS, AAOS and APK readiness | Verified by READY |
| Claude's access (`attune-claude`) | Verified |
| AG's access (`attune-ag`) | **Claude ran it once, which does not count. AG must confirm** |
| Browser access | A mapped browser profile on this PC only |
| Certificate trust | **Not done.** The browser warns until the owner trusts the private CA |
| Stable addresses | **Owner decision below** |

**Costs.** Estimates from run times, not a bill:

| Item | Amount |
|---|---|
| Compute and public IPv4 since this work began: 12.2 hours at about $1.16 per hour | About $14.15 |
| Of which idle while the AWS sign-in had expired, about 2.8 hours | About $3.30 |
| Disks, which continue while stopped | About $25.70 per month |
| Data transfer, under 1 GB | Under $0.10 |
| OpenAI | Not visible to Claude. The credit ran out during this work; the dashboard has the real figure |

Both instances are stopped, confirmed through the AWS API at 13:30 UTC.

## Decisions for the owner

1. **V5 acne chain.** It now runs on AWS, and its own manifest says `accepted:false`. Should it stay on?
2. **`regional.pt`.** It is probably the R1 model the acceptance gate rejected, though identity is not proven. It runs as one input to a
   classifier. Should it stay?
3. **Approval records.** None exist for most Skin indicators. Should the current set be approved as it is, or reviewed?
4. **Demo camera limit.** Keep 750 ms and accept the occasional drop, or raise it for the demo bridge only? This report did not change it.
5. **Permanent addresses.** Keep the mapped browser on this PC (free), update IONOS records at each Start (needs an API key on this PC), or
   Elastic IPs (about $7.30 per month).

Also open: whether draft PR #22 should be closed, and whether to look at speech being cut at a pause before the merge.

## What was not done

- No physical camera, microphone, person or vehicle.
- No clinical or detection accuracy assessment.
- The language review covered every screen in the recorded states and the mechanical catalog check. It was not a professional
  translation review.
- The definition of all 21 master tasks was not found. Searched: the repository and Drive.
- Antigravity's independent review has not started.

## How the evidence was produced

Reports come from the live page and the stored records, not from screen text alone. `vision-scoring-matrix.md`,
`mental-performance.md`, `hearing-evidence.md`, `skin-label-evidence.md`, `persistence-evidence.md` and `ui-measurements.md` are generated
from those reports.

Earlier in the day a stopped script kept running and overlapped manual runs, so **no result from that period is used here.** Everything
above comes from clean runs on `4bb51b3`, with one job per platform at a time.
