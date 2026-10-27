# Dryness source and acne diagnosis — 2026-10-23

No new model, source relabeling or product activation occurred. Existing regional NAS segmentation training `3485f8c67f957a1b850d` remains running at 05:42:45 UTC. Acne training is finished; under-eye 399 images have no generated version. Do not create duplicate jobs while this run proceeds.

## Dryness/flaking supervision

The selected Merve source was resolved from the repository ledger and verified via Roboflow Universe and version export: [ciltanalizi version 12](https://universe.roboflow.com/merves-workspace-uxyeb/ciltanalizi-rfa8m/dataset/12), publisher-declared CC BY4.0. Direct COCO archive SHA256 `8fdf070c0cae65fd27ce0046c93393e0ac17e5282bf472097453c756481b831e` exactly matches the original selected archive hash. Historical ledger assignment counts should not be confused with the raw source archive's splits; no export drift is claimed.

The immutable archive has 3,368 images: 2,949 train / 279 valid / 140 test; 12,741 annotations. All 2,590 `pul` annotations are valid boxes (2,232 train / 269 valid / 89 test); **zero are true polygons**. `kirisiklik` similarly has 2,513 boxes and no masks. Only two genuine polygons occur in other classes (one pore, one redness); these do not supply dry masks. No geometry issues or exact duplicate groups were found;74 cross-split perceptual candidate pairs and 39 cross-split filename groups require review. They are not confirmed person/photo identities.

All 3,368 filenames are CLAHE-prefixed. This agrees with the earlier repository ledger's declaration that reviewed Merve `pul` positives are processed and excluded from natural RGB calibration. Six deterministic TRAIN examples were viewed: broad overlapping boxes, visible peeling/fine texture, augmentation borders and a source watermark occur. Assistant review does not validate expert semantics or establish individual-photo rights. The source can inform a future box-localization research experiment after grouping/review; it cannot directly teach precise blue masks, normal regional truth or general natural-camera color calibration. Existing six Clean3 dry polygons remain insufficient for a broad regional dry model. No new dry training was launched merely to fill this gap.

The full audit is preserved as `merve-direct-audit-20261023-v1.json.gz`; summary and visual-selection receipts contain hashes and actual supervision counts. Reproduce with `audit_roadmap_archives.py --source merve=merve-v12-direct.zip --output <new-receipt.json>`. All original files remain unchanged.

## Acne localization versus class disagreement

`diagnose_detector_snapshot.py` replays existing pinned model 754885 validation predictions only: 165 images, original confidence thresholds 0.2 Pigmentation / 0.3 Pimple / 0.3 Post acne. No new inference, test access or threshold refitting was required.

At IoU 0.5, confidence-ordered **class-agnostic one-to-one** matching finds:

| Publisher truth | Predicted class | Matched instances |
|---|---|---:|
| Pimple | Post acne |205|
| Pigmentation | Post acne |93|
| Post acne | Pimple |67|
| Post acne | Pigmentation |11|

This matrix differs deliberately from class-aware precision/recall: a higher-confidence wrong-class prediction can claim a truth before a lower-confidence correct-class prediction. Counts are diagnostic disagreements; they do not prove which annotation is correct. Six high-IoU examples were inspected. Predicted/source box locations align closely, but tiny patches do not establish a reliable semantic boundary by assistant review. No labels were changed.

Source instance size is small: 275/283 Pigmentation, 787/802 Pimple and 6,748/6,820 Post acne boxes have source area below 32² pixels. At the stored inference floor, same-class best-overlap opportunities at IoU 0.5→0.75 fall 110→25 Pigmentation, 452→79 Pimple and 3,330→523 Post acne. These counts allow reused predictions and **are not recall**. They suggest tight localization and class separation both need attention; no unsupported claim about the selected NAS child's input resolution is made. There are no cross-class truth-box overlaps at IoU ≥0.5 in this validation set, and 124/165 responses reach the 300 prediction ceiling.

Next improve reviewed class boundaries, annotation coverage and localization on validation before another training. The previous bounded tiling experiment already increased false positives and is not accepted. Keep the exposed test unchanged and obtain independent camera/subject acceptance through the existing consent path.

## Verification

121 unit checks pass with zero failures/errors/skips. Six new regressions distinguish wrong-class matching, duplicate predictions, loose localization, low-confidence opportunities, source-label overlap and invalid thresholds. Previous source/export/API/combination safeguards also pass. Full diagnosis, visual-selection receipts and code hashes are versioned; no production merge/deploy, expert approval or complete roadmap acceptance is claimed.
