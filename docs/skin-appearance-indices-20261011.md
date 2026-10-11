# Skin appearance index definitions — 2026-10-11

This is the current arithmetic and provenance contract for `appearance-cv-6` and
`front-appearance-union-v3-local-target-coverage`. These engineering appearance
indices describe different image signals; their 0–100 values are not one common
physical quantity. Probability/confidence does not measure severity. A valid zero
is distinct from an unavailable measurement; unavailable sides remain unknown.
The frontend, source colours, cards, bars and approved meshes are preserved.

| Criterion | Version / arithmetic meaning | Source gradient / evidence | Limit and acceptance state |
|---|---|---|---|
| Skin type | Categorical normal/dry/oily/combination; no 0–100 severity | No severity map from logits or confidence | Expanded EfficientNet candidate fails classification; unavailable in product |
| Acne | `unique-detection-box-area-fixed-v1`: unique accepted box-support pixels / visible anatomical ROI ×100, plus deduplicated candidate count | Box support is localization, not pixel lesion severity; no binary mask or confidence becomes a severity gradient | No accepted detector, so normal API returns unavailable and no substitute heuristic map; a future density index needs its own scale controls |
| Oil | `visible-specular-area-fixed-v1`: fraction of valid visible pixels with measured local shine >.12 ×100 | Actual local specular support after observed-skin/non-skin exclusions | Visible shine, not sebum mass; natural-control separation currently weak; cream/light confounding remains open |
| Dry | `eligible-flake-area-fixed-v1`: fraction of valid pixels with eligible bright flake-component support >.04 ×100 | Actual local flake contrast; dark pore/hair ringing is excluded | Visible fine flaking, not moisture; texture roughness alone is not dryness. Separate weak presence network has no severity output |
| Redness | Regional `lab-red-excess-fixed-v1`: local positive CIELAB a* excess to observed regional reference, with fixed deadband/scale | Measured local colour contrast | Illumination/camera/makeup can alter colour. Existing accepted whole-photo ridge grade uses `ordinal-0-5-times-20-v1`; its single grade does not create a regional severity map |
| Tone | `lab-local-color-fixed-v1`: mean local chromatic Delta-ab to observed regional median | Actual local colour distance | Not a pigment diagnosis; light/makeup sensitivity and natural ordering remain unresolved. A detrended alternative performed worse and was not installed |
| Crow's feet | `outer-canthus-gabor-local-quality-v2`: mean fixed-scale, multi-direction Gabor line support ×100 in measured outer-canthus bands | Measured local line response; no model confidence | Each eye has its own exposure/detail/visible-support checks. Expression/lighting calibration and independent acceptance remain pending |
| Dark circles | `lower-lid-relative-contrast-local-quality-v2`: mean positive lower-lid gray contrast to that eye's observed adjacent skin, normalized by max(reference,.1) ×100 | Actual same-eye relative darkness | Adjacent usable reference must exist; no opposite-eye copying. Two negative natural controls are insufficient for scale acceptance |
| Bags | `contour-fold-local-support-v4`: mean of local fold support × sqrt(local paired-edge support), multiplied by supported continuity | Each source point uses its own joint fold/edge signal; no side-wide scalar spread | Lower-lid anatomy, expression, eyewear, detail and target exposure checks remain active; visible fold/contour support is not edema volume |
| Sag | `contour-fold-lower-face-local-support-v5`: bags-style local joint support multiplied by sqrt(independently measured lower-jaw boundary support) | Actual lower-cheek/jaw fold and independent contour evidence; deduplicated left/right lower paths | No forehead/brow substitution, age or personal baseline. Only valid local lower-face sides contribute; missing sides/regions stay unknown. Natural appearance scale is still unaccepted |

## Contour arithmetic and quality

At 64 arc-length samples the symmetric valley contrast must be supported on
both sides. `F_i=clip((contrast_i-.012)/.08,0,1)` and
`E_i=clip((pairedEdge_i-.018)/.12,0,1)`. Let `C` be the longest uninterrupted
supported run divided by 64, capped after normalization by .6. The base index
is `100 * mean(F_i * sqrt(E_i)) * min(1,C/.6)`. Sag also multiplies by
`sqrt(B)` from independent image-based jaw-boundary tracking. This prevents
fold and edge responses at different points from being multiplied into support.
The gradient uses the same local `F_i * sqrt(E_i)` factors, continuity and jaw
factor, only at actual supported source coordinates inside the eligible ROI.
A binary localization mask supplies support, not invented within-mask severity.

`guide-relative-displacement-v1` computes tracking noise after subtracting the
interpolated anatomical guide. Expected guide bends no longer count as unstable
image tracking. The 2.5 native-width-normalized rejection threshold is unchanged;
actual oscillating displacement still fails. Native face >=180, band/boundary
coverage >=.55, clipped target fraction <=.03, shadow/pose/expression/hair/eyewear
controls and fixed contrast constants are unchanged. Shape and local support
are read from the present photograph; historical `contour_geometry` is not used.

SAG exposure and shadow checks use the actual lower-fold/jaw corridors. Eye
criteria check each own lower-lid or outer-canthus target and same-eye reference.
A problem elsewhere in the photograph does not invalidate an otherwise usable
local target. Acquisition failure still invalidates the capture. Partial target
coverage is disclosed in numerical metadata; it never estimates unseen skin.

## Evaluation and record versions

`label-function-acceptance-v2.json` keeps detection/presence, localization,
appearance scale, paired grade calibration, independent final, export parity,
product integration and user readiness separate. The frozen detection/Dice/FPR
limits are unchanged. Grade MAE/minimum paired grades apply only to an intended
grade predictor with actually matched grades and matching target semantics.
They are not requirements for boxes, masks, presence or analytic indices.

Natural engineering labels and genuine source annotations are disclosed as
such; absence of expert grading does not reject valid localization. Unknown
partial-label pixels have zero loss. Existing opened tests are development data.
Same-input repetition and auxiliary exposure transforms do not substitute for
natural positives/negatives, expression/pose controls or an unused final.

Records keep their original method/calibration versions. No historic result is
relabelled with these formulas. Photos, gradients and geometry remain volatile;
persistent history contains numerical measurements and provenance only. This
change adds no permanent explanation/control to the product UI.
