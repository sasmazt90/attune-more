# Approved TR / EN / DE recording integration

**Recommendation: keep PR #5 draft; do not merge or deploy.** All 194 owner-approved recordings are integrated and technically verified. This establishes Cloud asset/routing/browser evidence, not Windows/AAOS physical acceptance, live female TTS availability or acoustic equivalence.

Verified repository: `sasmazt90/attune-more`, branch `feature/localization-en-de-tr-20261020`, parent `bb27283d8a7e4cf8c400eccd5412d269f5d1bb0a`. The request's `SasmazT90/AttuneMore` spelling returned 404; the authenticated existing PR and attached remote agree on the canonical repository. Main is unchanged at `1ee2386efd3dc30fe8d5b0d2bbf336ac7f03c98e`.

## Package and integrity

`Attune-more-audio-handoff-20261020-v1.zip`: **26,541,258 bytes**, SHA-256 **`e3eaced150581a30a10d0339d84e84388566fe64bd3fc96e97711b472bcd7ee7`**. Retrieved through authenticated Drive with raw download and no inline base64. Verified against the separate checksum before extraction. Path/collision/symlink/size checks and ZIP CRC passed; all 213 checksummed package members and 194 authoritative recording/script hashes passed independent verification.

All original M4As total **25,262,314 bytes**, each copied once to the supplied additive target path. **No derived files, conversions, pitch/speed changes or normalization.** Original file hashes and exact provider/script metadata are in [the runtime manifest](../../apps/vehicle-app/public/audio/user-approved/tr-en-de-20261020-v1/manifest.json) and [authoritative source inventory](approved-audio-handoff/authoritative-production-entries.json). Package-era activation/transfer flags in retained receipts describe historical preparation; the current owner request authorizes this integration.

| Disposition | Files | Current runtime use |
| --- | ---: | --- |
| Selected fixed guidance / exact Mental templates | 129 | Only approved language/module/event mappings |
| New hearing digit recordings | 30 | Staged; never selected by scored tests |
| Retained alternatives | 33 | Stored, not selected |
| Neutral demonstrations | 2 | Stored; never substituted for dynamic AI replies |

All 83 original audio preservation receipts still match. No previously tracked audio file was replaced or deleted. Fifteen source trailing-silence flags are retained without trimming; longest approved recording is **22.224 seconds**. Provider/character labels come from owner-supplied metadata, not inferred from Windows voices or the encoded audio.

## Voice coverage

| Module | TR | EN | DE |
| --- | --- | --- | --- |
| Mental | Emel | Ada | Katja |
| Skin | Emel | Ada | Katja |
| Vision | Ahmet | Andrew | Stefan |
| Dental | Ahmet | Andrew | Stefan |
| Hearing guidance | Ahmet | Andrew | Stefan |

All 15 combinations and 129 selected mappings passed. Five shared Skin/Dental quality events select distinct female/male recordings in every language. Ada keeps en-GB voice metadata and `en-GB-AdaMultilingualNeural`; the UI and recognition locale remain en-US. Katja/Stefan provider-specific live IDs were not supplied and are not invented. Cockpit-entry and inactive bank-only events are not activated.

## Changes

- `i18n/approvedAudio.ts` plus the new approved manifest select only authorized module/language/event tuples and literal exact Mental templates. `audioGuidance.ts` captures route/language ownership, cancels stale work, and fails closed when an approved event is missing.
- `fixedAudio.ts` retains byte/hash checks, adding MIME/duration support, cancellation and bounded downloads. `fixedFileSpeech.ts` uses original AAC/M4A `audio/mp4`, real playback/end events, single output monitoring, finite deadlines and cleanup for abort/mute/hidden/ownership changes. MP3 streaming remains separate for genuine dynamic responses.
- Vision uses approved male fixed recordings. Mental uses approved female fixed templates only when the complete response text matches; all other text keeps the dynamic response path. Backgrounding pauses the conversation without rewriting its transcript. Existing crisis, consent, vehicle and record logic is retained.
- Backend Mental speech requires the exact owner-specified female ID; it rejects eSpeak/male/unapproved overrides before provider dispatch. Live TR/EN catalog and synthesis checks remain enforced. DE without a supplied live identity returns a specific unavailable error. Provider output is never inferred from prerecorded demos.
- Voice settings show approved module assignments and truthful browser/provider inventory; global voice overrides cannot change these assignments. Locale/voice storage and health/consent keys are not cleared.
- Hearing rejects unvalidated EN/DE scored banks; the UI disables that action with a translated explanation. Original TR bank, tones, SNR, gain, scoring, thresholds and calibration algorithms are preserved. Both old synthesized and newly supplied digits remain inactive for EN/DE scored testing.
- Added four localized messages, focused tests and reusable Cloud browser harnesses. No AAOS/platform policy, production configuration or workflow file changes.

## Executed verification

All execution used managed Linux Cloud, existing pinned Node 22.20.0/Python 3.11/Chrome and cached dependencies. The production build ran from an isolated source copy with unchanged application source and task-owned loopback ports 3300/8101; paid keys were blank, backend data was isolated and external browser requests/capture were blocked.

| Check | Result | Evidence / boundary |
| --- | --- | --- |
| Package, all 194 mappings/assets and old hashes | PASS | Independent SHA-256/size/script verification; no collisions or missing mappings |
| FFprobe and complete FFmpeg decode, 194 files | PASS | AAC, 48 kHz stereo; no decode errors; no conversion |
| Real Chrome fetch/hash/decode, 194 files | PASS | HTTP `audio/mp4`, `canPlayType` and actual `decodeAudioData` |
| 15 module/language playback cases | PASS | Natural-speed `playing` and `ended`; screenshots; production dispatch functions imported on real app pages. Camera/microphone-dependent assessment entry was not exercised |
| Actual abort, mute, language and navigation cancellation | PASS | Unfinished playback resolves false; no successful-completion admission |
| Actual hidden-tab backgrounding | UNVERIFIED | Headless Chrome kept tab visibility visible; no hidden-state pass fabricated |
| Hidden/mute/stale-generation/early-end regression fixtures | PASS | Explicit media/platform event fixtures exercising actual modules; not physical evidence |
| Missing/size/hash HTTP failure fixtures | PASS | Real browser production dispatch rejects each injected response and emits unavailable state |
| Narrow voice dialog / locale persistence | PASS | 375 px TR/EN/DE screenshots; real assignments; other existing browser storage bytes unchanged |
| Independent backend moving / missing consent | PASS, isolated DEMO state | Three locales lock selection and reject speech; not actual vehicle evidence |
| Mental conversational and crisis/privacy regression | PASS | Existing provider generation path retained; real keyless DEMO HTTP replies in all locales; consent/exact-voice rejection precedes network |
| Focused regression suite | PASS | 35 passed, one existing AnyIO warning |
| Broader unit + automotive regression | PASS across dependency selections | Initial host run: 848 passed, 47 skipped, 10 passed subtests; eight failures were missing YOLOX/Chrome paths. Those same eight passed using cached YOLOX and real Chrome, with unchanged assertions. No model training or new dependency installation was needed for those rechecks |
| Typecheck, lint, production build | PASS | Catalog: 1441 messages / 1478 sources; lint retains six pre-existing hook/img warnings |
| Windows / new AAOS speech and physical listening | UNVERIFIED | No local processes, devices, mic capture or manual emulator run |
| Live exact female dynamic TTS | BLOCKED acceptance | TR Emel and EN Ada availability/parity not tested; DE live Katja ID unverified. No live/paid speech calls made |
| New scored hearing stimuli | BLOCKED | Acoustic validation incomplete; new digits inactive; no clinical equivalence claim |

Full evidence is retained in `/workspace/attune-approved-audio-20261020/`; [compact receipts/screenshots](evidence/approved-audio-20261020/) are committed. Earlier failed harness/environment diagnostics remain retained; their failures are not counted as passing runtime checks. The first browser pass completed all 194 codec and 15 playback cases before a lifecycle-harness synchronization failure; the corrected lifecycle-only pass is recorded separately. Final source/build input hashes and automatic CI results are recorded with the Cloud delivery receipt.

## Remaining gates

Do not treat asset approval as live API entitlement, Windows voice installation, clinical accuracy, or OEM/production certification. Actual Windows/AAOS playback/recognition/permission/lifecycle acceptance remains separate. Real hidden-tab behavior still needs platform evidence. TR/EN exact live female TTS requires an authorized availability/parity check; DE additionally requires primary evidence of the correct free live Katja identity. New hearing digits require separate acoustic acceptance before scored activation. No further personal recording review was requested or required.

PR #5 stays draft. No merge, deployment, paid service, main change or manual Actions dispatch is authorized by this report.
