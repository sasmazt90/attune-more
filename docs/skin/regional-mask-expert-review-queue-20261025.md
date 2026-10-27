# Regional Oily/Redness expert mask review queue

This queue turns the frozen regional v1 polygon export into an actionable expert-review package without changing Roboflow labels or reading the current test split.

- 81 unique train/validation images are selected: 64 train and 17 validation.
- Geometry extremes cover small and broad mask support, few and many instances, and complex boundaries.
- The primary queue contains 40 Oily and 41 Redness reviews; the sole train/validation co-occurrence image is included for independent-layer review.
- Test images read: 0. Test images selected: 0.
- Review item IDs are salted; filenames, provider IDs, raw source names, image bytes and the private resolver are not committed.

For each queued class/image, an expert must decide mask extent, hard-negative policy, ambiguous-case policy and assessability. An absent class annotation is not a reviewed negative and never means Normal. Redness remains an independent layer, and model predictions cannot be accepted as truth.

The queue is preparation evidence only. `scripts/skin-research/build_regional_mask_expert_protocol.py` now SHA-256 binds any decision receipt to this exact 81-item queue, requires exact one-to-one item/class/split coverage, rejects pending or duplicate decisions, excludes ambiguous or unassessable items, and refuses to keep an assessable mask whose extent was judged incorrect. Its template mode emits only salted review IDs and stays fail-closed.

The regional release gate independently verifies the frozen queue and requires the generated protocol to contain exactly 40 Oily and 41 Redness reviewed IDs from it. Until an expert completes those decisions and locks both class protocols, `maskProtocolReady`, training, test evaluation and activation remain false. The protocol builder never authorizes training by itself.
