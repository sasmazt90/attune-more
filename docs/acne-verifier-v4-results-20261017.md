# Acne verifier V4: one expanded-review round, not selected

Source: `attune-claude-acne-audit` / `claude/acne-measurement-audit`, frozen at `e6db3e1fc775b5cdbd09d63858993b2d55eb588f`. Work is isolated on `research/cdc-acne-verifier-v4-20261017`; source, AG and production checkouts are read-only.

All 1,868 unseen TRAIN candidates were visually reviewed once on blind sheets (tight crop, wider context and whole source). AI engineering review, not expert truth. The original V3 decisions, uncertainty and conflicts are preserved. New same-location conflict exclusions are explicit. The final pool contains 1,936 candidates: 316 positive/1,620 negative. Previously used group roles are preserved; learn and calibration groups stay separate. DEV, prior tests, the 15-photo supplement and the 941 uncertain-photo cohort were not used to fit/calibrate.

One verifier used the original frozen 1920 features, learn-only standardizer, L2 logistic regression C=0.1, balanced class weights, lbfgs, tol=1e-4, max_iter=2000. It converged in 91 iterations. Only the three user-approved dependencies were installed in this isolated worktree. There was no detector/backbone training or inference.

The TRAIN-only threshold is 0.0007721509634059334 (same floor(0.05*n) positive order-statistic rule). Calibration: 111/116 positives retained, 47/272 negatives removed, AUC 0.760649. This is not DEV accuracy.

The full scaler/coefficient model and threshold were frozen before one DEV pass. Cached Step0 candidates, source coordinates, labels, reviewed masks and canonical one-to-one matching were reused unchanged. Historical baseline counts matched exactly.

| Method | Found / targets | False | Duplicates | On uncertain |
|---|---:|---:|---:|---:|
| Step0 | 71/108 | 96 | 48 | 75 |
| v1 | 70/108 | 78 | 42 | 64 |
| v3 | 68/108 | 60 | 36 | 58 |
| v4 | 70/108 | 83 | 42 | 71 |

V4 gains `77176e51db41#P15`, `8a78e9d6efd5#P21`, `a2cd98ca9566#P2` and loses `0a8a14a662a5#P26` vs V3. It removes 2 false points and adds 25. The new 70/83 balance fails the registered development selection rule (>=68 found, <=60 false, at least one strict improvement). V3 remains preserved; no second fit or threshold tuning was performed. The V1 research default remains unchanged; production acne stays `accepted:false, file:null`.

The fixed table covers 28 exposed DEV photos, including 22 with nonempty reviewed masks. The 14 additional cached clear controls have zero Step0 candidates. Eyewear is UNKNOWN in the replay. These results do not establish live-camera, independent-test or clinical acceptance. Twelve post-freeze visual cases cover all gained/lost targets, both removed false points and six added false examples; labels were not revised after viewing predictions.

Fit: 0.564 s, measured private peak 176.87 MiB. V4 arithmetic on 42 cached photos: 0.0060 s; cache load+application 0.106 s; full scoring work section 1.334 s, private peak 91.87 MiB. These are cached-verifier timings, not capture-to-result latency. Historical baseline timings use different environments; the detailed report marks them separately.

Seven focused checks passed. No production build, normal-shortcut change, unrelated test campaign, push or merge was performed. Photos and visual sheets are not committed.

Local evidence root:
`C:\Users\PC\Desktop\AI Workspace\TOGG\cdc-progress\acne-verifier-v4-20261017`

The root contains atomic `status.json`, `review-list.json`, all 1,868 `review-decisions.json` entries, `group-roles.json`, `group-isolation.json`, `conflicts.json`, `data-list.json`, `calibration.json`, actual `verifier-v4.json`, pre-DEV `freeze.json`, `checkpoint-index.json`, `dev-decisions-v4.json`, `dev-results.json`, `report-data.json`, twelve local visual cases, `visual-review-notes.json`, `report.md`, focused checks and `hash-index.json`.

Model SHA-256: `4344482d345cc387b1b3c111b05ffc215c2f520c5774807995c2f4591c74d7c7`.
