# CPU deployment continuation — 2026-11-03

Deployment and acceptance record — final shutdown evidence is recorded below when complete.
The user explicitly approved WEB `r7i.2xlarge`; GPU capacity retries have ended.
The original instance IDs, EBS volumes, VPC, subnet and Security Groups are retained.
This record supersedes the stopped GPU-attempt state in EXECUTION-20261103.md.

## Installed services and assets

WEB started at 16:28 UTC. The two backend services, two frontend services, capture
bridge and Caddy are enabled and active. Both backend processes run on WEB:
`attune-api@web` on loopback 8000 and `attune-api@aaos` on loopback 8001.
AAOS reaches its backend through private mTLS; it does not need a provider key
copied to the emulator host or to the APK.

All 52 application model assets passed the final manifest checks on WEB. Step0
and Skin ONNX files were restored with the repository tool; the 31-member Regional
package and 117-member Chatterbox archive were verified. Backend dependency checks,
production frontend build and TR/EN/DE TTS asset preflight passed. TTS asset preflight alone
is not speech/playback acceptance. Subsequent actual generation returned a 9.44-second
English WAV (453,164 bytes; SHA-256 b373de69d69ef8459d52625bbe498fba3712987e793467b448ce55e0785168c9)
through the Next.js proxy in 77.29 seconds. Speaker profile female-calm-v1 uses its
existing approved reference and generation settings. The missing
`ATTUNE_MENTAL_TTS_FEMALE_CONFIG=/opt/attune-neural/config-female-calm-v1.json`
path was added to both API environment files. Playback acceptance remains separate. Model weights, thresholds and calibration remain unchanged. The user subsequently
approved CPU MediaPipe execution only for the AWS E2E frontend build. Its GPU default
remains unchanged outside that explicitly selected build.

AAOS 15 / API 35 resumed on M8i with the verified APK and 3072 MiB AVD memory.
The private mTLS API and AAOS loopback frontend return 200. The native application
accepts PARK. Backend simulation and emulated VHAL PARK/DRIVE transitions passed
on the actual native application, including WebView teardown/restoration and
HOME/foreground handling. These are not physical-vehicle tests. The emulator
reports zero native camera devices; assigned reference images use the real mTLS bridge.

Strict Caddy SNI validation requires the private upstream Host to match
`attune-internal`. The private Next.js upstream retains the AAOS application origin
`127.0.0.1:3000`. Both proxy corrections have been exercised on the hosts.

## Persistent provider secret and real authentication result

Both API units load `/etc/attune/provider.env` after their role environment file.
The shared file is root-owned mode 0600 and both running API processes have a
nonempty key. Values were never emitted. Enabled systemd units and the EBS-backed
file persist across Stop/Start; an actual subsequent EC2 Stop/Start-cycle acceptance has
not yet been performed (both systemd services were restarted successfully). Public IPs and short-lived demo TLS certificates still
require review after an EC2 restart.

The first credential failed actual provider authentication with HTTP 401,
`invalid_api_key`. After the user securely replaced it and restarted both units,
the real OpenAI models endpoint returned HTTP 200. Each running process was
verified to match the file in memory, reporting booleans only. The valid key was
not modified. No credential or provider error message was logged.

Both backend endpoints then transcribed the supplied Mental-Health-1 audio using
the unchanged `gpt-transcribe` request (HTTP 200, 135 transcript characters).
That actual transcript produced a nonempty LIVE_OPENAI conversation reply on each
backend; one completed turn also produced a real LIVE_OPENAI partial-session analysis.
Both roles also completed Mental-Health-1 through Mental-Health-5 in order, with
real ASR, five LIVE_OPENAI replies and a final LIVE_OPENAI summary. These establish
provider integration at the API boundary, not microphone playback, full five-turn
UI/session acceptance or any of the ten videos.

The AWS frontend build now explicitly sets `NEXT_PUBLIC_ATTUNE_SPEECH_PROVIDER=openai`
to select the existing consent-gated cloud recognizer. Backend ASR enablement alone
does not select that browser path. The production rebuild passed on WEB.

In an interactive Session Manager terminal on the existing WEB host:

```bash
sudo python3 /opt/attune/scripts/aws/configure_provider_secret.py --replace
sudo systemctl restart attune-api@web.service attune-api@aaos.service
```

Paste the key only into the hidden prompt, once. Do not put it in command arguments,
chat, source, Drive, screenshots or evidence files. The helper atomically replaces
the root-owned file, keeps mode 0600, rejects symlinks and repeated `sk-` prefixes,
and leaves the old file intact if input validation fails. A successful save confirms
storage only; a subsequent real provider response is required for authentication.

## Acceptance and cost

English reference-input video delivery is tracked in the
[verified manifest](evidence/english-e2e-videos-20261103.json), including file IDs,
byte counts, SHA-256 readback, mappings and source provenance. Recordings use the
real AWS application, Android 15 WebView, original models and configured providers.
They do not establish physical-camera, calibrated human-hearing or clinical acceptance.
AAOS Mental has a disclosed recording gap before inspecting the same session's saved results.

The emulator microphone was initially silent despite its Pulse source. Enabling
`adb emu avd hostmicon` fixed actual ASR input; startup now applies it when the
configured audio bridge is enabled. Both WEB and AAOS completed five ordered
Mental UI turns with real ASR, LIVE_OPENAI replies, Chatterbox generation/playback
and saved LIVE_OPENAI summaries. The original reference audio language is preserved;
application UI and requested provider reply language are English. The one-turn partial
session also passed real ASR/reply/TTS/summary and reopening after page reload.
A separate actual one-turn conversation passed summary cancellation: no late record
after five seconds or page reload.

The approved CPU frontend delegate resolved software-GPU face/camera stalls.
WEB Vision EN and DE each completed two assessments (48 valid trials per language),
using actual OpenAI ASR. AAOS Vision completed 24 valid trials at 3072 MiB with
actual Android microphone capture. The first German synthesized phrase was
misrecognized and failed; the existing supported command “Nicht erkennbar” then
completed the full UI flow. No parser, freshness threshold or model was relaxed.
AAOS Skin completed its three real responses and all six anatomical result tabs,
recommendations, unmeasured findings and saved history; the final recording adds
explicit scrolling for the narrow native display.

The remote camera adapter incorrectly emitted `ended` during intentional
`MediaStreamTrack.stop()`. Dental then aborted before analysis. The adapter now
preserves native stop semantics; unexpected transport loss and the unchanged
750 ms freshness limit still emit `ended`. Three lifecycle regressions passed;
the old implementation fails the intentional-stop case. Production build and
actual Dental flow passed on the patched build: HTTP 200, three measured views,
all result cards/layers/measurement notes and saved-history reopening. The assigned
female bite photo did not satisfy the unchanged capture gate. Existing skip was
used; bite alignment remains unmeasured. The AAOS Dental acceptance status is
PARTIAL, although its complete recorded flow correctly presents that limitation.
An initial WebView response-body observer failure was preserved and corrected to
record HTTP status independently; no model output was substituted.

Both Hearing DIN journeys use controlled listener responses and real generated
audio/scoring. Native backend DRIVE and emulated VHAL driving destroyed the WebView;
PARK restored it. WEB Skin and AAOS Hearing also passed with 57.128 seconds of
overlapping execution. See [additional acceptance evidence](evidence/native-concurrency-20261103.json).
Neither emulated vehicle signals nor controlled DIN inputs establish physical acceptance.
The earlier native blocked-screen recording is diagnostic only.

AWS Pricing API returned R7i Linux On-Demand **$0.63840/hour**. With the previously
verified M8i **$0.50716/hour** and two active IPv4 addresses **$0.01000/hour**, the
combined running rate is **$1.15556/hour**, excluding EBS, transfer, providers and tax.
Existing EBS remains approximately $25.704/month. Cost Explorer access is denied;
these are rates and duration-based estimates, not billed totals. The earlier AAOS
session estimate was $0.69262 compute/IPv4 before the current restart.

Both instances received normal Stop (no Force/hibernate). WEB was confirmed stopped
at 2026-11-03T19:07:43.341397+00:00; the final DescribeInstances readback at
2026-11-03T19:09:19.201027+00:00 confirms **both stopped**. API request ID:
`2b682cf1-53f8-4a53-ae84-285eca146f03`. See [Stop evidence](evidence/final-stop-20261103.json).
Original volumes, subnet and Security Groups are retained. No new infrastructure,
DNS changes or main merge occurred.

Current-session paid runtime to Stop request: WEB 2.6478 hours,
AAOS 2.6707 hours. Compute plus IPv4 estimate is
$3.0714 for this session, or
**$3.7640 including the earlier AAOS session**.
EBS, transfer, OpenAI and tax are excluded; EBS continues while stopped.
Actual AWS/provider billing was not available. See [cost calculation](evidence/final-cost-20261103.json).

All ten English recordings are uploaded and downloaded back with byte/SHA-256
verification. Controlled-input acceptance: **9 PASS, 1 PARTIAL (AAOS Dental bite)**.
Outstanding: physical camera/microphone, calibrated human hearing, physical vehicle,
full bite alignment with a valid input, and a separate EC2 Stop/Start-cycle test.
The enabled systemd/secret/AAOS boot configuration is persistent, but no completed
Stop/Start acceptance cycle is claimed. Demo IP/TLS must be reviewed before a future restart.

Validation: 36 local AWS preparation/origin tests and the Node routing/locale checks passed, including shared provider-file
privacy and symlink handling. Live installation/proxy observations above are separate
from automated tests and do not establish end-to-end health-module acceptance.

Final implementation validation: all GitHub jobs passed for `a133830e83c057708f251b69325c3068f0a080f7`;
local lifecycle regressions (3), deployment/wrapper tests (13) and locale/consent/source
regressions (17) passed. These automated checks remain distinct from the live
controlled-input evidence above. Final docs-only HEAD is reported in PR #22.
