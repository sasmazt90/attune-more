# FACE v3 wrinkle-source decision — 2026-10-23

FACE v3 contains 408 images and 138 `wrinkles` annotations on 106 images:
99 train, 28 validation and 11 test annotations. Geometry is mixed:

- 96 non-rectangular polygons;
- 42 axis-aligned rectangle polygons, which are box supervision rather than
  exact wrinkle masks;
- 35 non-rectangular masks cover at least 8% of the image;
- 10 cover at least 40%;
- 37 cover at most 2%.

The non-rectangular mask-area median is 3.39%, but the range is 0.11%–80.07%.
The class therefore mixes tiny local patches and broad face regions. Fifty-two
annotations occur on files not named `wrinkle_skin`, so the filename context
also does not provide a clean positive-only definition.

A stratified 18-example visual review covered six largest polygons, six small
polygons and six rectangle polygons. Large masks cover broad face, cheek,
chin or mouth regions; small masks include inconsistent under-eye, eye-adjacent
and nasal patches, including examples named `normal_skin`; rectangle samples
cover whole close-up crops. The class does not distinguish crow's feet from
forehead, under-eye, cheek or mouth lines.

Decision: **do not train or promote a crow's-feet model from FACE v3, and do
not merge these masks into a generic wrinkle segmentation training set.** This
removes FACE v3 from the active criterion-11 training pool without deleting or
relabeling the source. The separately selected Wrinkles Detector / skin-face
sources still require an explicit crow's-feet definition, geometry audit and
camera/expression evaluation.

Executable evidence:

- `scripts/skin-research/audit_wrinkle_geometry.py`
- `tests/unit/test_wrinkle_geometry_audit.py`
- `docs/skin/evidence/face-v3-wrinkle-geometry-20261023-v1.json`
- `docs/skin/evidence/face-v3-wrinkle-visual-review-20261023-v1.json`

Thirteen focused audit tests pass. No source image, contact sheet, label,
training run, model activation or product output was committed by this step.
