# Historical current-photo appearance v2

This document records the earlier v2 arithmetic. The current local-joint support,
guide-relative tracking quality and lower-face-only SAG definitions are in
[skin-appearance-indices-20261011.md](skin-appearance-indices-20261011.md).
The former forehead/brow SAG path is unavailable in the current product.

## Historical contract

`appearance-cv-2`, `appearance_proxy`, unit `contour-fold-index-0-100`.
The active path never calls historical `contour_geometry`, reads a personal reference, initializes one, or relabels old measurements. First and later scans have `analysisMode=instant-appearance-v2`, `isBaseline=false`. Optional historical methods and their record versions remain separate.

An index is visible photographic support, not disease probability, clinical severity, tissue displacement, edema volume, age or a percentage of sagging. Source photos/colors/backgrounds are unchanged. Analysis copies are resized; all displayed evidence is mapped back to normalized original source coordinates. No MediaPipe z coordinate enters the formula.

## Fixed formula

Actual gray values are 0..1. Each anatomical guide is sampled at 64 arc-length locations. Guide bands and offsets scale by the current face width projected onto the 2D eye axis (nominal width 320 analysis pixels). The eye axis rotates the horizontal/vertical sampling directions; local guide shape follows the current landmarks. Unsupported yaw >.65 or pitch >.22 is rejected. This is a 2D pose/roll/scale control, not a calibrated 3D perspective/depth reconstruction.

A supported valley requires brightness on *both* sides: `c=max(0,min(I[-2]-I[0],I[+2]-I[0]))`. Paired local edge is `e=min(abs(I[-1]-I[0]),abs(I[+1]-I[0]))`.

- `F=mean(clamp((c-.012)/.08,0,1))`.
- `E=mean(clamp((e-.018)/.12,0,1))`.
- `C=min(1,longest uninterrupted supported run /64/.6)`.
- Boundary is tracked **independently** from source image gradients across the jaw or brow. Broad anatomical guide curvature is subtracted with Gaussian sigma 8, rather than using landmark shape alone. Local displacement `d` is in face-width-normalized analysis pixels. `B=mean(clamp((abs(d)-1)/4,0,1)*clamp((edge-.04)/.18,0,1))`.
- **Sag appearance**: `100 * F * sqrt(E) * C * sqrt(B)`.
- **Infraorbital bags appearance**: `100 * F * sqrt(E) * C` on the separate curved lower-lid bands, with paired brightness support.

Valid local subregion indices are averaged, without copying a left result to the right. Missing sides remain null in component metadata. These constants are fixed engineering normalizations, not clinically validated decision thresholds. No per-photo min/max spreading, forced positive output or high/low disease categories are used.

Jaw+nasolabial/marionette bands support cheeks, lower jaw+local marionette bands support chin. Forehead uses separate brow boundary and above-brow fold bands; forehead wrinkle alone cannot yield a nonzero sag index. Right/left infraorbital bands are separate and exclude actual eye/lip/nostril/brow holes and ROI exclusions.

## Quality and confounders

Native face width >=180 px; analysis inter-eye width >=35 px; observed usable skin >=100 px; each band and boundary coverage >=.55. Mouth opening >.10 mouth width, corner elevation indicating smile, eye aspect <.12 for forehead/eyes, and raised brow <−.30 eye-width ratio cause null. A plane is fit across the **observed** regional skin, rather than extrapolating a tiny ROI to the full image; directional change >.55 causes null. Dense blackhat hair support >.22 of regional skin causes null. A long opaque infraorbital line detected by Hough support (dark <.18, minimum length .30 inter-eye width) is a possible eyewear/cosmetic confounder and causes null. Discontinuous tracking residual >2.5 prevents positive support.

These controls cannot identify every makeup product, transparent spectacle rim, facial expression or lighting condition. Single RGB photographs cannot separate cosmetic contouring/shadow from tissue volume in all cases. Normal asymmetry is not a pathology classification. Natural stable shape without supported local fold+boundary irregularity gives valid zero; poor detail/visibility/quality gives null with a reason. These outputs are engineering appearance proxies without clinical validation.

## Evidence and persistence

Only actual selected pixel support produces local signal intensity; no global scalar is spread across the mesh. Regional fills are clipped by the selected anatomical mesh and valid-mask holes. Source-supported contour paths are separate from the mesh. Changing criterion/region/photo clears the previous criterion layer. Photos, maps and masks stay volatile; persisted rows contain numerical measurements, method version, units, conditions and components only.

## Current verification

`tests/unit/test_current_health_contracts.py` exercises full positive bag and sag computation on declared pixel engineering patterns, uniform/dark negative controls, fold-only and boundary-only negatives, eyewear/hair/shadow nulls, poor angle/open mouth/no skin nulls, deterministic reference independence. These are not human photographs or clinical ground truth.

`tests/e2e/current_skin_contract.py` uses the existing licensed three-angle video through the real production MediaPipe camera flow, without pose/quality overrides; first scan and another scan with corrupt preserved historical keys, six selected source/mesh layers, original opaque background and native Chrome 200% zoom. Final photo-by-photo values/reasons and screenshots are in `audit-results/current-health-20261009/skin`. The fixture may lack suitable visible chin/cheek bands; a null for such a photo is not a healthy zero or completed clinical assessment. Physical user acceptance remains open.
