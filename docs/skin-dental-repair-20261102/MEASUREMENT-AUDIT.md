# Measurement audit and evidence boundaries

No weight, classifier, model threshold, NMS threshold or clinical claim was changed. Model identity and historical evaluation metadata were read from the preserved runtime and current repository. New functional evidence is separate from historical model evaluation.

## Active Skin methods

| Indicator / family | Active method and owning source | Input → output | Validation evidence / representation |
|---|---|---|---|
| Global skin type | Configured local three-class ViT in `local_skin_type.py`; valid `regional_skin_v3` result overrides the base presentation in `effectiveSkinType` | RGB face / regional evidence → dry, normal, oily, combination, independent sensitivity flag | In this isolated runtime the optional base ViT file is absent and preparation reports `FileNotFoundError`; its output is unavailable, not an active prediction. Regional classification remains a separate path. Its rule requires at least three measured regions and a measured forehead or nose; this is not proof of clinical skin type or complete cheek coverage |
| Regional skin type | Saved RF-DETR model evidence, color/texture features and `k_classifier.json`; `regional_skin_v3.KClassifier` | Same-photo normalized anatomical region → oily/dry/normal/unmeasured plus sensitivity | `normal` is displayed as `Balanced` in regional paint; global `Normal` represents that state at aggregate scope. Sensitivity is an additional flag, not another spelling of normal |
| Tone | Color distribution/appearance proxy in `appearance_analysis.py` | Supported source skin pixels → color/appearance index | Stored API/legacy indicator; not a pigment disease diagnosis |
| Oil | Local intensity/saturation contrast and supported highlights | Valid anatomical source pixels → percent of supported visible area | An area proxy, not sebum production; saturation/exposure/exclusion gates remain unchanged |
| Redness | Color/texture and same-region appearance measurements; detector-backed presence is separate | Supported pixels / classifier evidence → appearance score or regional finding | Shared redness-derived appearances are explicitly marked; not independent disease measurements |
| Acne indicator | Pinned trained candidate path; installed Latest also opts into the local V5 preview/verifier | Source pixels and anatomical support → candidates/count, method and hash | Candidate count is not clinical severity. Historical Roboflow training experiments are separate |
| Dry / flaking proxy | Native texture/flake support and calibrated dryness path | Source detail, exposure and bare-skin support → proxy or quality-gated unavailable value | Lighting/occlusion can prevent measurement; not hydration or eczema diagnosis |
| Sag | Source contour geometry and compatible longitudinal reference | Same-person normalized contour features → ratio/change when supported | No generic disease severity and no invented reference |
| Lines | Directional line/texture support; saved forehead/crow's-feet finding classifiers are separate | Source-coordinate paths / crop features → index or presence finding | Cosmetic line appearance, not clinical severity |
| Dark / bags indicators | Periorbital supported appearance / contour methods; saved eye-finding models are separate | Under-eye source geometry, color and embeddings → appearance or quality-gated result | Eyewear, pose, lighting and missing evidence matter |
| Post-acne / pigmentation indicators | Source-bound appearance and detector/crop candidates | Supported source region → appearance index / candidate measurement | Distinguish marks and unspecified spots; missing model evidence is not zero |
| Mole / melasma / rosacea findings | Hash-bound `findings.pt` regional evidence in `skin_findings_v1.py` | Valid three-pose regional evidence → seen / notSeen / inconclusive | Frozen decision thresholds 0.58 / 0.54 / 0.69. Detector-box area is explicitly box-covered area, not lesion segmentation |
| Acne / redness findings | Saved `findings-v2/acne.json` and `redness.json`, `skin_findings_det.py` | Three-pose detector/color evidence → regional presence, counts/appearance as supported | Actual frozen classifier thresholds about 0.599273 / 0.535848; count markers are separate from person-level classifier performance |
| Acne marks / cold sore / crow's feet / eye bags | Saved DINOv2 crop classifiers in `skin_findings_dino.py` | Same-photo crops and retained recipes → regional findings | Historical test persons were also used for method selection; not independent camera/clinical acceptance |
| Eczema / flaking / forehead lines | Saved DINOv2 classifiers | Supported pose crops → findings; saved measure/severity heads only where available | Internal nested/repeated validation metadata is not expert clinical ground truth |
| Dark circles | Saved color + geometry logistic classifier in `skin_findings_eye.py` | FRONT under-eye/cheek color with landmark depth → presence | Frozen threshold about 0.856684; historical nested validation P/R 0.89/0.46, not a guarantee on a new photo |
| Hooded eyelids | Saved roll-normalized geometry + lid DINOv2/PCA/LR | FRONT source landmarks/crops → presence | Frozen threshold about 0.638432; historical nested P/R 0.83/0.79 |
| Downturned eye corners | Saved geometry + corner DINOv2/PCA/LR | FRONT source landmarks/crops → presence | Frozen classifier threshold about 0.667752; historical nested P/R 0.82/0.51. Presence probability and displayed geometry rank are different numbers |
| Unspecified spots | No accepted current finding method (`NOT_VALIDATED`) | No supported measurement | Display not measured, never synthesize a negative or positive |
| Missing/quality-gated finding | Bundle/spec/pose/quality checks | Missing valid evidence → unavailable or inconclusive | Region-level empty states now preserve this distinction |

### Eye-corner displayed value

`skin_findings_eye.downturned_percentile` computes the negative of roll-normalized average eye tilt and finds its midrank among `sortedDownturn` positive reference geometries:

`100 × (count(reference < observed) + 0.5 × count(reference = observed)) / reference_count`.

The source docstring explicitly says this is **not validated against severity ratings**. It is a reference rank, not disease probability, affected-area percentage or clinical severity. Cards, overview and saved history now preserve that meaning. Other visibility scores likewise use a 0–100 scale; true area proportions retain `%`.

The preserved runtime contains 12 saved finding specifications plus separate measure/severity artifacts. Therefore the old module-header comment saying only three detector findings were available is stale documentation, not a correct inventory of dynamically loaded current specs. The evidence manifest records actual loaded files and hashes.

## Dental

Current `dental-yolox-s.onnx` SHA-256 is `eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03`, exactly matching `models/dental-yolox-s.json`.

| System | Active calculation | Limits |
|---|---|---|
| Detector | YOLOX-s, 320 px model tensor, objectness × class confidence, threshold 0.35, same-class NMS 0.45; source ROI scale and origin restored before display | Source mouth support rejects out-of-mouth boxes; technical model failures do not become valid zero results |
| Adult product policy | Raw `D`/`d` decode precedes explicit adult-permanent `D` filtering | `D` means decay in permanent teeth, `d` decay in primary teeth. The policy does not relabel primary-class detections. Zero adult candidates is not a healthy diagnosis |
| Build-up appearance | Color plus irregular texture on visible tooth pixels adjacent to the gum border; supported candidate area / evaluated border area | Stain, food, fillings and reflections can confound it. This is not calculus/tartar diagnosis |
| Alignment | Marker-controlled watershed on supported enamel; ellipse orientation normalized modulo 180°; upper/lower row assignment and at least three retained contours per row | Displayed degrees are median absolute orientation dispersion about the circular row axis. Perspective and segmentation influence the result; contours are not expert-assigned FDI identities |
| Quality | Native mouth resolution, enamel visibility, luminance, Laplacian sharpness, glare, tongue support and bite-contact gates | The existing operating points are preserved; passing a gate alone does not establish clinical accuracy |

The manifest's 347-image holdout at threshold 0.35 reports `D`: TP 898, FP 223, FN 160, P/R/F1 80.11/84.88/82.42%; `d`: TP 30, FP 28, FN 33, P/R/F1 51.72/47.62/49.59%. Patient independence was not proven; unannotated images were excluded, so healthy specificity is not established. These historical metrics are applicable provenance for the matching weight, not a new evaluation or correctness guarantee for any displayed user photograph.

## Required case coverage and truth

The new WEB journey uses controlled project media through real capture and inference. Existing automated regressions cover source transforms, positive/negative pixel anatomy, blur/lighting, partial visibility, bite contact, class filtering and contour quality. Tests with constructed arrays or numeric records are engineering contract tests, not clinical truth.

No newly matched expert annotation set has been supplied for clear positive/negative, borderline, lighting, blur, occlusion, skin-tone, eyewear, filling/reflection and head-pose strata of the newly captured journeys. Screenshots cannot supply that truth. Consequently **new precision, recall, F1, FP/FN rates, clinical measurement acceptance and superiority over historical candidates cannot be declared**. A matched, independently annotated protocol is required before model replacement, threshold changes or accuracy claims. No paid training or GPU evaluation was started.

Individual WEB/AAOS functional outcomes, photo-resolution/pixel-scale measurements and history acceptance are recorded in the private delivery acceptance matrix, only after the corresponding runtime checks finish.
