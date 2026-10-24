# Attune V5 / Roboflow source-bound comparison

## Result

The six complete Attune FRONT responses are now audited and joined to the already-saved Roboflow responses by the exact input JPEG SHA-256. This proves that the existing merged Attune result flow produced concrete outputs for the same six FRONT images; it does not measure either system's accuracy.

- Attune base commit: `7463eef112c5a40f7cd01192b6d1f4e9fa6ab285`
- Endpoint: `/api/local-health/skin`
- V5 results ZIP: `02c49ba5cbda603ddac24a176b42b618f3a913fe2171beb4ab316b7899d70af5`
- ZIP integrity: 1,310 payload files covered by SHA-256 plus CRC validation
- Attune requests: 18/18 completed with HTTP 200; 6/6 FRONT responses include the nine current appearance criteria, separate skin type, six regions and map/contour objects
- Source: generated still-image replay; physical-camera acceptance, temporal stability and expert ground truth remain false

The runtime records the merged commit as its base and a separate local execution revision (`4dc1f826...`); it explicitly records that no product, model or threshold behavior changed. This provenance is retained in the comparison receipt rather than presenting the runtime as a clean Git checkout.

## Existing Attune outputs

| Profile | Valid overview criteria / 9 | Skin type |
| --- | ---: | --- |
| 1.England | 9 | oily |
| 2.Germany | 9 | dry |
| 3.Kenya | 9 | oily |
| 4.Scotland | 9 | dry |
| 5.Turkey | 9 | dry |
| 6.usa | 6 | oily |

Across the six FRONT responses, 51 of 54 overview criterion values are available. The three unavailable values for 6.usa are tone, oil and redness; the response correctly preserves them as `insufficient` rather than silently converting them to normal. This is an output-availability rate, not a correctness or accuracy rate.

## Roboflow confidence effect on the same images

| Confidence floor | Total proposals | Acne | Pores | Wrinkles | Redness | Flakes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8% | 224 | 39 | 45 | 55 | 80 | 5 |
| 15% | 89 | 18 | 17 | 25 | 28 | 1 |
| 20% | 62 | 9 | 11 | 21 | 20 | 1 |
| 30% | 36 | 3 | 8 | 17 | 7 | 1 |
| 50% | 17 | 0 | 3 | 13 | 1 | 0 |

At 50%, 207 of the 224 proposals visible at 8% are suppressed (92.4%). This directly confirms the earlier concern that a high confidence floor can hide many candidate findings. It does **not** prove that the suppressed candidates are correct: these six generated images have no expert annotations, and the two systems' score/value scales are not comparable.

## Decision retained

- Keep low-confidence Roboflow results as review proposals, not product truth.
- Do not derive an Attune accuracy percentage from response availability.
- Do not activate the public Roboflow model or lower a production threshold from this replay alone.
- Continue with split-independent labeled evaluation and physical-camera captures before model acceptance.

The standalone HTML table contains the per-profile Attune values and Roboflow threshold counts. The JSON receipt preserves every Attune quality/limitation field and the exact source identities without committing face images.
