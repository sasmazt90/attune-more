# Attune.more release candidate: acceptance report

**Release candidate `b803182`, 2026-11-04.** Written by Claude, who built and tested it, so this is not an independent
review. Antigravity's review is the next step, and nothing is merged.

## Result in short

All pre-review tasks are finished, and every journey's automated checks passed. All of this used reference photos, synthesized
speech, a scripted listener and an emulator with simulated vehicle data.

**A pass here means the flow works and the checks held. It says nothing about clinical or detection accuracy**, which stays
NOT VERIFIED everywhere because no labelled ground truth exists for these runs.

What changed since `4bb51b3`:

| Item | Before | Now |
|---|---|---|
| Addresses | Changed at every Start, browser warned | `attunemore.sasmaz.digital` and `aaos.attunemore.sasmaz.digital`, trusted certificates, no manual step |
| Desktop shortcuts | **Had never worked**, despite earlier reports | Work. Opened from a real window to prove it |
| Skin models | Approval open | Owner approved 2026-11-04, as configuration, not accuracy |
| Character 49 chin | Not shown | 4 lesions |
| Character 49 forehead | 1 | 5 |
| Character 11 chin | Not shown | 3 lesions |
| Mental speech cut short | 1 turn in 10 lost most of its words | 10 of 10 turns complete |
| Mental, first sound after speech ends | 18.6 to 24.9 s | 11.0 to 15.3 s, **with a new pause between sentences** |
| Camera | Dropped at 750 ms | Survives late frames and a 3.3 s pause |
| Header | Two rows at 800 px, and on WEB during every scan | One row from 768 px, in every state |
| Start actions on short screens | Off screen at 517 px and below | In the first screen, down to 1024x400 and 800x480 |
| Vision referral | Offered, never followed | Followed to the provider and back |
| AAOS app update | The deploy uninstalled the app, deleting its data | In place, with one stable signing key. 2 real upgrades kept every record, consent and preference (QA-41) |

**Two decisions need the owner**: the pause in Mental speech, and where else the signing key should be kept. See [Decisions for the owner](#decisions-for-the-owner).

**`b803182` differs from `8c90ec4` only in the APK's signing and version number and in the deployment tools.** Results below come from the builds named beside them.

## Final acceptance matrix

| Module and platform | Functional E2E | Result completeness | Accuracy | Model configuration | Responsive UI | Persistence and history | Audio and video | Physical | Recording |
|---|---|---|---|---|---|---|---|---|---|
| Skin WEB | PASS | PARTIAL | NOT VERIFIED | OWNER APPROVED | PASS | PASS | PASS | NOT RUN | PASS |
| Skin AAOS | PASS | PARTIAL | NOT VERIFIED | OWNER APPROVED | PASS | PASS | PASS | NOT RUN | PASS |
| Vision WEB | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Vision AAOS | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Dental WEB | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Dental AAOS | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Mental WEB | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Mental AAOS | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing digits-in-noise WEB | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing digits-in-noise AAOS | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS, earlier build |
| Hearing pure-tone WEB | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS |
| Hearing pure-tone AAOS | PASS | PASS | NOT VERIFIED | Not in scope | PASS | PASS | PASS | NOT RUN | PASS, earlier build |

Why the cells that are not PASS say so:

- **Skin result completeness:** "Unclassified spots" reports `NOT_VALIDATED`, and pores are not executed. Both are stated on
  screen or in the contract, not hidden.
- **Physical:** nothing here used a physical camera, microphone, person or vehicle.
- **Earlier build:** see below.

## Videos

| Platform | Journey | File | Seconds | MB | Build | Result | Link |
|---|---|---|---:|---:|---|---|---|
| WEB | Skin | WEB_Skin_EN_E2E.mp4 | 120 | 5.1 | `8c90ec4` | PASS | [Open](https://drive.google.com/file/d/1AFoHasgULOZz4CYoXrVdD7or-6knAN9s/view) |
| WEB | Vision | WEB_Vision_EN_E2E.mp4 | 247 | 3.4 | `8c90ec4` | PASS | [Open](https://drive.google.com/file/d/1RwACXmewfP9aB5tfbFM7qCu7qE2c84xS/view) |
| WEB | Dental | WEB_Dental_EN_E2E.mp4 | 73 | 2.3 | `8c90ec4` | PASS | [Open](https://drive.google.com/file/d/1EOIi-GzwaI7eLVypTjmWbTrJWgjuSvGD/view) |
| WEB | Mental | WEB_Mental_EN_E2E.mp4 | 232 | 8.5 | `8c90ec4` | PASS | [Open](https://drive.google.com/file/d/11OVM1JlBZMLVlzkP_36NoPbDFzZqOioK/view) |
| WEB | Hearing digits-in-noise | WEB_Hearing_digits_in_noise_EN_E2E.mp4 | 103 | 2.7 | `8c90ec4` | PASS | [Open](https://drive.google.com/file/d/1jFZGapSyI9jgw03DILMHBMhrRgtx_sh4/view) |
| WEB | Hearing pure-tone | WEB_Hearing_pure_tone_EN_E2E.mp4 | 493 | 11.3 | `8c90ec4` | PASS | [Open](https://drive.google.com/file/d/1Zdb7T1GHuYjpT_-8pAE5l6TWkfNBorOZ/view) |
| AAOS | Skin | AAOS_Skin_EN_E2E.mp4 | 141 | 8.4 | `f7d861e` | PASS | [Open](https://drive.google.com/file/d/1x49sIt8qHRwwY-4FJakY6mf_Qq6_8L6_/view) |
| AAOS | Vision | AAOS_Vision_EN_E2E.mp4 | 302 | 5.7 | `f7d861e` | PASS | [Open](https://drive.google.com/file/d/1vUjTWyH_BpHtDnwhJi0ZJt4BqZKG5tsB/view) |
| AAOS | Dental | AAOS_Dental_EN_E2E.mp4 | 95 | 5.4 | `f7d861e` | PASS | [Open](https://drive.google.com/file/d/1IqmIUINDqRozcM2aDq7nvz_X2MnuTiqD/view) |
| AAOS | Mental | AAOS_Mental_EN_E2E.mp4 | 232 | 12.3 | `f7d861e` | PASS | [Open](https://drive.google.com/file/d/1jpKXJUhx5g7G5zv3iFpM4eeRJknUsE1Y/view) |
| AAOS | Hearing digits-in-noise | AAOS_Hearing_digits_in_noise_EN_E2E.mp4 | 115 | 4.9 | `4bb51b3` | PASS | [Open](https://drive.google.com/file/d/1F0W38aiERSUNTy1lFsuWi9oARVS8evQr/view) |
| AAOS | Hearing pure-tone | AAOS_Hearing_pure_tone_EN_E2E.mp4 | 489 | 14.5 | `4bb51b3` | PASS | [Open](https://drive.google.com/file/d/1n5YBGmP2xWSBQ40Lxny1OhBLpIFsG8V7/view) |

All are 1280x800 at 12 fps, with audio present. AAOS videos show the emulator's whole display, including the test build's
toolbar. Its "Camera: unavailable" refers to the emulator's own camera; the reference photos arrive through the demo camera
bridge.

**Three builds, and why.** WEB was recorded on `8c90ec4`, because every WEB journey changed. AAOS Skin, Vision, Dental and Mental were
recorded on `f7d861e`. The one product change after it hides a note in the header that was already hidden at AAOS's 564 px height, so
those journeys are unchanged. AAOS Hearing stays from `4bb51b3`, not re-recorded, because neither the camera nor speech is involved.
All of today's recordings passed first time.

### How delivery was checked

Everything is in [the Drive folder](https://drive.google.com/drive/folders/1LsbiNKlGinJUD5_gFSa2-SpHbtjJkmQa).

- **The original twelve videos:** the owner reports they passed an independent direct-cloud SHA-256 check (QA-40). That evidence stands for the two AAOS Hearing files, which are unchanged, with the same hashes.
- **The ten replaced videos:** SHA-256 of the local file and of the Drive for desktop copy match. Size on Drive's servers matches, read through the Drive API.
- **A direct-cloud hash of the ten replaced videos: not done.** The browser here is not signed in to Google, and Drive for desktop may serve its local copy. Hashes are in `videos.md`, so Antigravity can compare.

## Addresses and certificates (Task 17)

A genuine Stop and Start on the release candidate: **STOPPED in 34 s, READY in 126 s.** The hosts came back with new addresses, 51.102.2.240
and 63.183.142.196. With no manual step:

| Check | Result |
|---|---|
| Account and instance IDs confirmed; IONOS reached before anything started | PASS |
| Each A record updated from the address AWS reports for that exact instance | PASS, 28 s after START began |
| IONOS name servers, this PC and 2 public resolvers all return the new address | PASS |
| Browser trust with no bypass and no address pinning | PASS: curl on Windows, and a real Chromium, with no warning |
| Authentication still required | PASS: 401 on both addresses without a login |
| Private mTLS between hosts | PASS: accepted with a client certificate, refused without |
| Port 443 still limited to the operator's address, port 80 closed | Unchanged |
| A second run with nothing to change | No DNS write |
| WEB journeys in Chrome with certificate errors no longer ignored | PASS |
| Provider key and models after the restart | Present, no manual step |

**Renewal, tested for real.** START renews a certificate in the last third of its lifetime. One renewal was forced through the real
Let's Encrypt on running hosts: both serial numbers changed, the new certificates are trusted, and the temporary validation records were
removed. A stopped host cannot renew, and does not need to, because START runs first. If hosts ever stay up for weeks, press START again:
it changes nothing else.

**DNS, checked after all this.** The zone went from 49 records to 51: the two authorized A records. The root domain, website, mail and all
other records are unchanged. `_acme-challenge` TXT records exist for under a minute during issue and are removed even if validation fails.

**Safety rules, with tests.** 22 tests run the real script against a stand-in for IONOS and the CA. Only the two names can be written. This PC's
own address, private addresses and anything but IPv4 are refused. A name used by another service is reported, not overwritten. A missing or
refused key gives a specific instruction and stops before anything starts. The key never appears in output.

**A fault in earlier reports.** The desktop shortcuts pointed at a file only Claude's app could see, because a packaged app's writes under
AppData go to a private copy. They had never worked on a double-click, although earlier reports said one-click Start and Stop worked. That was
only true of the same script started from the repository. The tool now lives in `%USERPROFILE%\AttuneMore`, and the STATUS shortcut was
opened in a real window: READY, as the desktop role.

## What each module showed

### Skin: missed acne (QA-25)

Full trace: `QA-25-ACNE-TRACE.md`, with overlays and close-ups in `qa25-acne-trace/`.

**The detector had found these lesions. The product was throwing them away**, in two ways. A region classifier hid regions that held several marked
lesions: Character 49's chin had 4 boxes of 0.37 to 0.68 and a region score of 0.24 against a threshold of 0.60. And lesions on the hairline,
between the brows or on the jaw fell outside all five research regions. Thresholds, models and research regions are unchanged.

| Region | Character 49 on AAOS, before | Now | Character 11 on WEB, before | Now |
|---|---|---|---|---|
| Forehead | 1 | **5** | 4 | 4 |
| Right cheek | 5 | 5 | 4 | 5 |
| Left cheek | 5 | 6 | 2 | 2 |
| Chin | Not shown | **4** | Not shown | **3** |
| Nose | Not shown | Not shown | Not shown | Not shown |

**False positives.** Of 14 recovered boxes in the direct trace, 12 look like lesions in close-up and 2 are doubtful: one looks like a skin fold and one
holds fine bumps with no clear lesion. Three control sets had no box at or above 0.35 and stayed negative. The new rule shows a region with 2 marked
lesions even when the classifier disagreed, so a region with two false boxes would now show. Those rows are marked `decidedBy: markedLesions`.

V5 still produces only the heading and is not added to these counts, so there is no double count.

### Skin labels

Rechecked on the release candidate on real results: **WEB 594 states at 9 sizes, the real AAOS WebView 396 states at 6 sizes**, each in EN, DE and TR. All
checks passed, including every drawn marker matching the stored result on its own photo. Details are in `skin-label-evidence.md`.

### Vision and its referral (QA-37)

**24 valid trials, 12 per eye, exactly one "can't see it"**, read back from the stored records on both platforms. Scores recomputed from the spoken
answers match the result screen and saved history. Per-trial detail is in `vision-scoring-matrix.md`.

The recording now continues: Specialist options, eye care already selected, no region assumed, Berlin chosen, an option listed, consent, the
provider's page (`doctolib.de/augenarzt/berlin`), back, asked whether a booking was made, and nothing saved. On AAOS the native dialog appears before
leaving the app. No appointment was made with any provider.

### Dental

Unchanged from the previous candidate and rechecked: **the original female photos on the real AAOS WebView, all four views measured**, including the
supplied BITE photo. Preview 100% visible in 1.46 screens. Details are in `dental-bite-findings.md`.

### Mental (QA-36, QA-02)

A whole five-turn conversation on each platform, with real recognition, language model and speech. Language was clean.

**Speech being cut (QA-36).** Sentences in the reference clips are up to 950 ms apart, and a 900 ms silence limit ended the turn between them.
That is what lost 18 of 27 words in the previous AAOS run. Mental now waits 1500 ms and allows turns up to 60 s, from 15 s. **All 10 turns were
heard in full: 25, 24, 14, 30 and 27 words on both platforms.** Vision keeps its quick limit.

**Latency (QA-02).** Measured options on this CPU: 8 threads instead of 4 gave no gain (16.2 s against 15.9 s), two workers at once gave none (about 16 s for 3 s
of audio each), and `cfg_weight` was already 0. Speech takes about 2.6 s per second of audio. So the only free change left was to play the first sentence
while the rest is generated:

| Stage | Before | Now, WEB | Now, AAOS |
|---|---|---|---|
| Speech end to transcript, including the longer wait | 0.8 to 1.6 s | 1.5 to 1.9 s | 1.6 to 2.3 s |
| Language model | About 1 s | 0.9 to 1.2 s | 0.8 to 2.1 s |
| **Speech end to first sound** | **18.6 to 24.9 s** | **11.2 to 14.9 s, median 12.7** | **11.0 to 15.3 s, median 11.9** |
| **Silent pause between the two parts** | **None** | **7.8 to 10.3 s, median 9.3** | **4.2 to 11.2 s, median 9.6** |

The reply text appears on screen within about 3 s. The whole reply finishes at about the same time as before, because generation is no faster overall. Same voice and weights. This is
still slow for conversation, and a real improvement needs a GPU, which is not provisioned. Replies reached 32 words against the 25 the prompt asks for, and longer replies mean longer waits.

### Hearing

Both protocols completed on both platforms. **The responses come from a scripted listener, so this proves the flow and the audio path, not anyone's hearing.** Levels are
uncalibrated digital levels and are not presented as clinical thresholds. Details are in `hearing-evidence.md`.

### Camera (QA-38)

**What was measured.** Normally 332 ms between frames at the median and 590 ms at most. With 12 busy processes on the WEB host: median 531 ms, 99th percentile 686 ms, and 792 ms at most, against
a 750 ms limit. Separately, a frame arriving while the last was decoding closed the connection, and a 500 ms limit applied towards the page. On the real capture path, a lossless
3.3 MB frame needs over 35 Mbit/s of upload to arrive in 750 ms, so a home connection could not meet it at all.

**What changed.** A frame may take 4 s to arrive, a frame arriving during decoding is dropped, and the connection ends after 7 s with no frames. The bridge logs why each session ended. **This did not relax what
reaches analysis:** pages still use only frames they have not seen, and stop trusting the preview after 750 ms without one. Each frame is still lossless, and still answers a fresh challenge from the bridge.

**PARK and DRIVE.** PARK is now checked every 250 ms whatever the frames are doing, so a slow frame cannot delay leaving PARK. An unreadable state stops frames at once and ends the session in 2 s.

| Test | Result |
|---|---|
| Source slowed to 1.5 s per frame, then paused 3.3 s, on a full AAOS Skin journey | PASS: 7 gaps over 750 ms, connection kept, result reached |
| Source stalled 9 s | Clean end after the 4 s limit, logged as `timeout-challenge`; the screen says the camera closed and offers Try again |
| Leaving PARK while a frame is awaited | Session ends in under 1.5 s (unit test) |
| Native PARK and DRIVE gates on the real Android app | 7 of 7 |
| Recordings today | All passed first time |

A real camera over a home connection was **not** tested. The slow source stands in for it. Below about 7 Mbit/s of upload a lossless frame would still miss the 4 s limit.

### Appointments, persistence and camera states

- **Appointments:** no region assumed, opening a provider saves nothing, local time, and deleting says the provider's booking is not cancelled. Passed on both platforms.
- **Persistence across restarts:** save, history, refresh, re-entry, a real host Stop and Start, history, delete. 11 of 11 checks on each platform. This never replaced the APK. Upgrades are covered in [the next section](#apk-upgrades-qa-41).
- **Changed origin:** browser data is per origin, so records saved under the old WEB address are not visible at the new one.
- **Camera states:** fresh entry, unavailable, retry, waiting and live, on Skin and Dental, on both platforms.

### APK upgrades (QA-41)

The full record is in `QA-41-APK-UPGRADE.md`.

**Root cause.** CI signed each APK with its runner's temporary debug key. Android refuses to update an app whose certificate changed, so the deploy tool uninstalled it first, which deleted its local data.

**Fix.** One stable signing identity, `2aacbb13...`, whose key is in a protected GitHub environment and never in the repository. The deploy now updates in place, and stops with nothing changed if the certificate differs.

| Check | Upgrade 1, 1056 to 1057 | Upgrade 2, 1057 to 1058 |
|---|---|---|
| Uninstalled | No | No |
| Signing certificate | Same | Same |
| First install time | Unchanged | Unchanged |
| 6 records across all 5 modules: IDs and hashes | Identical | Identical |
| Duplicated or corrupted records | None | None |
| Consent, privacy choices, region, language | Identical | Identical |
| Stored photos, 2 stores | Identical | Identical |
| App works: API, 5 modules, History, a record opens | 10 of 10 | 10 of 10 |

After the upgrades, a new Dental journey saved a new record, a real Stop and Start kept all 7, and the native gates passed 7 of 7 on the signed APK.

**A fault in my tool.** The one-time move to the new key stopped on its first real run, after removing the old app, and wrongly reported that nothing had changed. The data was restored complete from the backup, and the tool was fixed. The corrected move has not run uninterrupted on a device.

**Older installs.** A device holding an APK signed by an old CI key cannot be updated in place, because that key no longer exists. It needs the one-time move once, or it loses its local records on reinstall. The AWS emulator has had it. No other device was found or tested.

### Layout and language (QA-39, QA-32, QA-10, QA-11)

| Check, on both platforms | Sizes | Result |
|---|---|---|
| Header one row, 57 px | 1280x564, 1280x517, 1024x600, 1024x400, 800x480, EN, DE, TR | PASS |
| Header one row in every marked state, including active scans | WEB: all journeys at 1280x800. AAOS: camera, appointments, labels and UI at 1280x564 | PASS |
| All 5 Start actions in the first screen height | Same 5 sizes and languages | PASS, from 0 of 5 at 517 px and below |
| Each Start action can be reached and pressed, including across the carousel | Same | PASS |
| No sideways overflow, no undersized controls | Same | PASS |

AAOS small sizes are emulated inside the real WebView, whose real display is 1280x564. Below 1000 px inactive tabs show only their icon and keep their names for assistive technology. Below 540 px high the Cockpit keeps each module's name
and Start action, opening a card shows its saved values, and the Cockpit's introduction is hidden.

**A fault found while checking this.** The language lock note added a header row on WEB during every activity. No fixed screen measurement saw it, because it only appears mid-scan. It was found in a screenshot, fixed, and journeys now read the header in every state.

**Language.** Every state's rendered text was read in EN, DE and TR. 16 strings were corrected: cards saying "No records" twice, German mixing Facharzt and Fachkraft, an ungrammatical German consent title, the technical phrase "voice flow", inconsistent capitals and a stray "04" label. The catalog scan found no mixed-language text or placeholder mismatch. This was one reader's review, not a professional translation review, and result screens were read in English only.

## Findings register

**These comparisons are Claude's reading of the photos, not ground truth.**

| Input | Finding | Model said | The photo shows | Kind |
|---|---|---|---|---|
| Character 49 | Eczema or psoriasis tendency on the forehead | Seen, 1.9% of area | No plaque visible; shiny skin | Possibly wrong |
| Character 11 | A box of 0.38 on the jaw | Counted | Looks like a skin fold | Possibly wrong, new with QA-25 |
| Character 11 | A box of 0.44 on the left cheek | Counted | Fine bumps, no clear lesion | Possibly wrong, new with QA-25 |
| Both Skin runs | Visible spots below the 0.35 marker score | Not counted | Some small red spots | Possibly missed; no threshold was changed |
| Female dental set | Caries candidates | 0 on all four views | Brown marks between teeth | Possibly missed |
| Both Skin runs | Unclassified spots | `NOT_VALIDATED` | | Not an error: the model is withheld |
| Both Skin runs | Pores | Not executed | | Known gap |

Other limits a reader should know:

| Finding | Detail | Suggested next step |
|---|---|---|
| A placeholder echoed in a hidden field | One German analysis returned the prompt's Turkish placeholder "Klinik öneri gerekçesi veya null" as `professionalSupportReason`. Nothing in the app displays this field, so no user saw it | Fix with the review's other changes: ignore the placeholder, and make the prompt language-neutral |
| Replies exceed the word limit | The prompt asks for at most 25 words; final runs reached 32, which lengthens the wait | Decide whether to enforce it after generation |
| Detection varies with the crop | The same photo gave different counts through different landmarks, for boxes near the 0.35 limit | For AG to judge |
| Recognition is imperfect | One Vision trial per run needed the code word | Accept, or review the fallback |
| DNS after STOP | Records keep the last address until the next START, and AWS may give it to another customer meanwhile | Elastic IPs would remove this, at about $7.30 per month, with approval |
| Public certificate logs | Issuing certificates lists both names publicly. Access is still limited by the Security Groups | Accept |

## Model approval (QA-31)

**Closed as OWNER APPROVED on 2026-11-04.** `SKIN-OWNER-APPROVAL-20261104.md` records the decision with model identifiers, versions and hashes. It covers product configuration, not accuracy. Research records keep their old flags: V5's manifest still says `accepted:false`, and no artifact was changed. All 52 model files on the release candidate match.

## Source and build

The full record is in `RELEASE-CANDIDATE.md`. Commit `b803182`, all CI workflows pass.

## Costs

Estimates from run times, not a bill:

| Item | Amount |
|---|---|
| Compute and public IPv4 since this work began: about 17.4 hours at about $1.16 per hour | About $20.16 |
| Disks, which continue while stopped | About $25.70 per month |
| DNS and certificates | No cost from AWS. IONOS and Let's Encrypt were used as they are |
| OpenAI | Not visible to Claude. The dashboard has the real figure |

No AWS resources were created. Both instances are stopped, confirmed through the AWS API, with shutdown at 21:29 UTC.

## Decisions for the owner

1. **The pause in Mental speech.** First sound now comes about 7 s sooner, but there is a silent pause of about 4 to 11 s between the two parts of a reply. Keep it, or go back to one longer wait with no pause? It is one setting, and Claude recommends keeping it because the first response is what makes the wait feel long. Antigravity's view would help, as this needs a person listening.

2. **Where else to keep the signing key.** The only recovery is `%USERPROFILE%\AttuneMore\secrets\android-cloud-demo-signing.xml`, because GitHub secrets cannot be read back. It opens only under this Windows account on this PC, so a plain copy would not help if the PC is lost. Keeping the key in a password manager as well would. Without the key, no data has to be lost, but every installed app would need the one-time move to a new identity. Claude has not copied the key anywhere else.

Also open: whether draft PR #22 should be closed.

## What was not done

- No physical camera, microphone, person or vehicle.
- No clinical or detection accuracy assessment.
- No professional translation review.
- A direct-cloud hash of the ten replaced videos.
- An uninterrupted run of the corrected signing move on a device, or an upgrade on a physical head unit.
- The definition of all 21 master tasks was not found. Searched: the repository and Drive.
- Antigravity's independent review has not started, and AG's own AWS access still needs confirming by AG.

## How the evidence was produced

Reports come from the live page and the stored records, not from screen text alone. `vision-scoring-matrix.md`,
`mental-performance.md`, `hearing-evidence.md`, `skin-label-evidence.md`, `persistence-evidence.md`, `qa41-apk-upgrade/apk-upgrade-evidence.md` and `ui-measurements.md` are generated
from those reports.
