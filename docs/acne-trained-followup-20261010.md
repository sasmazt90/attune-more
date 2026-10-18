# Trained acne follow-up — 10 October 2026

**Acne detection remains FAIL / not ready for user testing.** This commit preserves all production modules and records further independent investigation, not a successful detector release. The failed research ONNX is not installed or imported by the application. No private source photos, per-case manifests, labels, weights, or model outputs are committed.

## Rights and practical options

Code, weights and source images were considered separately. The current research uses the already installed CPU PyTorch infrastructure, project-authored detector code, no pretrained weights and the official pinned SCIN data release. SCIN's attribution and no-reidentification conditions are retained for derivative research artifacts; application code is separate. This does not make an undocumented third-party MIT/Apache model's training images permissible.

Additional primary sources examined:

| Source | Code / weights | Data / suitability | Outcome |
|---|---|---|---|
| [Original ACNE04](https://github.com/xpwu95/LDL) / [original-source mirror](https://huggingface.co/datasets/Layered-Labs/ACNE04) | Detection training available | Original release academic/research only; mirror explicitly preserves restriction | Excluded from commercial training |
| [Original AcneSCU](https://github.com/pingguokiller/acnedetection) / [SA-RPN weights](https://github.com/Kumario1/sa-rpn-acne-detection) | Apache code in original repository; additional trained weights available | Original author explicitly prohibits commercial data use without permission; mirror CC BY tags do not override | Not imported |
| [ACNE-DET paper](https://arxiv.org/abs/2301.12219) | DSDH detector described | Paper's public-data link temporarily anonymous; commercial permission/subject metadata not established in examined source | No permitted artifact identified; not a claim all later releases unavailable |
| [Tinny-Robot/acne](https://huggingface.co/Tinny-Robot/acne) | Apache project tag, YOLOv8 weights | Per-image training provenance not identified | No commercial rights chain verified |
| [Glowlytics](https://huggingface.co/mufasabrownie/glowlytics-skin-models/blob/main/README.md) | MIT tag and acne ONNX | Acne image origins/permissions undocumented in card | Not imported |
| [Facefixer](https://replicate.com/dobariyz/facefixer/readme) | MIT claim, YOLOv8n architecture | Custom data mentioned without documented origin/permissions | Not imported; no provider invocation |
| [Skintelligent](https://huggingface.co/imfarzanansari/skintelligent-acne/blob/main/README.md) | MIT tag, ViT classification weights | No localized lesion boxes; training rights not documented | Cannot satisfy source-bound count/rings |
| [Nexdata facial skin defects](https://github.com/Nexdata-AI/26090-Images-Human-Facial-Skin-Defects-Data) | Commercial data offering | No free commercial grant established | No purchase/contact |
| [Cuebot multisource collection](https://huggingface.co/datasets/Cuebot/skin-assessment-images-multisource-provenance-preserved) | Classification package | Card explicitly warns upstream rights are not independently established | Excluded |
| [Kaggle acne/wrinkles](https://www.kaggle.com/datasets/hafsamahbub17/acne-and-wrinkles-dataset) | Dataset candidate | Upstream per-image rights/localized labels could not be verified | Not relied on |
| [FFHQ original](https://github.com/NVlabs/ffhq-dataset) | Dataset metadata/download implementation BY-NC-SA | Individual photos mixed BY/BY-NC/CC0; no acne boxes, subjects unpartitioned | No blanket commercial use of package; separately permitted original photos remain a possible future source |
| [Official SCIN](https://github.com/google-research-datasets/scin), [license](https://github.com/google-research-datasets/scin/blob/main/LICENSE) | Local from-scratch experiment, no external acne weights | Consented donated photos; gradable case differentials, not local lesion truth; source/license pinned | Data preparation + actual trained experiment completed; product gate failed |

These are specific examined options, not a claim that every possible free dataset/model has been exhausted. No paid GPU, license, API call, image upload or unsolicited message was made.

## Data preparation, split and fixed acceptance

The existing entire SCIN download was preserved. All 207 photos in 96 acne-named contributions were visually reviewed as contact sheets, rather than treating the previous seven full-face geometry candidates as the entire usable inventory. Torso, macro-only/nonfacial images were excluded from this localization experiment. Twenty-five visible facial/cheek/chin crops at native 224–508 pixel widths were manually prepared; their exact source-pixel equality and original PNG SHA are checked. No color changes or synthetic detail. Native RGB, not a 320-pixel whole-face copy, reaches the learned detector.

Direct visual engineering boxes: 12 training photos / 47 marks, 6 validation photos / 18 marks, 7 protected-test photos / 24 marks. These are provisional appearance boxes, not dermatologist local diagnoses. Ambiguous scarring, occlusion/redaction and selected non-skin areas are ignored. Provisional negative crops include pores/diffuse redness and beard context; all six requested confounder types are not comprehensively represented.

Each contribution and known photo derivative stays in one split; SHA/perceptual image duplicate checks found no cross-split duplicate among selected sources. **SCIN does not provide a donor identity linking distinct contributions: subject independence is unverified.** No identity recognition/re-identification was attempted to fill that gap. This alone prevents claiming person-disjoint acceptance.

`native-acne-acceptance.json` was frozen before training/test predictions. Its SHA is `90dc84fa2f2a9d8191cd67f5d27b54d3f03a5f83489e7f7f1b0c641bc8f4b0da`. It preserves the previous 50 positive / 50 negative independent-photo floor and precision/recall/F1 >= .80; requires >=100 local marks and negative FP <=1/photo, confounder coverage, subject/domain/local-label review. The sample is deliberately insufficient to establish these product claims; it can show failure without weakening the gate. Matching is one-to-one IoU >= .30; unignored unmatched outputs count as FP. Loose .30 accommodates engineering boundary uncertainty; it does not excuse wrong locations. Larger counts without precision do not pass.

## Actual training and protected result

A 20,987-parameter center/box-size CNN was trained from scratch on the local CPU. Native 256-pixel overlapping tiles have 64-pixel overlap, averaged probabilities/size output and global NMS. The model outputs center confidence and box size; confidence is never severity. Native crop origins preserve source-pixel mapping. The detector does not use the old blackhat hair filter or a red-blob proposal gate, so it also exposes the need for learned beard/skin negative discrimination.

Two bounded validation configurations were examined. The first revealed an untrained log-size/threshold-startup problem with zero validation localization; the second initialized size from the training-only median and searched low scores using validation only. The second configuration was monitored with fixed validation-loss patience 6 and maximum 30 epochs / 1,200 seconds; stopped at epoch 23. Test predictions were not opened during selection. Its checkpoint/evaluation threshold came from validation; epoch 1 remained the best F1 despite the 23-epoch run. This experiment did not learn reliable localization. The first artifact is retained locally. No retraining or threshold changes followed the protected test.

| Same seven protected native facial crops | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy core, crop normalized to <=320px | 0 | 1 | 24 | 0 | 0 | 0 |
| Rejected core, crop normalized to <=640px | 0 | 25 | 24 | 0 | 0 | 0 |
| Trained native CNN | 3 | 482 | 21 | 0.00619 | 0.125 | 0.01179 |

There are five positive and two provisional negative test crops. On positives alone: TP 3 / FP 265 / FN 21, precision 0.01119, recall 0.125, F1 0.02055. On negatives: 217 false candidates over two crops. These partitions are recorded separately, not pooled into an accuracy claim. CNN false candidates on negative crops average 108.5/photo. All predictions after the detector's declared 300-peak/photo cap are evaluated; reported FP is not an exhaustive uncapped false-output measure. Visualization shows spurious pores, hair and background edges and missed visible marks. Green matched truth / red misses / magenta predicted boxes are retained locally. Small engineered crops do not establish clinical accuracy or absence of acne.

This is a detector-core ROI comparison, not normal capture/anatomical acceptance. The old cores use measured crop width for their controlled resize, not an invented full-face measurement. The new learned model failed decisively and was not integrated. Its dynamic ONNX is 85,967 bytes, hash `f19cc25cd1a8515cb78b18059a8e15140c8ed6caaca4f0f27588dac77dc27ac3`. Actual CPU loading and variable-shape Torch/ONNX parity were verified; technical playback/loading is not detection acceptance. Technical errors/non-finite model output raise instead of becoming valid zero. Source pixels and sealed detections remain unchanged after runtime guards.

## Successful isolated backend wipe

`current_skin_photo_wipe_success.py` starts the actual ASGI application with a fresh temporary `ATTUNE_DATA_DIR` on port 8001, local env loading disabled and no provider key. It creates two test session summaries through the real save endpoint (no LLM), performs one actual licensed three-pose scan with real production MediaPipe/quality gates in a separate browser profile, and retains its three photos/maps under explicit photo consent (initial default OFF).

Only that test browser's backend requests are forwarded to the real isolated service. Wipe returns actual backend success, GET verifies no sessions, actual sessions/deletion files are empty, IndexedDB/numeric browser records are empty, and whole-browser relaunch remains empty. The normal backend is only read and its before/after content hash is equal. No fake 200/503 or deletion of user's actual records.

## Delivery and remaining external inputs

The acne gate is still CLOSED. No failed artifact is in the product backend or normal model directory. All application/voice/measurement source paths match the preserved delivery; no result design/model/effect added. Focused regressions, typecheck, fresh production build, exact current-build controlled scan/history/wipe/responsive evidence and normal shortcut verification are recorded locally. Seven known development high findings remain open/disclosed in `docs/live-test-followup.md`; no new security audit/closure claim is made.

Next viable training input must supply a commercially permitted facial localization corpus with verifiable source/weight permissions, anonymous stable subject grouping (without re-identification), adequate visible native camera detail, explicit local appearance labels including negatives/confounders and independent splits. Alternatively, original authors' written commercial grants plus subject metadata for ACNE04/AcneSCU could enable the established detection infrastructure. These permission/data inputs are not present. More unlinked engineering marks or new threshold loops cannot establish the missing subject/domain evidence. This bounded CNN is not proof that stronger architectures cannot work. Users are not asked to repeat a physical test against it.

Private evidence: `audit-results/acne-trained-20261010/` contains source/crop/license/annotation hashes, frozen acceptance, selection log, both candidate artifacts, comparison JSON, TP/FP/FN screens, real ONNX runtime manifest and isolated-wipe proof. Final exact commit/build/chunk hashes appear in its delivery report. PR #2 remains Draft; no main merge.
