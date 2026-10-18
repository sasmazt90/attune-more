# Exact local MediaPipe assets

These are the unchanged runtime/model bytes previously loaded from public
CDN/Google URLs. Only delivery is local; model, thresholds and geometry are not
changed. `manifest.json` records each source, byte length and SHA256.

- MediaPipe Tasks Vision 1.0.1 runtime: Google/MediaPipe authors, Apache-2.0.
  Original JS/WASM bytes are retained, including their embedded notices.
  Source: https://github.com/google-ai-edge/mediapipe
- Face Landmarker float16 v1: original official Google model bundle. Its Face
  Detector, Face Mesh V2 and Blendshape model cards and licenses are recorded in
  `third-party/skin-research/sources.json` and `THIRD_PARTY_NOTICES.md`.
- Hand Landmarker float16 v1: original official Google bundle, Apache-2.0.
  Official task documentation:
  https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
  Official hand tracking model card:
  https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf
  The downloaded card hash is recorded in `manifest.json`.

Full Apache license is included in `LICENSE-2.0.txt`. No person identification,
skin/dental diagnosis or clinical accuracy claim follows from these geometry
models. No training photographs or adapted research weights are included.
