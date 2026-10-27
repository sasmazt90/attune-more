# Eye-area finding classifiers: restored (darkCircles, hoodedEyelids, downturnedCorners)

Everything here uses existing cached features, the same labels (gen/state.json, K-181..K-320, 140 persons), the same folds and seeds, and the same hyper-parameters. Thresholds use thr_prev from rf/thr_rule.py (P0 = 0.25, target precision 0.80).

Not done: no new data, no paid APIs, no hyper-parameter search, no RF-DETR, no git commit, and no edits to existing repo files.

## 1. Which recipe each finding uses
| Finding | Research row reproduced | Features (order) | Pipeline |
|---|---|---|---|
| darkCircles | eye_grid3.py A) "Renk kıyası (ışık düzeltmeli) \| Ön". This is the row the handoff cites (thr ~0.82, P 0.89, R 0.46). The eye_fair3.py colour row is a different recipe (thr 0.80, P 0.88). | [log(Lc/max(Lc-dL,1e-3)), da, db] averaged over the readable eyes, then the pose one-hot [1,0] (5 values) | StandardScaler + LR(C=1.0, balanced) |
| hoodedEyelids | eye_fair3.py "Sarkma: kapak \| Geometri + DINOv2" | 7 sag_geo values (tilt, aperture, brow_lid, crease_lid, mouth_corner_drop, cheek_low, jaw_width_ratio), then the mean of the lid_L/lid_R DINOv2 embeddings (768): 775 values | StandardScaler + PCA(20, rs=0) + LR(C=0.1, balanced) |
| downturnedCorners | eye_fair3.py "Sarkma: göz dış köşe \| Geometri + DINOv2" | The same 7 geometry values, then the mean of the corner_L/corner_R embeddings | same as hoodedEyelids |

**darkCircles training detail.** In the eye_grid3 recipe the model is trained on three rows per person: the front row plus the two 20° side rows (rf/eye_pose_rows.npz, one eye each). The person score uses the front row only. The deployable model keeps this exactly: 420 rows from 140 persons. Inference uses the front photo only.

## 2. Reproduction against the recorded tables
Nested evaluation, 10 repeats of stratified 5-fold. Outer seeds 0-9, inner seeds 100-109.

| Finding | Recorded TP/FP/FN, P, R, AUC, mean thr | Reproduced |
|---|---|---|
| darkCircles | 24.9/3.0/29.1, 0.89, 0.46, 0.86, 0.82 | identical |
| hoodedEyelids | 24.5/5.0/6.5, 0.83, 0.79, 0.97, 0.65 | identical |
| downturnedCorners | 16.4/3.7/15.9, 0.82, 0.51, 0.92, 0.82 (no threshold in 1/50 folds) | identical (also 1/50) |

Environment: sklearn 1.9.1. For each finding, the numpy predict_proba read from the JSON matches sklearn to at most 2e-15.

## 3. Deployed models (rv3model/findings-v2/)
**Fitting rule.** The same pipeline is fitted on all 140 valid persons. The threshold is thr_prev applied to 5-fold out-of-fold person scores of those same persons. The split is StratifiedKFold(5, shuffle=True, random_state=100), which is the research inner split of repeat 0. For darkCircles the OOF score is the front-row probability, from a model trained on front + side rows.

| Finding | Threshold | OOF at threshold (TP/FP/FN) | thr_prev across OOF seeds 100-109 (informational) |
|---|---|---|---|
| darkCircles | 0.8567 | 21/2/33 | 0.79-0.93 |
| hoodedEyelids | 0.6384 | 26/6/5 | 0.54-0.78 |
| downturnedCorners | 0.6678 | 24/6/9 | 0.65-0.93 |

**Deviation to note.** The threshold depends heavily on the OOF split. For downturnedCorners, seed 100 lands near the bottom of the range (0.668 against a nested mean of 0.82). The deployed operating point is therefore likely to have higher recall and lower precision than the nested estimate (P 0.82, R 0.51). The nested numbers in each JSON's `evaluation` remain the honest performance estimate. I did not change the rule; changing it is a decision for the user.

Each JSON stores:
- model.scaler{mean,scale}, model.pca{mean,components} (or null), model.lr{coef,intercept}
- the ordered feature definitions, threshold, thresholdRule, decision, training
- evaluation (nested TP/FP/FN/P/R/AUC, persons, positives, recorded values)
- version is skin-findings-v2-eye-20261026. The prefix differs from skin-findings-v2-dino, so skin_findings_dino.specs() does not load these files.

**Geometry value for downturnedCorners (added at the lead's request).** File: findings-v2/severity_geo/downturnedCorners.json, marked "geometry percentile among positives, not validated against ratings".
- Feature: sag_geo `tilt`. For each eye, (Q[inner].y - Q[outer].y)/eye width in the roll-normalised frame (L eye: inner 133, outer 33; R eye: inner 362, outer 263), averaged over both eyes. A value > 0 means the outer corner is higher.
- Orientation: downturn = -tilt.
- The file stores the sorted downturn values of the 33 persons labelled 'sarkma: göz dış köşe'.
- downturned_percentile() returns the midrank percentile, where 100 = most downturned.
- This value is weak. As a separator of positives from negatives it reaches AUC 0.66 (median tilt 0.064 for positives vs 0.078 for negatives).

## 4. Feature parity (production code against research caches, all 140 persons)
Setup: front photo, Python MediaPipe (same face_landmarker.task) landmarks turned into dicts {x,y,z}, local rv3model/dinov2-small loaded with local_files_only using the KClassifier.embed code. Output: parity_eye.json.

| Quantity | max abs diff | median | Decision flips |
|---|---|---|---|
| darkCircles colour vs eye_pose_rows front col | 3.0e-8 | 0 | 0 |
| Light-corrected image vs research light.py (scipy) | 0.0 | 0 | - |
| Geometry, 7 values (vs sag_geo.json) | 0.0 | 0 | - |
| Downturn slope tilt (vs sag_geo.json) | 0.0 | 0 | - |
| lid / corner mean embedding vs eye_fair_emb.npz | 4.8e-7 | 2.4e-7 | - |
| Probability darkCircles / hooded / downturned | <=1e-5 (from 5-dp rounding) / 0 / 0 | 0 | 0/0/0 |

**Port note: triangulation.** The production module is numpy/cv2 only:
- Triangulation uses cv2.Subdiv2D, plus a pocket fill for the thin hull triangles that Subdiv2D omits. Without that fill, 5 of 12 persons were missing 1-2 triangles.
- Normals are interpolated per pixel with barycentric weights.
- After the fix, the mesh is identical to scipy for 140/140 persons (tri_all.py).

**Landmark z.** light.analyze needs z for the surface normals.
- The browser does send z: skinAnalyzer.ts takes result.faceLandmarks[0] (MediaPipe JS NormalizedLandmark has x, y, z), and skinSnapshot.ts:85 sends landmarks with {...p}.
- The API validator local_health.landmarks accepts z but treats it as optional.
- Without z, darkCircles is omitted (no z=0 fallback); the other two findings are still returned. Checked on 140/140 persons.
- Not verified: JS landmarks against Python MediaPipe numerically.

Other edge cases checked on 140/140 persons: a side view returns {}, and the front view returns all 3 findings.

## 5. Files and sha256
- rv3model/findings-v2/darkCircles.json 03a1e3eb584399791e578eae8ee35cc682901310aa63d5afa12cc0a1ea2b286c
- rv3model/findings-v2/hoodedEyelids.json 647141640b5c2cb5cb68e5557e0c43af723b2659777087b2824978c568c3607f
- rv3model/findings-v2/downturnedCorners.json dec94ef7cd89d6badce52cb59e496f168e66cc4c1ccdfbd5f3ad12be7a468360
- rv3model/findings-v2/severity_geo/downturnedCorners.json 50d0784310a69304360292cae474056e446fc7922abdb8a7ffac7091401e03b4
- repo/claude-skin/services/core-api/skin_findings_eye.py (new) d11a8e2a0c77c63ded329e1d2d09ebd481a3512e74a9082ca26f784162215eee
- v2/export_eye.py 971a3e3d4babe5f3456b3d3b06416c20937ca18ce6b31119ce224f4cbcf0e197
- v2/export_eye_severity.py e115c59c557ca9ba47e2d6f945929b7d491b2222f73348be2741c2468245bc40
- v2/parity_eye.py 55260f27e3bb8714475c2616c5d4970c21282b37758091c5ffbb8622d38ef91b
- v2/parity_tilt.py f4564eea6c5036efeca1057f2bb57505e3028f03bcc85324580c54ed39411968

The JSONs still have to be copied into the deployed bundle directory (models/regional-skin-v3/findings-v2/). That copy has not been done.

## 6. How analyze_photo should call it (regional_skin_v3.py not edited)
```python
    import skin_findings_eye as SEYE
    eye_scores = SEYE.photo_scores(bgr, landmarks_norm, view, kc, MODEL_DIR)   # {} unless view == 'front'
    eye_specs = SEYE.specs(MODEL_DIR)
    eye_findings = {fid: dict(region=SEYE.REGION, probability=p, state=SEYE.decide(p, eye_specs[fid]))
                    for fid, p in eye_scores.items()}                          # missing id => unmeasured, not notSeen
    if eye_findings.get('downturnedCorners', {}).get('state') == 'seen':
        eye_findings['downturnedCorners']['geometryPercentile'] = SEYE.downturned_percentile(bgr, landmarks_norm, MODEL_DIR, view)
    # return dict(..., findingScoresEye=eye_findings, ...);  model_manifest(): out.update(SEYE.manifest(MODEL_DIR))
```
