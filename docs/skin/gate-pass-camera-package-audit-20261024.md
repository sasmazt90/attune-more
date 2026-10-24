# Gate-pass three-pose camera package audit

Date: 2026-10-24

## Outcome

The replacement package
`Attune_6_Profiles_18_Images_GATE_PASS_20261024.zip` was independently audited
without committing image bytes. The 25,480,198-byte archive has SHA-256
`5096055f1cbd3afb28f4cdc1c2a40584b9c5d8159a6371e0d558f38a2ca90f28`.
All 57 ZIP members decompress successfully; 56 non-index members are covered by
the package checksum table and every byte count/hash recomputes.

The manifest contains six people with one FRONT, RIGHT and LEFT capture each.
All 18 image byte hashes and measured photo IDs are unique. Decoding the image
headers confirms the declared sizes: eight at 2048×1529, five at 2400×1792 and
five at 1451×1084; 13 are JPEG and five are PNG. The source inventory is eight
original-package images, five user replacements and five assistant-generated
revisions.

For every image the audit verified:

- 478 MediaPipe landmarks;
- the declared person/measurement alias and expected pose;
- source dimensions and the manifest-bound measured `photoId`;
- `OPTIMAL` static quality, matched skin angle and no geometry/failure reason;
- `CLEAR` capture-check output from immutable model hash
  `66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9`;
- no physical-camera or temporal-stability acceptance claim.

The privacy-safe receipt is stored at
`docs/skin/evidence/gate-pass-camera-package-audit-20261024-v1.json`.

## Roboflow reuse decision

The six FRONT SHA-256 hashes are byte-for-byte identical to the FRONT inputs
already stored in `generated-front-roboflow-20261024-v1.json`. The earlier six
8% calls therefore remain the correct Roboflow evidence. Repeating them would
consume inference without changing the inputs. The revised/replacement files
are side views and were not sent to Roboflow.

The source-bound Attune/Roboflow comparison gate was updated to map Attune
capture aliases and filenames by the immutable FRONT hash. It now accepts the
new package naming (`01_england/front.jpg`, etc.) without weakening image
identity. Twelve focused checks pass across the package auditor and comparison
gate, including checksum/preflight/camera-claim failures and renamed-file hash
binding.

## Acceptance boundary and next executable step

This package proves that the generated stills pass the product's static
capture/preflight gates. It does not say that Attune.more lacks a working skin
result flow: the merged product already produces the nine appearance criteria,
separate skin type, regional results and maps. It says only that this exported
package does not yet contain the six full V5 FRONT analysis response bodies;
the package manifest itself records `fullV5SkinAnalysisCompletedForThisSet=false`.

The next execution must run the six unchanged FRONT files through the merged
product analysis, export the complete `/api/local-health/skin` responses with
their source-bound photo IDs, and pass that bundle to
`build_attune_roboflow_comparison.py`. The gate will then create the direct
side-by-side JSON/Markdown result. It will not accept partial responses,
renamed criteria, substituted values, or a different product commit.

Physical real-camera acceptance, temporal stability, expert skin truth,
Precision/Recall/F1 and production activation remain separate pending work.
No model training, repeated Roboflow inference, deployment or production merge
was performed.
