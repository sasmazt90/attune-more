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
