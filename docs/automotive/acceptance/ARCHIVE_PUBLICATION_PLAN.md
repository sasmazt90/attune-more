# Evidence archival proposal — awaiting approval

Status: **actual original bytes preserved in Cloud; durable external storage not yet created**. No Release, tag, public asset, private upload or sharing change has been made. The user explicitly required approval before binary archival/publication.

## Recommended private destination

Subject to owner approval and available account capacity, create a new private Google Drive folder named `Attune.more AAOS acceptance - run 39321125673 - a3943b6` in the connected account. Do not enable link sharing or alter inherited sharing. Verify the destination's privacy before upload; if unavailable or insufficient capacity, stop rather than subscribe, pay for storage or substitute a public archive. This proposal does not assert an existing folder, stable URL, account quota or successful upload.

Upload the unchanged original ZIP, complete connector-exported job log and lightweight preservation metadata (inventory, integrity receipt, checksums and run metadata). Approximate payload is under 6MiB; no application data directory, source checkout, credentials, model weights or unrelated asset is included. After successful upload, retrieve/check stored metadata and downloaded bytes where supported, record exact IDs/URLs and SHA-256 values, and update this manifest on the feature branch. No application test or Actions run is needed.

| Prepared payload | Bytes | SHA-256 |
| --- | --- | --- |
| `aaos-39321125673-1.zip` | 5475596 | `664c8bd56f13d9d59940290cbd6bb21e4b6ced48ba4033cdf3f9c44161f19171` |
| `job-118295153003.log` | 169234 | `73ca5a08bbe03051e9817665aa30b0e74c328ef24f9e466268c72d077d908c20` |

All prepared original bytes reside under `/workspace/attune-aaos-evidence-archive/39321125673`. Raw logs contain public package-contact metadata and diagnostic identifiers; private archival preserves originals without publishing that material. Public documents contain summarized technical results and hashes only. Do not redact/repack the original ZIP and call it the original.

## GitHub pre-release alternative

If explicitly selected and approved by the owner after reviewing public visibility, use a clearly labeled **AAOS emulator validation evidence — pre-release** associated with exact source `a3943b6c62e6f0282ff021e1de2f73a5c3c43e18`. It must not be a production release or target the later documentation commit. A proposed dedicated tag is `aaos-emulator-validation-run-39321125673`; no such tag is created by this task. Turn off “latest release” designation and do not generate an unrelated main release.

The current GitHub connector retrieved the artifact, metadata and full log successfully but exposes no Release-asset upload capability. Read-only `gh auth status` reports the environment's existing token invalid. No credentials were inspected or changed. Therefore automated Release publication is currently unavailable; do not claim a Release exists. If the owner prefers this route, an authenticated owner can use repository Releases → Draft a new release, create/review the dedicated tag at the exact validated source, mark pre-release, attach the unchanged original ZIP and checksum metadata, review visibility, and publish only with explicit approval. Record the actual resulting release/asset URLs afterward.

Public raw assets need a separate publication review; existing synthetic-run classification does not eliminate public contact metadata or confer new image redistribution rights. Prefer the private archive for unchanged originals.

## Preservation fallback and expiry

The original [Actions artifact](https://github.com/sasmazt90/attune-more/actions/runs/39321125673/artifacts/12220138469) expires **2026-10-20 20:50:15 UTC**. Artifact retrieval succeeded, so no local executor transfer is required. An owner can manually save the already downloaded Cloud ZIP or download the Actions artifact before expiry, then verify the exact byte size and SHA above. Workspace copies are not guaranteed permanent storage. Do not delete either the source artifact or downloaded evidence when creating the durable copy.
