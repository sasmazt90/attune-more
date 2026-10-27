# Audio backup and Cloud recovery

The durable destination is the [owner's Drive folder](https://drive.google.com/drive/folders/1FrN4RQz_j6QBmuXJe4RIpJGcQcSUB4sS), with this production run under [female-calm-v1 / 2026-10-27 / v1](https://drive.google.com/drive/folders/16nXYqOOXPPA5GTtmHtPE6QLLsG2q9mGy). Cloud storage is temporary. Backup is currently incomplete; progress inventories must not be mistaken for the final inventory.

The run separates catalog recordings by TR/EN/DE, approved previews, unchanged official-default comparisons, reference/runtime provenance, reproduction packages, closing validation, reports and immutable progress snapshots. Each inventory entry records the backup path, size, SHA-256 and Drive ID/URL, with a repository or runtime restore path where applicable. Only an independent Drive download with matching bytes and SHA-256 creates a verified receipt. Upload success alone is insufficient. Pending IDs are saved before readback and reused after interruptions.

The original workspace was recovered with 237 verified catalog recordings, including 28 uncommitted recordings beyond the previous GitHub checkpoint. The nine approved samples, six previews and 18 original comparison files retained their protected hashes. See [the recovery record](recovery-checkpoint.json). No Cloud audio copies have been deleted.

## Restoring a completed backup

1. Use a Cloud/Linux workspace. Check out the recorded PR commit and download the final inventory and verification report from Drive. Match the inventory hash against the versioned verification record before using it. Retrieve every listed file by its recorded Drive ID, preserving `backupPath` under a separate backup directory.
2. Audit all bytes before restoring anything. The restore helper checks sizes, hashes, path containment and existing targets. A conflicting target is an error, never an overwrite. Use `--apply` only with the completed, verified final inventory.

```sh
python scripts/restore_mental_audio.py --inventory /absolute/backup/backup-inventory.json --backup-root /absolute/backup --repository-root /absolute/repository --runtime-root /absolute/runtime
python scripts/restore_mental_audio.py --inventory /absolute/backup/backup-inventory.json --backup-root /absolute/backup --repository-root /absolute/repository --runtime-root /absolute/runtime --apply
```

3. Restore the pinned model from its existing permanent Drive bundle. [pinned-runtime.json](pinned-runtime.json) records its exact ID, 3,283,572,066-byte size, SHA-256, versions and model-file hashes. The backup retains the sanitized manifest of all 98 permanent parts and their Drive IDs/hashes. There is no duplicate multi-gigabyte model upload in this run. If materializing parts, verify every part before reassembly:

```sh
python scripts/reassemble_mental_runtime.py --manifest /absolute/backup/reference-and-runtime/pinned-model-parts.json --parts-root /absolute/parts --output /absolute/runtime/owner-bundle.zip
```

4. Verify the archive and extracted member hashes against the backed-up member manifest. Keep all extracted paths inside the runtime directory. The existing bundle contains the official Chatterbox source, model files, dependency sources/assets and provenance. Rebuild the isolated CPython 3.11 environment using the versioned, hash-pinned runtime requirements and packaging provenance in `tests/automotive/neural-runtime`. Install the verified bundled official source without changing it. Restore the approved reference/configuration and local auxiliary caches; retain the upstream watermark. Preserve the venv's executable path rather than resolving its symlink to the base Python interpreter.
5. Run the worker's configuration/source checks before synthesis. Set `ATTUNE_MENTAL_TTS_FEMALE_CONFIG` to the restored female configuration; retain a separate legacy/default configuration. Model weights, installed environments and validation caches stay outside GitHub. Provision the independent ASR verifier using `scripts/provision_mental_audio_verifier.py` and the backed-up official release checksums/provenance.
6. Audit the catalog, protected approved bytes and pronunciation evidence. Use the batch CLI only for genuinely missing, unapproved recordings. Existing matching recordings are reused; missing approved recordings must be recovered from GitHub/Drive. Repair tooling creates bounded new-seed revision paths and preserves prior takes, scripts, conditioning and settings.

The reproduction ZIP includes source/manifests, exact scripts, necessary regression fixtures, requirements and a source inventory tied to a Git commit. Full pronunciation evidence and retired-take evidence belong in Drive; concise validation records and required application assets belong in GitHub. Authentication tokens, API keys and private user transcripts are excluded. No recovery step requires a personal computer or Windows directory.
