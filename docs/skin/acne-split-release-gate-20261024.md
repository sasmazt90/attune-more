# Acne replacement-split release gate

Date: 2026-10-24  
Dataset: `tolgar-sasmaz/attune-skin-acne-marks-pigmentation/1`  
Bound COCO archive SHA-256: `29f40e80c8b1f63d43abbc35d11efdbaac4cf754531af2bee64283dde64c34e2`

## Outcome

The replacement split is blocked, and no training is authorized. The gate replayed all 800 privacy-safe record IDs and found:

| Requirement | Current evidence |
|---|---:|
| Dataset records indexed | 800 / 800 |
| Confirmed cross-split source/person groups | 9 |
| Members in those confirmed leakage groups | 19 |
| Full reviewed group-coverage receipt | Missing |
| Records covered by a full group receipt | 0 / 800 |
| Expert semantic and hard-negative receipt | Template supplied; completion missing for all 3 classes |
| Ready to generate a replacement split | No |
| Training authorized | No |
| Test evaluation authorized | No |

The `0 / 800` group-coverage value does not discard the 19 already confirmed leakage members. The gate now validates the review-incomplete, privacy-safe 800-record grouping proposal and uses its nine cross-split confirmed groups as stronger current-split leakage evidence. This does not promote the proposal into a reviewed coverage receipt: 762 singleton records still lack provenance/person review, so no replacement split is authorized.

## Enforced controls

`scripts/skin-research/check_acne_split_release.py` fails closed unless:

1. every hashed record appears exactly once in a reviewed group receipt;
2. no unknown or duplicate record assignment exists;
3. every existing test record remains in test;
4. the receipt explicitly locks the existing test set;
5. an expert locks positive definitions, hard-negative policy and ambiguous-case policy for `Pimple`, `Post acne` and `Pigmentation`.

The optional grouping proposal input is independently checked for archive binding, privacy, split/member consistency and exact one-time coverage before its confirmed cross-split groups may strengthen the leakage count. It cannot satisfy the reviewed group-coverage requirement.

Even when all five conditions pass, the tool authorizes only deterministic replacement-split generation. Training remains unauthorized until the generated split is re-audited. This prevents an incomplete receipt from silently becoming a new training version.

## Privacy and verification

- The gate consumes hashed record IDs only; it commits no image bytes, faces, filenames or raw source names.
- Seven focused release-gate tests and the broader twenty-test source/grouping/semantic/gate suite pass.
- Both scripts compile under Python 3.
- The real 800-image export replay passed and produced the committed receipt.
- No Roboflow labels, split, threshold, upload, inference or training state changed.

Evidence:

- `docs/skin/evidence/acne-source-group-review-20261024-v1.json`
- `docs/skin/evidence/acne-split-release-gate-20261024-v1.json`
- `docs/skin/evidence/acne-semantic-review-queue-20261024-v1.json`
- `docs/skin/evidence/acne-semantic-negative-review-20261024-v1.json`
- `docs/skin/evidence/acne-group-coverage-proposal-20261024-v1.json`
