# Generated three-pose camera package and Roboflow FRONT review

Date: 2026-10-24

## Outcome

The supplied package contains six complete subjects with `front`, `side_1`, and
`side_2` captures (18 JPEGs total). Every file is 2048×1529, all byte hashes are
unique, and geometry is consistent within each triplet. Visual review confirms
that each row preserves the same person, background, lighting family, clothing,
and broad framing. The two side views are three-quarter views rather than full
profiles, which is suitable for the current three-pose product flow.

These images are user-declared generated images. They are useful for capture,
pose, identity-continuity, UI, and inference smoke tests. They are not real
camera acceptance evidence, expert skin annotations, or threshold-calibration
truth. Country words in filenames are sample identifiers, not verified
demographic labels.

The deterministic manifest is stored at
`docs/skin/evidence/camera-triplet-generated-smoke-20261024-v1.json`. No image
bytes were committed.

## Direct Roboflow comparison

Only the six `*_front.jpg` inputs were sent to the already selected public
candidate `ciltanalizi-rfa8m/12`. Each input was inferred exactly once at 8%
confidence and 50% overlap. The server resolved every call to immutable package
`7ee34fce76456d9ff4cfe6e7049aad1e` (`onnx`, `fp32`). Threshold rows below are
filters over those same responses; they are not repeat inference calls.

| Confidence | All | Acne | Pores | Wrinkles | Redness | Flakes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8% | 224 | 39 | 45 | 55 | 80 | 5 |
| 15% | 89 | 18 | 17 | 25 | 28 | 1 |
| 20% | 62 | 9 | 11 | 21 | 20 | 1 |
| 30% | 36 | 3 | 8 | 17 | 7 | 1 |
| 50% | 17 | 0 | 3 | 13 | 1 | 0 |

At 50%, 207 of the 224 proposals visible at 8% are hidden (92.4%). The effect
is not limited to one class: all acne and flake proposals disappear, redness
drops from 80 to 1, and pores drop from 45 to 3. This establishes that a high
global threshold can conceal a large portion of this model's candidate output.
It does **not** establish that all 207 removed boxes are correct.

| FRONT input | 8% proposals | 50% retained |
| --- | ---: | ---: |
| 1.England | 19 | 5 |
| 2.Germany | 40 | 1 |
| 3.Kenya | 24 | 1 |
| 4.Scotland | 40 | 2 |
| 5.Turkey | 29 | 5 |
| 6.usa | 72 | 3 |

### Engineering visual review

This review compares the boxes' class mix with features visibly present in the
input contact sheet. It is a plausibility check, not expert ground truth.

- **1.England:** forehead, eye-area, and lower-face lines are visibly prominent;
  wrinkle is the dominant proposal class at both 8% and 50%. This is broadly
  plausible, while the overlapping wrinkle boxes still require deduplication
  review.
- **2.Germany:** diffuse cheek/nose redness and several small blemishes are
  visible. At 8% the response includes 21 redness and 5 acne proposals, but at
  50% only one redness proposal remains and all acne proposals disappear.
- **3.Kenya:** the visible complexion is comparatively even in this lighting.
  The response has 24 proposals at 8% but only three at 15% and one at 50%, so
  this image is a warning that the low-confidence tail can also contain weak or
  spurious candidates.
- **4.Scotland:** redness is visibly present, while beard/stubble can confound
  flake and texture boxes. At 8% there are 19 redness and 5 flake proposals;
  only one flake remains at 30% and none at 50%.
- **5.Turkey:** age-related lines are visibly prominent and wrinkle remains the
  dominant class (16 at 8%, 4 at 50%).
- **6.usa:** multiple forehead/cheek blemishes with associated redness are
  clearly visible. The 8% response contains 25 acne and 32 redness proposals;
  at 50% both classes fall to zero. This is the clearest package example that a
  high global threshold can suppress visibly relevant candidates.

The package therefore supports using 8% as a **review floor**, not as a
production decision threshold. It also shows why class-specific calibration,
duplicate handling, and negative examples are required instead of one global
cutoff.

The complete bounding boxes, confidence values, inference IDs, per-image
threshold counts, input hashes, and metric restrictions are stored at
`docs/skin/evidence/generated-front-roboflow-20261024-v1.json`.

## Accuracy boundary

Precision, recall, F1, and mAP cannot be calculated for this package because it
has no expert object-level ground truth. Visual plausibility is useful review
evidence but cannot replace labelled positives, labelled negatives, and a
person-independent validation/test protocol. Production thresholds must be
selected on validation truth per class and then tested unchanged. The 8%
outputs remain proposals for review; high-confidence boxes are not
automatically correct, and low-confidence boxes are not automatically wrong.

## Acceptance effect

- Capture and integration smoke-test eligibility: **yes**.
- Qualitative model-proposal review eligibility: **yes**.
- Real-camera acceptance: **no**.
- Expert-label acceptance: **no**.
- Precision/Recall/F1 or threshold calibration: **no**.
- Production model activation: **no**.

The existing learned-model acceptance gate therefore remains closed. This
package advances the independent product test harness without weakening the
roadmap's expert-label, real-camera, privacy, or holdout requirements.
