# Calibrated native dryness v2 admission and selective lower-face expression gate — 2026-10-14

Protected baseline: `72b90172084711cd200637cedab831f80e3fb973`, build `9DheD3msEFSOMhjMp-kK8`. New production build: `YShP4ZdJdKL34lP_ALnmW`. PR #2 stays Draft; no merge.

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

## Delivery checks

23 focused regressions passed, including atomic rejection of a missing General scope. A separate frontend unit check confirms raw precision, the dry-only method allowlist and history-version separation; it is not browser acceptance. Native PNG checks match score numerators and visible denominators on 35 actual API maps, with zero active pixels outside their eligible masks. Focused ESLint passed; production build completed including TypeScript validation. Frozen frontend source receipt matches the promoted build. The old build remains in `.runtime/skin-pre-dry-calibrated-v2-20261014`.

The normal shortcut launched the new build. Its own actual backend completed a cold full request (dry encoder initialization included) in 6.625 s and a warm full request in 5.438 s. 217 frozen frontend source files, 18 served JavaScript assets, the loaded model identities and the approved audio match. Exact pinned model bytes are protected from Git line-ending conversion. Full fresh camera→result→history visual acceptance is still pending resource availability: a single owned verification browser/job stopped when system available RAM reached 153.47 MiB (private process peak 729.47 MiB). Its own lifecycle drained; no user application was closed. The hard reserve was not lowered. Desktop/narrow/native-200% claims must not be made until a successful final receipt exists. New full checks require at least 1600 MiB start availability, with an 1100 MiB owned-process cap and the unchanged 400 MiB stop reserve.

Protected: production skin-type/hosted consent configuration, eyewear policy, Turkish labels, all other health modules, natural photos, design, audio, user permissions and records. Acne remains `accepted=false`, `file=null`.
