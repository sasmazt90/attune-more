# Acne v3: is the corrected step-300 a score problem or a discrimination/localisation loss? (2026-10-16)

No training and no change to production. The development set and the independent test set were not used. The rules were frozen before any raw score was computed: `acne-v3-calibration-preregistration-20261016.json`, SHA `b03e8468…`.
- **Code SHA.** The pre-registration records SHA `ffe6796b…`. Amendment 1 is a crash fix only, with no rule change; the code after it is `e8c12cdc…`.
- **Inventory path.** The desktop copy keeps an equivalent inventory path. `CODE.parent/attune-claude-acne-audit` is the same folder as `CODE`.

## Sample (TRAIN only)

- **Positives:** the first 20 photos of the v2 trainProbe rule, with 170 targets.
- **Negatives:** 9 reviewed TRAIN negative photos with known clean pixels, 41 product tiles.
- **Raw anchors:** obj×cls ≥ .001, in source coordinates. A negative candidate counts only if its centre lies inside the reviewed clean mask, after product NMS at .30.

## Results

| | Step0 | Corrected step 300 |
|---|---|---|
| Targets with a raw anchor at IoU ≥ .50 (localisation capacity) | .765 | **.847** |
| Median IoU of the best-scoring anchor at IoU ≥ .50 | .67 | .60 |
| Median best score per target (IoU ≥ .50) | .574 | **.036** |
| Median objectness / class of that anchor | .80 / .86 | **.12** / .53 |
| Candidates on the clean negatives (≥ .001) | **0** | 59 (max .014) |
| Targets scoring above the highest negative | not definable | 112 / 170 |
| AUC: targets vs negatives | **not definable** (no negatives) | .80 |
| Missed at conf .30, by stage: score / localisation / NMS / filter | 26 / 40 / 10 / 7 (found 87) | **126** / 26 / 1 / 0 (found 17) |
| TRAIN-only threshold: smallest t with ≤ 1 negative candidate per photo | .001 (recall .76) | .005 (recall .78) |

## Decision

| Question | Answer |
|---|---|
| Score calibration problem? | **Most likely yes, but the registered rule could not prove it.** In the corrected model, 126 of 170 targets have a correctly placed anchor (IoU ≥ .50) whose score fell below .30; objectness collapsed from .80 to .12. Localisation capacity did not drop. |
| Real loss of learning or localisation? | **Not shown.** Capacity rose from .765 to .847, and the matched IoU fell only a little (.67 → .60). |
| Not enough evidence? | **Yes, for the formal verdict.** Step0 produced no candidate on these negatives, so its AUC cannot be defined, and the registered "PRESERVED" condition cannot be computed (amendment 1, no rule change). These negatives and positives were also part of Step0's own training, which favours Step0. |
| Calibration result on the same development targets? | **Not run.** The registered condition for that step ("PRESERVED") was not met. The TRAIN-only threshold (.005 for the corrected model) was not applied to development and is not proposed for production. A threshold 60 times below .30 would point to a highly compressed score scale. |

The training logs contain only the total loss. Positive and negative objectness, box and class contributions cannot be separated from them, so they are unknown.
