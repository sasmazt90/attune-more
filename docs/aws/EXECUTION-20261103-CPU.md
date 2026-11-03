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
production frontend build and TR/EN/DE TTS asset preflight passed. TTS asset preflight
is not evidence of successful speech synthesis or playback. Model weights, thresholds,
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
file persist across Stop/Start; an actual subsequent restart-cycle acceptance has
not yet been performed. Public IPs and short-lived demo TLS certificates still
require review after an EC2 restart.

The user entered the key interactively on WEB. Actual reference-audio ASR requests
returned 502 from both backends. A direct provider call identified HTTP 401,
`invalid_api_key` (SSM command `36632365-0f73-4279-9db6-63f6f6624747`). Authentication
has therefore failed. No Mental or ASR provider acceptance is claimed. The provider
error message and credential were not logged. The user reported possible repeated
pasting and was given the secure replacement command below.

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

0/10 required English full module E2E videos completed at this observation.
The earlier native blocked-screen recording is diagnostic only. Actual module
inference, complete results/history/session views, ordered Mental turns 1–5,
ATT-T03-05, WEB Vision DE ASR, AAOS Vision 3 GiB, Mental partial-session and
PARK/DRIVE transition acceptance remain open. Reference media retain the user's
platform assignments. Reference replay must be distinguished from physical camera,
microphone and hearing/listener acceptance.

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
