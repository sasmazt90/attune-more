# Final AAOS runner and observer preparation

This change prepares PR #5's existing manually launched AAOS job. It changes no
application functionality, approved recordings, Hearing scoring or safety policy.
It does not establish AAOS acceptance, authorize deployment, or merge the PR.

## Private runtime delivery

The runner downloads the existing owner-approved original ZIP through the official
Google Drive v3 API using a **read-only service account explicitly granted access**.
An authenticated ChatGPT Drive connector session is not a credential for Actions.
No anonymous Drive link, cookie export, public release, paid storage, Actions
cache, model artifact upload, or access to Cloud `/workspace` is used.

Required repository configuration:

| Kind | Name | Meaning |
| --- | --- | --- |
| Actions secret | `ATTUNE_AAOS_DRIVE_SERVICE_ACCOUNT_JSON` | Google service account JSON key with reader access to only the approved ZIP |
| Actions variable | `ATTUNE_AAOS_TTS_BUNDLE_FILE_ID` | Drive ID of `Chatterbox-Multilingual-V3-offline-20261021-v1.zip` |

The entry workflow passes only this named secret to the reusable workflow.
The backend bearer token is generated per job, masked, and held only in the
runner's environment for its loopback backend and same-origin frontend proxy.
It is not a repository secret, browser value, committed value or artifact.

Owner configuration procedure (no key values should be pasted into chat):

1. Use an existing authorized Google project with Drive API enabled. Do not enable
   billing or purchase a service. If this configuration is unavailable, stop.
2. Give the service account **Viewer** access to the existing original ZIP only.
   Keep General access **Restricted**; do not publish the file or share the folder
   broadly. The original ZIP is already owner-uploaded; no new model upload is
   implemented by this change.
3. In repository Settings → Secrets and variables → Actions, set the secret and
   variable above. The Drive API read is authorized only as that service account.
4. Confirm the account can read/download that exact file. If this cannot be
   independently confirmed, readiness remains BLOCKED. Connector access alone
   does not confirm repository secret availability or service-account access.

The importer pins the original 3,283,572,066-byte ZIP to SHA-256
`5e98c442627ad78ce22a9bff151b0badd2343f1392b590b42889a0beb679f3fc`.
It verifies the exact member set and all 117 recorded member sizes/hashes before
installing or loading code. Traversal, duplicates, unexpected members and symlinks
are rejected. The original bundle's tokenizer cache, default `conds.pt`, Perth
watermark assets and pkuseg ZIP/cache layout are preserved.

Source packaging uses the bundle's pinned official source and the exact official
Perth packaging files at `ff1c8ac55a976971245cdd53c18d6131ca00d993`.
SHA-256-pinned Python 3.11 Linux wheels reproduce the successful Cloud dependency
versions, including CPU Torch/torchaudio 2.6.0. Source installs are offline with
`--no-deps --no-build-isolation`; no recursive Git dependency resolver is invoked.
The original verified Cloud runtime and bundle remain untouched.

## Gates and resource limits

- Standard `ubuntu-24.04`, public-repository guard, one initial attempt, 40 minutes.
- Private import/install has an eight-minute internal deadline and nine-minute
  step cap. It requires 20 GiB free before download. Only the disposable runner's
  downloaded ZIP is released after verified extraction.
- Before emulator launch, the existing offline model/source preflight, real native
  imports and isolated real backend/frontend readiness must pass. Checks observe
  unauthenticated backend 401, authenticated no-consent 403, and authenticated
  frontend-proxy moving denial 409 **without synthesis**.
- Require at least 12 GiB available memory and 22 minutes remaining before boot.
  A separate launch guard rejects a missing/failed neural readiness receipt.
- No inference-network fallback, security bypass, paid runner or automatic job
  retry. Evidence remains bounded to 49 MiB source files plus ZIP overhead within
  50 MiB, with one-day retention. Model assets and credentials are outside the
  evidence directory.

Fresh installation was executed in 75.064 seconds in Cloud Debian 13 / CPython
3.11, with `pip check`, native imports and all 50 installed source fingerprints
passing. No model was constructed and no inference was repeated. All selected
manylinux wheels require glibc 2.28 or older; Ubuntu 24.04 provides 2.39. This is
ABI evidence, not an executed Ubuntu installation or private Drive transfer.
The retained historical standard-Ubuntu AAOS evidence showed 98 GiB free after
runner cleanup and an approximately 11-minute complete old run. Those figures do
not guarantee current runner capacity or the combined final run's duration.

The new isolated environment occupied approximately 2 GiB. The verified bundle
expands to about 3.28 GB; download/extraction peak includes another 3.28 GB ZIP.
Private transfer throughput and combined emulator/inference peak memory remain
unmeasured. The finite job gates stop rather than expand the authorized budget.

## Additional actual-emulator observations

All historical 17 automotive scenarios remain, as do 27 localized route visits,
194 original AAC decodes and 15 module/language playback cases.

`hearing-scored-locales` runs the actual Hearing UI for TR/EN/DE. Only the random
seed and synthetic engineering replies are controlled. The real bank loader,
hash checks, PCM presentation, response gate, 24-trial staircase, saved result
and localized scorecards remain unchanged. Each run verifies 26 completed stereo
PCM sources (two channel checks plus 24 DIN presentations), the selected bank,
submitted responses and expected 50% score / -1 dB SNR result. Channel checkboxes
are synthetic test acknowledgments, not human headphone or clinical acceptance.

`mental-neural-interruptions` retains the actual English WAV returned by this
run's successful neural transport check. It reuses those real bytes through the
production shared WAV lifecycle, avoiding seven extra synthesis requests. It
observes active output followed by mute, AbortSignal cancellation, real synthetic
consent withdrawal, locale change and SPA navigation/session boundary. It checks
the stopped/cleared source and no restart for 1.5 seconds after restoration.
Independent backend-motion and actual emulator Car UX transitions must destroy
the active WebView; a fresh target must contain no stale session/media state.
The motion observation alone loops the unchanged real WAV so natural clip
completion cannot falsely establish safety cessation. Destruction must be observed
within 30 seconds, before the shared output deadline; no new audio is synthesized.
No media event, neural response, vehicle safety gate or scoring result is mocked.

These are shared output and route/session-boundary checks. They do not start a
microphone, paid LLM, full live conversation or physical vehicle session. Emulator
`-noaudio` remains: native WebView playback events verify software transport and
lifecycle, not acoustic listening or pronunciation.

Host preparation evidence: 68 focused tests plus 14 subtests passed; actionlint,
JavaScript/Python syntax and offline source wheel builds passed. The new Hearing
observer also passed 72 actual UI trials across TR/EN/DE in Cloud Chromium.
Five interruption-observer checks passed in Cloud Chromium with a clearly labeled
prior verified WAV fixture. Neither browser check establishes AAOS acceptance or
new neural inference. Existing Cloud speech evidence is reused, not regenerated.

## Launch handoff and current blocker

No manual run was dispatched during preparation. Secret administration is not
available through the GitHub connector, and no runner-compatible Drive credential
is bound in Cloud. Private authorization, actual transfer and combined runner
timing therefore remain **BLOCKED / UNVERIFIED**. Do not launch merely because
static CI is green; first confirm the configuration and private reader access.

Once prerequisites are confirmed and the final PR HEAD's CI/review checks pass:

1. Open https://github.com/sasmazt90/attune-more/actions/workflows/e2e-audit.yml.
2. Run workflow → `feature/localization-en-de-tr-20261020`.
3. Set `expected_source_sha` to the **exact final verified feature HEAD**.
4. Launch once; do not rerun automatically. Inspect actual results/artifacts before
   considering merge. This preparation does not authorize deployment.
