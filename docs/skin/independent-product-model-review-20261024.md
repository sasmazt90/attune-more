# Independent product/model review ingestion

## Scope

The 24-page independent review and its shorter pasted follow-up were materialized and hashed. The source PDF is internally explicit that screenshots, generated images and Roboflow evaluation panels do not establish clinical truth, physical-camera acceptance or a production threshold. Neither source file nor any embedded face image is committed.

The shorter follow-up is not treated as an instruction to activate the cited 0.31/0.35 or lesion-class thresholds. The full review says these are validation/test-optimum observations, not a validation-selected threshold locked before an independent test.

## Implemented finding

One finding is directly verifiable in the roadmap branch: skinDisplayKind previously grouped color indices, directional line indices, generic 0-100 appearance indices and true supported-area ratios into the same percent presentation. SkinIndicatorValue therefore applied the same percent sign, meter and green-to-red severity color to unlike quantities.

Commit 1ef3ba929ba5678a75435e8d0985fac112639978 changes the presentation contract:

- only percent-visible-area and visible-highlight-area-percent receive a percent meter;
- color, line, fold and generic 0-100 indices remain numeric, neutral and bar-free;
- candidate counts and normalized contours preserve their existing distinct render paths;
- no model, threshold, stored measurement or analysis formula changes.

node tests/unit/skin_presentation_semantics.mjs passes ten behavior/source assertions covering both accepted area units and the separate index/count/contour cases.

## Remote refresh

Roboflow still contains 16 private projects. Acne/post-acne/pigmentation NAS 5b632a5c12b76fcfe703 remains finished with 89 children. Regional NAS 3485f8c67f957a1b850d remains finished with 75 provider records. The regional project currently reports 337 images and the grouped under-eye project remains empty. No training, inference, upload or threshold refit was started.

## Remaining boundary

This change improves semantic honesty only. It does not validate the current color/shine formulas, establish a skin type, accept any learned model, measure accuracy, resolve the unknown tested build, or replace the required consented physical-camera and expert-labelled acceptance work.
