# Calibrated native dryness v2 admission and selective lower-face expression gate — 2026-10-14

Protected baseline: `72b90172084711cd200637cedab831f80e3fb973`, build `9DheD3msEFSOMhjMp-kK8`. Accepted production build: `mlOb9YC5JKNnbE_1xzdjD`. PR #2 stays Draft; no merge.

## Frozen identity and scope

The four user-pinned artifacts from AG `1b2ee037d1d835fcd29a8f5bf78eb99d034632dd` were copied into an independent snapshot and verified byte-for-byte. These ignored package artifacts are absent from its Git tree: their authority is the user's explicit SHA-256 pins, not a fabricated Git blob. The v2 manifest's commit metadata matches. No moving AG module is imported at runtime. No acne weights, new contour/prominence method, training, encoder export, download or hosted call was used.

Production assets live in `services/core-api/models/dryness-calibrated-v3/`. Head SHA-256: `7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1`; actual ORT encoder: `a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987`; source encoder: `e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a`. Runtime checks assets, parity receipt, graph contract and the pinned 64-row head. Threshold remains 0.50; no feature rescaling is applied twice.

## Optical admission (existing exposed development scope)

| Scope | Native hits | Half-source hits | Reviewed negative support |
|---|---:|---:|---:|
| TRAIN partial material targets | 7/13 | 9/13 | 0 / 0 source pixels |
| Seen validation partial material targets | 7/8 | 4/8 | 0 / 0 source pixels |
| Combined | 14/21 | 13/21 | 0 / 0 source pixels |

These are mixed processed/natural, partial optical targets, not independent final-test accuracy, complete-mask Dice or biological dryness labels. Unknown pixels remain unknown. Seven native targets and half-source instability remain open. Adding C04's reviewed negative to TRAIN is a training-label correction, not a new validation gain.

Fresh encoder: C04 component 29 changes from prior head p=0.5270069 / 151 reviewed-negative pixels to p=0.01631247 / 0 pixels. C08 component 50 retains 71 positive-polygon pixels at p=0.55545222. Fresh/cached feature maximum differences are 0.0000298 and 0.0000490; both decisions agree. These crop times are not full API times.

## Normal production selector and lifecycle

`product_dryness.py` wraps the existing normal analyzer and atomically replaces only dryness rows/maps. Model failures do not fall back to old dryness under a new map. Source identity must match. General score uses `native.general.value`, not an invented `overviewScore` key. The tested front frame has a measured General score of 0.0 with no limitation; this is a measured no-support result, not a metadata-null workaround.

New identities: `appearance-native-dry-2`, `native-calibrated-material-source-area-v8`, `frozen-imagenet-two-crop-material-calibrated-v3`, `native-source-closed-cells-max-union-v5`. Composite model identity binds head, runtime encoder and source encoder. Scores count unique accepted source pixels over visible anatomical source pixels; the General union counts overlaps once. Confidence never becomes severity. Existing records are not rewritten.

Real HTTP router tests use the production analyzer without substituting a research analyzer. 640×640 first full request including encoder initialization: 5.641 s; warm full request: 5.219 s. 1280×960 controlled-camera payload: 12.328 s. 408×612 development source 24031977: 6.266 s. Source 24031977 General score is 0.21098452 (95/45027 source pixels); this does not imply its previously missed target positions were recovered. The 1280×960 source's 1.68646769 is runtime/map evidence, not a manually reviewed material label.

The original 2316×3088 29cc4ba7 source exceeded the unchanged 45 s budget and returned HTTP 504 (`LOCAL_ANALYSIS_TIMEOUT`) at 45.188 s with no result. It was not silently resized or counted as passing normal-camera performance. The native source fold comparison below therefore uses the existing product fold analyzer at the same original payload, separately from the full dryness request. The router's cooperative cancellation/deadline tests verify worker drainage before busy-lock release. Encoder batches remain four; crop reuse is request-local only. The 400 MiB system reserve and both ownership leases remain enforced.

## Selective lower-face expression correction

Only the existing `instant_proxy` lower-face gate changes. Chin v9 / cheek v7 tracking, boundary geometry, local score/map construction and source coordinates are retained. Periorbital gates and maps are unchanged; no AG wholesale file replacement. The capture passes real MediaPipe blendshapes beside the same accepted landmarks, bound to the resulting photoId. Backend validates version, required fields, every score's finite 0–1 range and same-source identity. No `conditions.observation` fallback or missing-score-to-zero conversion exists. Without an observation, geometric smile rejection remains conservative even with broad lips.

| Same original product payload | Before | After | Meaning |
|---|---|---|---|
| 29cc4ba7 cheeks | Expression rejection | Right 0.02818151; left 0.24375337 | False expression rejection removed, not a whole-face zero-sag label |
| 29cc4ba7 chin | Expression rejection | Null / `CONTOUR_TRACKING_INSUFFICIENT_SUPPORT` | Tracking remains unavailable; not a healthy zero |
| 4d05d72b | Measured zero in the CDC baseline | Same zero | Preserved behavior; no invented new gain |
| dedbb492 left cheek | 3.03379189 | Same 3.03379189 | Existing measured support retained |
| dedbb492 chin | Null / directional shadow | Same null / directional shadow | No shadow override or localization-success claim |

Other criterion rows and non-dry/non-sag maps match before/after on these three payloads. Regional formula identities and General normalization distinguish the new expression scope from legacy history. The existing real browser observation for fc3a6b13 still yields `EXPRESSION_OPEN_MOUTH`. Unit checks cover smile, open mouth, frown, puff, press and pucker, invalid/missing/mismatched observations and conservative geometric fallback. The stored control set does not contain a separately reviewed true pucker photo; that optical coverage is explicitly incomplete. No general sag-detection success is claimed.

## Product boundary defects found and corrected

The API returned the new method correctly, but `validMeasurement` still rejected it at persistence after `attachAppearance` accepted it. Both now use one criterion-specific allowlist. A real API response passes regional and General validation; other criteria cannot claim the native-dry method.

The new dry calibration and lower-face expression identities were also missing from the renderer's closed-cell compatibility mapping. The backend used closed anatomical cells while the SVG could fall back to sparse edge triangles. Only the exact admitted versions now reuse their underlying closed-cell geometry; legacy and unrelated methods keep their prior supports. Numerical methods, thresholds, source pixels and scores were not changed to make the rendering pass.

On the actual normal 1280×960 camera payload, the General dryness value is 1.66396292004635 = 1436/86300 visible source pixels. The DOM uses the actual API PNG and source coordinates. Its real SVG clip contains 179 paths: 1430 accepted pixel centers are inside, all 1436 pixel footprints intersect the clip, and none is fully discarded. In the real, non-emulated browser viewport, switching the map on/off changes 1195 photo pixels (maximum channel difference 61), while the original photo URI and history remain unchanged. This source is a rendering/performance control, not a semantic dryness ground-truth label.

## Final delivery checks

23 focused backend regressions passed. The frontend contract test covers actual API attachment, regional/General persistence validation, precision, criterion-specific admission, legacy comparison and closed-cell support. Focused ESLint and the final production build including TypeScript validation passed.

The normal Windows shortcut runs the accepted build and actual normal API (verification=false). A fresh real browser MediaPipe/canvas-camera scan completes a cold full API request including dry encoder loading in 9.9399 s; its warm full request takes 7.921 s. The separate 1280×960 camera case completes in 13.9522 s. Capture snapshots keep actual source dimensions; no complete photo is silently reduced for the native path. These controlled-stream checks do not claim physical phone/vehicle-camera accuracy.

Fresh result and the same-record history use matching photoId, dimensions, model/method identities and map. Both General and regional legacy/new comparisons separate into two method series without persisting/recalculating the legacy clone. Appending the second source preserves the existing isolated records exactly. Region and criterion changes clear the prior map. The approved introductory voice plays once; the glasses control creates zero analysis requests and zero records.

Desktop and actual narrow-window checks passed (706 CSS px, no horizontal overflow). Native Chrome 200% checks passed without CSS zoom/emulated viewport (DPR 3, innerWidth 641, outerWidth 1298); positive-map history geometry matches the API. Natural source pixels/background, existing layout, labels, integer bars, meshes and audio are retained.

49 maps across seven real saved API outputs have exact active/eligible pixel counts, no active pixels outside their eligible masks, and source coordinates within the original frame. Reconstructing regional source-space unions equals the General numerator and visible denominator exactly. These are integrity checks, not 49 independent labeled photographs.

217 frozen frontend files and 18 served JavaScript assets match. Actual loaded head/encoder identities and approved audio match local/committed assets. Pinned model/head/parity bytes are protected from Git line-ending conversion. The original protected build remains in `.runtime/skin-pre-dry-calibrated-v2-20261014`; subsequent builds are also retained.

Early resource/monitor stops failed closed and were resolved before final acceptance. The 400 MiB system stop reserve, one-second ownership observation, dual leases and AG exclusion remain intact. No guard was disabled. No user application was closed; only owned delivery/test sessions were managed.

Remaining scope: seven native optical targets remain missed; half-source seen validation is 4/8. Source 29cc4ba7 chin tracking remains unavailable. A separately reviewed true-pucker photograph is not in the fixed control set; pucker branches are tested as contracts, not advertised as broad optical validation. The real smiling/open-mouth camera control is rejected by the lower-face expression gate (`EXPRESSION_OPEN_MOUTH` takes priority), and the existing real open-mouth observation remains rejected. No general sag-detection success is claimed.

Protected: skin-type/hosted consent configuration, eyewear policy, Turkish labels, other health modules, natural photos, design, audio, permissions and user records. Acne remains `accepted=false`, `file=null`. No training, export, download or hosted call was introduced.
