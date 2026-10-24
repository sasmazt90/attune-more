# Original-photo/model comparison audit

## Result

The 46.5 MB self-contained comparison HTML was audited without committing face images, overlays, masks or individual boxes. Its six embedded FRONT JPEGs match the previously audited generated V5 replay package byte-for-byte. Despite the filename and presentation text, this is not new physical-camera evidence.

- HTML SHA-256: `83def109c93c2ca5b16580cee9f61ddb5ba08dd18f8f86e214aa9bb00139752e`
- V5 result ZIP SHA-256: `02c49ba5cbda603ddac24a176b42b618f3a913fe2171beb4ab316b7899d70af5`
- Embedded FRONT images verified: 6/6
- Pinned Roboflow model identities: 10/10
- Prediction boxes: finite, class-bound and within source dimensions
- Product activation: rejected

The receipt is privacy-safe and contains only hashes, aggregate counts, model identities, metric rows and blockers.

## Material findings

### The exploration floor is not a production threshold

The HTML stores predictions from a 5% exploration floor and presents columns at 7%, 11%, 30%, 33% and 50%. Fifteen model/profile pairs reach exactly 300 predictions: the lesion model and the highest-recorded-mAP acne/post-acne/pigmentation NAS candidate on all six profiles, plus the broad skin-findings NAS candidate on three profiles. A capped response cannot support a complete-recall claim or an operating-threshold decision.

### Acne marks and pigmentation candidate is rejected

The live Roboflow evaluation for `...--a5e262` was re-read using evaluation `0xMgfVLFzMyNEOhN1baC`. Its test F1 is 0.094 for Pimple, 0.052 for Post acne and 0.007 for Pigmentation. This evaluated NAS child is not acceptable for product integration. Roboflow's `recommended` flag is not interpreted as highest accuracy, a hardware winner or production approval.

The HTML's `...--929397` candidate is described as the highest recorded mAP child, but has no bound test evaluation in the artifact and reaches the 300-prediction cap on every profile. It is also not accepted. A different child may only advance after an exact-ID, class-specific evaluation and independent camera/expert checks.

### Regional candidate is incomplete and the map contract is wrong

The live test evaluation for regional child `...--e79545` reports F1 0.513 for Oily and 0.533 for Redness. It supplies neither Dry nor evaluated Normal, so it cannot establish dry/normal/oily skin type or the mixed-skin rule by itself. Its evaluation exposes object-detection-like metrics and no mIoU; those metrics cannot be presented as pixel-level regional map accuracy.

The HTML's hybrid map preserves 2,200,740 anatomy pixels as Unknown and colors zero pixels outside the face anatomy, which is correct fail-closed behavior. However its output schema uses `Sensitive` rather than the accepted independent `Redness` layer. `Sensitive` must not replace redness. The accepted product contract remains:

| Layer | Product rule |
| --- | --- |
| Dry | Blue |
| Oily | Green |
| Redness | Independent red contour/hatching; not sensitivity |
| Normal | Uncolored only when explicitly evaluated normal |
| Unknown | Light gray; never counted as normal |

### Metrics are source-bound, not correctness for these six faces

All six evaluation IDs present in the HTML were refreshed from Roboflow and match the exact model IDs and test metric rows. This verifies provenance only. The six displayed profiles have no expert ground truth, and the V5 evidence has no unused independent final-test artifact. No accuracy percentage, threshold change or production model switch is authorized from this comparison.

## Next acceptance work

1. Exclude the evaluated acne-marks/pigmentation child from integration and keep both new product headings unavailable.
2. Evaluate any alternative NAS child by exact model ID and per-class test metrics before spending inference effort on it.
3. Correct the research map schema so redness remains an independent red overlay; do not synthesize Dry or Normal from missing model classes.
4. Run a person-independent, expert-labelled benchmark and then real browser-camera captures with temporal checks.
5. Only after those gates pass, integrate a selected model and verify the existing 12-heading product contract end to end.

Evidence:

- `docs/skin/evidence/original-photo-model-comparison-audit-20261024.json`
- `docs/skin/evidence/roboflow-live-evaluations-20261024.json`
- `scripts/skin-research/audit_original_photo_model_comparison.py`
