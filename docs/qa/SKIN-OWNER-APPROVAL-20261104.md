# Owner approval record: production Skin model configuration

**Date of approval:** 2026-11-04
**Given by:** the product owner, in the instruction "Final Skin model approvals, IONOS domain integration and pre-AG completion", section 1
**Recorded by:** Claude, from that instruction and from the hashes of the deployed build
**Configuration approved:** the Skin models deployed on release candidate `4bb51b3`, listed below
**Tracker item:** QA-31, closed as OWNER APPROVED

## What the owner decided

1. **V5 acne pipeline: approved.** It stays enabled for the acne heading. An older research manifest holding `accepted:false` is not a reason to disable it. No further V5-against-baseline selection is to be done.
2. **`regional.pt`: approved.** It stays in the combined regional pipeline. An unmeasured or uncertain region must still not become Normal automatically.
3. **All other configured Skin models: approved.** Individual approval is not to be requested again. An existing model is not to be disabled, replaced, retrained or altered merely because an older research record labelled it blocked, experimental or unaccepted.
4. **The separate lesion and finding pipeline** stays responsible for its own detections, counts and subtypes.

## What this approval does not say

- **It covers product configuration, not clinical accuracy.** Accuracy stays NOT VERIFIED wherever no labelled ground truth exists. No accuracy figure may be drawn from this record.
- **It does not rewrite history.** Earlier experimental decisions and research records are kept as they were. No artifact was changed to remove an old flag, so `acne-v5-preview/manifest.json` still says `accepted:false`, and the runtime still reports `experimental:true` and `accepted:false` for V5.
- **It does not settle QA-25.** Missed detections on specific photographs stay a defect to investigate under that item.

## When model selection may reopen

Only for a newly demonstrated technical defect, or concrete evidence of an incorrect result. An older research label is neither.

## Approved configuration

Hashes were read on the WEB host on the deployed build, 2026-11-04T09:41:04Z. All 52 model files matched the verified record, and the runtime reported the same hashes for the 27 regional-pipeline files it loaded. The V5 detector, verifier and source Step0 hashes below were reported by the running analysis (`status: measured`). Source Step0 SHA-256: `18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655`. Combined V5 model hash: `b8200e999c6c744247d264de70df5280900e08f0ba5130479425a6dac92d13f5`.

The later release candidates did not change any of these files. A full re-hash on `f7d861e` found the same 52 files with the same hashes.

Both platforms run Skin inference on the WEB host. AAOS reaches it over the private mTLS connection, so the model files on the AAOS host are not used. That host still holds an older copy of the V5 manifest and verifier, and they were not changed.

### V5 acne pipeline: the acne heading

| File under `services/core-api/models` | Role | Version | Bytes | SHA-256 |
|---|---|---|---:|---|
| `acne-v5-preview/step0-with-features-stable-silu.onnx` | Detector | experimental-step0-verifier-v5-local-preview-v1 | 39,122,518 | `9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be` |
| `acne-v5-preview/verifier-v5.json` | Verifier | experimental-step0-verifier-v5-local-preview-v1 | 152,591 | `0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb` |
| `acne-v5-preview/manifest.json` | Thresholds and hashes | experimental-step0-verifier-v5-local-preview-v1 | 1,197 | `a9f939deb312cfc957d8456fc865e1d3a6f21a5d4e0ba227b94bedb1413a8fe0` |

### Combined regional pipeline: regional skin type and the skin map

| File under `services/core-api/models` | Role | Version | Bytes | SHA-256 |
|---|---|---|---:|---|
| `regional-skin-v3/regional.pt` | Regional detector, input to the classifier | regional-skin-v3, params regional-skin-v3-params-20261025e | 127,380,775 | `b23cd0ed5a18caa679a5a77607e855ef263483f712edd34d4ddeb215ce557365` |
| `regional-skin-v3/skinmap.pt` | Skin map detector | regional-skin-v3, params regional-skin-v3-params-20261025e | 133,802,451 | `bc4e8aab0866ece0048a7306284e1bf26ef5ba31bf56ba8834ff2e2494d2a4a5` |
| `regional-skin-v3/k_classifier.json` | Regional classifier | k-regional-20261025f | 133,992 | `a7ab0b05686d4d9664c115fa324589e492fc7e8829e4f9ef4488354b25688a54` |
| `regional-skin-v3/params.json` | Pipeline parameters | regional-skin-v3-params-20261025e | 4,474 | `5d1dc44de3fb4e3b150151eb642d0c152aa2fdc0161d4d7acbcc78f2847cd330` |

### Lesion and finding pipeline: finding cards, counts and subtypes

| File under `services/core-api/models` | Role | Version | Bytes | SHA-256 |
|---|---|---|---:|---|
| `regional-skin-v3/findings.pt` | Finding detector | regional-skin-v3, params regional-skin-v3-params-20261025e | 127,525,031 | `c8d94801bf86c65a4ff0c3c1e5ae663aaa4774fdccd4b31d4782aeed33675c99` |
| `regional-skin-v3/acnes.pt` | Acne detector | regional-skin-v3, params regional-skin-v3-params-20261025e | 133,845,459 | `5db24d92049c0d335665a883ebd83dda115608a63594ccd2c336f504060abe15` |
| `regional-skin-v3/wrinkles.pt` | Wrinkle detector | regional-skin-v3, params regional-skin-v3-params-20261025e | 133,788,115 | `ba5c527859c1cb59ff6244b674eee1caca07984c28b8b4426ce8c1acb412f7b2` |
| `regional-skin-v3/dinov2-small/model.safetensors` | Image features | DINOv2 small | 88,249,960 | `ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1` |
| `regional-skin-v3/findings-v2/acne.json` | Finding model | skin-findings-v2 | 17,799 | `21bf8c718e1642c07da29fc0490c2c7071a5e4dacb1247a12eb6f74b00e0e6d5` |
| `regional-skin-v3/findings-v2/acneMarks.json` | Finding model | skin-findings-v2 | 455,097 | `beb5ad94d93dced59ddbcb31cb6e6d701923d8fa2adcf5fe2646116b6ce79e20` |
| `regional-skin-v3/findings-v2/coldSore.json` | Finding model | skin-findings-v2 | 455,533 | `a271536005a1a481586d307ebd3d5991ee87b71a60af4ffd17bf653a716b847b` |
| `regional-skin-v3/findings-v2/crowsFeet.json` | Finding model | skin-findings-v2 | 455,082 | `04a54cafe125a00ec8a37c7c84134714d249312c31d5a892ee82b7992e8117ea` |
| `regional-skin-v3/findings-v2/darkCircles.json` | Finding model | skin-findings-v2 | 3,081 | `03a1e3eb584399791e578eae8ee35cc682901310aa63d5afa12cc0a1ea2b286c` |
| `regional-skin-v3/findings-v2/downturnedCorners.json` | Finding model | skin-findings-v2 | 377,257 | `dec94ef7cd89d6badce52cb59e496f168e66cc4c1ccdfbd5f3ad12be7a468360` |
| `regional-skin-v3/findings-v2/eczema.json` | Finding model | skin-findings-v2 | 227,478 | `f4c54d2e68867d15afdfea67d1618bc5fce602819da41f851d332dace409ee9b` |
| `regional-skin-v3/findings-v2/eyeBags.json` | Finding model | skin-findings-v2 | 455,620 | `90e8d9455c127987b45cc4dfa1fcd4338af9dc0876341203cbab72157712baa5` |
| `regional-skin-v3/findings-v2/flaking.json` | Finding model | skin-findings-v2 | 227,443 | `6affd88f675776d11224894f87961e353f80d2b34913991ca5a19e4d6c1d736e` |
| `regional-skin-v3/findings-v2/foreheadLines.json` | Finding model | skin-findings-v2 | 228,471 | `db0705de20fc604c5f94f1b44ece292f7895b89a2d220068639f89b19b6bce36` |
| `regional-skin-v3/findings-v2/hoodedEyelids.json` | Finding model | skin-findings-v2 | 377,413 | `647141640b5c2cb5cb68e5557e0c43af723b2659777087b2824978c568c3607f` |
| `regional-skin-v3/findings-v2/redness.json` | Finding model | skin-findings-v2 | 5,333 | `2b455387db17d89c62ca69926402dae3558c65662769fb7014c72b6dd2ef3fd9` |
| `regional-skin-v3/findings-v2/severity/acneMarks.json` | Severity model | skin-findings-v2 | 55,514 | `c6a9088c5f0dfa85eae5daa5087c0393fe63abf56718732244757150e9b5a4da` |
| `regional-skin-v3/findings-v2/severity/crowsFeet.json` | Severity model | skin-findings-v2 | 56,872 | `bb44af67b2db8b2490694ed10fda6911888e588f6de556ca6899a6121cc126de` |
| `regional-skin-v3/findings-v2/severity/darkCircles.json` | Severity model | skin-findings-v2 | 58,766 | `144531cf334f751e8a1c548552cdfb71c96c332bd513af44ca28c259ddf08b23` |
| `regional-skin-v3/findings-v2/severity/eyeBags.json` | Severity model | skin-findings-v2 | 57,394 | `b140e5a91eeb185d8febb71328d03a2c9e43148cce29d2f8f36b02bd2ba4b692` |
| `regional-skin-v3/findings-v2/severity/foreheadLines.json` | Severity model | skin-findings-v2 | 54,587 | `239300f8168979be8c16b5bdbf4e63a28c1686a9095f3861d68fa161fa1676ec` |
| `regional-skin-v3/findings-v2/severity/hoodedEyelids.json` | Severity model | skin-findings-v2 | 54,370 | `346cc675ea0c910d760ef71a5acc8464521b11402b3a74195880f417140ef603` |
| `regional-skin-v3/findings-v2/severity_geo/downturnedCorners.json` | Severity model | skin-findings-v2 | 1,646 | `50d0784310a69304360292cae474056e446fc7922abdb8a7ffac7091401e03b4` |
| `regional-skin-v3/findings-v2/measures/flaking.json` | Measure model | skin-findings-v2 | 5,098 | `04bcd877729994ba24cd56a5ed2e8d697bc5553b406123cb928473dd72739a14` |

### Other configured Skin models

| File under `services/core-api/models` | Role | Version | Bytes | SHA-256 |
|---|---|---|---:|---|
| `skin-type-local-v1/model.onnx` | Overall skin type | local-vit-dima806-5aace4f-v1 | 343,341,982 | `99b4c2fa1e9ac013d539f635eb948c5a29f4c5f86f34fe26c380ad308c26c65a` |
| `skin-focused-degrees.onnx` | Redness heading | skin-appearance-photo-ridge-20261010-v1 | 16,037,017 | `65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3` |
| `skin-focused.json` | Head record for the redness heading | skin-appearance-photo-ridge-20261010-v1 | 7,043 | `14ee7ed0c49006d10c4abd7f246f8653bfc855c4e9f42ce0d4edc33483b32f29` |
| `dryness-calibrated-v3/encoder.onnx` | Dryness encoder | calibrated-material-v3-c04-clean | 16,019,972 | `a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987` |
| `dryness-calibrated-v3/head.json` | Dryness head | calibrated-material-v3-c04-clean | 204,818 | `7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1` |
| `skin-eyewear-framefind-v1.onnx` | Eyewear check | skin-eyewear-framefind-v1 | 6,402,858 | `66f75c686974a04bf956d0ed6411315309afcabd36c400edec743953adafccb9` |

Unchanged rules from the code, not part of the hash list: V5 threshold 0.15628, confidence 0.30, NMS 0.30. Downturned-corner threshold 0.668 was approved separately on 2026-10-26 (`CODEX_HANDOFF.md`).
