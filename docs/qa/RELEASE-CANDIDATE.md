# Release candidate

| Layer | Value | How it was checked |
|---|---|---|
| Commit | `b7fe187b302669cb117911ad01a3dcee89e2ead8` | Deployment record for both hosts |
| Branch and draft PR | `claude/aws-ops-automotive-ux-20261103`, [sasmazt90/attune-more#23](https://github.com/sasmazt90/attune-more/pull/23) | |
| CI on that commit | CI / Submission QA Guard `41796222922`, Automotive prototype `41796222828`, AWS OEM preparation `41796222745`. All pass | GitHub Actions |
| Source archive | `27697d7351b45065fb3d701f54c2de22b0ec3a44597237f607420a6e25fbed41` | Same archive on both hosts |
| Frontend build | `9blsTy3oEG7JnynzdGch4`, built on the WEB host | `.next/BUILD_ID` |
| APK | `e3e7b46ef5d8c3fb6131f3f1f45d82a380c8811ae4ab94a324e29dfffdf829d5`, 66,382 bytes, from the AWS OEM run above | Hash read back from the emulator |
| Android | Android 15, SDK 35, `sdk_gcar_x86_64` emulator, WebView 147.0.7727.137 | `getprop`, `dumpsys webviewupdate` |
| Model files | 52 of 52 match the verification record, by SHA-256 | Every file hashed on the host |
| Python packages added for Skin | `mediapipe 0.10.32`, OpenCV stays `4.12.0` | Imported by the host's interpreter |
| Speech | Same Chatterbox voice and weights, kept resident, 4 threads | `speech.conf` drop-in |
| Provenance record | `rc-provenance/provenance.json` per host, in the delivery folder | |

**Commits after this one contain only QA tooling and documents, no product code.** Check with:

```bash
git diff --stat b7fe187b302669cb117911ad01a3dcee89e2ead8 HEAD -- apps services shared infra
```

## What the recordings are and are not

Real: the deployed application, the Android 15 emulator's WebView, Chrome on the WEB host, API processing, the model
files, OpenAI speech recognition and the language model, and Chatterbox speech generation.

Stand-ins: camera input is reference photos, microphone input is synthesized speech through a virtual microphone,
Hearing responses come from a scripted listener, and vehicle data is simulated. No physical camera, microphone, person
or vehicle took part. Nothing here is a clinical measurement.

The AAOS native toolbar in the recordings is a test build's toolbar. Its "Camera: unavailable" refers to the emulator's
own camera, because the reference photos arrive through the demo camera bridge.

## An earlier candidate

`0091399` was recorded first and passed. The owner's Skin label brief arrived after that, so all 12 videos were recorded
again on this commit, and all 12 here come from one build. The earlier run is kept only as a local reference.

## Faults only the real environment found

Each of these passed unit tests or a local check before the real run caught it:

1. **Labels pointed at the wrong spot on T-zone and Lips.** The photo was drawn in one frame and the labels were placed
   from another: rings sat 15 to 59 px away, and Redness pointed at the lips instead of the nose. It predated the
   redesign. Fixed in `9f04710`. Local test data had no regional map, so that path never ran locally.
2. **The regional map's patchwork covered the face** while findings were shown. Same cause, fixed in `b7fe187`.
3. **Text in the German Mental consent dialog showed below the pinned buttons.** Fixed in `41d9593`.
4. **No module Start action was in the first screen at 1280x564.** Fixed in `0091399`.
5. **A restart reported PARTIAL.** The readiness check compared two restored V5 files with an old record. Fixed in
   `ea9d2b4`, against pinned hashes rather than by loosening the check.

Faults in the test itself, which would have overstated results:

- `/history` does not exist, so an earlier WEB run measured a 404 page for one state. Fixed in `14a65ff`.
- AAOS rows labelled 800x480 and similar had all measured 1280x564, because a size set in the WebView did not hold. The
  check now fails unless the page reports the size under test. Fixed in `68ff3d2` and `b80b33a`.

## Delivery

Evidence, videos and the acceptance report are on Google Drive under
`Attune.more / Claude Release Candidate E2E English / 2026-11-04 /`. Links are in the acceptance report and on the PR.
