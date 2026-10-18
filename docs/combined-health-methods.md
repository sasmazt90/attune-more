# Local appearance and digital hearing methods

This document describes implementation, not clinical acceptance. Current build,
test outputs, model metrics and Windows delivery evidence are recorded separately
under `audit-results/combined-health-20261008/`. Those generated results must not
be promoted to acceptance of a different build or of real human interaction.

## Measurement meanings

`appearance_proxy` describes visible photographic features. A 0–100 index is an
engineering scale, not disease probability or severity. `trained_prediction`
describes a learned localized candidate; confidence is not severity.
`longitudinal_measurement` tracks an individual's compatible captures or digital
hearing session. Missing evidence produces null and a limitation code, not zero.

Results identify method, unit, quality, evaluated area, capture conditions,
uncertainties and the applicable source/reference/model. Native source RGBA bytes
are hashed. Backend maps and boxes use source coordinates. Display crop, CSS size
and device pixel ratio do not alter source motion or analytical coordinates.
Each skin measurement has a nullable `localMap` descriptor linking its criterion,
region and source hash to the separate ephemeral map. Numeric records may retain
this descriptor; map pixels and mask PNGs remain in volatile response/snapshot
memory and are not serialized into history.

## Skin

The displayed photograph retains its background and colors. Only the selected
anatomical mesh and source-bound local signal are drawn in separate layers.
Analysis uses a separate face-scale-normalized copy. Eyes, lips, nostrils, brows,
hair, strong clipping and externally supplied exclusion regions are removed from
eligible skin. Fine-detail measurements require at least 180 native face pixels;
the analytical copy is capped at 320 face pixels. No new face detail is generated.
Dark hair/crease exclusions include the black-hat filter's three-pixel support
to remove bright antialiasing/compression rings. Flaking components are rechecked
inside each region's eligible area; an excluded component's isolated remnants
cannot retain the original component's size/shape acceptance.

| Criterion | Type / unit | Calculation and limits |
|---|---|---|
| Uneven tone | appearance_proxy / relative-color-index-0-100 | 100 × standard deviation of `(R-G)/(R+G+B)` over eligible pixels. Light, pigmentation and shadows remain confounders. |
| Redness tendency | appearance_proxy / relative-color-index-0-100 | Mean clipped `100 × max(0, 2R-G-B)` in normalized RGB. This is a relative color index. |
| Oily appearance | appearance_proxy / percent-visible-area | Skin-Scan specular proposal intersected with local brightness excess and saturation drop. Eligible area with shine signal > .12 divided by eligible area; mean local intensity retained separately. Clipped highlights are quality failures. No sebum measurement. |
| Dry appearance | appearance_proxy / percent-visible-area | Fine bright islands supported by two high-pass scales, LBP, bounded local contrast and component geometry. Signal > .04 divided by eligible area. Roughness and non-uniform LBP retained separately; neither alone is dryness. No moisture, TEWL or Corneometer estimate. |
| Acne appearance | appearance_proxy / candidate-count | Skin-Scan proposal plus fixed two-scale red center-surround, contrast, small round component geometry and bright microstructure. Stores source boxes and eligible area. Freckles, moles, hairs and linear scars have separate negative controls. Not expert lesion detection. |
| Contour tracking | longitudinal_measurement / normalized-contour-ratio | Region-specific geometry, scale normalization, roll correction, compatible yaw/pitch, neutral mouth and at least three stable frames. First usable capture creates a reference. Later compatible captures report normalized differences; no universal sagging percentage. |
| Under-eye darkness | appearance_proxy / relative-color-index-0-100 | Local under-eye darkness relative to adjacent eligible skin within the face oval, divided by adjacent median brightness. Shadow and source-detail sensitivity remain. |
| Lower-lid/bag tracking | longitudinal_measurement / normalized-contour-ratio | Lower-lid geometry with at least three stable source-frame edge/contrast samples. Tracks a personal reference; does not measure edema or tissue volume. |
| Outer-eye lines | appearance_proxy / directional-line-index-0-100 | Maximum bounded response across two Gabor frequencies and four orientations, restricted to outer canthi and eligible skin. Not age or wrinkle severity. |

Forehead, right cheek, left cheek and chin each expose six criteria. The T-zone
combines forehead and nose for five criteria and excludes chin; only the selected
reference mesh's visible portion is filled. Periorbital output exposes darkness,
lower-lid tracking, outer-eye lines and dry appearance. Region-specific geometry
is not copied from another region.

Local maps use fixed signal ceilings and cyan alpha 0–100/255. A photo does not
receive a forced dark spot from per-image minimum/maximum normalization. Geometry
has contour evidence rather than a fabricated pixel heat map. Changing source,
pose, criterion or region removes the previous layer. Displayed values are rounded
with normal half-up nonnegative rounding; stored precision remains unchanged.

References are created only from usable evidence and are not silently replaced by
an incompatible pose, exposure or scale. Later missing regional references are
filled only by the first compatible valid measurement. Deleting a reference also
invalidates dependent deltas. Pre-existing records retain their original methods.

SCIN diagnosis is a case label, not a lesion box or mask. The local geometry audit
distinguishes cases, full-face photographs and local labels. The active skin path
uses working appearance proxies, not an unvalidated classifier/Grad-CAM lesion
boundary or an empty model adapter.

## Dental

Four camera captures are front, anatomical right, anatomical left and comfortable
natural bite. Native inner-mouth pixels determine tooth visibility, light,
sharpness, saliva/clipping and tongue obstruction; normalized lip opening alone
does not establish visible teeth. Source motion, actual pose, freshness and a
1400 ms stable window are independent of the smoothed display crop. Repeated
photos or repeated pose names cannot supply multiview evidence.

The detector is official Megvii YOLOX-s with a two-class head and random
initialization. Raw dataset `D` and `d` codes remain separate; an unsupported
clinical subtype mapping is not invented. Labeled photos are deduplicated by
exact hash and conservatively grouped by case/capture identifiers and perceptual
duplicates. Empty/unannotated photos are excluded, not labeled healthy. Patient
identity is not verified, so the split does not claim patient independence.

Validation selects checkpoint and confidence threshold. A validation-only
stopping rule registered before held-out evaluation has maximum 20, minimum 8 completed epochs,
patience 3 and .005 macro-F1 improvement. The held-out set is not used for tuning.
Evaluation reports localized precision/recall/F1, AP at IoU .5 and .5:.95, per-class
false positives and group bootstrap intervals. Calibration diagnostics cover
retained detections only, not disease probability or the omitted population.

The product verifies its ONNX hash and performs CPU inference on the real mouth
crop with a 15% source margin, maintaining source box coordinates. Candidates
outside the visible mouth are excluded. Absence of candidates does not establish
absence of decay, particularly on unseen surfaces or under different camera
conditions. Torch/ONNX equivalence and actual normal API inference are independent
technical checks, not clinical validation.

Accumulation candidates require gum/enamel-border proximity, bounded yellow
color, irregular texture, gradient structure and non-clipped appearance. Color
alone is insufficient. Distinct-view support uses normalized mouth position,
area and eligible-border fraction consistency. Only supported candidates are
drawn; insufficient or disagreeing views produce null, not “no calculus.” Food,
stain and filling remain confounders.

Natural-bite alignment uses marker-controlled watershed on actual visible enamel
and conservative contour geometry. Each row needs at least three reliable
contours. Its value is visible axial orientation dispersion in degrees; normalized
row residual and view tilt are retained separately. It does not invent teeth,
FDI numbering, a millimeter Little index, malocclusion or treatment decisions.
Adjacent visible contours are also projected onto the fitted row direction. Mean
overlap length divided by the smaller projected interval width is stored as a
0–1 geometric ratio. This is a camera-plane projection, not physical overlap,
hidden surfaces or three-dimensional crowding.

## Hearing

The browser produces its own PCM through Web Audio. Microphone/STT is not needed.
Users report stereo headphone use and hear/confirm the two real channel examples
separately. The browser does not claim to detect a worn headphone or OS volume.
Device changes, backgrounding, audio suspension and cancellation stop playback
and require preparation again. Pending asynchronous resume cannot start stale
audio after stop. The completed engine releases its bank and audio resources.

Pure tones use 48 kHz source PCM, 35 ms cosine ramps, random duration/gaps and
silent catch trials. Frequencies are 1000, 2000, 4000, 8000, 500, 250 Hz plus a
1000 Hz repeat, for each ear. A response window opens only after actual node
start; early/repeated key presses do not become heard responses. Start is -60,
minimum -90 and maximum -30 dBFS peak. Heard responses reduce 10 dB, missed
responses increase 5 dB, with amplitude `10^(dB/20)`. Threshold requires at least
two ascending heard presentations and at least 50% heard at that level. Limits,
trial exhaustion, catch false positives and repeat inconsistency remain distinct.
No calibration profile is active; no dB HL, dB SPL or hearing-loss label is given.

DIN uses ten frozen Ahmet 0–9 PCM files and speech-shaped noise derived from their
long-term spectrum. Profile is tr-TR-AhmetNeural, rate -10%, pitch -10Hz; those
settings are not applied to generated test tones. The bank is hash/version
checked, never synthesized during a test. Its auditory acceptance remains a
separate human check; technical playback is insufficient to accept pronunciation.

SNR uses full common presentation-window RMS: `20 log10(speechRMS/noiseRMS)`.
Shared gain preserves SNR, limits mixture peak to .08 and targets .015 RMS;
speech/noise mixture edges receive a common 30 ms fade. Sessions use crypto-random
seeds; engineering tests record declared deterministic seeds. Exactly 24 scored
triplets start at 0 dB SNR, change initially 4 then 2 dB within -15..15, and require
six reversals without boundary pileup. Replays are excluded; unknown/timeouts are
not wrong answers. Result includes accuracy, trial/replay counts and an SNR
estimate only if sufficiently stable. No published clinical DIN cutoff applies
to this experimental TTS bank.

## Data and rights

New skin/dental source photos and derivatives are local volatile memory. Processing
consent does not grant save consent. Optional persistent history contains numeric
results/geometry and compatible references, not new source photographs. Cancel,
navigation, privacy withdrawal, individual deletion and full wipe have independent
checks. Public fixtures are segregated from user input; they do not establish real
camera, subjective hearing or clinical acceptance.

Exact source/library notices and hashes are in `third-party/combined-health/` and
`third-party/skin-research/`. Skin-Scan revision
`afc55f5cb87fcc644f36b472c37083b254bd3fe4` is MIT; official YOLOX revision
`6ddff4824372906469a7fae2dc3206c7aa4bbaee` is Apache-2.0. The Zenodo 14827784
dataset is CC BY 4.0, with archive MD5/SHA-256 checks and attribution retained.
Own trained weights are distinct from code/data rights and follow the existing
repository ownership policy. No unverified pretrained weights, new Ultralytics
analysis path, cloud analysis service or paid GPU is used. Existing Edge-TTS has
its own LGPL notice. The OpenCV Python wrapper is MIT, the OpenCV binary has its
Apache-2.0 license and bundled third-party notices include LGPL components; these
notices and ONNX Runtime's third-party notices are retained in full. The dependency
set is not described as entirely MIT.
