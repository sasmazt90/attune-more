# Regional Oily/Redness expert mask review queue

This queue turns the frozen regional v1 polygon export into an actionable expert-review package without changing Roboflow labels or reading the current test split.

- 81 unique train/validation images are selected: 64 train and 17 validation.
- Geometry extremes cover small and broad mask support, few and many instances, and complex boundaries.
- The primary queue contains 40 Oily and 41 Redness reviews; the sole train/validation co-occurrence image is included for independent-layer review.
- Test images read: 0. Test images selected: 0.
- Review item IDs are salted; filenames, provider IDs, raw source names, image bytes and the private resolver are not committed.

For each queued class/image, an expert must decide mask extent, hard-negative policy, ambiguous-case policy and assessability. An absent class annotation is not a reviewed negative and never means Normal. Redness remains an independent layer, and model predictions cannot be accepted as truth.

The queue is preparation evidence only. Until an expert receipt binds reviewed item IDs and locks both class protocols, `maskProtocolReady`, training, test evaluation and activation remain false.
