# Test-fixture provenance

The generated `audit-fixtures/three-angle.y4m` and all derived screenshots are
CC BY-SA 4.0, attributed to NMu11er, **Head Shake** (3 March 2022):
https://commons.wikimedia.org/wiki/File:Head_Shake.webm
https://creativecommons.org/licenses/by-sa/4.0/

Changes: uniformly crop the source to 900x675 at x90/y190, scale to 640x480,
select three genuinely different source frames, and hold each frame for 15 seconds.
No rotation, texture enhancement, landmark replacement or pose mocking is used.
The source SHA-1 is pinned to `fb35a2ecbf0771ab818c2ca336142c30b515a414`.

`prepare_multi_angle_fixture.py` runs the production SkinAnalyzer and actual
MediaPipe on every sampled frame. `multi-angle-fixture-provenance.json` records
all pose/quality results; it must admit FRONT, anatomical RIGHT and LEFT without
lowering the existing quality thresholds. This proves software behavior with a
licensed controlled fixture. It does not prove clinical validity or vehicle hardware.
Generated media stays ignored and is never an application asset. CI evidence
containing these derived frames carries this attribution and license notice.
No private user face frame is saved by this workflow.


## Native-resolution controlled portraits

Two front-only NASA sources are acquired during diagnostics, checked against
pinned SHA-256 hashes, cropped at original pixel resolution, and converted to
uncompressed YUV420 video. JPEG decoding and video chroma subsampling are
explicit; no resizing, face generation, beauty filter or sharpening is used.
These fixtures are not user photographs, clinical evidence, three-pose captures
or visual acceptance. The deliberately poor Head Shake fixture stays rejected.

- NASA Eileen Collins, early portrait, 2250 x 2848; native crop 1280 x 960.
  https://commons.wikimedia.org/wiki/File:Eileen_Collins,_early_NASA_portrait.jpg
- NASA / Robert Markowitz, Robert L. Behnken (2018), 4500 x 6000; native crop
  1920 x 2160. This digital source has stronger visible facial detail.
  https://commons.wikimedia.org/wiki/File:Robert_L._Behnken_in_2018.jpg
- NASA-created US-government photos are identified as public domain in the US;
  NASA's media guidelines apply. No NASA endorsement is implied and the sources
  are used only for testing, never as a user's result or product stock portrait.
  https://www.nasa.gov/nasa-brand-center/images-and-media/

The pinned hashes, authors, source URLs, crop rectangles and conversion steps
are emitted by `prepare_high_detail_fixture.py` into per-source provenance JSON.
Actual captured pixels, snapshot and selected graph are checked separately at
native 100% and 200% browser zoom. Technical assertions leave visual status FAIL.

Cheek presentation uses 19 real landmarks in seven neighbouring anatomical rows.
The explicit opposite-side indices were checked against MediaPipe's canonical
face geometry. Topology is fixed; no new vertices or photo-based runtime
triangulation is used. Numerical sampling ROIs and clinical limitations remain.
https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model.obj
