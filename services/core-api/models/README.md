# Local dental detector

The product loads `dental-yolox-s.onnx` only after its SHA-256 matches
`dental-yolox-s.json`. No pretrained model is downloaded at application startup.
The two raw source labels, `D` and `d`, remain separate. A detection confidence
is not a disease probability or severity score. Missing candidates do not prove
healthy teeth; nonvisible surfaces are not evaluated.

The official Megvii YOLOX-s program uses Apache-2.0, with its notice in
`third-party/combined-health`. The checkpoint is created for this repository
from random initialization; it does not contain imported third-party weights.
The repository's existing ownership policy applies to this project-created
artifact. This does not relabel the program or dataset license.

Training photographs and annotations come from Zenodo record
[14827784](https://zenodo.org/records/14827784), CC BY 4.0. Source authors,
archive hashes, license and attribution are retained in the model manifest and
`third-party/combined-health/dental-dataset-attribution.json`. Photographs, temporary
training files and safe NPZ checkpoints remain outside Git. User photographs
are never used as training data.

Validation selects the checkpoint and threshold. The final held-out test is
then evaluated without threshold adjustment. Source case IDs, shared capture
families and exact/perceptual duplicates stay in the same partition. Patient
identity remains unverified, so no patient-independent performance is claimed.

For an explicit local retraining run, `python scripts/download_combined_sources.py`
downloads and hash-checks only the selected public sources. Run CPU training
with `python scripts/train_dental_yolox.py --batch 2 --threads 2` after installing
the CPU PyTorch/torchvision and ONNX versions in
`services/core-api/training-requirements.txt`. This source download
does not run when the product opens. `scripts/dental_model_validation.py` adds diagnostics at the already
frozen threshold, including retained-detection calibration and actual ORT CPU
time/memory samples. It does not tune the model or establish clinical accuracy.
