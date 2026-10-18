# Current runtime source index (2026-10-18)

The dated entries below retain their historical scope. For the actual installed
model files, separate code/weight/data declarations and outstanding documents,
see [the 2026-10-18 source matrix](docs/model-sources-20261018.md) and its hash
index. Earlier statements about the MVP shipping no research-trained weights
are not a current inventory. This index does not relicense our application,
change runtime flags, or declare all model/data rights resolved. Original
license texts and attribution files referenced by the matrix remain retained.

# Skin research third-party notices (2026-10-08)

The product remains UNLICENSED. These notices do not relicense our application.
No SCIN photograph, metadata row or research-trained skin weight is bundled in
the product or committed. Research artifacts live in ignored audit-results.
The pinned MIT skin-scan oiliness/blemish functions are retained with their
license in services/core-api/skin_scan_baseline and called by appearance_analysis.

- Google/Stanford Skin Condition Image Network (SCIN): revision
  b5a498233ef23b24c2f9fdb41b53e162c6eeb98d, custom SCIN Data Use License.
  Source https://github.com/google-research-datasets/scin/tree/b5a498233ef23b24c2f9fdb41b53e162c6eeb98d
  Full license: third-party/skin-research/scin-LICENSE.txt. Royalty-free reproduction
  and adaptation subject to attribution, license retention, modification notices,
  no downstream restrictions and strictly no subject re-identification/re-linking.
  No Google/Stanford endorsement. Research metadata/crops are adaptations.
  For these local research weights we preserve this Data Use License as a conservative
  distribution policy; they remain private, and no product weights are distributed.
  Rights in images/data, our training code, and derived weights are recorded separately.
- DurtyDhiana/skin-scan: revision afc55f5cb87fcc644f36b472c37083b254bd3fe4,
  MIT, Copyright (c) 2025, full notice third-party/skin-research/skin-scan-LICENSE.txt.
  Source https://github.com/DurtyDhiana/skin-scan/tree/afc55f5cb87fcc644f36b472c37083b254bd3fe4
  Pinned oiliness.py and blemishes.py are used as supporting appearance filters
  in the local production API. They are not calibrated ground truth; hydration
  is not used. Our additional contrast, anatomical and quality gates are separate.
- OpenCV 4.12.0 core Apache-2.0; opencv-python 4.12.0.88 wrapper MIT;
  Haar frontal-face data BSD/Intel notice. Installed wheel third-party notices
  (including FFmpeg LGPL components) are retained separately. OpenCV is used in
  the local appearance/dental API as well as research. Commercial use requires the
  retained notices and applicable license obligations, not a blanket waiver.
- NumPy 2.2.6 BSD-3-Clause and its retained bundled notices; PyTorch 2.9.1 BSD-style
  and retained third-party notices; Pillow 12.0.0 HPND. Exact installed license texts
  and SHA256s are under third-party/skin-research and sources.json.
- scikit-image 0.26.0 (BSD with mixed permissive notices) and SciPy are used by
  the local appearance/dental API (LBP, Gabor, watershed and numeric filters).
  Their retained notices and exact versions are recorded in the runtime manifests.

Exact code revisions, license hashes, official source links and the Haar model hash
are in third-party/skin-research/sources.json. The focused model registry separately
records any accepted pretrained skin model; rejected research models are not shipped.
The existing licensed three-angle video is controlled engineering evidence only;
its unchanged attribution is retained in the existing fixture notices.

- Existing MediaPipe Tasks Vision 1.0.1 is used for production/research geometry.
  Official Face Landmarker documentation links FaceDetector, FaceMesh-V2 and
  Blendshape model cards, each stating Apache-2.0; exact SDK/task hashes and card
  URLs/hashes are recorded separately in sources.json. Full Apache license is
  retained. This does not make landmark geometry a clinical label or certify
  whole-face acne. Accepted additional skin weights, if any, are listed separately
  in services/core-api/models/skin-focused.json.

Additional private research (2026-10-10):
- Torchvision Faster R-CNN/ResNet50-FPN code: BSD-3-Clause. The classification
  starting weights timm/resnet50.a1_in1k, revision
  767268603ca0cb0bfe326fa87277f19c419566ef, have the distributor's explicit
  Apache-2.0 model-card release. These are backbone weights, not acne weights.
- Detectron2 Faster R-CNN R50-FPN 3x, official model zoo revision
  1e3e13bbf607b54f62205c4c33922521822fb298: code Apache-2.0; downloadable
  weights separately CC BY-SA 3.0, as stated in MODEL_ZOO.md.
  https://github.com/facebookresearch/detectron2/blob/1e3e13bbf607b54f62205c4c33922521822fb298/MODEL_ZOO.md
  Original weights SHA256 3c25caca37baabbff3e22cc9eb0923db165a0c18b867871a3bf3570bac9b7ef0.
  Local conversion/fine-tuning is an adaptation; attribution and share-alike
  obligations apply to any distribution of those adapted weights. No such
  research weights are shipped or represented as accepted acne detection.
- ACNE-DET repository code is Apache-2.0. That code license does not establish
  commercial rights to the linked Baidu image/annotation archive. Current share
  accessibility was checked separately; no account, purchase or bypass was used.

Local runtime delivery (2026-10-10):
- The existing MediaPipe Tasks Vision 1.0.1 WASM and original Face/Hand Landmarker
  float16 v1 bundles are now served locally, byte-identical to the previous
  package/official downloads. Source/hash/license manifest and Apache notice:
  apps/vehicle-app/public/mediapipe/manifest.json, NOTICE.md and LICENSE-2.0.txt.
  This removes runtime CDN/model download dependency; it does not change model
  weights, inference thresholds or the meaning of any health measurement.
- Fixed vision speech files are generated from the existing PROMPTS with
  tr-TR-AhmetNeural, -10%, -10Hz using the same free edge-tts integration.
  apps/vehicle-app/public/audio/vision-speech/manifest.json records exact text,
  profile and actual audio hashes. No user speech or personal text is included.
  Technical decoding/playback is not auditory pronunciation acceptance.

Focused skin research and acceptance gate (2026-10-10):
- Killa92 facial-skin-analysis-and-type-classification: publisher-declared
  Apache-2.0; archive SHA256
  8f2bebd6b97bdd3acd06a42798babbd377b7937db362a734586ff5fb3d0ea4a1.
  https://www.kaggle.com/datasets/killa92/facial-skin-analysis-and-type-classification
  Source labels are not a verified expert clinical protocol. Our changes are
  quality exclusions, source-family grouping, fresh splits and native camera crops.
- Skin Condition Detection merged v2, original Roboflow publisher: CC BY 4.0;
  archive SHA256 03afd248006874f714a1b39210801be70918cf96e669084c5776a6590ca73f03.
  https://universe.roboflow.com/skin-condition-detection/skin-condition-detection_merged/dataset/2
  Attribution and adaptation notices apply separately from model/code licenses.
  No source images or personally identifiable research samples are distributed.
- ResNet18 starting tensors: torchvision f37072fd; corresponding timm
  resnet18.tv_in1k model card BSD-3-Clause. EfficientNet-B0 starting tensors:
  torchvision rwightman 7f5810bc; corresponding efficientnet_b0.ra_in1k card
  Apache-2.0. Hashes and original/safe-tensor conversion are recorded in the
  focused protocol and installed model registry. These are ImageNet starting
  tensors, not pretrained skin-type or severity models.
- YOLOX-S: official same-project 0.1.1rc0 release; pinned code revision
  6ddff4824372906469a7fae2dc3206c7aa4bbaee, Apache-2.0. Original weight SHA256
  f55ded7181e1b0c13285c56e7790b8f0e8f8db590fe4edb37f0b7f345c913a30.
  https://github.com/Megvii-BaseDetection/YOLOX/releases/tag/0.1.1rc0
  Same-project release terms and upstream COCO data terms are recorded separately;
  a separate explicit weight license is not invented.
- Segmentation Models PyTorch UNet implementation is MIT; its ResNet18 encoder
  uses the separately recorded ImageNet tensors. Rectangular polygons and boxes
  are excluded from exact eye-bag mask supervision.
- Optional whole-object Acnes_model.pth was inspected statically with ZIP and
  pickletools only. Unresolved original training/weight provenance means it is
  neither executed nor installed. This does not block independent YOLOX training.
- Research dependencies stay in the private research runtime; production does
  not add Torch, SMP, unsafe pickle loading, external downloads or a cloud service.
  Only hash-pinned models that pass the recorded frozen acceptance gates can be
  installed. Confidence, ordinal grade, boxes and pixel masks remain distinct.

2026-10-18 provenance addendum: `docs/model-source-gap-recovery-20261018.md`
and its JSON recover the V4/V5 and 64-row material-head membership links to the
original publisher-declared archive licenses. This does not establish individual
photo rights or replace the separate upstream tensor and code declarations.
