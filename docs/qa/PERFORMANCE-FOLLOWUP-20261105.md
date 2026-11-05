# Performance and AAOS stability follow-up — 2026-11-05

Engineering baseline: merged main `7ea8334`. The hosts initially ran `9a938b4`; this follow-up must deploy a reviewed, CI-passing merged commit before claiming an updated runtime. The original independent audit and recordings remain unchanged in the private QA archive. This document contains aggregate technical measurements only.

## Accepted changes

- Add request-local, bounded numerical `Server-Timing` measurements for verification, warm-up wait, resident worker execution and validated worker phases. Forward the header through the existing same-origin proxy. No text, identifiers, credentials or model paths enter the header.
- Mark each browser segment's request, headers and complete-body arrival separately from playback. Preserve the existing two-segment schedule and all admission, consent, cancellation, locale and visibility checks.
- Add an observational Android/CDP collector for targeted investigations: native PID/activity, memory, process inventory, vehicle-state response time, lifecycle/renderer logs and CDP closure events. It neither clears logs nor restarts/retries the application. New evidence directories must not already exist.
- Add a reproducible offline synthetic speech probe that times the existing pinned worker, speech-token generation, waveform decoding and watermarking. Runtime wrappers measure calls without replacing arguments, return values, source or weights. Run under the application account with its existing non-secret cache configuration, including `PKUSEG_HOME`; never download replacement assets.

## Measured synthesis bottleneck

Existing r7i.2xlarge host, resident CPU model, four threads, unchanged pinned runtime/model, two fixed sentences per language, seeds 42 and 43, four measured segments per language after a separate warm-up. These are small sample medians, not population percentiles or listening approval.

| Seconds unless stated | EN | DE | TR |
|---|---:|---:|---:|
| Complete segment generation | 8.659 | 9.698 | 10.708 |
| Speech-token generation | 3.505 | 4.274 | 4.872 |
| Waveform decoding | 5.129 | 5.433 | 5.810 |
| Watermarking | 0.011 | 0.012 | 0.013 |
| Audio duration | 2.160 | 2.640 | 3.020 |
| Real-time factor | 4.013 | 3.703 | 3.547 |

The independent phase medians need not sum to the total median. The first short warm-up took 21.186 s, including imports/construction. Ordinary warm requests spend almost all their time in speech-token generation and waveform decoding. The approved default conditioning does not re-read a reference clip on these calls. Verification, encoding and watermarking are not the dominant cost.

A two-thread candidate was slower and is rejected. Part of that experiment overlapped a targeted Skin scan, so it is not a clean quantitative comparison and no optimization percentage is derived from it. The existing four-thread setting remains. Earlier measured higher thread counts and extra workers also provided no gain; see [the preceding investigation](MENTAL-LATENCY-20261105.md).

No significant warm conversational latency improvement is established by this patch. The pinned runtime returns a complete waveform, so proxy chunking cannot create sample streaming. Buffering both sentences would hide the gap at the expense of initial waiting. Changing segmentation, model precision, decoding, weights, voice or runtime source without appropriate validation is not an accepted shortcut. The completed historical audit is not repeated to manufacture new acceptance evidence. Fixed-text HTTPS/playback comparisons and targeted deployment regressions belong in the final execution record.

## AAOS Skin investigation

A targeted scan using the original approved reference photos reached a result and passed saved-record, placeholder, finding-selection and header assertions. It also exercised result regions. Across 40 snapshots the native PID remained unchanged, all 40 vehicle observations were PARK (maximum response time 6.1 ms), available Android memory stayed above 1,056,600 KiB and native app PSS peaked at 168,627 KiB. No CDP crash event occurred; closure/disconnect events correspond to harness cleanup. No target closure occurred during the scan/result inspection. This establishes only a successful observed run; the historical closure remains inconclusive until correlated evidence demonstrates a cause. Do not mark it resolved or add blind retries/native lifecycle changes.

The first new diagnostic launch stopped before scanning because its task output directory was not writable by the application account. Its cleanup also incorrectly reused a closed Playwright context. Both QA harness failures and their logs were preserved; original settings were restored and verified before a separately named, corrected attempt. These are distinct from the historical Skin interruption.

## Validation and release record

Targeted timing, worker, resident, frontend/proxy and observational collector tests: 146 passed locally. They cover concurrent request timing isolation, numerical bounds/privacy, cancellation/error/language/playback boundaries and unchanged proxy behavior. CI and exact merged/deployed commit, signed APK identity, storage/photo integrity, targeted runtime regressions and final AWS shutdown will be recorded after execution. No subjective listening or owner UAT acceptance is implied.
