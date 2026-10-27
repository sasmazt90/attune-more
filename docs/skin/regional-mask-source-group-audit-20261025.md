# Regional mask source/group and geometry audit

The frozen Roboflow v1 COCO export is structurally usable for review: all 337 images are represented, the 244/63/30 split matches the version receipt, and all 1,636 Oily/Redness annotations are valid polygon geometry. There are no box-only or out-of-bounds annotations in this export.

The cross-split candidate scan found no exact normalized-pixel matches and no pairs passing both dHash and pHash thresholds. This is a candidate screen, not a person-identity review. All 337 source IDs remain without complete reviewed person/source-group coverage, so the existing split is not proven independent and the exposed 30-image test remains ineligible for final acceptance.

The audit binds both the original source archive digest and the provider-export digest because provider export/re-encoding changes the archive bytes. The private filename-to-source resolver and all image bytes remain uncommitted.

No training is authorized. Before one controlled regional experiment, complete person/source-group review, produce a replacement group-locked split, approve the expert mask-extent and hard-negative protocol, reserve a new untouched final test of at least 50 images, and reserve a separate real-camera holdout. Missing masks must never become Normal, and Redness remains an independent layer.
