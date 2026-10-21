# AAOS run #123: private Drive metadata failure

Run: https://github.com/sasmazt90/attune-more/actions/runs/39564541338

Tested source: `cfcdd5341d9b26053ad5d846bee7224cd672c74b`.
Job: `119103561468` (`aaos-emulator / validate`).

The complete 596-line job log and the original 18,151-byte evidence ZIP were
inspected. The evidence ZIP SHA-256 is
`596b1a62000d1ee6e19f906946e53bdfc373e6e4e8c812a03e9bca2fe43ce81d`.

| Observation | Evidence and conclusion |
| --- | --- |
| Credential-shape check | Passed at 07:48:31 UTC. This validates JSON/selector shape, not Google authorization. |
| First failure | At 07:48:56 UTC, the importer reported `HTTPError`, exit 69. |
| Failing operation | `GET https://www.googleapis.com/drive/v3/files/{file_id}` with `fields=name,size,trashed,capabilities(canDownload)`. The file ID is intentionally redacted. |
| Source attribution | At the tested source, `provision_neural.py:87–88` makes the metadata request and calls `raise_for_status()`. This is the importer's explicit HTTPError source. Media failures instead produced `PRIVATE_DRIVE_DOWNLOAD_BLOCKED`. |
| HTTP status | **UNRECOVERABLE from retained evidence.** The catch at lines 195–202 kept only the exception class. Neither the full log nor `neural-provision.json` contains the response status or provider reason. |
| Artifact receipt | `{"status":"BLOCKED","reason":"HTTPError","inference":"NOT_EXECUTED"}`. |
| Downstream work | ZIP media download, installation, Android SDK setup, image/build, neural readiness and emulator acceptance were not reached. |

The owner confirms Reader access and configured repository secret/variable. The
retained evidence does not establish whether Google's rejection concerned API
enablement, token scope, file visibility, quota or another provider condition.
In particular, 400, 403 and 404 must not be guessed from `HTTPError` alone.

## Confirmed correction

The confirmed code defect is **loss of HTTP diagnostics**, not a proven permission
or transfer-policy defect. The importer now retains only:

- HTTP status, metadata/media stage and method;
- a fixed endpoint template containing `{file_id}`, never the actual identifier;
- the public request selector (`fields=...` or `alt=media`);
- recognized, allowlisted Google reason codes, when present in metadata errors.

Free-text messages, response/request objects, headers, tokens, private filenames,
account/project identifiers and response bodies are not written to logs or
receipts. Streaming media error contents are not inspected. Metadata and media
failures remain BLOCKED with exit 69; authentication, scope, timeout, retry,
private access and archive integrity controls remain unchanged.

There is also a bounded `--metadata-only` mode. It uses the same read-only service
account and file selector for one metadata request, then exits without downloading
the ZIP, installing dependencies, generating speech or launching the emulator.
The investigation did not dispatch a workflow. A dependency-free manual workflow
route was subsequently prepared at the owner's request, as described below.

In an authorized environment with `google-auth[requests]==2.40.3` and
`requests==2.34.2` installed, and with the two existing environment variables
securely bound (do not print or paste their values):

```sh
python tests/automotive/provision_neural.py --metadata-only
```

Required names: `ATTUNE_AAOS_DRIVE_SERVICE_ACCOUNT_JSON` and
`ATTUNE_AAOS_TTS_BUNDLE_FILE_ID`. GitHub repository configuration does not make
those values available in this Cloud executor. No live service-account probe was
performed here and no permission/API-enablement changes were made.

Focused fixtures cover metadata 400/401/403/404/429/500/503, safe provider-reason
extraction, non-JSON errors, no media-body inspection, session cleanup, stopping
before download on metadata failure, and the metadata-only mode's prohibition on
download/install/process launch. These fixtures are not Google authorization or
AAOS success evidence.

The provider rejection remains unresolved until a safe metadata probe supplies
its actual status/reason. A new owner-authorized AAOS run is eventually necessary
for final acceptance, but another full run should not be used merely to recover
these missing diagnostics. Run #123 was not retried. No manual workflow, emulator,
new inference, merge or deployment was launched for this investigation.

## Owner-launched metadata diagnostic using existing repository configuration

Direct execution in Cloud cannot use an encrypted GitHub repository secret. The
existing registered **Attune browser audit** workflow now has an explicitly
separate diagnostic route; main and workflow registration are unchanged.

1. Open https://github.com/sasmazt90/attune-more/actions/workflows/e2e-audit.yml.
2. Select **Run workflow** and branch `feature/localization-en-de-tr-20261020`.
3. In the existing `expected_source_sha` field, enter
   `drive-metadata-only:<exact final feature commit SHA from the handoff>`.
   The prefix and full SHA are mandatory. A plain SHA selects the AAOS route;
   **use the diagnostic prefix for this task**.
4. Click **Run workflow** once. Do not use **Re-run jobs**.
5. Read the `Drive metadata diagnostic` job summary: `requestStage`, `httpStatus`,
   `safeGoogleReasons` and `metadataAttempts`. Share only that safe result.

Only `drive-metadata-diagnostic / metadata` runs. AAOS and the browser audit jobs
are excluded by the diagnostic marker. It has a separate concurrency group so it
cannot cancel an AAOS run. An exact-source guard and initial-attempt guard run
before credentials are provided to the script.

The reusable workflow uses standard `ubuntu-24.04`, a three-minute timeout,
preinstalled Python/OpenSSL, and a sparse `blob:none` checkout of only the
diagnostic script. No package installation, model/audio download, build, emulator,
artifact upload, permissions change or paid service is used.

The existing `ATTUNE_AAOS_DRIVE_SERVICE_ACCOUNT_JSON` secret is passed through.
The existing `ATTUNE_AAOS_TTS_BUNDLE_FILE_ID` variable is forwarded as an internal
reusable-workflow secret (`DRIVE_METADATA_FILE_ID`) so GitHub masks it before step
environment logging. **No new repository configuration is required.**

The script performs one OAuth token POST using RS256 service-account credentials,
then exactly one Drive metadata GET with the same read-only scope and fields as
the importer. Token failure prevents the metadata request. Neither operation
retries or follows redirects. Only status/stage and allowlisted reason codes are
reported; no raw metadata, identifiers, credentials, tokens or free-text provider
messages enter the summary. A 200 means metadata access succeeded, not that model
download, integrity, inference or AAOS acceptance passed.
