# Locally runnable third-party acne detectors: licence, weights, verified behaviour (2026-10-16)

**Scope.**
- No training was done.
- No threshold sweep: one fixed confidence (ultralytics default .25; KerasCV .25; BlemishBot app mode .01 as published).
- No product change. Acne stays `accepted:false, file:null`.
- Weights were downloaded from the public sources listed below and kept outside Git (`audit-results/acne-external/`, cloud scratch). Photos, overlays and weights are not committed.

## 1. What exists

**Hugging Face.** I searched for "acne", "acne detection", "acne yolo" and "pimple" (60+ hits). Most are classifiers (whole-image severity or class) or image generators (LoRA/diffusion). Classifiers cannot mark individual lesions, so they were excluded.

| Repo | Type | Weights | Stated licence | Checkpoint metadata | Training data (from checkpoint) |
|---|---|---|---|---|---|
| Tinny-Robot/acne | YOLOv8 (ultralytics 8.0.85), class `acne` | `acne.pt` 52 MB, sha `2cef23fe…` | Apache-2.0 (model card / config.json) | Initialised from an external `best.pt` (pythonanywhere URL), not COCO | Kaggle `acneda1`, labelled with VIA; card says the focus is dark skin tones |
| drpauloreis/dermapro-acne-yolov8m | YOLOv8m ONNX (ultralytics 8.4.39), class `acne` | 104 MB, sha `db8b4625…` | Apache-2.0 tag | ONNX metadata: `license: AGPL-3.0` | Same `acneda1` dataset as Tinny-Robot |
| HilmiZr/YOLOv8-AcneDetect | YOLOv8m and YOLOv8s, 13 classes | 52 MB and 23 MB | none | ultralytics 8.0.2xx | `data.yaml` (13-class skin dataset) |
| Jasnk/yolo-acne-detector | – | `acne.pt` | Apache-2.0 tag | **Byte-identical to HilmiZr YOLOv8s** (sha `06f06b58…`) | – |
| KhaMinh/yolov11s-acne-detection | YOLO11s, 12 classes (+ ProtoNet files) | 19 MB | none | `AGPL-3.0` | Kaggle `acne-1` |
| carsten12/acne-detection-model | YOLOv8m, class `Acne` | 52 MB | none | `AGPL-3.0` | Roboflow "Acne Trac v5" via Kaggle |
| tristan-gray/acne-detector | YOLOv8n, class `Acne` | 6 MB | WTFPL tag | `AGPL-3.0` | `data-2` (unnamed) |
| aldinnasrun/acne_detect | KerasCV YOLOV8Detector, 1 class | 47 MB | Apache-2.0 tag | KerasCV (Apache-2.0 library; not ultralytics) | not stated |
| Devon12, carsten12/Acne_Model_V1, SyedAliJafri, mrehan071, bakerrac ×2 | – | **no weights** (README/.gitattributes only) | – | – | – |

**GitHub.** Searched via web search. The GitHub search API is not available in this session, so repositories were checked one by one.

| Repo | Weights | Licence | Note |
|---|---|---|---|
| Dewiin/DTM_CTP2024 (BlemishBot) | `models/acne.pt` (7 classes), `no_acne_model.pt` (1 class) | Repo MIT; checkpoints carry `AGPL-3.0` | Roboflow `acne-7` and Kaggle acne data, imgsz 320 |
| UnzelaNoor/acne-detection-treatment-assistant | `best.pt` (YOLOv5su) | none | The `acne` class never fires on our photos; all detections come from the unexplained class `fore` (shown as acne by its own app). README reports P .23 / R .21. |
| KeruZheng/Faster-RCNN-Acne-…ACNE04 | Faster R-CNN (VGG16) `.pth` 114 MB in Git LFS, downloaded (sha `33dd7064…`) | **none** | Trained on ACNE04 (Roboflow copy). **Not run**: the repo's inference code is a modified third-party tutorial without a licence. |
| wenh06/acne_detection (paper: Technology and Health Care 2022) | Weights only on MEGA (not reachable); the `.pb` in the repo is a TF test checkpoint, not acne | MIT | Not runnable here |
| openface-io/acne-lds, razanjiryis/acne-severity-assessment, lqrhy3/skin-disease-recognition, sufiinamulhassan/…, others | none | – | Grading code or no weights |

**Roboflow Universe.** Many acne detection projects exist (e.g. ACNE04 copies). Their trained weights are served through Roboflow's hosted API or paid downloads. They are not freely downloadable local models, so they are out of scope here.

## 2. Licence findings (not legal advice)

- **Ultralytics-trained weights.** Every Ultralytics-trained checkpoint we opened embeds `license: AGPL-3.0` in its metadata, including the ONNX export. Ultralytics states that "All Ultralytics YOLO trained models fall under the AGPL-3.0 License by default", and that commercial use without open-sourcing the whole project needs an Enterprise License ([ultralytics.com/license](https://ultralytics.com/license)).
  - The Apache-2.0 / WTFPL / MIT tags on HF or GitHub are the uploaders' own claims. They do not remove that condition.
  - None of these models can go into a closed product without an Ultralytics Enterprise License or full AGPL compliance.
- **Training data.** No model documents a licence for its training data. Kaggle and Roboflow datasets of unknown origin, and an initialisation from an unknown external `best.pt` (Tinny-Robot), are open questions. No individual consent records are stated anywhere.
- **The KerasCV model** (aldinnasrun) is the only detector whose framework is Apache-2.0. Its data source is unstated.

## 3. Verification on our frozen DEV pack (label-independent, same as V6)

**Test set**
- 28 replay-pass positive DEV photos with 201 source targets, of which 63 are small (< 16 px).
- 14 Clear negative photos.
- Frozen reviewed clean-skin ROIs on 13 positive photos.

**Input modes**
- **full:** the whole photo at the model's training image size.
- **crop:** the product face crop.
- **tiles:** the product native tiles (≤ 384×288 source px) at imgsz 384, merged with NMS .30.

**Scoring**
- Only acne-type classes count as candidates.
- Hits are one-to-one matches at IoU .50 and .30.
- A false candidate is a candidate whose centre lies in a reviewed clean ROI or in a Clear mask.

**Reference:** Step0 in the product chain on the same photos gives hit50 17, hit30 25, small hit50 14/63, unlabeled 280, ROI FP 0, Clear FP 0.

Best mode for each model:

| Model / mode | Hits .50 / .30 | Small .50 / .30 (63) | Medium .50 (138) | Final / unlabeled | Clean-ROI FP | Clear FP | Area ratio | s/photo (CPU) |
|---|---|---|---|---|---|---|---|---|
| **Step0, product chain (reference)** | **17 / 25** | **14** / – | 3 | 305 / 280 | 0 | 0 | 1.14 | ~4.5 (whole chain) |
| Tinny-Robot / crop | **17 / 23** | 4 / 6 | **13** | 181 / 158 | 1 | 2 | 1.16 | 0.68 |
| drpauloreis ONNX / crop | 16 / 24 | 4 / 6 | 12 | 201 / 177 | 1 | 2 | 1.11 | 0.39 |
| Dewiin no-acne gate / tiles | 13 / 36 | 5 / 15 | 8 | 277 / 241 | 0 | 0 | 1.15 | 0.37 |
| tristan-gray / tiles | 12 / 32 | 4 / 9 | 8 | 246 / 214 | 0 | 0 | 0.70 | 0.31 |
| carsten12 / tiles | 12 / 17 | 4 / 4 | 8 | 117 / 100 | 0 | 0 | 0.86 | 2.2 |
| UnzelaNoor (`fore` class) / crop | 8 / 14 | 3 / 5 | 5 | 82 / 68 | 0 | 0 | 1.18 | 0.24 |
| KerasCV aldinnasrun / crop | 8 / 8 | 3 / 3 | 5 | 55 / 47 | 0 | 0 | 0.97 | 0.67 |
| Dewiin 7-class, app pipeline | 7 / 16 | 3 / 6 | 4 | 448 / 432 | 2 | 0 | 1.09 | 0.04 |
| HilmiZr YOLOv8s / tiles (= Jasnk) | 6 / 11 | 4 / 6 | 2 | 127 / 116 | 0 | 0 | 1.87 | 0.81 |
| HilmiZr YOLOv8m / tiles | 6 / 14 | 4 / 10 | 2 | 138 / 124 | 0 | 0 | 1.66 | 1.9 |
| KhaMinh YOLO11s | 1 / 1 | 0 | 1 | 2 / 1 | 0 | 0 | – | 0.8 |

All modes for every model, and the weight hashes, are in `acne-external-scores-20261016.json`.

**Visual check** (overlays viewed on 4 positive photos and one Clear photo; not committed):
- Tinny-Robot, tristan-gray and carsten12 do mark visible red papules and pustules, sometimes ones without a source box.
- Tinny-Robot puts 2 boxes on small marks of a clean-face Clear photo.
- The Dewiin no-acne model in tile mode also fires on background (wall) outside the face.
- The Dewiin 7-class model at conf .01 produces large nested boxes.

## 4. Conclusions

- **Downloadable, runnable lesion detectors that really mark acne do exist.** But none is better than our current Step0 on our product-like photos at small-lesion localisation, which is where most product targets are.
  - The best ones, Tinny-Robot and the drpauloreis ONNX (same `acneda1` data), match Step0's total hit50 (17 vs 17).
  - They catch 4/63 small targets against Step0's 14/63.
  - They catch more medium targets (13/138 against 3/138), with fewer unlabeled candidates (158 against 280).
  - On reviewed clean skin they produce 1 ROI FP and 2 Clear FP, against Step0's 0 and 0.
- **No candidate is licence-clean for a closed product.**
  - The Ultralytics-trained ones are AGPL-3.0 per their own checkpoint metadata.
  - The training-data rights are undocumented for all of them.
  - The KerasCV model is Apache-2.0 at the framework level but is weak (8/201).
- **Not verified here:** the unchanged product chain was not run on these models. Integrating a different architecture is out of scope for this task. The DEV targets are publisher labels (not reviewed), so absolute numbers carry that noise.

Sources:
- https://huggingface.co/Tinny-Robot/acne
- https://huggingface.co/drpauloreis/dermapro-acne-yolov8m
- https://huggingface.co/HilmiZr/YOLOv8-AcneDetect
- https://huggingface.co/Jasnk/yolo-acne-detector
- https://huggingface.co/KhaMinh/yolov11s-acne-detection
- https://huggingface.co/carsten12/acne-detection-model
- https://huggingface.co/tristan-gray/acne-detector
- https://huggingface.co/aldinnasrun/acne_detect
- https://github.com/Dewiin/DTM_CTP2024
- https://github.com/UnzelaNoor/acne-detection-treatment-assistant
- https://github.com/KeruZheng/Faster-RCNN-Acne-Detection-on-ACNE04-and-Cross-Domain-Acne-Classification_2
- https://github.com/wenh06/acne_detection
- https://ultralytics.com/license
