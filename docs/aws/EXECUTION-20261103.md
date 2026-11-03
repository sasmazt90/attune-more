# Task 13 — actual EC2 installation progress, 2026-11-03

This execution record supersedes the pre-start state in the preparation documents.
Models, inference parameters and the verified Cloud staging bundles are unchanged.
The user approved operation until completion or an unrecoverable blocker, with cost
monitoring and normal Stop afterwards; there is no two-hour automatic cutoff.

## Actual observations

- AAOS `i-0f4cca4e92e94c351` started at approximately 15:04 UTC. SSM and KVM work.
- Six official Android archives were downloaded on the host and checked against the
  previously verified SHA-256 manifest. SDK metadata must use `common/01`; `common/02`
  caused `avdmanager` to reject it and infer inconsistent paths from source.properties.
- Android Automotive 15 / API 35 booted with 3072 MiB requested RAM, 3,050,220 KiB
  reported guest memory and a 1280×800 display. The verified cloudDemo APK installed.
- Caddy 2.10.2 and Node 22.20.0 match the prepared archive hashes. Python 3.11.17
  came from the official 20261003 standalone release (archive SHA-256
  `aadcba18994cb8f9ee752aceb31d61e04f75b5d900d76fb575c6fbfabadec434`).
  All 19 audio-service wheels match the prepared backend wheel manifest; pip check passed.
- PulseAudio microphone/output sinks and the loopback audio bridge run. This does
  not establish guest audio, physical microphone, listener or calibration acceptance.
- The guest reports **zero camera devices**. Remote reference-media/camera transport
  still requires the deployed backend and a separate real integration test.
- A private CA and AAOS server/client certificates were generated on the AAOS host.
  Direct-IP TLS needed `default_sni` because IP clients may omit SNI. The verified
  HTTPS request now returns 401 without authentication. Private mTLS remains untested
  because the WEB host is stopped. Private keys and credentials are not in Git.
- Immutable public GitHub source was transferred directly to EC2. No application
  archive was uploaded to Drive. The installed application source is `11ea103`,
  with the separately documented deployment configuration corrections applied.

## WEB capacity and selected 8-vCPU type

Repeated actual `StartInstances` calls for `g6.2xlarge` returned
`InsufficientInstanceCapacity` in `eu-central-1c`. An initially approved g6.4xlarge
change was blocked by IAM and never applied. The user then selected 8-vCPU
alternatives because the observed G/VT quota is 8 vCPU; their separate 16-vCPU
quota request remains pending and was not modified or canceled.

After IAM permission became available, the existing WEB instance was changed to
`g5.2xlarge`, then to `g6e.2xlarge`, in the user's approved order. **Both actual
start calls returned InsufficientInstanceCapacity.** Its selected type is now
`g6e.2xlarge`; it has not reached running. The original EBS volume, VPC, subnet and
Security Group are preserved. No new EC2, VPC or EBS was created.

| Authorized alternative | AZ offering | vCPU / RAM | GPU | AWS USD/hour |
|---|---|---|---|---:|
| g5.2xlarge | eu-central-1c | 8 / 32 GiB | A10G, API memory 22,888 MiB | 1.51560 |
| g6e.2xlarge | eu-central-1c | 8 / 64 GiB | L40S, API memory 45,776 MiB | 2.80350 |

Both support the existing x86_64/EBS/UEFI platform. The prepared backend uses
`torch==2.9.1+cpu`, `torchvision==0.24.1+cpu` and `onnxruntime==1.26.0`; the isolated
TTS runtime uses torch/torchaudio 2.6.0+cpu. These wheels have no CUDA driver
requirement. A type change does not enable or validate GPU acceleration. No weights,
thresholds, calibration, precision or inference device settings were changed.
Live runtime compatibility remains unverified until an instance actually boots.

An AZ offering is not a capacity guarantee. Actual API errors and prices are in
`evidence/gpu-alternatives-20261103.json`. The g6e + AAOS hourly compute and two
active IPv4 addresses would total **$3.32066/hour**, before storage, transfer,
provider use and tax; the stopped WEB instance has incurred no running compute.

## Acceptance status

**0/10 required English module E2E videos completed.** Dental, Vision, Skin, Mental
and Hearing are blocked on both platforms by the unavailable WEB/backend host.
The real AAOS application displays the fail-closed vehicle-data-unavailable screen.
A short diagnostic recording is not a completed module journey and is not counted.

ATT-T03-05, WEB Vision EN/DE provider ASR, AAOS Vision at 3 GiB, Mental partial-session,
ordered Mental turns, native PARK/DRIVE transitions, real media, complete results,
history and session checks remain open. WEB provider secrets cannot be audited
until that host starts. Their presence is unknown; no replacement weights or mock
provider results were introduced.

The 25 reference files were downloaded, sized and locally hashed. Image contact
sheets were visually reviewed; the requested platform assignments were retained.
Mental files remain ordered 1–5; their spoken content has not yet been reviewed.
The detailed private input manifest remains in the ignored execution directory.

## Validation and restart notes

29 AWS preparation tests and the cloud routing/locale checks pass. Real SSM receipts
are summarized in `evidence/execution-20261103.json`; these are installation evidence,
not model/provider acceptance. The archive installer and AVD configuration were
exercised on the actual M8i host. Existing installed SDK packages are retained when
`prepare.sh` is rerun, avoiding unintended upgrades.

Runtime paths: `/opt/attune`, `/opt/android-sdk`, `/opt/node`, `/opt/python311`,
`/opt/attune-venv`, `/etc/attune`, `/var/lib/attune/evidence`. Source/model staging in
Cloud remains intact. After an EC2 stop/start, recheck its assigned public IP and
certificate validity before updating the private demo endpoint configuration.
Do not print secret environment files. No DNS modification is authorized.

AWS Cost Explorer returns AccessDeniedException, so actual billed cost is unavailable.
Use observed instance duration × $0.50716/h plus active IPv4 $0.005/h as the AAOS
compute/network-address estimate. Existing 270 GiB gp3 storage remains approximately
$25.704/month while stopped. Provider API calls during this resume: none.
