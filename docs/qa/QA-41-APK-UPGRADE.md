# QA-41: AAOS APK upgrade persistence

Written by Claude, who built and tested this, so it is not an independent review. Evidence is in `qa41-apk-upgrade/` in the delivery folder.

**Result.** Two consecutive in-place upgrades, across three signed builds, kept every saved record, consent and preference. The app was not uninstalled for either upgrade, and it worked after each. This was on the Android 15 emulator, with records created by the test journeys.

**One fault to read first.** The one-time move to the new signing key stopped halfway on its first real run, because of a bug in my tool. The old app was gone, and the tool wrongly said nothing had changed. The data was safe in the backup and came back complete. See [The first move failed](#the-first-move-failed).

## Two different questions

| | Restart persistence | APK-upgrade persistence |
|---|---|---|
| Question | Does data survive a host Stop and Start, on the same APK? | Does data survive replacing the APK with a new version? |
| What can break it | Storage that does not outlive a process or boot | A new signing certificate, or an uninstall |
| Check | `persistence_check.py`, 11 of 11 on `8c90ec4` | `apk_upgrade_check.py`, this document |
| Did the first answer imply the second? | No. The 11 of 11 never replaced the APK | |

## Original root cause

Android updates an app in place only if the new APK has the same signing certificate. CI built `cloudDemo` with `initWith debug` and no stored key, so each run signed with that runner's temporary debug key. Android refused the update, so `scripts/aws/deploy_release.py` ran `adb uninstall` first, which deleted all of the app's local data: Health History, consents, preferences and stored photos.

This had already caused trouble: after one earlier deploy, AAOS persistence and label journeys failed until records were created again.

## What changed

| Area | Change |
|---|---|
| Signing | One stable identity. The key is in the GitHub environment `android-cloud-demo-signing`, readable only by the `cloud-apk` job. The workflow removes its temporary copy after the build |
| Key protection | Never in the repository. `.gitignore` blocks key files, and a test fails if one appears. Forks get no secrets, and the job skips them |
| Recovery | One encrypted copy for the owner's Windows user: `%USERPROFILE%\AttuneMore\secrets\android-cloud-demo-signing.xml`. GitHub secrets cannot be read back |
| Package identity | Unchanged: `more.attune.automotive.prototype.clouddemo` |
| Version | Each CI build gets 1000 plus its run number, so upgrades always go up |
| Deploy | `deploy_release.py` no longer uninstalls. `apk_upgrade_host.py` compares certificates, then runs `adb install -r` |
| Failing safely | A wrong certificate, a lower version or a bad file name stops with a named reason and nothing changed. The stage file `run.sh` installs at boot changes only after Android accepted the APK |
| Unintended uninstall | A test checks that the only uninstall in the deployment code is inside the named one-time move |

No Skin model, threshold, calibration, app page, API or consent behaviour changed. Since `8c90ec4`, the only changes under `apps`, `services`, `shared` and `infra` are `build.gradle`, the public certificate file and a README section.

## Signing identity

| Item | Value |
|---|---|
| SHA-256 fingerprint | `2aacbb13bad91c2ef982d594a8d98b65f523a71fdc97772d50222fe9f9843876` |
| Subject and alias | `O=Attune.more, CN=Attune.more Cloud Demo`, `attune-cloud-demo` |
| Valid until | 2056-10-27 |
| Schemes | v2 and v3 |

This is a demo signing key for this test build type, which stays debuggable. It is not a production release key.

Each build's certificate was checked by three separate readers: this repository's parser in CI and again on the PC, Android's `apksigner` in CI, and Android's own installed copy, pulled from the device after each upgrade.

| Build | Commit | CI run | versionCode | APK SHA-256 |
|---|---|---|---:|---|
| A | `d93ec10` | `41907375896` | 1056 | `9941899fa5a5c38c273b5e2e8a1ee142c152b4186c048a2cecc9f1c4d4fcc7bf` |
| B | `32b021c` | `41910402999` | 1057 | `98404950881d1947e12972a31d909b81ccc852cf868299f0b379774231b48240` |
| C | `b803182` | `41913573683` | 1058 | `89f4cd1013ecfba8adb4e9ea5dbf56a7b55b1eab2ea6d723301637d04ea03417` |

The APK on the device at the end hashes to build C.

## The test

Each stage reads the real WebView's local storage and IndexedDB, and Android's package record. It saves IDs and hashes, never record content. Comparing stages fails on any missing, changed or duplicated record, on any changed consent or preference, or on any sign of a reinstall.

| Step | What happened | Result |
|---|---|---|
| 1 | Snapshot of the old app: debug key, version 1, 1 Skin record, 12 local values | Taken |
| 2 | Deploy of build A without the migration flag | Refused: `SIGNATURE_MISMATCH`. Nothing changed |
| 3 | One-time move to the stable identity, keeping that app's data | PASS after the fault below. All data matched step 1 |
| 4 | 5 real journeys on build A, saving Skin, Dental, Vision, Hearing and Mental records. All passed | 6 records, 20 local values, 2 photo stores |
| 5 | **Baseline.** Region Berlin and language German, chosen through the real controls | Recorded |
| 6 | **Upgrade 1:** build B, in place, 1056 to 1057 | **PASS**, 10 of 10 operational checks |
| 7 | 4 live refusals, listed below | All refused. Data unchanged |
| 8 | **Upgrade 2:** build C, in place, 1057 to 1058 | **PASS**, 10 of 10 operational checks. Also PASS compared directly with the baseline |
| 9 | A new Dental journey on the upgraded app | PASS. New record saved, older ones unchanged |
| 10 | Real host Stop and Start. This measures restart persistence and is not an upgrade | PASS. 7 records, nothing changed |
| 11 | Native PARK and DRIVE gates on the signed APK | 7 of 7 |

At both upgrades:

- First install time stayed the same and last update time moved, so Android treated them as updates, not reinstalls.
- The certificate stayed the same, and the microphone grant stayed for both Android users.
- All 6 records kept their IDs and hashes. None was duplicated or corrupted.
- Consent, the 5 privacy choices, region and language kept their hashes. So did both photo stores.
- With the app in German, each module opened with its consent still given, and the API answered through the app. History showed all 6 records once each, and a saved record opened.

I also read the screenshots after upgrade 2: German text, PARK, the history cards and a saved Mental conversation.

The step 4 comparison reports 4 changed values and is marked FAIL. That stage is not an acceptance check: the journeys set the language, consent, latest Skin result and referral context themselves. No older record was lost. Step 9 names its 2 expected changes (language and latest Dental result), and the result file records them.

### Refusals tried on the real emulator

| Attempt | Answer |
|---|---|
| Old debug-signed APK, through the deploy tool | `APK_NOT_PINNED_IDENTITY`, nothing deployed |
| Old debug-signed APK, on the host, with and without the migration flag | `APK_NOT_PINNED_IDENTITY`, exit 3 |
| Same identity, lower version | `INSTALL_REFUSED` (`INSTALL_FAILED_VERSION_DOWNGRADE`), exit 3 |
| File not ending in `.apk` | `APK_NAME`, exit 3 |

The migration flag with matching certificates did not start a move. It ran a normal in-place update of the same version.

## The first move failed

The first real `--migrate-signing-once` backed the data up, uninstalled the old app, then failed: the upload was named `app-cloudDemo.apk.incoming`, and adb refuses names that do not end in `.apk`. The tool then printed "The installed app and its data were not changed", which was false. The app was not installed at that moment.

The unit tests had not caught it because the stand-in for adb did not check file names, and no test exercised the move at all.

Recovery: the backup held 41 data files, 4,479,152 bytes. The data was restored from it, and every file's name and size matched. The comparison with step 1 then passed on every record and local value. Nothing was lost.

Fixes in `32b021c`, with tests:

- The file now has a name adb accepts, and the name is checked before anything is touched.
- The move first offers the APK to Android and expects a certificate refusal and nothing else.
- If the move stops after the removal, it says so, names the backup and gives the command to finish it. `--resume-migration` refuses a changed backup, a different installed app and a move that already finished.
- The microphone is regranted to every user who held it. The first run missed user 0, who has no data. I restored that grant by hand.

## Migration requirement for older installs

**Any device holding an APK signed by an old CI key cannot be updated in place.** That key was temporary and no longer exists, so Android has no route. Each such device needs the one-time move once, or it loses its local records on reinstall. The AWS emulator has already had it. No other device was found or tested.

Plain `deploy_release.py` refuses such a device with `SIGNATURE_MISMATCH` and changes nothing. The move has to be asked for by name. Steps are in `docs/aws/OPERATIONS-CONTROL.md`, under "Moving to the stable signing identity".

If the private key is ever lost, no data has to be lost, but every installed app needs this step again, with a new identity. The recovery file opens only under the owner's Windows account on this PC, so a plain copy of it does not protect against losing the PC. For that, the key and its password would have to be kept somewhere else as well, such as the owner's password manager. This is the owner's decision.

## Not verified, and limits

- **The corrected move has not run uninterrupted on a device.** The real run was the failed attempt plus the resume. The new first check, which expects Android's certificate refusal, has only run against the stand-in, because the one installed app had already moved. If Android answers differently, it stops with `MIGRATION_PREFLIGHT` and nothing changed.
- This used the Android 15 emulator, with records from test journeys. No physical head unit or real user data.
- An update that changes how the app stores its data was not tested, because none of these builds did. These upgrades prove the signing and install path.
- Whether the WebView's own data survives a much larger WebView version jump was not tested.
- The backup from the move stays on the AAOS host at `/var/lib/attune/apk-migration/20261104T204408Z`, readable by root only. It holds test data, and can be deleted after the review.
- The environment's pull request pattern first failed in CI (`*/merge`, then `pull/*/merge`). `refs/pull/*/merge` works, and is what `create_android_signing_identity.py` now sets.

## Why the twelve videos were not recorded again

The journeys did not change. The APK has a different signature and version number, and its pages, API and models are the same. The 5 real journeys in step 4, the Dental journey in step 9 and the native gates all passed on the signed builds.

## Evidence

| File | Contents |
|---|---|
| `qa41-apk-upgrade/apk-upgrade-evidence.md` | Every stage, each record's hash through the upgrades, each consent and preference |
| `qa41-apk-upgrade/evidence/*.json` | Raw stage snapshots and results |
| `qa41-apk-upgrade/evidence/after-*.png` | The real screen after each upgrade |
| `qa41-apk-upgrade/deploy-*.json` | Deployment records, with Android's before and after state |
| `qa41-apk-upgrade/evidence/native-gates-signed-apk.json` | Native gates on the signed APK |
| `tests/aws/test_apk_upgrade.py` | 29 tests, including the failed move and its recovery |
