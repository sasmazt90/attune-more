# Measurement validation coverage and remaining evidence

The current implementation was traced to its actual models, transforms, thresholds and stored evaluation metadata. No new clinical precision, recall, F1, false-positive or false-negative rate is calculated from UI screenshots. A correct source ID, a plausible overlay, or a successful camera scan is engineering evidence rather than expert truth.

| Requested case | Evidence available in this task | Acceptance boundary |
|---|---|---|
| Skin clear positive / clear negative / borderline | Saved historical finding specifications, their own internal evaluation metadata, and deterministic seen/notSeen/inconclusive UI fixtures | No matched independent expert labels for the new controlled camera journey; clinical accuracy NOT VALIDATED |
| Skin poor lighting / blur / partial occlusion | Existing quality gates and regression coverage; real camera quality admissions recorded | No new expert-labelled stratified challenge set; no per-stratum accuracy claim |
| Different skin tones | Historical model provenance and regional sensitivity rule examined | No new balanced, subject-independent tone-stratified clinical validation |
| Skin head poses | Real controlled FRONT/RIGHT/LEFT capture attempts; source/session/pose guards and crop tests | Pose acquisition and identity are functional checks, not clinical truth |
| Eyewear | Existing source-bound eyewear admission policy retained | No new eyewear-labelled clinical study |
| No measurable finding | Missing/unavailable/inconclusive/negative states exercised in regressions and actual details dialogs where produced | Unmeasured is not converted into a negative finding |
| Dental positive / negative caries | Frozen accepted ONNX hash matches its manifest; historical 347-image evaluation retained | Historical aggregate results are not truth for a new mouth image |
| Dental partial visibility / side angle / bite | Real controlled four-view camera and actual intraoral upload pipeline | Supported-visible-surface functional coverage only |
| Fillings / reflections / blur / tooth and skin tones | Source methods and existing rejection gates examined | No new matched expert annotations covering these strata; clinical accuracy NOT VALIDATED |
| Alignment contours | Actual source-coordinate contours, counts and orientation spread retained, with native source pixels | Perspective-dependent appearance proxy; no orthodontic ground-truth validation |
| Accumulation | Source masks, visible tooth/gum-border denominator and color/texture method traced | Appearance proportion, not calculus diagnosis; no new plaque/calculus annotations |

The supplied manual observation has no corresponding admitted raw source photos, meshes and expert annotations in this task. Its individual finding/negative outputs therefore cannot be declared correct or incorrect from its numbers alone. The audit does resolve the meaning of those numbers and the UI's missing/unmeasured ambiguity.

The historical 347-image Dental evaluation reports D-class precision/recall/F1 approximately 80.11/84.88/82.42%, and d-class approximately 51.72/47.62/49.59%, at confidence 0.35. D denotes decayed permanent teeth and d decayed primary teeth. Adult postprocessing filters primary candidates without relabelling them. Patient independence is not established by the artifact and unannotated negatives were excluded. These limitations prevent a new population-level acceptance claim.

Older candidate experiments cannot be ranked against the active model using different datasets, splits, annotation policies or operating points. A meaningful model comparison needs the same independent labelled cases and protocol. No model was replaced or trained, no threshold was lowered to create extra findings, and no paid training run was started.
