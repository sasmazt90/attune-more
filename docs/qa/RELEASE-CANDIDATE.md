# Release candidate

| Layer | Value | How it was checked |
|---|---|---|
| Commit | `8c90ec419197cc627b9fc60d866a6cb99fe71599` | Deployment record for both hosts |
| Branch and draft PR | `claude/aws-ops-automotive-ux-20261103`, [sasmazt90/attune-more#23](https://github.com/sasmazt90/attune-more/pull/23) | |
| CI on that commit | CI / Submission QA Guard `41887368177`, Automotive prototype `41887368217`, AWS OEM preparation `41887368415`. All pass | GitHub Actions |
| Source archive | `f027eda5c823942490add4e47eb774e248603138b73547ea9625a46b3e4923e2` | Same archive on both hosts |
| Frontend build | `upgmpuSjeTb5mKKvjnMfK`, built on the WEB host | `.next/BUILD_ID` |
| APK | `71ed01e8c61ecaa2742490ccb94c364b1b0c7abb71a29d21e14bdad213a22fc5`, 66,382 bytes, from the AWS OEM run above | Hash read back on the AAOS host at install |
| Android | Android 15, SDK 35, `sdk_gcar_x86_64` emulator, WebView 147.0.7727.137 | `getprop`, `dumpsys webviewupdate` |
| Model files | 52 of 52 match the verification record and the owner's approval record, by SHA-256 | Every file hashed on the WEB host |
| Python packages added for Skin | `mediapipe 0.10.32`, OpenCV stays `4.12.0` | Imported by the host's interpreter |
| Speech | Same Chatterbox voice and weights, kept resident, 4 threads | `speech.conf` drop-in |
| Addresses | `https://attunemore.sasmaz.digital`, `https://aaos.attunemore.sasmaz.digital` | Real DNS, no bypass |
| Certificates | Let's Encrypt, 90 days, renewed by START | `openssl s_client`, curl and Chromium |
| Provenance record | `provenance-WEB.json`, `provenance-AAOS.json`, in the delivery folder | |

**Commits after this one contain only QA tooling and documents, no product code.** Check with:

```bash
git diff --stat 8c90ec419197cc627b9fc60d866a6cb99fe71599 HEAD -- apps services shared infra scripts/aws
```

## Which videos come from which build

| Videos | Build | Why |
|---|---|---|
| WEB: all 6 | `8c90ec4` | Address and certificate changed for every WEB journey, and the header during activities |
| AAOS: Skin, Vision, Dental, Mental | `f7d861e` | Recorded after the camera, acne, referral and speech changes. The only later product change hides a note that was already hidden at AAOS's 564 px height |
| AAOS: Hearing digits-in-noise, Hearing pure-tone | `4bb51b3` | Not affected, so kept intact as the owner asked. Same files and hashes as before. They use neither the camera nor Mental speech, and the header does not change at the recorded size |

Everything other than the recordings was rerun on `8c90ec4` on both platforms: the real Stop and Start, persistence, camera states, appointments, Skin labels, the UI journey and the native gates. Camera recovery and the acne trace ran on `f7d861e`, and their code has not changed since.

## What the recordings are and are not

Real: the deployed application, the Android 15 emulator's WebView, Chrome on the WEB host, API processing, the model
files, OpenAI speech recognition and the language model, Chatterbox speech generation, public DNS and a public certificate authority.

Stand-ins: camera input is reference photos, microphone input is synthesized speech through a virtual microphone,
Hearing responses come from a scripted listener, and vehicle data is simulated. No physical camera, microphone, person
or vehicle took part. Nothing here is a clinical measurement.

The AAOS native toolbar in the recordings is a test build's toolbar. Its "Camera: unavailable" refers to the emulator's
own camera, because the reference photos arrive through the demo camera bridge.

The WEB journeys run on the WEB host, which maps the public name to itself, because its Security Group admits only the operator's
address. They no longer ignore certificate errors, so Chrome is checking the real certificate.

## Earlier candidates

`0091399` and `4bb51b3` were recorded first and passed. The owner's later instructions changed what they should do. Earlier runs are kept as a
local reference.

## Faults only the real environment found

Each of these passed unit tests or a local check before the real run caught it:

1. **The desktop shortcuts had never worked.** Claude's desktop app is packaged, so its writes under AppData went to a private copy. The
   shortcuts pointed at a file nobody else could see. Earlier reports said one-click Start and Stop worked, which was only true of the
   same script started from the repository. The tool now lives in `%USERPROFILE%\AttuneMore`, and a real shortcut was opened to prove it.
2. **IONOS answers 503 to a request with no User-Agent.** It looked like an outage until the same request worked from another client.
3. **Labels pointed at the wrong spot on T-zone and Lips.** The photo was drawn in one frame and the labels were placed
   from another: rings sat 15 to 59 px away. Fixed in `9f04710`.
4. **The regional map's patchwork covered the face** while findings were shown. Fixed in `b7fe187`.
5. **Text in the German Mental consent dialog showed below the pinned buttons.** Fixed in `41d9593`.
6. **A restart reported PARTIAL.** The readiness check compared two restored V5 files with an old record. Fixed in `ea9d2b4`.
7. **READY did not notice an empty OpenAI account.** Fixed in `8939fa7` with a one-token call.

Faults in the test itself, which would have overstated results:

- `/history` does not exist, so an earlier WEB run measured a 404 page for one state. Fixed in `14a65ff`.
- AAOS rows labelled 800x480 and similar had all measured 1280x564, because a size set in the WebView did not hold. The
  check now fails unless the page reports the size under test. Fixed in `68ff3d2` and `b80b33a`.
- AAOS screenshots named `compact-*` show the real display's layout cropped, because taking a screenshot clears the emulated size. The
  measurements are read before the screenshot and are valid. Use the WEB `compact-*` screenshots to see those layouts.

## Delivery

Evidence, videos and the acceptance report are on Google Drive under
[`Attune.more / Claude Release Candidate E2E English / 2026-11-04 /`](https://drive.google.com/drive/folders/1LsbiNKlGinJUD5_gFSa2-SpHbtjJkmQa). The report is `docs/qa/ACCEPTANCE-REPORT-20261104.md`.
