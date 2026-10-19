# AAOS emulator acceptance baseline

**AAOS emulator-validated prototype**, validated source `a3943b6c62e6f0282ff021e1de2f73a5c3c43e18`. Original [run #122](https://github.com/sasmazt90/attune-more/actions/runs/39321125673): 17 PASS and nine routes PASS. These documents preserve that existing execution; they do not authorize a new run.

- [Technical acceptance report](AAOS_EMULATOR_ACCEPTANCE_REPORT.md)
- [Machine-readable manifest](AAOS_ACCEPTANCE_MANIFEST.json): original ZIP digest, all 172 member hashes, scenario/route references, APK identity, observed versions and immutable source hashes
- [Known limitations](AAOS_ACCEPTANCE_LIMITATIONS.md)
- [OEM technical summary](OEM_TECHNICAL_VALIDATION_SUMMARY.md)
- [Durable archive proposal — approval pending](ARCHIVE_PUBLICATION_PLAN.md)

The source commit is the tested baseline. A later documentation commit does not imply another application execution. Only lightweight documentation belongs in this directory. ZIPs, APKs, screenshots and full logs stay outside normal Git history.

## Evidence locations and verification

Current verified Cloud copy: `/workspace/attune-aaos-evidence-archive/39321125673/aaos-39321125673-1.zip`. Extracted original members: `/workspace/attune-aaos-evidence-archive/39321125673/extracted`. Complete executing-job log export: `/workspace/attune-aaos-evidence-archive/39321125673/job-118295153003.log`. These workspace paths are accessible in the current managed Cloud environment; they are not portable permanent links.

ZIP: **5,475,596 bytes**, SHA-256 **`664c8bd56f13d9d59940290cbd6bb21e4b6ced48ba4033cdf3f9c44161f19171`**, 172 members, 11,316,421 uncompressed bytes, flat root. Original Actions artifact ID 12220138469 expires **2026-10-20 20:50:15 UTC**. The [Actions artifact page](https://github.com/sasmazt90/attune-more/actions/runs/39321125673/artifacts/12220138469) is temporary. **No durable binary archive has been published; manifest stable URL is null pending explicit owner approval.**

All member filenames in the report/manifest resolve relative to the flat ZIP root after extraction. The ZIP SHA is the primary byte identity; each member has its own recorded SHA. The full job log is a separately hashed connector text export, not a member of the original ZIP. SHA-256/CRC, JSON/JUnit, PNG structure and evidence receipt checks have been performed without executing application code. Rechecking archive/document integrity does not require an emulator, build, server or application tests.

Once an archive destination is approved, upload the unchanged ZIP and separate log/checksums privately, verify stored byte hashes, then update the manifest with actual stable object URLs. Do not invent a permanent location or alter the original to sanitize it. See the concrete [storage proposal](ARCHIVE_PUBLICATION_PLAN.md).
