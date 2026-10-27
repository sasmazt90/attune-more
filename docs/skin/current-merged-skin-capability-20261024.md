# Current merged skin capability receipt

Observed: 2026-10-24T06:12:17Z

## Result

The current merged Attune.more skin baseline already produces concrete output. It is not an empty shell waiting for a Roboflow model.

The source-bound generated replay is pinned to commit `7463eef112c5a40f7cd01192b6d1f4e9fa6ab285` and endpoint `/api/local-health/skin`. The execution provenance explicitly records no product, model or threshold behavior change from that baseline.

| Verified output | Result |
| --- | ---: |
| Complete FRONT subjects | 6/6 |
| Existing appearance criteria | 9 |
| Valid criterion values | 51/54 |
| Criteria with at least one valid value | 9/9 |
| Separate skin type results | 6/6 valid |
| Complete six-region inventories | 6/6 |
| Subjects with maps | 6/6 |
| Subjects with contours | 6/6 |

Existing criteria: `tone`, `oil`, `redness`, `acne`, `sag`, `dry`, `lines`, `dark`, `bags`. Skin type is separate from those nine appearance criteria.

## Durable gate

`scripts/skin-research/summarize_current_merged_skin_output.py` now verifies this baseline from the already source-bound comparison receipt and fails closed when:

- the merged commit or endpoint changes;
- product/model/threshold behavior was changed during replay;
- any of the nine existing criteria disappears;
- skin type or any of the six regional inventories is missing;
- a subject has no concrete map output;
- the upstream receipt claims accuracy, expert truth, real-camera acceptance, threshold calibration or production activation.

Five dependency-free tests pass, including negative cases for a missing criterion, missing maps, evidence overclaim and a mismatched commit. The actual committed comparison receipt also passes and produces `docs/skin/evidence/current-merged-skin-capability-20261024-v1.json`.

## Roadmap implication

Post acne and Pigmentation are additive work on top of a functioning baseline. They must not replace, disable or misdescribe the current nine-criterion plus separate-skin-type product. The receipt proves concrete execution, not criterion accuracy: expert truth, physical-camera acceptance and calibrated learned-model activation remain separate acceptance requirements.

## Remote refresh

- Roboflow workspace: 16 private projects.
- Acne/post-acne/pigmentation NAS `5b632a5c12b76fcfe703`: finished, 89 children.
- Regional NAS `3485f8c67f957a1b850d`: finished, 75 provider records.
- Under-eye grouped research project: still empty; no version or training.
- No training or inference was started or duplicated in this run.
