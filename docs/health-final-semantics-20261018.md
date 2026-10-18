# FINAL-01: permission and history semantics

The finite source/store closeout is complete. No production defect was reproduced in the inspected branches, so production source, normal processes, profile, build, models and stored records were not changed. This is **not normal-browser visual/history acceptance**.

Pinned baseline: checkout `attune-cdc-health-final-technical-20261017`, branch `research/health-final-technical-closeout-20261017`, initial HEAD `c39055c7e8d72f77976a19d82c923c37c24bb43d`. Normal launcher source remains `8e8a51711ccdfb372cc7b2e60d328c888a78e8fe`, BUILD_ID `A-e1UWQmCW1DpJXm9fY46`. Focused test commit: `8133bf5`.

## Permission evidence and limits

| Question | Evidence | Decision |
|---|---|---|
| Why did the old combined permission aggregate hash change? | The combined before snapshot contains an aggregate only; its final receipt says application consent/effective native grants were not inspected. | **UNKNOWN**. A current allow value cannot identify a historical changed field, actor or cause. |
| What did later deliveries preserve? | SAG lifecycle preserved its profile/data/shortcut scope. DRY production lifecycle additionally reports selected persisted camera/mic settings unchanged across its own paired stop/build/reopen window. | Interval-specific preservation; does not explain the earlier aggregate delta. |
| What is stored for the normal TOGG origin now? | One allowlisted read of `Preferences`: `http://127.0.0.1:3000,*` camera=1 and mic=1; no explicit selected defaults or pan/tilt/zoom exception. | Persisted Chromium allow entries; **not proof of effective browser/OS grant or in-memory state**. Other origins were not output or hashed. |
| What are current application consent/history values? | No installed verified read-only origin/key LevelDB parser (`ccl_chromium_reader`, `ccl_leveldb`, `plyvel`). | **Not read**. No profile copy, live DB open, profile restore or new dependency installation. No claim that actual user consent/history semantics were observed. |

Service processing consent (`attune_health_processing_v1`), app camera/mic preferences, hosted-photo permission and photo-saving permission are distinct. Camera/mic app preferences default to enabled unless explicitly false; this is not a browser permission grant. Hosted and photo saving require explicit true. `HealthConsentGate` returns children directly when complete service consent exists; missing/revoked consent presents unchecked requirements. Grant does not start a capture. The privacy page changes the application preference and emits `attune-privacy`; it does not set Chromium/native permissions.

## Focused controls

`node tests/unit/final_permission_history_semantics.cjs`: **9/9 groups passed**. Actual TS store/gate/reader/view-model modules were invoked. Skin and mental privacy callbacks and owned-stream cleanup were extracted as AST from actual source and executed with synthetic state/media adapters. This is narrower than mounted React/browser scheduling.

- All five services: grant/reentry bypasses the modal; revoke restores unchecked requirements; other service grants survive. Partial/malformed consent and failed writes fail closed without success events; cancel routes home.
- Skin: mic-only revoke leaves camera state alone; camera revoke and driving invalidate acquisition. Actual scan cleanup cancels analysis/RAF and stops only its owned synthetic track. Mental: camera preference does not cancel voice; mic revoke cancels voice, while numeric storage is not erased.
- Actual numeric writer/reader preserves old rows and exact synthetic photo identity, region/bar/point metadata through prepare/reopen. Consent revoke, stale acquisition, embedded raw media and a failed multi-key write do not add a record; failed write restores the prior snapshot.
- Volatile photos are keyed by record, and media preference revoke clears their support while numeric rows survive. Actual photo writer rejects mismatched map/photo identity and stale work before opening IndexedDB.
- Actual view builder keeps legacy six-region records without inventing an overview, preserves scores and resolves known labels centrally without rewriting the record.

The earlier `health-ui-consent-audio-followup-20261017/consent-proof.json` already records isolated-browser first-entry, unchecked checkbox, no-autostart, reload/reentry, cross-tab revoke and failed-storage checks. Its report records header mute versus microphone separation, route/cancel cleanup, and hearing ownership. Those old controls were **not rerun or relabeled as today's normal-window acceptance**. Current header source still dispatches cancellation on pathname changes and calls `muteGuidance`; guidance disposal aborts fetch, pauses/unloads its audio, revokes its URL and settles the job. Vision/dental/mental unmount and driving handlers remain in source; only the missing skin/mental selective-revoke and owned-track edges were exercised here.

## History scope

Existing frozen DRY `product-contract-checks.json` supplies old/new method roundtrip and cross-method rejection evidence; the already admitted V5 final-list receipt supplies the final candidate/area contract. Neither model/API proof was rerun. Existing photo-history tests describe isolated IndexedDB persistence/hash/transaction checks; this task did not rerun them or open live user IndexedDB.

`RecordHistory` selects a row by category/id and keys detail by record id. `SkinRecordDetail` resets region/criterion selection on record change, guards asynchronous photos with current/revision/id, and selects an angle from the stored record's scope. Its display consumes the stored result and centrally labeled view model. These source paths support the reopen contract; they do **not prove the current normal browser's rendered photo, bar, point and map relationship**.

## Remaining individual limits

1. Historical aggregate permission cause remains UNKNOWN; a missing field-level before image cannot be reconstructed.
2. Live application consent/history fields were not read. Current in-memory/native effective camera/mic grants were not queried.
3. Normal-window modal/revoke, rendered reopened history/photo/map, narrow layout and native 200% visual acceptance remain OPEN under the existing Computer Use URL identity boundary. No UI retry or alternate browser/CDP/OS capture bypass occurred.

No model/analysis request, TTS, build, restart, live storage write, profile copy, hosted call or new training was performed. The launcher identity endpoint was read only to verify the same four normal owned processes. No push, merge or next task was started. Evidence, result, index and cleanup are under `cdc-progress/health-final-semantics-20261018` outside the repository.
