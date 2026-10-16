# Acne v3: controlled run with the corrected background rule, first stage of 300 steps (2026-10-16)

**Result:** the correction removed the false candidates, but the detector stopped finding almost all real targets as well. At step 300 it is not better than Step0 and not better than the failed run. Step0 is not an accepted product model either. Acne stays `accepted:false, file:null`. No automatic continuation follows. The independent test set is still sealed.

## Setup

- **Pre-registration:** `acne-v3-fix-preregistration-20261016.json`, SHA `0f448303…`, frozen before training.
- **Code:** `train_acne_v3.py` at SHA `5da005fd…`.
- **Run directory:** a separate one, `run-fix/`.
- **Start:** Step0 (SHA `18e94a95…`, hash-checked) with a new optimizer state. The failed run, including its step-1250 checkpoint, is preserved and was not resumed.
- **The only change:** the objectness loss. The failed run used the shared head's normalisation (mean over known negatives ×20) with sigmoid focal loss. The corrected run uses standard YOLOX BCE, summed over positives and known negatives and divided by num_fg. This **changes the normalisation and the focal→BCE weighting at the same time**, so the result cannot be attributed only to the ~180× hard-negative gradient ratio.
- **Unchanged:** the plan (same SHA), groups, per-step sample order and seed, augmentation, scale targets, guard, trainable layers, BatchNorm handling, AdamW, LR 2e-4, warmup 100, ACCUM 8, conf .30, NMS .30, and the evaluators.
- **Schedule:** cosine over 1,800 steps, not compressed. The run stopped at step 300 with LR 1.94e-4.
- **Checks before training:** 5 of 5 focused tests passed.
- **Checks during training:**
  - loss and gradients stayed finite at every step;
  - all 80 trainable tensors were updated;
  - the frozen state was unchanged at every checkpoint (SHA `20149bbc…`);
  - every 50 steps a checkpoint was saved with model, optimizer, scheduler and log.
- **Gradient size:** before clipping, the gradient norm peaked at 286,400 early in the run and was 22 at step 300. Clipping (norm 5) was decisive in the early phase.
- **Step-300 checkpoint:** model `5644d62c…`. The desktop received a copy of the weights for evaluation only; nothing was trained there.

## Validation: the same 150 photos, conf .30, IoU ≥ .30

| Model | Recall | Precision | F1 | False candidates per photo |
|---|---|---|---|---|
| Step0 | .247 | .280 | .262 | 5.27 |
| Failed run, step 300 | .492 | .141 | .220 | 24.8 |
| Corrected run, step 300 | **.010** | .765 | .021 | 0.03 |

## Product chain: the unchanged v2 evaluator

IoU ≥ .50 is the primary rule. Results at IoU ≥ .30 are shown in brackets and reported separately. Step0 and the failed-run step 900 were already saved; the failed-run step 300 had not been evaluated on the product chain before, so it was run once.

| Set | Step0 | Failed run, step 300 | Corrected run, step 300 |
|---|---|---|---|
| Scope B positives: 14 targets | 4 (4) | 4 (4) | 2 (2): lost 2 |
| Valid reviewed negatives (7 photos): false candidates | 3 | 41 | **0** |
| Controls: 29 targets | 16 (16) | 7 (17): +1 / −10 | **1 (2): −15** |
| 20 held-out photos: 95 targets | 39 (52) | 39 (56): +11 / −11 | **4 (5): −35** |
| Unmatched candidates, held-out 20 photos | 254 | 606 | 1 |
| Matched-box area ratio, held-out 20 (median) | 1.17 | 1.57 | 1.36 (n=5) |
| Median time per photo, held-out 20 | 3.6 s | 3.6 s | 3.4 s |

The held-out 20 photos pass the replay gate, but their eyewear check is UNKNOWN; they are not counted as full product passes. Two of the reviewed-negative photos are not product-valid and were excluded.

## Reading

- The correction reversed the direction of the failure. The background term now dominates and objectness is suppressed almost everywhere: false candidates went from 41 to 0, but real targets went from 39 to 4.
- **The fall in false candidates is not success.** Under the agreed reading rule it does not count, because targets were lost.
- Box placement is not proven to have improved: only n = 5 matched boxes are available.
- Why it collapsed is a **hypothesis**. With ~12k known negatives against ~16 positive anchors per tile, standard BCE gives the background a very large total weight. Together with early gradient clipping, the first ~100 steps pushed objectness down across the board. Whether the positives recover over more steps cannot be inferred from the first 300.
- **A failed short run is not proof that the architecture cannot learn.** Standard YOLOX training normally takes many epochs, and LR here is still at its peak.

## What was proven

The failed run's false-candidate increase is sensitive to the strength of the background term. Weak background (failed run) gives many false candidates; standard background (corrected run, 300 steps) gives nearly no output. Neither one beats Step0 on the product chain at step 300.

Continuing is the owner's decision. It was not started automatically.
