# Current product verification and crows-feet source preparation

## Existing product flow

The merged `main` code at `7463eef112c5a40f7cd01192b6d1f4e9fa6ab285`
already returns concrete skin results. It is not an empty integration target.
The backend contract contains the nine current appearance IDs (`tone`, `oil`,
`redness`, `acne`, `sag`, `dry`, `lines`, `dark`, `bags`), a separate skin-type
result, six regional views, a whole-face overview, local maps/contours and a
validated persistence boundary. The camera page attaches those outputs and the
result component renders regional criterion selection.

This verifies implementation presence, not universal accuracy. The code itself
distinguishes analytic appearance proxies from accepted learned heads and
independently validated measurements. The roadmap therefore upgrades evidence
and individual methods while preserving the already working result experience.
The exact file/blob record is in
`docs/skin/evidence/current-product-skin-contract-20261023-v1.json`.

## Crows-feet preparation

The selected `skin_face_detection` snapshot had 875 `crows_feet` annotations on
166 images, including 20 invalid polygons and two visually confirmed source-photo
groups crossing the original train/validation boundary. A new deterministic
preparation script now:

- preserves the source archive byte-for-byte;
- removes only invalid mask annotations, without repairing or inventing geometry;
- groups Roboflow transform siblings and exact decoded-pixel duplicates;
- assigns each source group to exactly one split;
- excludes unlabelled images instead of treating missing labels as negative;
- writes a review manifest that keeps `trainingAuthorized=false`.

The resulting local review archive contains 166 images, 855 valid polygons and
163 source groups. The group-safe split is 116/25/25 images and 572/133/150
annotations for train/valid/test. A second independent archive audit reports
zero geometry issues and zero cross-split exact, filename or perceptual candidate
pairs. The archive SHA-256 is
`467a00f0aaf0569a2bf6bcf9abac063bb32caabf195c577c22a4afbb918ef5e5`.

This is a positive-only annotation review package, not a train-ready dataset.
Negative-label completeness, expert semantic review, expression/pose coverage,
independent camera tests and product acceptance remain open. No model training,
deployment or result activation was performed.
