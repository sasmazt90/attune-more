# AAOS acceptance limitations

The supported designation is **AAOS emulator-validated prototype**. Run #122 supports the 17 recorded assertions at its exact source/APK/environment. It does not certify broader compatibility.

| Area | Status / limit |
| --- | --- |
| Defined emulator suite | 17 PASS; nine routes PASS in the original evidence |
| Other AAOS releases/devices | UNVERIFIED; only API 35 extension 15 x86_64 image revision 4 was run. Minimum API 29 declaration is not API 29 testing. |
| Physical vehicle and OEM integration | UNVERIFIED; no BMW, TOGG or other physical vehicle, OEM approval, certified signal provider or real CAN/VHAL integration tested. |
| Vehicle-state trust | Backend is an explicit debug simulation. Platform restriction is real Car Service on a virtual vehicle. Neither is certified physical telemetry. |
| Hardware/media | Camera absent; microphone feature present with permission denied; OS microphone denial observed. No physical camera dialog, recording, audible output, acoustic calibration or Windows/device performance checks. |
| Lifecycle | Pause/stop and removal of inactive WebView observed. Active capture interruption, process death/recreation, prolonged soak and all lifecycle races remain unverified. |
| Visual breadth | One 1280×800 display. Other widths, actual 200% zoom, full scroll content, all forms, accessibility, rotary/multiple displays and OEM skins are unverified. |
| Transition screenshots | Captures after restored scenarios can show Park. Backend-moving PNG shows dashboard while contemporaneous native XML is locked; cause is unproven. Hash integrity does not establish pixel/state synchronization or transition latency. Keep behavioral assertions and images distinct. |
| Network/providers | Local debug HTTP via ADB reverse; bounded frontend/backend fault recovery. Production TLS, remote backend/provider behavior, degraded mobile connectivity and external integrations remain unverified. |
| Production/distribution | Debug APK only. Release origins intentionally unusable, real signal provider not connected. No production readiness, Google Play for Cars eligibility, OEM integration approval, homologation or safety certification claim. |
| Health/models | No clinical accuracy, clinical acceptance, model promotion, new health analysis or commercialization/compliance certification follows from these tests. |
| Console/crash | No unexpected observed error in a finite interval; deliberate faults and blocked external resources classified separately. Not exhaustive error/security coverage. |
| Runtime optional binaries | Five documented unused TIFF/RenderScript library warnings remain. No claim all SDK optional binaries run on Ubuntu 24.04. |
| Reproducibility | Exact source, APK hash and observed tool versions recorded. Runner/actions/package feeds, image revisions and WebView may drift; debug rebuild hash equality is not guaranteed. Read-only probe APK not present in original archive, although its build/install/probe output is retained. |
| Privacy | No real user health records or credentials found in bounded review; original logs include public package-contact metadata and diagnostic identifiers. Raw binary publication withheld; no blanket privacy/security/asset-rights certification. |
| Billing | No billing receipt/cost conclusion available in artifact. Standard runner, finite timeout and artifact size observed; zero additional charges not established. |
| Permanent storage | Pending explicit approval. Cloud copy verified but workspace durability is not guaranteed; Actions artifact expires 2026-10-20 20:50:15 UTC. |

Do not convert these unverified capabilities into passing scenarios. No application changes, new tests, Actions runs, deployment, main merge or binary publication were performed for this documentation baseline. Raw original evidence remains unchanged. See the [report](AAOS_EMULATOR_ACCEPTANCE_REPORT.md), [manifest](AAOS_ACCEPTANCE_MANIFEST.json) and [storage proposal](ARCHIVE_PUBLICATION_PLAN.md).
