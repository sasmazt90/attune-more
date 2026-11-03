# CPU deployment continuation — 2026-11-03

Observation at 16:57 UTC: both existing instances are running and SSM is online.
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
path was added to both API environment files. Playback acceptance remains separate. Model weights, thresholds,
calibration and inference device settings remain unchanged.

AAOS 15 / API 35 resumed on M8i with the verified APK and 3072 MiB AVD memory.
The private mTLS API and AAOS loopback frontend return 200. The native application
accepts PARK. Backend vehicle signals are simulated; native restrictions still
need real transition acceptance. The emulator reports zero native camera devices.

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

Six of ten English reference-replay videos are uploaded and downloaded back for
byte/SHA-256 verification: WEB Dental, WEB Skin, WEB Mental, AAOS Mental, WEB Hearing and AAOS Hearing.
See [video manifest](evidence/english-e2e-videos-20261103.json) for URLs, mappings,
recording boundaries and source provenance. Actual model/provider responses,
complete result inspection and saved-history reopening were exercised. These are
reference-media integration results, not physical-camera or human-listener acceptance.
AAOS Mental has a disclosed recording gap before same-session result inspection.

The emulator microphone was initially silent despite its Pulse source. Enabling
`adb emu avd hostmicon` fixed actual ASR input; startup now applies it when the
configured audio bridge is enabled. Both WEB and AAOS completed five ordered
Mental UI turns with real ASR, LIVE_OPENAI replies, Chatterbox generation/playback
and a saved LIVE_OPENAI summary. The original reference audio language is preserved;
application UI and requested provider reply language are English.

AAOS Dental is currently blocked: remote frames arrive, but the WebView preview
is black and the active face model reports no face. No result is fabricated.
AAOS Skin/Vision, WEB Vision EN/DE completion and full partial-session persistence remain open.
Both Hearing DIN journeys completed with controlled responses and real audio/scoring.
Native backend DRIVE and emulated VHAL driving destroyed the WebView; PARK restored
it, and HOME/foreground transitions passed. WEB Skin and AAOS Hearing also passed
with 57 seconds of overlapping execution; see [native/concurrency evidence](evidence/native-concurrency-20261103.json).
These are emulator/controlled-input checks, not physical vehicle or human hearing acceptance.
The earlier native blocked-screen recording is diagnostic only.

AWS Pricing API returned R7i Linux On-Demand **$0.63840/hour**. With the previously
verified M8i **$0.50716/hour** and two active IPv4 addresses **$0.01000/hour**, the
combined running rate is **$1.15556/hour**, excluding EBS, transfer, providers and tax.
Existing EBS remains approximately $25.704/month. Cost Explorer access is denied;
these are rates and duration-based estimates, not billed totals. The earlier AAOS
session estimate was $0.69262 compute/IPv4 before the current restart.

The current session has not been stopped yet. Both instances must receive normal
Stop and an AWS API `stopped` readback when work completes or cannot progress.
There is no two-hour automatic cutoff. No new infrastructure or DNS changes occurred.

Validation: 36 local AWS preparation/origin tests and the Node routing/locale checks passed, including shared provider-file
privacy and symlink handling. Live installation/proxy observations above are separate
from automated tests and do not establish end-to-end health-module acceptance.
