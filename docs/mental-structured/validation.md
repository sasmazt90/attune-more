# PR #12 validation

The owner approved the nine `female-calm-v1` representative recordings and six joined previews and authorized remaining-catalog production and routine verification. Production is in progress; this document will record the final inventory and PR-head checks. No merge or deployment is authorized.

- The selected structured profile and personalized-closing request are `female-calm-v1`; a separate female runtime configuration preserves the legacy/default voice configuration.
- Approved recordings and original comparison files are protected by SHA-256 baselines. Existing bytes are never overwritten.
- New recordings are checkpointed with exact scripts, IDs, conditioning/settings, deterministic seeds, hashes, PCM metrics and production timing. Resident model reuse is explicit in new recipes.
- An independent, checksum-verified multilingual Whisper recognizer runs locally for pronunciation screening. It neither changes the TTS model nor certifies natural prosody; uncertain transcripts are retained for review rather than hidden.
- Integrity/PCM checks, catalog completeness, all allowed A+B pairs, same-profile closing, lifecycle/consent/storage protections and session boundaries are covered by final validation and regression tests.
- Classifier comparison is closed by the owner: retain current rules. No semantic-model integration or further benchmarking is pending.
- Google Drive is the durable backup destination. The backup is incomplete until final expected-file inventory and independent readback hashes are verified; no Cloud copies are deleted.

Current targeted suite: 164 passed. Final broader tests, frontend build and exact-head GitHub CI will be recorded after production and implementation are complete. Physical vehicle acceptance remains outside these Cloud tests.
