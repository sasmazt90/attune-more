# Skin model selection and measurement contract (QA-31, task 18.9)

**Status: OWNER APPROVED on 2026-11-04 as product configuration. Accuracy not verified.** The dated record with model
identifiers, versions and hashes is `SKIN-OWNER-APPROVAL-20261104.md`. Model selection reopens only for a newly
demonstrated technical defect or concrete evidence of an incorrect result, not because of an older research label.

Nothing here changes a model, threshold or calibration. The audit did find two places where the AWS deployment was not running what the records describe, and
both were corrected. Runtime values come from `skin-contract-runtime.json`, saved per platform with the recordings.

## What the runtime check found

**Two defects, both fixed in this release:**

1. **The V5 acne chain never ran on AWS.** Its verifier is checked by SHA-256, and git stored it with converted line
   endings, so the hash passed on Windows and failed on every Linux host. V5 reported
   `EXPERIMENTAL_ACNE_V5_MODEL_UNAVAILABLE`, and the acne heading stayed unmeasured. All earlier AWS recordings have this
   gap. The file now keeps its exact bytes, with a test. V5 now runs: hashes match, 9 tiles, status `measured`.
2. **Python MediaPipe was missing on the host.** The handoff record requires it for the acne and redness findings.
   Without it they used client landmarks instead of the research recipe, and redness had no measure ("Score not
   calculated"). It is now installed, without replacing OpenCV. Redness now reports area, intensity and score.

Both change Skin numbers compared with earlier AWS runs, because they restore what was configured. **This is a change
the owner should know about:** V5 still carries `accepted:false` in its own manifest.

**Three questions this audit raised, all answered by the owner on 2026-11-04.** The findings stay as written, because
they describe the records. V5 and `regional.pt` were both approved, and so were all other configured Skin models. The
acne heading stays with V5, and the finding pipeline keeps its own detections, counts and subtypes, so the two paths
remain separate by decision and must not be added together.

1. **No record of explicit owner approval exists for most indicators.** The records hold "selected" or "configured".
   Explicit approval was found only for the rebuild of the finding models from the same research recipes, and for the
   downturned-corner threshold 0.668 (`CODEX_HANDOFF.md`, 2026-10-26). This audit does not treat anything else as
   approved.
2. **The acceptance gate and the runtime disagree.** The gate rejected the learned candidates, yet five RF-DETR weights
   run in the product. Most significant is `regional.pt`, named `regional-r1-v2`: the R1 RF-DETR Small record has dry
   F1 0.215, oily F1 0.279, `accepted:false`. Identity is probable, not proven, because the receipt has no immutable
   hash. The gate judged it as a standalone detector, and the runtime uses it as one input to a separate classifier.
   That may be legitimate, but no record says someone decided it.
3. **Acne has two independent paths.** V5 produces the `acne` heading. RF-DETR plus a logistic classifier produces the
   acne finding, its count and subtypes, which is what the result cards show. They can disagree. In the Character 49
   dry run, V5 kept 6 candidates and the finding path counted 11.

Also, the internal record of 2026-11-01 says the RF-DETR research candidate is not the active product classifier. The
code and runtime contradict this: `findings.pt` scores directly decide mole, melasma and rosacea.

## Candidates

| Candidate | Identity | Record | Decision on record | In runtime? |
|---|---|---|---|---|
| V5 acne chain | detector `9c87475d…`, source Step0 `18e94a95…`, verifier `0d7bf03c…`, threshold 0.15628, confidence 0.30, NMS 0.30 | `acne-v5-camera-integration-20261017.md` | `accepted:false`, called a preview | **Yes**, on by default (`experimental_acne_v5.py:17`) |
| R1 RF-DETR Small, regional dry/oily | training `a9e8b8a0…`, `attune-skin-type-regional-r1-2-rfdetr-small-t1`; dry F1 0.215, oily F1 0.279 | `skin-type-combination-release-receipt-20261026-v2.json` | `accepted:false`, "rejectedBoxModel" | Probably, as `regional.pt` (`b23cd0ed…`); identity unproven |
| R2 RF-DETR NAS | **Not found under this name.** Nearest: regional NAS `3485f8c6…`, child `--e79545`, Oily F1 0.513, Redness 0.533 | `original-photo-model-comparison-audit-20261024.md` | Rejected. No Dry or Normal classes | No |
| Acne, marks, pigmentation NAS | training `5b632a5c…`, 89 children. `--a5e262`: Pimple F1 0.094, Post acne 0.052, Pigmentation 0.007. `--929397`: no bound evaluation | same | Rejected | No |
| Acne RF-DETR Small T2 | research-only; 1,414 TP, 4,896 FP, 2,604 FN at 0.2 | `acne-rfdetr-small-t2-diagnosis-20261025.md` | Research-only | No |
| Regional Seg Small T2 | training `af287a00…`; Oily F1 0.571, Redness 0.524 | `regional-rfdetr-seg-small-t2-diagnosis-20261025.md` | Research-only | No. `skinmap.pt` is named `v1-small`, a different version |
| RF-DETR Large, lesion | `lesion-detection-ruc40-qzwqz-1-rfdetr-large-t1`, mAP 0.35 | `roboflow-live-evaluations-20261024.json` | Research-only | Only behind `ATTUNE_EXPERIMENTAL_HOSTED_SKIN_RESEARCH=1`; not mixed into results. Must be confirmed off |
| Earlier EfficientNet type head | `skin-focused.json`, `accepted:false`, macro F1 0.357 | same file | Rejected | No file distributed |
| Earlier YOLOX acne and bags heads | `skin-focused.json`, `accepted:false` | same file | Rejected | No file distributed |

## Indicator matrix

SHA values are prefixes; full values are in `docs/aws/evidence/model-verification-final.json` and Drive
`r2-Skin-model-reconciliation.json`. WEB and AAOS were read from each platform's real responses on the release
candidate. Both platforms use the same model files through separate API processes. No accuracy figure below comes from
real labelled photographs of the target use: all finding figures are from synthetic characters, on a test set also
used to choose the method.

Runtime proof exists for every row marked **ran** below. The "approved" and status columns show what the audit found in
the records before 2026-11-04 and are kept as history. The owner's approval of 2026-11-04 now covers every configured
Skin model listed in `SKIN-OWNER-APPROVAL-20261104.md`, as product configuration. It says nothing about accuracy.

| Indicator | Original approved model/version | Actual WEB model | Actual AAOS model | Artifact SHA | Approved measurement method | Approved threshold/calibration | Actual inference evidence | UI result | Accuracy evidence | Status | Required correction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Acne heading | **Owner approved 2026-11-04.** V5 configured; research manifest keeps `accepted:false` | ran | ran | `9c87475d`, `0d7bf03c` | Unique accepted box pixels / visible anatomical support x100 | Verifier 0.15628, detector 0.30, NMS 0.30 | `acneRuntime`: measured, 9 tiles | Appearance score | None on real labelled photos | NOT VERIFIED | Owner confirms V5 |
| Acne finding, count | Recipe rebuild approved by owner | ran | ran | `findings-v2/acne.json` `21bf8c71`, `findings.pt` `c8d94801`, `acnes.pt` `5db24d92` | Detector feature fusion LR; counted boxes score >= 0.35; each region counted from one photo | About 0.599 | `findings.models` hash match | Count on card | Synthetic: P 0.86, R 1.00, only 6 positives | NOT VERIFIED | Runtime proof; QA-25 |
| Blackheads, whiteheads | No separate approval found | ran | ran | `acnes.pt` `5db24d92`, `findings.pt` `c8d94801` | Detector classes inside the acne count | Score >= 0.35 | Runtime receipt | "Acne types" section | Not validated on real labels | NOT VERIFIED | Runtime proof |
| Acne subtypes | No separate approval found | ran | ran | `acnes.pt` `5db24d92` | Papule, pustule, nodule detector classes; rows sum to total | Score >= 0.35 | Runtime receipt | "Acne types" section | "Subtype split not validated" on record | NOT VERIFIED | Runtime proof |
| Post-acne marks | Recipe rebuild approved by owner | ran | ran | `findings-v2/acneMarks.json` `beb5ad94`, severity `c6a9088c`, DINOv2 `ae1e99fc` | DINOv2 crop LR, FRONT + 20 degrees | Saved in spec | Runtime receipt | Prominence | Synthetic, 22 people: P 0.83, R 0.83 | NOT VERIFIED | Runtime proof |
| Pigmentation, dark spots | Heading stays unavailable by contract | ran | ran | none | No accepted local detector | n/a | `ACCEPTED_PIGMENTATION_LOCAL_DETECTOR_NOT_AVAILABLE` | Not measured | None | NOT EXECUTED | None; must not be derived from tone |
| Melasma | Frozen threshold on record | ran | ran | `findings.pt` `c8d94801` | `Gunes Lekesi` detector score | 0.54 | Runtime receipt | Box area on cheek | Synthetic: P 0.83, R 0.56 | NOT VERIFIED | Runtime proof |
| Unspecified spots | No accepted method | ran | ran | none | None | n/a | `NOT_VALIDATED` | Not measured | Never reached 80% precision | NOT EXECUTED | None |
| Redness heading | `skin-focused` degrees, `accepted:true`, whole-face only | ran | ran | `65936939` | Ridge on EfficientNet features, ordinal x20 | Ordinal normalization | Runtime receipt | Score | Own validation; camera domain not accepted | NOT VERIFIED | Runtime proof |
| Redness finding | Recipe rebuild approved by owner | ran | ran | `findings-v2/redness.json` `2b455387` | Detector LR and light-corrected a* mask | About 0.536 | Runtime receipt | Area and tone difference | Synthetic: P 0.86, R 0.97 | NOT VERIFIED | Runtime proof |
| Wrinkles, fine lines heading | Analytic method on record, no learned approval | ran | ran | `wrinkles.pt` `ba5c5278` masks features only | Directional line and texture | Method constants | Runtime receipt | Index | Not expert-validated | NOT VERIFIED | Runtime proof |
| Crow's feet, forehead lines | Recipe rebuild approved by owner | ran | ran | `crowsFeet.json` `04a54caf`, `foreheadLines.json` `db0705de`, severity files | DINOv2 crop LR | Saved in spec | Runtime receipt | Prominence | Synthetic: P 0.94, R 0.81; P 0.86, R 0.85 | NOT VERIFIED | Runtime proof |
| Pores | **None.** `Genis Gozenek` class exists in `findings.pt`; pores candidate marked exploratory | No product output found | No product output found | none active | None | n/a | Source search only | Not shown | None | NOT EXECUTED | Owner decides whether pores is required |
| Oiliness heading | Analytic method on record | ran | ran | none | Share of supported area above highlight threshold | 0.12 | Runtime receipt | Area percent | Proxy, not sebum | NOT VERIFIED | Runtime proof |
| Dryness heading | `appearance-native-dry-3` selected as normal path | ran | ran | head `7f13c7cb`, encoder `a93e5445` | Dual-scale calibrated material fields | 0.50 / 0.04 | Runtime receipt | Area percent | Limited reviewed negatives; no clean-skin claim | NOT VERIFIED | Runtime proof |
| Flaking finding | Recipe rebuild approved by owner | ran | ran | `flaking.json` `6affd88f`, measures `04bcd877` | DINOv2 LR, flake texture rank | Saved in spec | Runtime receipt | Rank | Synthetic: P 0.92, R 0.78 | NOT VERIFIED | Runtime proof |
| Skin type | ViT `local-vit-dima806-5aace4f-v1`; regional fusion may govern (reconciliation decision) | ran | ran | `99b4c2fa` | ViT dry, normal, oily; regional rule can override | `combination-regional-user-v2…` | Runtime receipt | Type name | Publisher: accuracy 0.65 on 1,529 samples, not our product | NOT VERIFIED | Runtime proof |
| Mixed skin type | Naming rule "product owner" in code | ran | ran | `params.json` `5d1dc44d`, `k_classifier.json` `a7ab0b05` | Oily somewhere plus dry or normal elsewhere gives combination | Needs at least 3 measured regions including forehead or nose | Runtime receipt | Type name | Three-class regional: normal F1 0.49 | NOT VERIFIED | Runtime proof with mixed input |
| Regional T-zone, cheek | **Owner approved 2026-11-04**, `regional.pt` included. See finding 2 | ran | ran | `regional.pt` `b23cd0ed`, `skinmap.pt` `bc4e8aab`, `k_classifier.json` `a7ab0b05` | RF-DETR evidence and DINOv2 LR per region; uncertain stays `unmeasured` | Per-tone thresholds in `params.json` | Runtime receipt | Region map | Synthetic validation: oily F1 0.74, dry 0.71, normal 0.49 | NOT VERIFIED | Owner decision; verify uncertain never shows normal |
| Periorbital | Not validated for regional typing, on record | ran | ran | none for the region | Excluded from regional decision | n/a | Runtime receipt | Separate eye items | "Periorbital not validated" | NOT VERIFIED | Runtime proof |
| Dark circles | Recipe rebuild approved by owner | ran | ran | `darkCircles.json` `03a1e3eb` | Color and geometry LR, FRONT | About 0.857 | Runtime receipt | Prominence | Synthetic: P 0.89, R 0.46 | NOT VERIFIED | Runtime proof |
| Eye bags | Recipe rebuild approved by owner | ran | ran | `eyeBags.json` `90e8d945` | DINOv2 crop LR | Saved in spec | Runtime receipt | Prominence | Synthetic: P 0.89, R 0.44 | NOT VERIFIED | Runtime proof |
| Hooded eyelids | Recipe rebuild approved by owner | ran | ran | `hoodedEyelids.json` `64714164` | Geometry and DINOv2 PCA LR | About 0.638 | Runtime receipt | Prominence | Synthetic: P 0.83, R 0.79 | NOT VERIFIED | Runtime proof |
| Downturned corners | **Threshold approved by owner, 2026-10-26** | ran | ran | `downturnedCorners.json` `dec94ef7` | Geometry and DINOv2 PCA LR; displayed value is a reference rank | 0.668 | Runtime receipt | Rank | Synthetic: P 0.82, R 0.51 | NOT VERIFIED | Runtime proof; threshold value must read 0.668 |
| Mole | Frozen threshold on record | ran | ran | `findings.pt` `c8d94801` | `Riskli Ben` detector score | 0.58 | Runtime receipt | Marked count | Synthetic: P 1.00, R 0.30 | NOT VERIFIED | Runtime proof |
| Rosacea | Frozen threshold on record | ran | ran | `findings.pt` `c8d94801` | `Rozasea` detector score | 0.69 | Runtime receipt | Area, tone difference | Synthetic: P 1.00, R 0.82 | NOT VERIFIED | Runtime proof |
| Eczema, psoriasis tendency | Recipe rebuild approved by owner | ran | ran | `eczema.json` `f4c54d2e` | DINOv2 LR | Saved in spec | Runtime receipt | Area, tone difference | Synthetic: P 0.85, R 0.69 | NOT VERIFIED | Runtime proof |
| Cold sore | Recipe rebuild approved by owner | ran | ran | `coldSore.json` `a271536d` | DINOv2 lip crop LR | Saved in spec | Runtime receipt | Count | Synthetic: P 1.00, R 0.54 | NOT VERIFIED | Runtime proof |
| Tone | Color proxy, separated from pigmentation by contract | ran | ran | none | Color distribution | Method constants | Runtime receipt | Index | Not a pigment diagnosis | NOT VERIFIED | Runtime proof |
| Sag | Geometry; same-person comparison only | ran | ran | none | Contour and fold geometry | Method constants | Runtime receipt | Ratio or change | No generic severity | NOT VERIFIED | Runtime proof |

## How the runtime proof was taken

`scripts/qa/realistic/skin_contract_readback.py` reads the API responses saved during the recorded run on each platform
and writes `skin-contract-runtime.json`:

1. Model hashes reported by the running worker, compared with the files on disk.
2. `acneRuntime`: chain hashes, tile count, detector forward count, timing and the proof that non-acne results stayed
   unchanged.
3. `activeCriterionMethods`: per criterion, method, model version, hash, status and reason.
4. Skin type from the local model and from regional fusion, and the state of each region.
5. Every finding with its status, count and score.

Uncertain regions: the code keeps them as `unmeasured`, and a run with no measured region would show none as normal.
All five regions were measured in these runs, so that branch was not exercised live. Unit tests cover it.

## Lookup trail

Read: `docs/skin/*`, `docs/skin/evidence/*`, `docs/skin-dental-repair-20261102/*`, `CODEX_HANDOFF.md`,
`research/skin-findings/*`, `services/core-api/models/*`, Drive `MODEL_MANIFEST.json`,
`r2-Skin-model-reconciliation.json`, `attune-weights-rfdetr-recovery.json`, `RESEARCH-RESULTS.md`,
`INTERNAL-TEKNIK-KANIT-TR.md`.

Not yet read: Drive `Attune Skin & Dental Diagnostics.html`, `CED-HANDOFF.md`, `Skin_v3_REAL_MODEL_API_EVIDENCE.zip`,
`ag-PR20-07e77df.diff`, `r2-PR20-e4c72dd.diff`, and the wider Roboflow account.

Missing, which would settle the open items:

- A signed-off decision naming the model per indicator. None was found.
- A hash link between the Roboflow R1 record and `regional.pt`.
- Anything named "R2 RF-DETR NAS".

Expected but acceptable mismatch: `skin-type-local.json` reads 947 bytes in the host record and 983 here; the file has
36 lines and this Windows checkout uses CRLF. Compare git blobs, not working-copy bytes.
