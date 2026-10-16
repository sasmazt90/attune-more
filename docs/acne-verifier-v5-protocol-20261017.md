# Verifier V5: fixed weighted mean L2 protocol

This round uses the completed V4 data/roles/conflict exclusions unchanged, on the existing research branch. No photographs, labels or detector outputs are created. No new dependency, download, paid call, product change, push or merge.

- Positive weight mass: 50%; each of flat/mole-mark/pore-shine/other: 12.5%. Equal mass per existing research/near-copy group inside each category, equally divided among that group/category's candidates. Normalize mean weight to 1; `class_weight=None`.
- Standardizer mean/population std uses the exact fitting subset and those same weights only.
- Objective: weighted mean logistic loss + lambda/2 * ||coef||², with unpenalized intercept. `lambda0=1/(0.1*276)`. Only lambda0, 3*lambda0, 10*lambda0; for every fit `C=1/(lambda*sum(sample_weight))`.
- StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=20261017), binary label stratification, existing groups; folds frozen before fits. CV reads only the learn feature caches. Each training fold calculates its own weights/scaler.
- Fold metric: retain >=95% of validation positive candidates with the previous positive order statistic rule; average negative removal equally across four negative types and, within each, groups. These weights are for validation scoring, never a fitted scaler. Mean of the three fold scores chooses lambda; exact ties choose stronger penalty. No new candidates or lambda options after results.
- Maximum 9 CV fits and one final fit on full learn. Solver lbfgs, L2, tol=1e-4, max_iter=2000. Calibration features are first read after lambda selection, never fitted; final threshold uses the same >=95% positive protection order statistic. Discard fold thresholds.
- Freeze full model/scaler/threshold and hashes before exactly one DEV application. Reuse the V4 comparator and old frozen Step0/V1/V3/V4 results, with identical 108 targets/masks/coordinates/matching. Select for research only if found>=68, false<=60, and one strict gain vs V3. No post-DEV tuning or automatic extra round.

Implementation scaling was checked in the already installed sklearn 1.5.2 source. Its variation with sample count is verified; it is not presented as a proven cause of V4 regression.

Artifacts are in `C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\acne-verifier-v5-20261017`, including atomic status, frozen protocol/folds/input snapshot, per-fit CV records, group/type weight summary, actual model JSON, calibration, DEV results, hashes and final report. V4 artifacts and source/AG/product checkouts remain read-only. Person independence is not claimed for unknown identities.
