# Acne replacement-split release gate

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

The replacement split is blocked, and no training is authorized. The gate replayed all 800 privacy-safe record IDs and found:

| Requirement | Current evidence |
|---|---:|
| Dataset records indexed | 800 / 800 |
| Confirmed cross-split source/person groups | 5 |
| Members in those confirmed leakage groups | 10 |
| Full reviewed group-coverage receipt | Missing |
| Records covered by a full group receipt | 0 / 800 |
| Expert semantic and hard-negative receipt | Template supplied; completion missing for all 3 classes |
| Ready to generate a replacement split | No |
| Training authorized | No |
| Test evaluation authorized | No |

The `0 / 800` group-coverage value does not discard the ten already confirmed leakage members. It means no complete, reviewed receipt yet assigns every record to exactly one source/person group and a proposed split. Confirmed leakage evidence and full coverage are deliberately tracked as different claims.

## Enforced controls

`scripts/skin-research/check_acne_split_release.py` fails closed unless:

1. every hashed record appears exactly once in a reviewed group receipt;
2. no unknown or duplicate record assignment exists;
3. every existing test record remains in test;
4. the receipt explicitly locks the existing test set;
5. an expert locks positive definitions, hard-negative policy and ambiguous-case policy for `Pimple`, `Post acne` and `Pigmentation`.

Even when all five conditions pass, the tool authorizes only deterministic replacement-split generation. Training remains unauthorized until the generated split is re-audited. This prevents an incomplete receipt from silently becoming a new training version.

## Privacy and verification

- The gate consumes hashed record IDs only; it commits no image bytes, faces, filenames or raw source names.
- Four focused release-gate tests and the existing three source-group tests pass.
- Both scripts compile under Python 3.
- The real 800-image export replay passed and produced the committed receipt.
- No Roboflow labels, split, threshold, upload, inference or training state changed.

Evidence:

- `docs/skin/evidence/acne-source-group-review-20261024-v1.json`
- `docs/skin/evidence/acne-split-release-gate-20261024-v1.json`
- `docs/skin/evidence/acne-semantic-review-queue-20261024-v1.json`
- `docs/skin/evidence/acne-semantic-negative-review-20261024-v1.json`
