# Acne verifier V5 results: small registered development improvement

V5 uses the unchanged V4 reviewed candidate pool and 1920 cached features. No new photo review/label, dependency, data download, detector/backbone execution or production change. This round was limited to 9 learn-only CV fits, one final learn fit, held-out TRAIN calibration and one frozen DEV application.

The implemented objective is weighted mean logistic loss plus lambda/2 times squared coefficient norm. Positive weight mass is 50%; flat/mole-mark/pore-shine/other negative categories each receive 12.5%. Within category each existing research group has equal mass; candidates split its mass equally. Mean sample weight is 1, `class_weight=None`; weighted standardization is fit only on the relevant training subset. `C=1/(lambda*sum(sample_weight))` keeps regularization relative to average data loss independent of sample count. The sklearn scaling was verified, but is not claimed to be the proven cause of V4 regression.

Fixed StratifiedGroupKFold(3, shuffle=True, random_state=20261017) selection on learn only:

| Lambda | Mean type/group-balanced CV negative removal at >=95% positive retention |
|---|---:|
| lambda0 = 1/(0.1*276) | 24.2598% |
| 3*lambda0 | 28.3623% |
| 10*lambda0 | 30.5617% |

Selected lambda: 0.36231884057971014. Full-learn weight sum: 1548. Actual final C: 0.0017829457364341088. All 9 CV fits and the final fit converged; final fit took 32 iterations. Calibration did not enter fitting or lambda selection.

TRAIN calibration: final threshold 0.15628215094908582, 111/116 positives retained (95.6897%), 115/272 negatives removed (42.2794%; 42.5567% type/group-balanced), unweighted AUC 0.837380. The actual model/scaler/threshold and hashes were frozen before DEV. No threshold was adjusted after DEV.

| Method | Found / fixed targets | False points | Duplicates | On uncertain |
|---|---:|---:|---:|---:|
| Step0 | 71/108 | 96 | 48 | 75 |
| V1 | 70/108 | 78 | 42 | 64 |
| V3 | 68/108 | 60 | 36 | 58 |
| V4 | 70/108 | 83 | 42 | 71 |
| V5 | 69/108 | 59 | 41 | 63 |

The old Step0/V1/V3/V4 records were reused, not re-inferred or re-scored. V5 reused the V4 canonical matcher, masks, labels and unchanged scope. V5 gains `77176e51db41#P15`, `8a78e9d6efd5#P21`; loses `0a8a14a662a5#P26` versus V3. It removes 7 false points and adds 6. The registered research rule passes: found>=68, false<=60, and at least one strict improvement.

This is a small +1 target/-1 false development gain, not independent or product/clinical acceptance. Duplicates rise 36->41 and uncertain-area points 58->63. The 108-target scope comprises 28 exposed DEV photos (22 with nonempty reviewed masks); 14 additional cached clear controls have zero baseline candidates. Eyewear in replay remains UNKNOWN. No extra round was started.

Runtime: nine CV fits/work section 5.979 s, final fit+calibration 1.355 s (solver 0.308 s), DEV apply/scoring 1.069 s. Peak private memory across these phases 164.20 MiB; peaks refer to the owned Python process, not all applications/children. Cached-verifier timing is not camera-to-result latency.

Eight focused checks passed without extra model fits: weight/group totals, full-group duplication invariance, C/lambda conversion, disjoint folds, synthetic and actual train-only weighted standardizers, held-out calibration sequencing, saved-model probability parity and single DEV/baseline reuse. No unrelated build or test campaign.

The actual model and complete evidence are local:
`C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\acne-verifier-v5-20261017`

This contains atomic status, input snapshot, frozen protocol/folds, weight summaries, all nine CV models/results, selected lambda, actual `verifier-v5.json`, calibration, pre-DEV freeze, checkpoint index, DEV decisions/results, coordinate-level false-point changes, full report and hash index. No photos were added to Git.

V5 model SHA-256: `0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb`.

V1 research default, V3/V4 models, labels, roles and exclusions are unchanged. Production remains `accepted:false, file:null`. Claude/AG/product checkouts, main, records, UI, voices, build and launcher are unchanged. No push/merge or product activation.
