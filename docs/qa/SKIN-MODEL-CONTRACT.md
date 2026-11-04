# Skin model selection and measurement contract (QA-31, task 18.9)

**Status: in progress.** This version is a source and record audit. It does not prove runtime execution. Nothing here
changes a model, threshold or calibration. Runtime columns are filled from the release-candidate Skin runs on WEB and
AAOS, and each status then becomes final.

## The three findings the owner needs to see

1. **No record of explicit owner approval exists for most indicators.** What the records hold is "selected" or
   "configured". Explicit owner approval was found only for the rebuild of the finding models from the same research
   recipes, and for the downturned-corner threshold 0.668 (`CODEX_HANDOFF.md`, 2026-10-26). This audit does not treat
   anything else as approved.
2. **The acceptance gate and the runtime disagree.** The gate rejected the learned candidates, yet five RF-DETR weights
   run in the product. Most significant is `regional.pt`, named `regional-r1-v2`: the R1 RF-DETR Small record has dry
   F1 0.215, oily F1 0.279, `accepted:false`. Identity is probable, not proven: the receipt has no immutable hash. The
   gate judged it as a standalone detector, and the runtime uses it as one input to a separate classifier. That may be
   legitimate, but no record says someone decided it. **Owner decision needed.**
3. **Acne has two independent paths.** The V5 chain produces the `acne` heading (`accepted:false`, enabled by default
   in code). RF-DETR plus a logistic classifier produces the acne finding, its count and subtypes. They can disagree,
   and "the acne model" is ambiguous until the runtime shows which one each screen displays.

Also, the internal record of 2026-11-01 says the RF-DETR research candidate is not the active product classifier. The
code contradicts this: `findings.pt` scores directly decide mole, melasma and rosacea (`skin_findings_v1.py:31-35`).

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
`r2-Skin-model-reconciliation.json`. **WEB and AAOS columns read "pending" until the release-candidate runs.** No
accuracy figure below comes from real labelled photographs of the target use: all finding figures are from synthetic
characters, on a test set also used to choose the method.

| Indicator | Original approved model/version | Actual WEB model | Actual AAOS model | Artifact SHA | Approved measurement method | Approved threshold/calibration | Actual inference evidence | UI result | Accuracy evidence | Status | Required correction |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Acne heading | No approval found. V5 configured, `accepted:false` | Pending | Pending | `9c87475d`, `0d7bf03c` | Unique accepted box pixels / visible anatomical support x100 | Verifier 0.15628, detector 0.30, NMS 0.30 | Pending `acneRuntime` | Appearance score | None on real labelled photos | NOT VERIFIED | Owner confirms V5 |
| Acne finding, count | Recipe rebuild approved by owner | Pending | Pending | `findings-v2/acne.json` `21bf8c71`, `findings.pt` `c8d94801`, `acnes.pt` `5db24d92` | Detector feature fusion LR; counted boxes score >= 0.35; each region counted from one photo | About 0.599 | Pending `findings.models` | Count on card | Synthetic: P 0.86, R 1.00, only 6 positives | NOT VERIFIED | Runtime proof; QA-25 |
| Blackheads, whiteheads | No separate approval found | Pending | Pending | `acnes.pt` `5db24d92`, `findings.pt` `c8d94801` | Detector classes inside the acne count | Score >= 0.35 | Pending | "Acne types" section | Not validated on real labels | NOT VERIFIED | Runtime proof |
| Acne subtypes | No separate approval found | Pending | Pending | `acnes.pt` `5db24d92` | Papule, pustule, nodule detector classes; rows sum to total | Score >= 0.35 | Pending | "Acne types" section | "Subtype split not validated" on record | NOT VERIFIED | Runtime proof |
| Post-acne marks | Recipe rebuild approved by owner | Pending | Pending | `findings-v2/acneMarks.json` `beb5ad94`, severity `c6a9088c`, DINOv2 `ae1e99fc` | DINOv2 crop LR, FRONT + 20 degrees | Saved in spec | Pending | Prominence | Synthetic, 22 people: P 0.83, R 0.83 | NOT VERIFIED | Runtime proof |
| Pigmentation, dark spots | Heading stays unavailable by contract | Pending | Pending | none | No accepted local detector | n/a | Pending; expected `ACCEPTED_PIGMENTATION_LOCAL_DETECTOR_NOT_AVAILABLE` | Not measured | None | NOT EXECUTED | None; must not be derived from tone |
| Melasma | Frozen threshold on record | Pending | Pending | `findings.pt` `c8d94801` | `Gunes Lekesi` detector score | 0.54 | Pending | Box area on cheek | Synthetic: P 0.83, R 0.56 | NOT VERIFIED | Runtime proof |
| Unspecified spots | No accepted method | Pending | Pending | none | None | n/a | Expected `NOT_VALIDATED` | Not measured | Never reached 80% precision | NOT EXECUTED | None |
| Redness heading | `skin-focused` degrees, `accepted:true`, whole-face only | Pending | Pending | `65936939` | Ridge on EfficientNet features, ordinal x20 | Ordinal normalization | Pending | Score | Own validation; camera domain not accepted | NOT VERIFIED | Runtime proof |
| Redness finding | Recipe rebuild approved by owner | Pending | Pending | `findings-v2/redness.json` `2b455387` | Detector LR and light-corrected a* mask | About 0.536 | Pending | Area and tone difference | Synthetic: P 0.86, R 0.97 | NOT VERIFIED | Runtime proof |
| Wrinkles, fine lines heading | Analytic method on record, no learned approval | Pending | Pending | `wrinkles.pt` `ba5c5278` masks features only | Directional line and texture | Method constants | Pending | Index | Not expert-validated | NOT VERIFIED | Runtime proof |
| Crow's feet, forehead lines | Recipe rebuild approved by owner | Pending | Pending | `crowsFeet.json` `04a54caf`, `foreheadLines.json` `db0705de`, severity files | DINOv2 crop LR | Saved in spec | Pending | Prominence | Synthetic: P 0.94, R 0.81; P 0.86, R 0.85 | NOT VERIFIED | Runtime proof |
| Pores | **None.** `Genis Gozenek` class exists in `findings.pt`; pores candidate marked exploratory | No product output found | No product output found | none active | None | n/a | Source search only | Not shown | None | NOT EXECUTED | Owner decides whether pores is required |
| Oiliness heading | Analytic method on record | Pending | Pending | none | Share of supported area above highlight threshold | 0.12 | Pending | Area percent | Proxy, not sebum | NOT VERIFIED | Runtime proof |
| Dryness heading | `appearance-native-dry-3` selected as normal path | Pending | Pending | head `7f13c7cb`, encoder `a93e5445` | Dual-scale calibrated material fields | 0.50 / 0.04 | Pending | Area percent | Limited reviewed negatives; no clean-skin claim | NOT VERIFIED | Runtime proof |
| Flaking finding | Recipe rebuild approved by owner | Pending | Pending | `flaking.json` `6affd88f`, measures `04bcd877` | DINOv2 LR, flake texture rank | Saved in spec | Pending | Rank | Synthetic: P 0.92, R 0.78 | NOT VERIFIED | Runtime proof |
| Skin type | ViT `local-vit-dima806-5aace4f-v1`; regional fusion may govern (reconciliation decision) | Pending | Pending | `99b4c2fa` | ViT dry, normal, oily; regional rule can override | `combination-regional-user-v2…` | Pending | Type name | Publisher: accuracy 0.65 on 1,529 samples, not our product | NOT VERIFIED | Runtime proof |
| Mixed skin type | Naming rule "product owner" in code | Pending | Pending | `params.json` `5d1dc44d`, `k_classifier.json` `a7ab0b05` | Oily somewhere plus dry or normal elsewhere gives combination | Needs at least 3 measured regions including forehead or nose | Pending | Type name | Three-class regional: normal F1 0.49 | NOT VERIFIED | Runtime proof with mixed input |
| Regional T-zone, cheek | Regional v3 configured. See finding 2 | Pending | Pending | `regional.pt` `b23cd0ed`, `skinmap.pt` `bc4e8aab`, `k_classifier.json` `a7ab0b05` | RF-DETR evidence and DINOv2 LR per region; uncertain stays `unmeasured` | Per-tone thresholds in `params.json` | Pending | Region map | Synthetic validation: oily F1 0.74, dry 0.71, normal 0.49 | NOT VERIFIED | Owner decision; verify uncertain never shows normal |
| Periorbital | Not validated for regional typing, on record | Pending | Pending | none for the region | Excluded from regional decision | n/a | Pending | Separate eye items | "Periorbital not validated" | NOT VERIFIED | Runtime proof |
| Dark circles | Recipe rebuild approved by owner | Pending | Pending | `darkCircles.json` `03a1e3eb` | Color and geometry LR, FRONT | About 0.857 | Pending | Prominence | Synthetic: P 0.89, R 0.46 | NOT VERIFIED | Runtime proof |
| Eye bags | Recipe rebuild approved by owner | Pending | Pending | `eyeBags.json` `90e8d945` | DINOv2 crop LR | Saved in spec | Pending | Prominence | Synthetic: P 0.89, R 0.44 | NOT VERIFIED | Runtime proof |
| Hooded eyelids | Recipe rebuild approved by owner | Pending | Pending | `hoodedEyelids.json` `64714164` | Geometry and DINOv2 PCA LR | About 0.638 | Pending | Prominence | Synthetic: P 0.83, R 0.79 | NOT VERIFIED | Runtime proof |
| Downturned corners | **Threshold approved by owner, 2026-10-26** | Pending | Pending | `downturnedCorners.json` `dec94ef7` | Geometry and DINOv2 PCA LR; displayed value is a reference rank | 0.668 | Pending | Rank | Synthetic: P 0.82, R 0.51 | NOT VERIFIED | Runtime proof; threshold value must read 0.668 |
| Mole | Frozen threshold on record | Pending | Pending | `findings.pt` `c8d94801` | `Riskli Ben` detector score | 0.58 | Pending | Marked count | Synthetic: P 1.00, R 0.30 | NOT VERIFIED | Runtime proof |
| Rosacea | Frozen threshold on record | Pending | Pending | `findings.pt` `c8d94801` | `Rozasea` detector score | 0.69 | Pending | Area, tone difference | Synthetic: P 1.00, R 0.82 | NOT VERIFIED | Runtime proof |
| Eczema, psoriasis tendency | Recipe rebuild approved by owner | Pending | Pending | `eczema.json` `f4c54d2e` | DINOv2 LR | Saved in spec | Pending | Area, tone difference | Synthetic: P 0.85, R 0.69 | NOT VERIFIED | Runtime proof |
| Cold sore | Recipe rebuild approved by owner | Pending | Pending | `coldSore.json` `a271536d` | DINOv2 lip crop LR | Saved in spec | Pending | Count | Synthetic: P 1.00, R 0.54 | NOT VERIFIED | Runtime proof |
| Tone | Color proxy, separated from pigmentation by contract | Pending | Pending | none | Color distribution | Method constants | Pending | Index | Not a pigment diagnosis | NOT VERIFIED | Runtime proof |
| Sag | Geometry; same-person comparison only | Pending | Pending | none | Contour and fold geometry | Method constants | Pending | Ratio or change | No generic severity | NOT VERIFIED | Runtime proof |

## Runtime proof to collect on the release candidate

For each platform, from the real Skin response and the host:

1. `all-models-verified.json` hashes against the files the API process actually reads.
2. `findings.models` in the fused result, plus the regional manifest from `model_manifest()`.
3. `acneRuntime`: `onnxSHA256`, verifier hash, `tileCount`, `detectorForwardCount`, timing, `nonAcnePreservation`.
4. `activeCriterionMethods`: per criterion and region, method, model version, hash, status and reason.
5. `general.modelInference`, including skin type provider and hash.
6. The environment of both API processes, by variable name and state only: V5 on, hosted research off.
7. No uncertain region shown as normal.

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
