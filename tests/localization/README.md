# Cloud browser localization acceptance

Use the published **Linux Cloud environment**, cached Node/Python/Chrome and an isolated app/API with synthetic storage, blank paid API keys and explicit loopback trusted origins. Do not point this script at Windows, a real profile or production. It does not install packages or start a server.

```sh
python tests/localization/browser_qa.py \
  --base-url http://127.0.0.1:3200 --api-url http://127.0.0.1:8100 \
  --chrome /path/to/existing/cloud/chrome --output /workspace/new-localization-evidence
```

This is finite: nine routes × three languages × three widths, with actual consent dialogs, navigation and voice availability screens. A new browser profile is used; physical capture requests are blocked and counted. Requests outside the isolated app/API are blocked. It asserts locale persistence, initial disabled consent action, dismissal after explicit checkbox selection, one manifest owner, no page overflow, overlapping controls, clipped visible text, broken images, console errors or capture attempts and menu Escape behavior. Screenshots, geometry, visible text and errors are retained; an incomplete/failed case yields a failing exit code. The output must be new/empty.

These are browser UI/rendering checks, not physical microphone/camera/vehicle acceptance, live voice recognition, clinical validation or proof of installed Windows/AAOS voices. Voice availability is queried from actual platform metadata; no synthetic successful speech provider is installed by the harness. Longer German text and intentional carousel/assistive offscreen content still require screenshot review.

The implementation report describes additional actual 200% Chrome zoom, synthetic result-dialog/Unicode persistence, app-owned audio event, backend safety/error and native host-policy checks executed in Cloud. Their full evidence is retained separately; they are not silently counted as runtime AAOS acceptance.
# Approved recording checks

`approved_audio_bundle.cjs` bundles the actual production dispatch functions for Cloud-only evidence without adding product hooks. Run it from the repository root, redirecting output to a new evidence directory. `approved_audio_qa.py` checks all 194 actual M4A decodes, 15 module/language playbacks and cancellation on a keyless isolated app/backend. Its `--lifecycle-only` option rechecks only remaining lifecycle cases. `approved_audio_supplemental.py` checks the narrow voice UI, storage preservation, isolated DEMO moving locks and explicitly injected missing/size/hash HTTP faults. Supply existing `--chrome`, `--bundle`, `--output`, `--base-url` and `--api-url` paths/options as applicable; no browser/dependency download is performed. Hidden-tab visibility that cannot be observed is UNVERIFIED. None of these checks establishes physical audio, microphone/recognition, real vehicle or live provider acceptance.
