# One-click control: START, STOP, STATUS, LOGIN

Everyday control of the two existing EC2 instances from Windows. It creates no AWS
resources and changes no DNS.

| Desktop shortcut | What it does |
|---|---|
| START ATTUNE.MORE | Starts both instances, starts services, verifies everything, reports READY, PARTIAL or ERROR, opens the browser |
| STOP ATTUNE.MORE | Normal stop of both instances, confirms with AWS, shows session cost and continuing storage cost |
| STATUS ATTUNE.MORE | Shows state and cost, and service health if running. Starts nothing |
| LOGIN ATTUNE.MORE | Shows the web page login in that window only. Needs the instances running |

Install or refresh the shortcuts after updating the repository:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\aws\windows\Install-AttuneShortcuts.ps1
```

## Access

The account has no IAM users by default, so `scripts\aws\windows\Setup-AttuneOperator.ps1`
creates one, run once by the account owner:

| Identity | Used by | Allowed |
|---|---|---|
| IAM user `attune-operator` | Browser sign-in through `aws login`. No access keys | Assume the two roles below, nothing else |
| Role `attune-ops-control` via profiles `attune-desktop`, `attune-claude` | Desktop tool, Claude | Start, stop and run commands on the two instances, read state, port-forward, edit the HTTPS source IP on their two Security Groups |
| Role `attune-ops-verifier` via profile `attune-ag` | Antigravity | The same, without Security Group edits |

Both roles carry `infra/aws/iam/no-new-infrastructure.json`, an explicit deny on creating
or terminating infrastructure. `scripts\aws\windows\Test-AgentAccess.ps1` proves a profile's
limits using dry runs; results are in [evidence/agent-access-20261103.json](evidence/agent-access-20261103.json).
Sign-in lasts up to 12 hours. When it expires the tool opens the browser. The tool refuses
to run as the root user.

## What survives a restart, and why

A restart assigns new public IPs. The first deployment had written the old addresses into
six settings files and its certificates, so the applications stopped answering after a
restart. `scripts/aws/apply_stable_config.py` was applied once to fix this:

- Origins use `attune.sasmaz.digital` and `aaos.sasmaz.digital`, never an address.
- Certificates come from a private CA valid 10 years, leaves 825 days, constrained to the
  four Attune names. Existing private keys stayed on their hosts. The CA key was destroyed,
  so renewal means re-running the script, which issues a new CA. STATUS warns 30 days ahead.

Unchanged across a restart, verified in [evidence/restart-acceptance-20261104.json](evidence/restart-acceptance-20261104.json):
OpenAI key, application and models, frontend build, AAOS image and emulator, APK, mTLS.

## Stable addresses

DNS for the two names does not exist yet, and changing it needs the owner's approval.
Until then START opens a dedicated browser profile that maps both names to the current IPs,
which works on that PC only. The private CA is not trusted by default, so the browser warns
until the certificate at `%LOCALAPPDATA%\AttuneMore\attune-private-ca.crt` is trusted.

Options for permanent addresses:

| Option | Extra cost | Needs | Effect |
|---|---|---|---|
| Keep the mapped browser | None | Nothing | This PC only |
| Update IONOS records on each START | None | An IONOS API key stored on this PC | Any allowed device; addresses update at each START |
| Elastic IPs plus fixed A records | About $7.30 per month for 2 addresses | Approval for paid addresses and one DNS change | Never changes; simplest |

HTTPS is limited to one source IP by the Security Groups. START offers to update it when this
PC's address changes. Other devices would need their own rule.

## Costs

Rates are recorded AWS On-Demand prices in Frankfurt. Estimates, not bills, excluding data
transfer, OpenAI and tax.

| While | Compute and public IPv4 | Storage |
|---|---|---|
| Running | About $1.16 per hour | Continues |
| Stopped | $0.00 | About $25.70 per month |

## Deploying a release

`scripts/aws/deploy_release.py --commit <full SHA>` installs one pushed commit on both running
hosts from the public GitHub archive, rebuilds the frontend with the AWS flags and records
provenance. Model weights, secrets and the build cache are outside the archive and are not touched.
Do not patch files on a host by hand. Provenance would no longer match a commit.
