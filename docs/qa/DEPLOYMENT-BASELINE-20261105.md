# Deployed demonstration baseline — 2026-11-05

The reviewed source and targeted instrumentation are deployed. This is a demonstration baseline, not production/clinical acceptance. Significant conversational latency reduction is **not achieved**; the historical Skin closure remains **inconclusive**. Owner listening and UAT remain outstanding. The twelve primary audit journeys were not repeated.

## Source, build and deployment identity

- [PR #26](https://github.com/sasmazt90/attune-more/pull/26): head `bdc3c759eeb71164e46e852647d4010e266d8e6f`, merged `ba43b5a5758be86f858b87c14c1ff17d5d0baf45`. Request-local bounded timing, proxy/client milestones, synthetic synthesis probe and observational native lifecycle capture; no inference/voice/segmentation/native safety changes.
- PR CI [41980538759](https://github.com/sasmazt90/attune-more/actions/runs/41980538759): backend **1,986 passed, 44 skipped**, research **298 passed**, frontend build passed. Main CI [41981316420](https://github.com/sasmazt90/attune-more/actions/runs/41981316420) passed. Local targeted timing/worker/frontend/diagnostic tests: **146 passed**. Review was performed by the executing agent, not an independent human reviewer.
- WEB and AAOS host helpers deployed exact merged `ba43b5a5758be86f858b87c14c1ff17d5d0baf45` through the existing release procedures. Archive SHA-256 `f33c9ee8fc9a19c743a0b9dba8a2aec3fc8de32ef78e1d384c48eae42a31675a`; WEB build ID `MOeVLCvXmMCE_ntBwUbDI`. WEB deployment 06:37:13–06:38:02 UTC; AAOS helper deployment 06:38:58–06:39:16 UTC.
- APK **1061 → 1065**, `0.1-prototype-aws-demo`, installed in place at **07:00:03 UTC**. First install remains **2026-11-04 20:48:31**. Package identity and both Android users' microphone grants preserved. Certificate SHA-256 remains `2aacbb13bad91c2ef982d594a8d98b65f523a71fdc97772d50222fe9f9843876`.
- APK SHA-256 `ff3ee828410db03bd7bf8e95bad8ff1f93d1f5cf507e42ed2da363393f74746d`, 70,782 bytes. Reused the existing successful [build 41973266913](https://github.com/sasmazt90/attune-more/actions/runs/41973266913), artifact `13390568036`, build head `6955ab6ea2821e948cb663df03f6b14f314ab59c`. This is **not** a newly built ba43 APK: native tree `04ba49131e5e448d2449edb07f4839bca75486e5` and all native build/workflow inputs are identical at that build and deployed main. The shell bundles no WEB code or commit ID. Existing signed artifact reuse avoided a redundant build after CLI authentication expired; GitHub connector verification remained available.

Documentation and QA-only follow-up commits do not change the deployed runtime. No key migration, uninstall, reset, infrastructure/access-control change or replacement model was performed. SHA-256 verification matched all **52** approved model files.

## Mental timing and limitations

Two fixed synthetic sentences per language, two browser turns per language before and after, same existing four-thread resident CPU runtime and actual Chrome playback. Seconds below are small-sample means of browser playback events, **not measured acoustic onset** and not statistically established improvements.

| Language | First playback before → after | Segment gap before → after | Completion before → after |
|---|---:|---:|---:|
| EN | 8.089 → 7.966 | 7.577 → 8.036 | 20.023 → 20.476 |
| DE | 8.676 → 8.951 | 8.790 → 7.873 | 22.648 → 21.936 |
| TR | 11.724 → 11.097 | 7.399 → 7.582 | 25.583 → 24.894 |

There is no consistent improvement. Separate instrumented synthesis medians and rejected thread experiment are in [the performance investigation](PERFORMANCE-FOLLOWUP-20261105.md). A representative warm request measured total 7,965 ms, worker 7,964 ms, inference 7,951 ms, verification 0.495 ms, warm wait 0.003 ms and body transfer about 1 ms. Token generation and waveform decoding dominate; networking/proxy buffering is not the measured bottleneck. The earlier API/ASR observations (~0.9 s / 1.5–2 s) remain historical observations, not newly matched before/after claims.

The matched-run loopback recorder failed because the temporary Pulse sink disappeared during browser startup. Failed logs are retained; these runs support browser-event timing only. Starting the recorder immediately after creating the existing sink produced a separate valid post-deployment TR/EN/DE capture: **91.531 s, 24 kHz mono, RMS −26.268 dBFS**, 4,393,560 bytes. Its harness misclassified normal ffmpeg SIGINT termination as failure; independent WAV/sample validation passed. This separate recording does not repair missing baseline acoustic evidence or establish subjective quality approval.

Live cancellation: competing synthesis returned 429; the cancelled client received AbortError; the resident worker PID disappeared **209.497 ms after abort**, observed with 100 ms polling; subsequent warmed recovery returned 200. Disposable-profile privacy validation passed without invoking deletion against preserved user data.

Next measurable work requires a compatible approved-runtime optimization that reduces speech-token/decoder execution, then repeated fixed-text TR/EN/DE acoustic onset/gap distributions and owner listening. Proxy chunking cannot stream samples that the pinned model has not generated. Caching sensitive conversation audio, changing voice assets/model precision or hiding gaps by delaying both segments was not accepted. Existing four-thread scheduling and approved assets remain.

## Targeted runtime evidence

- Skin: one baseline diagnostic scan and one after WEB deployment. Result in approximately **84 s / 77 s**, all six checks passed each. Baseline 40 snapshots and candidate 38 snapshots retained native PID 2378, with no CDP crash event; terminal disconnects match harness cleanup. Baseline minimum Android available memory 1,056,600 KiB, peak app PSS 168,627 KiB, all vehicle observations PARK. No reproduced renderer termination/resource failure; the historical retry is not resolved by these successful samples.
- Mental: one targeted five-turn AAOS conversation; all five ASR inputs/replies and final saved summary passed the six journey checks. Remote video/audio evidence retained. Skin/Mental used the updated WEB bundle with APK 1061 before upgrade; its native code is identical to 1065 and deployed main, so the complete journeys were not repeated after the version-only native update.
- APK 1065 native provider return: approved HTTPS link and native confirmation opened LinkViewer; actual Android Back restored the care route and pending question. Minimal state, Not booked cleanup, no automatic appointment, and expiry at 24 hours passed. An earlier test used an invalid internal specialty; another used `am start`, which raised a task still topped by LinkViewer. Both failures are retained. Continuing the existing handoff with Android Back passed; no product navigation change or blind full-journey retry was introduced.
- Native PARK/DRIVE: PARK exposes the WebView; DRIVE removes it; native process remains alive; returning PARK creates a fresh WebView and app API responds. Vehicle restored to PARK.
- Deployment health: services/API/provider response and all 27 Skin models checked; local-hostname HTTPS certificate verification returned 0, with expected authenticated endpoint response. Direct cloud ingress timeout was retained and no security group was changed.

## QA corrections and preservation

The upgrade smoke check previously demanded German/Berlin even when preserved user preferences differed. It now verifies the persisted language/region against the visible UI without writing them. CDP selection now matches the native app PID rather than choosing the last socket, which can belong to an external browser. This removes a QA ambiguity, not a proven cause of the historical Skin failure. **33 local tests passed, 1 optional test skipped** for these changes and existing upgrade identity coverage.

Final comparison passed: all **16 original records**, **20 local settings/consents**, and all original photograph content hashes are unchanged. Two Skin scans and one Mental conversation added three QA records: **19 total** (Skin 6, Dental 3, Hearing 3, Mental 3, Vision 4). All 19 pre-upgrade records and all eight photo-store entries (Skin 5, Dental 3) were identical after the APK update and final native tests. All ten upgrade operational checks passed. WEB storage snapshots before and after deployment were identical. Native DRIVE removal was observed in 2.584 s and PARK recreation in 3.318 s; these include UI polling overhead, not exact gate latency. Private evidence contains failed attempts, correlated logs, recordings, screenshots, source/build receipts and SHA-256 download verification. No raw credentials, pairing configuration or browser profile is included in the deliverable.

## Shutdown and remaining gates

Owner's approved DNS-aware startup launched WEB at **05:56:52 UTC** and AAOS at **05:56:54 UTC**. Stop requested through the authorized AWS identity at **07:31:31 UTC**; AWS API confirmed **both STOPPED at 07:32:04 UTC**. Elapsed upper bound 1.587 hours at the supplied combined $1.16/hour estimate: **$1.84 compute**, excluding storage/other charges; this is not a billing statement. All necessary host evidence was downloaded with matching SHA-256 before shutdown. Later documentation/CI work ran with the hosts stopped.

Outstanding: significant Mental latency reduction, matched acoustic before/after evidence, owner listening/UAT, and the unreproduced historical Skin interruption. Legacy signing migration remains blocked for any future legacy rollout and is unnecessary for this preserved same-certificate demonstration. CQ-02/CQ-03 fixes from PR #25 are now deployed; OPS-01 is fixed in repository source, while the owner's Windows shortcut copy was not altered or retested. No subjective listening acceptance or general release approval is claimed.
