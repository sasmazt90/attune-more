# Under-eye provider v2 grouped reproduction

Observed at: 2026-10-25T09:32:00Z

The existing private pilot was converted by Roboflow into augmentation-free version 2 without starting training or activating a model. Its COCO export was then validated and regrouped locally with the reviewed source-photo-pair receipt.

## Verified result

- Provider version: `tolgar-sasmaz/attune-skin-under-eye-pilot/2`
- Source export: 399 images, 869 polygons; train/valid/test 279/81/39
- Classes: 382 `darkcircle`, 487 `eyebag`
- Reviewed cross-split source-photo groups: 3
- Records moved to train: 4
- Reproduced split: 283/78/38
- Image bytes changed: 0
- Annotation payloads changed: 0 (only COCO IDs were deterministically reindexed)
- Reproduction SHA256: `9ef3c36e16ce5ae84ff52d527f82f15e5f9fcbaf63f0a6f6720388339133d6fc`

## Fail-closed decision

The reproduced ZIP was not uploaded. Its SHA256 differs from the previously authorized archive SHA256 `41985daef4e2ba6336be5b67ada1c0001cd188a930df6ce29ef67cdf2999fbc8`. The existing grouped-project upload task still has no bytes and remains at `created`; no duplicate upload task was created.

This artifact proves deterministic reproduction from the current private provider export. It does not establish person independence, expert review, a camera holdout, training authorization, activation, or roadmap acceptance.

