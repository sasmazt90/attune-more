# Source preparation checkpoint — 23 October 2026

The roadmap is still **in progress**. This checkpoint implements and runs source
validation; it does not accept any skin model or change the live application.

## Concrete work

- Added a read-only COCO ZIP auditor. It decodes each image, verifies dimensions,
  inventories original classes and supervision geometry, checks boxes and
  polygons, hashes bytes/pixels, and queues perceptual/export-name leakage hints.
- Ran it on the existing 800-image three-class acne import and the 399-image
  under-eye import. All 37,342 acne annotations are boxes without segmentation;
  all 869 under-eye annotations contain non-rectangular, geometrically valid
  polygons. No invalid box/polygon/dimension was found in these two archives.
- Verified that all 800 filtered acne image files are byte-identical to the
  original SmartSkinCare export, and every retained annotation is identical.
  The original source preserves 2,082 Mole, 853 Freckles and 1,191 Enlarged pores
  annotations for confounder-aware evaluation. They are not negative skin labels.
- Added ten executable regression tests covering exact pixel duplicates across
  encodings/splits, weak similarity and crop-name hints, box versus mask handling,
  invalid polygons, unsafe paths, changed import bytes/annotations, and unavailable
  labels. All ten passed with Python unittest and Pillow 12.3.0.

The durable machine-readable evidence is in `evidence/archive-audit-20261023-v2.json`
and `evidence/acne-import-provenance-20261023-v2.json`. Original archives were not
rewritten, extracted or uploaded again. No excluded archive was accessed. No new
training, dataset version, project, permission, production merge or deployment
was created.

## Leakage and acceptance limits

There are no exact byte/pixel duplicate groups among these 1,199 imported files.
There are six perceptual candidate pairs, four crossing existing splits. These
are review candidates, **not confirmed duplicate photos or person matches**.
Export filenames also carry possible original-photo/left-right crop relations;
the report records those separately without inventing identity. Candidate
evaluation rows are listed in the quarantine sidecar. Source/Roboflow splits
remain unchanged; the sidecar is an exclusion list for clean-subset evaluation,
not an assertion that remaining images constitute an accepted independent test.

Image pixels were processed only for deterministic fingerprinting; no visual
review of test photos, model predictions or threshold tuning was performed.
Different photos of one person, mirrored/cropped material and prior review or
training exposure remain unresolved. Both READMEs declare CC BY 4.0, which does
not settle individual-photo rights. SmartSkinCare's README reports prior resize
and crop augmentation; the under-eye README reports resize and no augmentation.
Raw platform validation/test scores alone cannot close these acceptance gaps.

## Remote state and next execution

The existing RF-DETR NAS acne run `5b632a5c12b76fcfe703`, version 1, remains
`running` with no produced model IDs. Its immutable version lists 553/165/82
train/validation/test images. Continue that run; do not launch a duplicate.
The private regional map project remains empty. The private under-eye project
has 399 images and no generated versions; geometrically valid source masks do
not alone authorize treating every annotation as reviewed.

Next: resolve source/photo-group hints and previous-exposure provenance, verify
the remote model-version export against this import, and obtain the selected
oil/dry/redness archive geometry using direct accessible sources. Retain the
original SmartSkinCare labels when inspecting acne/mark/pigmentation confounders.
When NAS finishes, page its children by modelGroup and collect per-class metrics
before selecting validation thresholds. Camera and regional-map acceptance stay
open. The current product's combination rule uses visible-support proxies and
can trigger on tiny nonzero areas; it is not yet a validated regional truth
model. Re-evaluate it under the accepted coverage and unknown-region contract.

## Reproduce

From the repository root, with the three existing import archives available:

```bash
python -m unittest discover -s tests/unit -p test_skin_roadmap_archive_audit.py -v
python scripts/skin-research/audit_roadmap_archives.py \
  --source acne=/path/to/acne-three-class.zip \
  --source dc=/path/to/dc-eb-2-pilot.zip --output /new/path/audit.json
python scripts/skin-research/verify_roadmap_filter.py \
  --source /path/to/smartskincare.zip --filtered /path/to/acne-three-class.zip \
  --classes Pimple 'Post acne' Pigmentation --output /new/path/filter-receipt.json
```

Outputs use exclusive creation so an earlier receipt is never overwritten.
