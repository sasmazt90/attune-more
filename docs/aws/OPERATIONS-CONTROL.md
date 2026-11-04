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

- Origins use `attunemore.sasmaz.digital` and `aaos.attunemore.sasmaz.digital`, never an address.
  START confirms them on both hosts and restarts the affected services if they differ.
- The private mTLS link between the hosts keeps a private CA valid 10 years, leaves 825 days,
  constrained to its two private names. The CA key was destroyed, so renewal means re-running
  the script, which issues a new CA. STATUS warns 30 days ahead.

Unchanged across a restart, verified in [evidence/restart-acceptance-20261104.json](evidence/restart-acceptance-20261104.json):
OpenAI key, application and models, frontend build, AAOS image and emulator, APK, mTLS.

## Addresses and certificates

| Name | Host | Certificate |
|---|---|---|
| `attunemore.sasmaz.digital` | WEB | Browser-trusted, Let's Encrypt |
| `aaos.attunemore.sasmaz.digital` | AAOS | Browser-trusted, Let's Encrypt |

START does this on its own, so a normal Stop and Start needs no DNS step:

1. Confirms the AWS account and both instance IDs.
2. Authenticates to IONOS before starting anything. If that fails while the hosts are stopped, it stops there and nothing is charged.
3. Starts the instances and reads each public IPv4 from AWS for that exact instance ID.
4. Writes the A record only if it differs. TTL is 60 seconds.
5. Asks the IONOS name servers and this PC's resolver, and reports each result.
6. Renews a certificate when it is missing, wrong, or in the last third of its lifetime.
7. Checks HTTPS the way a browser does, with no certificate bypass or address pinning, and expects 401 without a login.
8. Opens both addresses in the ordinary browser.

**Limits on what it can write.** Only the two names above, and only an IPv4 address that is public and is not this PC's own address. It never touches the root domain, website, mail or any other record. A name already used by another service is reported and left alone: the tool updates only a record whose ID it saved when creating it, in `%USERPROFILE%\AttuneMore\dns-records.json`.

**Why DNS validation.** Port 443 is limited to the operator's address and port 80 is closed, so a public CA cannot reach the hosts, and opening them just for a certificate was ruled out. Validation therefore uses ACME DNS-01: for about a minute during issue or renewal there is a TXT record at `_acme-challenge.<name>`, removed afterwards whether validation passed or failed. These are the only records other than the two A records that the tool writes. The owner should know about them, because the DNS authorization names A records.

**Where the secrets are.**

| Secret | Where | Leaves it? |
|---|---|---|
| IONOS API key | This PC, `%LOCALAPPDATA%\AttuneMore\secrets\ionos-dns.xml`, encrypted for this Windows user | Only in the `X-API-Key` header to IONOS |
| Let's Encrypt account key | This PC, `%USERPROFILE%\AttuneMore\secrets\acme-production-account.xml`, same protection | Never. It signs requests only |
| Certificate private keys | Each host, `/etc/attune/tls`. Reused on renewal | Never |

**Renewal.** Certificates last 90 days. START checks them every time and renews any in the last third of its lifetime, so regular use needs nothing else. A stopped host cannot renew, and that does not matter, because START runs first. Press START on running hosts if they ever stay up for weeks: it changes nothing else, and STATUS and the readiness report warn 30 days before expiry. To renew now, add `-RenewCertificates` to START.

**One-time setup.** Let's Encrypt needs an account and acceptance of its terms, so this is the owner's own step. It sends no email or personal data:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\AttuneMore\bin\AttuneControl.ps1" -Action SetupCertificates
```

**If something goes wrong.**

| Message | Meaning | What to do |
|---|---|---|
| IONOS key file is missing or could not be opened | Wrong Windows user, or the file is gone | Save it again with the command in the message |
| IONOS refused the API key | Expired or revoked | Create a new key at IONOS and save it |
| Already points to … and this tool did not create that record | The name is in use | Decide who owns the name. The tool will not overwrite it |
| This PC still resolves it to … | IONOS is right and a local resolver is caching | Press STATUS in a few minutes |
| Certificate is not trusted | Issue or install failed | Read the certificate problem above it in the report |

**Known limits.**

- Certificates are public record. Issuing them lists both names in public Certificate Transparency logs. Access does not change: the Security Groups still decide who can reach the hosts.
- After STOP the records keep the last address, because AWS releases it and DNS is only written at START. Until the next START, that address could be given to another AWS customer. Elastic IPs would remove this, at about $7.30 per month for two, and need the owner's approval.
- HTTPS stays limited to one source address by the Security Groups. START offers to update it when this PC's address changes. Other devices need their own rule.
- Browser data is per origin, so records saved under the old address are not visible at the new one.
- Dated records under `docs/aws/evidence` and `CONTINUATION-20261103.md` keep the old names, because they describe what happened then.

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
