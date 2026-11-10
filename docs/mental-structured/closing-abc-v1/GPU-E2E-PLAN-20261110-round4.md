# Round 4 plan: live closing end to end with GPU speech (prepared, awaiting the owner's approval)

**Status (2026-11-10, 15:10 UTC):** prepared only. No AWS resource was created for it. The earlier 5 USD approval
belonged to round 3 and is closed; this run needs a new explicit approval of the scope, the cost cap and the time limits
below. The feature stays off; nothing is merged or deployed; the 45 A/B/C recordings are not regenerated, lengthened or
repeated; the normal closing keeps *sen* and structured-v1 keeps *siz*; no listening approval is implied by any result.

## 1. What is measured, and what is not replayed

Chain under test: **WEB browser** (system Chrome on the WEB host, this branch's production build served by a test Next
server) → **real analysis API** (a test API process on the WEB host running this branch, the product API environment
read in memory, the real provider `gpt-4o-mini`) → **GPU speech** (the same resident worker, run on a temporary GPU
host) → **real playback** of A, B, C and the personal line in the page. Nothing in this chain is a recorded analysis or a
delayed WAV; the only scripted part is the microphone (one synthetic, non-personal utterance per closing). Round-3
replays stay separate and are not mixed into these numbers.

Optional second chain (needs a separate yes, see 3.3): **AAOS WebView** → the same test API → the same GPU worker.

## 2. Instance, region and the request path

| | |
| --- | --- |
| Type | one `g5.xlarge` (NVIDIA A10G 24 GB, 4 vCPU, 16 GiB) — the type measured in round 3; no other type on capacity failure |
| Region / zone | eu-central-1; WEB's zone eu-central-1c first, then 1b, 1a (same type only) |
| Image | `ami-061e11c485e439112`, Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04) 20261106 (same as round 3) |
| Disk | 100 GiB gp3, encrypted, deleted on termination |
| Software | the round-3 CUDA environment: `torch 2.6.0+cu124`, the WEB host's pins, `chatterbox-tts` source `5de7a54…`, Perth `ff1c8ac…`; model files from `ResembleAI/chatterbox` revision `5bb1f6e…`; every file hashed against the WEB host before any run |
| Settings | FP32, TF32 off for matmul and cuDNN (the worker sets this on CUDA), same reference voice (`4d2bd83f…`), exaggeration 0.35, cfg_weight 0.0, temperature 0.8, watermark on |

**How the WEB API reaches the GPU (no provider key on the GPU, no port open to the internet, no IAM change).** The API
starts its resident worker as `[ATTUNE_MENTAL_TTS_PYTHON, mental_neural_resident.py]` and talks to it over stdin/stdout.
For the test API process only, `ATTUNE_MENTAL_TTS_PYTHON` points to `scripts/mental_closing_abc/remote_resident_bridge.py`,
which carries that unchanged line protocol over one private TCP connection to `remote_resident_server.py` on the GPU
host; the server starts the branch's `mental_neural_resident.py` in the GPU environment and maps the WEB configuration
path to the GPU configuration of the same profile. Everything else stays on WEB and in the product code path: the HTTP
endpoint, consent and park gates, `verify_speaker` (re-hashing the bundle on WEB, ≈ 2.3 s), admission (one request at
a time, `429` otherwise), timing headers, and cancellation by killing the worker — killing the bridge closes the
connection and the server kills the GPU worker's process group (unit-tested with a stub model,
`tests/unit/test_mental_remote_resident.py`). A one-off random handshake line is created for the window on WEB and
passed to the GPU host through SSM; it is useless after the window. Traffic stays on private VPC addresses and carries
only the synthetic test lines.

Evaluated and not chosen: SSM port forwarding (needs `ssm:StartSession` for the WEB instance role — an IAM change — and
the session-manager plugin, and relays through public SSM endpoints, which would not represent a private deployment's
latency); copying the provider key to the GPU host (not needed: analysis stays on WEB); an internet-facing port (not
needed).

## 3. Network and permission changes, exactly

### 3.1 New, temporary (deleted at the end)
- Security group `attune-gpu-e2e-round4` in the default VPC `vpc-074768071df6b9266`: **one inbound rule, TCP 8191 from
  the WEB security group `sg-023659b3a447ab759`** (group reference, no CIDR, no IPv6); default egress (SSM, package and
  model downloads). Attached only to the GPU instance.
- The GPU instance (public IPv4 for outbound SSM/downloads only; nothing listens publicly; the server binds the private
  address and also checks the peer address).

### 3.2 Not changed
WEB and AAOS instance types, their security groups and routes, product services (`attune-api@web`, `attune-web@web`,
`web-aaos`, `api-aaos`) and their configuration (hashed before and after), IAM (users, roles, instance profiles).
The GPU instance uses the existing instance profile `attune-ec2-ssm-role`, as in round 3.

### 3.3 Optional, needs its own yes: AAOS live
AAOS reaches WEB only on 8443 (the product mTLS chain), so a live AAOS closing cannot reach the test API without a
change. Proposal: a second new temporary group `attune-closing-e2e-web-test` with **one inbound rule, TCP 8190 from the
AAOS security group `sg-0476f580c44063a5d`**, added to WEB's network interface **next to** its existing group for the
window, removed and deleted at the end (both verified by API). This is a temporary change of WEB's network
configuration. If the session ends before the removal, the rule stays inert (nothing listens on 8190 after the test
processes end) until it is removed on resumption. The AAOS harness then sends the closing's analysis and speech
requests to the test API (`CLOSING_LIVE_API`; it stands in for the Next speech route with the same request and the same
answer checks; the conversation reply stays replayed) and mirrors the vehicle speed of a driving case to the test API.
**Without this yes:** AAOS runs the interruption cases (including the corrected consent cases) with recorded responses,
labelled replay, and AAOS live is reported as blocked.

All of these calls passed a `DryRun` permission check on 2026-11-10 at 15:07 UTC (RunInstances, CreateSecurityGroup,
AuthorizeSecurityGroupIngress, ModifyNetworkInterfaceAttribute, TerminateInstances, DeleteSecurityGroup); quota
“Running On-Demand G and VT instances” 8 vCPU, no G instance exists.

## 4. Time limits, order and shutdown that survives a lost session

| | Hard limit from start | Layers |
| --- | --- | --- |
| GPU | 120 min | user data arms `shutdown -h +120` at boot with instance-initiated shutdown = **terminate** (independent of this session); local guard sends TerminateInstances at 115 min; the run plan ends work at 100 min |
| WEB | 150 min | OS `shutdown -h` timer (stop) armed at start; local guard |
| AAOS | 100 min | OS `shutdown -h` timer (stop) armed at start; local guard |

Order: check that no other experiment runs (no running/pending instance, no G instance, product hashes) → launch GPU
(setup ≈ 20–25 min) → start WEB ≈ 10 min later, build/verify the test stack → live WEB runs → start AAOS once WEB serves
(AAOS needs WEB: `curl http://127.0.0.1:3000/api/vehicle/state` = 200 on AAOS before its runs) → AAOS runs → pull the
evidence (SSM at ≈ 26–29 KB/s; packed early) → terminate GPU → stop **AAOS first, then WEB** → verify by API: GPU
`terminated`, its volume and group gone, the optional WEB group detached and deleted, WEB/AAOS `stopped`, no running
instance, no unattached volume, no Elastic IP. If the session is lost, the OS timers end every instance within its
limit; what can remain is the empty GPU security group (and, with 3.3, the inert WEB rule), removed on resumption.
No new run is started once the GPU is past 95 minutes; the remaining time goes to evidence transfer and cleanup.

## 5. Cost (official prices, AWS Price List API, effective 2026-11-01, eu-central-1, queried 15:02 UTC)

g5.xlarge 1.258 USD/h · r7i.2xlarge 0.6384 USD/h · m8i.2xlarge 0.50716 USD/h · gp3 0.0952 USD/GB-month ·
public IPv4 0.005 USD/h · data out 0.09 USD/GB (cross-zone 0.01 USD/GB each way).

| Item | Expected | At the hard limits |
| --- | --- | --- |
| GPU g5.xlarge | 100 min → 2.10 | 120 min → 2.52 |
| WEB r7i.2xlarge | 130 min → 1.38 | 150 min → 1.60 |
| AAOS m8i.2xlarge | 80 min → 0.68 | 100 min → 0.85 |
| GPU disk 100 GiB gp3 | 0.02 | 0.03 |
| Public IPv4 (3 hosts) | 0.03 | 0.03 |
| Data transfer | ≤ 0.01 | 0.02 |
| **AWS total** (taxes excluded) | **≈ 4.2 USD** | **≈ 5.05 USD** |

Proposed hard budget: **5.50 USD + tax** for this experiment, WEB and AAOS included. The provider calls of the live
analyses (≈ 150 `gpt-4o-mini` analyses, ≈ 0.1 USD) go to the existing provider account on WEB and are not AWS cost. The
WEB and AAOS root volumes are billed whether or not the instances run and are not counted as extra.

## 6. Samples and acceptance criteria (fixed before the run)

Every sample is reported (median, min–max; p95 only for n ≥ 20); no slow sample is removed and no single middle value is
chosen. Live (this run), replay (round 3) and mock results stay separate. The criteria are this plan's proposals; no
repository or OEM requirement exists for them.

| # | Samples | Criterion |
| --- | --- | --- |
| P1 warm | WEB live, 8 warm closings per language (n = 24) | C ends → personal audio starts ≤ 1.0 s in ≥ 90 % overall and per language; no overlap; no extra tap |
| P2 prepared start | 3 fresh API starts per language with the closing voice prepared at start (`ATTUNE_MENTAL_TTS_WARM_PROFILES=female-calm-v1`), first closing after the warm-up | C → personal ≤ 1.0 s in each of the 9; the warm-up's own time reported per profile (default, female), never inside a closing's numbers |
| P3 cold | 3 fresh API starts per language without preparation (today's start-up), first closing | reported only (no pass/fail); shows what P2 removes |
| P4 ready vs played | every live closing | playback starts ≤ 0.2 s after C ends when the audio was ready earlier, else ≤ 0.2 s after it is ready |
| P5 errors | every request | no failed analysis or speech request that was not cancelled; a refused spoken line is counted on its own (written summary stays, nothing long is spoken) |
| P6 memory | worker process group RSS and GPU memory every second (server log) | two resident models (default + female) use ≤ 16 GB of the A10G's 22.9 GB |
| P7 concurrency | 3 pairs of simultaneous closing-voice requests to one API | one `200` and one `429 NEURAL_TTS_BUSY` per pair, no worker failure; times reported |
| P8 AAOS (only with 3.3) | 6 complete closings (TR/EN/DE × CDP click and calibrated real touch) + the interruption cases | warm C → personal ≤ 1.0 s in ≥ 5 of 6; the app's player leaves `started` ≤ 1000 ms after the stop condition, measured only after Android reported `started` (else the case is blocked, not passed); consent before start: the player never starts; no closing audio afterwards in any case |
| P9 German acceptance | real provider on WEB, current prompt, 24 analyses per language (72) | reported with the round-4 validator (formal acceptance; content labelled separately); no threshold or test change |

Recorded for every live closing: end tap → A, A → B, B → C, C → personal audio; analysis time; summary text ready;
personal audio ready vs playing; speech request total, `verify`, `warm-wait`, worker and remote worker times (Server-Timing,
server log); memory series; HTTP status and errors; spoken line status. Speech-token generation and waveform decoding are
measured in a **separate diagnostic run** (`tts_device_benchmark.py` profile mode on the GPU, the lines returned by the
live run, 3 per language), never mixed into P1–P8, because its timers synchronize the GPU.

Real A/B/C durations (WAV frames, not estimates): A+B+C audio is 7.28–9.56 s in English (median 8.48), 8.64–12.56 s
in Turkish (10.56) and 8.52–11.40 s in German (10.20) over the 125 combinations per language, plus two ≈ 0.13 s pauses.
This is the time the personal line can be prepared during the closing; it is not a fixed 8–9 s and not a guarantee. The
goal is that the personal line follows C fluently, with as little waiting as possible.

## 7. Evidence

Raw JSON/CSV, server logs (numbers only), WAVs of the personal lines, timelines and the report go to a new Google Drive
folder (`Review-2026-11-10-round4-…`); each uploaded file is read back and its size and SHA-256 compared; earlier folders
are not touched. Listening links for TR/EN/DE (A/B/C + personal line) are given for the owner; no quality approval is
given or implied by the run.
