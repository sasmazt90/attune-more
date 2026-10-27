# Pinned regional source pairs — 23 October 2026

## Implemented

Obtained complete COCO image–annotation exports for FACE v4, Redness v2 and
Dryness v1 through supported Roboflow export tools. FACE v4 contains visible
patch rearrangements from bounding-box rotation augmentation, so obtained its
unaugmented v3 and selected that version for inspection. These are separate
sources from the ledger's `face` alias (`skin_face_detection`); no alias was
silently replaced.

Built a deterministic, source-preserving 120-image review ZIP, without model
inference, relabeling, split mutation, retraining, source project forks or serving
changes. Every selected image is from source train, has a distinct exact-pixel
group, and has no known exact-pixel match to the four existing pinned audit
manifests. Cross-split exact, perceptual and filename candidates were excluded
from selection. These precautions do not certify person-disjoint splits.

| Source | Frozen export | Images | Relevant nonrectangular polygons | Existing exact-pixel matches |
|---|---|---:|---|---:|
| [FACE](https://universe.roboflow.com/datasetbola/face-a7el6/dataset/3) | v3 COCO segmentation | 408 | dry 48; oily 98; normal 88; wrinkles 96 | 0 |
| [Redness](https://universe.roboflow.com/model-cn9k6/redness-ik5oe/dataset/2) | v2 COCO segmentation | 1,746 | redness 2,150 | 45 |
| [Dryness](https://universe.roboflow.com/skinanalysisv22025/dryness-q1yyf/dataset/1) | v1 COCO | 2,072 | Dryness 61 | 700 |

These polygon counts include masks with separately invalid source boxes. The
review sampler requires both a valid box and a valid nonrectangular polygon for
a mask quota. Rectangle polygons remain box supervision. API annotation counts
and frozen-export counts differ; archive-specific counts are preserved rather
than silently reconciled. The combined three-export audit contains 57
cross-split exact groups; this is a review flag, not an identity finding.

The 120 pairs comprise FACE dry/oily/normal/wrinkles: 16 each; Redness polygons:
32; Dryness polygons: 12; Dryness box-only records: 12. All original image bytes,
annotation objects, class IDs, coordinates, source IDs, README and licence
records remain present. The box samples are for semantic diagnosis and cannot
become blue masks. All labels remain unreviewed source claims.

## Source geometry findings

FACE has localized multi-label polygons, including dry cheeks and an oily nose
in the same source image. It also has broad anatomical masks and full-face
normal masks that include eyes. It therefore supplies review candidates,
not an already accepted regional normal/assessability benchmark.

Redness has actual cheek masks as well as rectangles and incomplete source
coverage. Both available version records declare augmentation; v2 training
images include brightness/saturation/noise changes and visible patch edits.
Original-resolution source images are accessible through Universe image search,
but original matching annotation geometry has not been obtained. Do not apply
resized/augmented annotations to those originals by assumption.

Dryness contains 6,679 box-only instances, 65 rectangle-polygons and 61 actual
nonrectangular polygons. Train examples include visible peeling, broad skin
regions, nonfacial skin and lesion-like targets. Generic Dryness cannot be
silently treated as confirmed facial flaking or a normal-negative label. The
700 existing exact matches substantiate why this entire archive should not be
counted as new training coverage.

Twenty-four selected source-class records from FACE v3 and Redness/Dryness
train were visually inspected by the assistant. Images and polygons were not
changed. The original IDs/hashes and selected annotation objects are recorded
in `source-visual-inspection-20261023-v1.json`; no facial board is committed.

## Licensing and data use

All three export records and supplied README files declare CC BY 4.0. The
[official licence deed](https://creativecommons.org/licenses/by/4.0/) permits
commercial copying and adaptation with attribution and change disclosure;
its scope does not settle other facial-image rights. Source versions, uploader
workspaces, original README text and attribution links are retained. No
per-photo consent/provenance evidence was supplied by these exports. This is a
documentation gap, not a conclusion that consent is absent. No complete
commercial clearance or product-training approval is claimed.

## Durable artifacts and replay

The private review ZIP and full audit have persistent file identities in
`source-acquisition-summary-20261023-v1.json`; facial images are not published in
the code repository. ZIP SHA-256:
`39c5a43b9ae87926b63b19fe5dd139409e55e38d3202affb04884e18daab61ce`.

The source configuration contains canonical version URLs, transformation
settings and quotas. Use `prepare_source_review_bundle.py --help` for replay.
The full audit and source archive hashes are pinned; the compressed review
manifest records selection, exclusions, exact-match references and unresolved
labels. Existing audit reports are reused, not regenerated. Re-export links
can be obtained through `versions_export`; expiring/key-bearing links are not
committed.

Verification: 10 new behavioural tests passed. All 120 bundle images matched
source bytes, all selected image/annotation/category records matched the
source COCO objects, and all selection exclusion checks passed. The sampler
also rejects source archive drift and overwrite and produces identical ZIP
bytes on replay of the same inputs.

## Continue without repeating this work

Do not redownload these archives, rerun these source audits or restart NAS
without source drift or a concrete experiment change. Use the prepared pairs
to resolve label semantics and regional boundary/normal completeness; do not
train directly on the current samples. Keep natural-camera calibration and
person-independent acceptance open. Existing rejected acne and regional
model evidence remains unchanged.

Other unblocked work remains: source-bound SVG overlay and method-compatible
history wiring under the existing accepted-method gate; under-eye grouping and
review; selected crow's-feet sources; sagging and real-camera acceptance. No
roadmap item is marked product-complete by this data-preparation step.
