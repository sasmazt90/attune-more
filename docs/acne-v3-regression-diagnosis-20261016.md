# Acne v3 regression diagnosis (2026-10-16)

This review covers only existing records and code: no new training, no new inference campaign. The independent test set is still sealed and the checkpoints are preserved.

**Step0 is not an accepted, working product model either.** It is only the comparison baseline. Production acne stays `accepted:false, file:null`.

Evidence: `audit-results/acne-v3-20261015/diagnosis-v3-regression.json`, produced by `scripts/skin-research/diagnose_acne_v3_regression.py`. It reads the saved final boxes of the unchanged v2 product evaluator.

## 1. The 3 → 41 false candidates on reviewed negatives (7 product-valid photos)

| | Count |
|---|---|
| Candidates also present in Step0 (IoU ≥ .30 between models, source coordinates) | 2 |
| New candidates | 39 |
| Candidates that disappeared | 1 |

- Every one of the 41 candidates has its centre inside the reviewed known-negative mask: the evaluator's `unknown` count is 0. Nothing outside the mask was counted as an FP.
- The candidates cluster: 24 of the 41 come from one photo (`0560bfd8`), and 2 of the 7 photos have none.
- New-candidate size: median side 16.3 px (range 10–39 px).
- No visual interpretation was used as a label.

## 2. The 12 lost control targets (IoU ≥ .50)

| Cause | Targets |
|---|---|
| A step-900 final box still exists at IoU .30–.50 (localization got worse) | 7 |
| A final box overlaps the target but IoU < .30 | 5 |
| No overlapping final box | 0 |

- **Box size is shifted.** On matched pairs (IoU ≥ .30), predicted area divided by labelled area has a median of 1.11 for Step0 and 1.57 for step 900.
- **Root cause of the 5 low-overlap targets is UNKNOWN.** Raw pre-NMS candidates, scores and filter decisions were not saved, so these cannot be split into missing raw candidate, low score, NMS, or anatomical filter. A new inference run would be needed to tell them apart, and none was started.

## 3. Code review

### Proven implementation error

The declared rule was not what the code did.

- **What was declared.** The owner-approved rule was the "standard method": unlabeled skin is background, as in public detectors. The standard YOLOX objectness loss is BCE over positive and background anchors, divided by `num_fg`.
- **What the code did.** It reused the shared `yolox_p2` head's sparse-negative normalization: the mean over known negatives × 20, plus focal loss.
- **Why that mattered.** There were about 12.2k known negatives per tile and `num_fg` was about 16.5. On step-900 training tiles, the gradient on a hard background anchor (p > .3) was a **median of 0.0056 times** the standard YOLOX value (p10 .0016, p90 .020). Background supervision was about 180 times weaker than declared.
- **Status as a cause.** That this contributed to the FP increase is strongly suggested, but it is not proven on its own.

**Fix.**
- `train_acne_v3.py` now has `OBJ_LOSS='standard-yolox-bce'` (`StandardBackgroundObjLoss`). The shared head and the CDC behaviour are unchanged.
- The old behaviour is kept only for audit, as `shared-head-mean-x20`.
- The pre-registration records `objLoss`.
- Any new run needs a new pre-registration; the code SHA has changed.

**Check.** `tests/unit/test_acne_v3_training.py` passes 4/4.
- Head anchor order equals the mask anchor order.
- With the fix, the background gradient equals `p/num_fg` (rtol 1e-4).
- The old mode reproduces the error: ratio < .05.
- Targets and ignore regions stay aligned through scaling, jitter and flips (0 misaligned out of 365 synthetic targets). A cut lesion is never background.

### Checked and found correct

| Area | Result |
|---|---|
| Starting weights | Step0, SHA-verified, loaded with strict load |
| Trainable tensors | 80 trainable tensors, exactly the head and PAFPN convs, all of them changed |
| Frozen tensors | 455 BatchNorm tensors and the backbone did not change |
| Resume | Logs run 1–1250 with no gap; LR matches the formula exactly; Adam step counter is 1250 on all 80 parameters; data RNG is stateless per step |
| Missing-label guard | Averages ≤ 1 anchor per tile after warmup, so it is not a meaningful factor. This refutes the earlier hypothesis. |

## 4. Proven data and label issues

- **Public labels are incomplete and inconsistent.** On the same photos, annotators from different sources agree little. In one pair of sources, 215 and 80 boxes give only 23 matches. In multi-class, 340 of 1,119 photos marked "acne-free" have acne added in the corrected version. In the v3 training this unlabeled skin is used as background (the owner-approved method).
- **Scale mismatch.** The training target lesion side was sampled around 16.5 px, × 0.8–1.25. The labelled targets in the product evaluation sets have a median side of 13 px (p25 9, p75 18.5).

## 5. Still only hypotheses

- Box inflation (area ×1.57) comes from different box conventions across sources, or from the scale mismatch above.
- The training never saw a clean, product-like webcam face as a negative: 80% of photos were acne photos and 85% of tiles were centred on a lesion. Domain mismatch increased FPs.
- Weak background supervision (the proven error above) is the main cause of the FP increase.

## 6. What a new trial would test differently, and why

A new trial would change only **one variable**: the corrected `standard-yolox-bce` background rule. Everything else stays the same:
- data and plan;
- scale and sampling;
- steps and selection rule;
- product-chain gates.

That separates the proven code error from the hypotheses above. If FPs on reviewed negatives still rise, the cause lies in the data, labels or scale, not in the code. Starting the trial is the owner's decision; it has not been started.
