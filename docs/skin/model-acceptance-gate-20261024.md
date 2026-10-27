# Shared learned-model acceptance gate

The roadmap now has one fail-closed promotion check for learned skin-model
candidates. A finished training, provider recommendation flag, headline metric
or partial integration receipt is not enough to activate a model.

The gate requires all of the following:

- immutable model and source identities;
- reviewed rights, expert label protocol, person-independent splits, reviewed
  negative coverage and a test set untouched during selection;
- per-class validation and locked-test precision/recall/F1, with thresholds
  selected on validation and locked before test;
- an independent camera benchmark using the product capture contract, including
  lighting, pose and skin-tone slices;
- API, product-contract, unavailable-fallback, privacy/consent, history and
  regression-test evidence.

Missing values and truthy strings fail closed. The tool does not train, infer,
activate a model or convert predictions into labels.

## Current replay

The pinned acne/post-acne/pigmentation and regional oil/redness candidates both
remain rejected. Their locked per-class metrics are preserved, but source
independence, expert/negative coverage, independent camera acceptance and
working learned-model API integration are incomplete. The grouped under-eye
project has no uploaded images, version or model and therefore also fails
closed. No existing analytic result flow was disabled or renamed.

Four focused tests and Python compilation pass. Machine-readable inputs and
verdicts are in docs/skin/evidence/model-acceptance-gate-20261024-v1.json.
