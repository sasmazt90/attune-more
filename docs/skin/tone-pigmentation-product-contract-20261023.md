# Tone and localized pigmentation product contract — 2026-10-23

The merged product already returned nine appearance criteria and a separate skin type. This increment extends that existing result flow to the accepted 12-heading product inventory without promoting the rejected acne-marks/pigmentation research candidate.

## Implemented

- The product contract now contains eleven appearance headings plus the separate skin-type heading.
- `postAcne` and `pigmentation` are overview headings with explicit unavailable receipts, `candidate-count` units and separate localized-instance meanings.
- Neither localized heading can be populated from the regional tone proxy.
- Tone is explicitly defined as broad regional chromatic variation. Its receipt states that it cannot supply a localized pigmentation result and uses a separate-heading co-reporting policy.
- Historical nine-heading overview records remain valid and readable; new results contain all eleven appearance headings.
- The UI labels the new headings as `Sivilce izi görünümü` and `Pigmentasyon görünümü` and explains that the accepted local model is not active instead of displaying a fabricated zero or score.

## Verification

The updated browser converter and overview validator passed 91 executable contract checks using four real server-builder regional fixtures and three retained-photo source aspect ratios. Four backend contract tests passed. The current committed `skin_general.py` was executed in memory to construct a result and verified to return exactly eleven appearance rows, explicit unavailable localized rows and the tone-separation receipt. The committed `appearance_analysis.py` parsed successfully and was verified to stamp regional tone rows while preserving localized-row normalization.

Evidence: `docs/skin/evidence/tone-pigmentation-product-contract-20261023-v1.json`.

This is honest product-contract integration, not model acceptance. The current Pimple/Post acne/Pigmentation research candidate remains rejected on the recorded independent test metrics. Post-acne and pigmentation therefore remain visible-but-unavailable until a model, split independence and camera benchmark pass acceptance.
