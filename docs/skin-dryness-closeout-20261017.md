# DRY-01 finite frozen-record diagnosis — 2026-10-17

No production bug was proven and no production code, model, threshold, proposal, history or runtime changed. Seven optical native misses remain. This closes the bounded diagnosis, not dryness accuracy or final product acceptance.

Runtime preserved: `b2573b512595adc7cae86d7ab932abb318f61689` / BUILD_ID `PlmGO62XYbiAMR2PNNLGr`. This report's later audit commit contains only this report, photo-free evidence and the offline audit script. No push/merge. SAG-01 neutral voice/live capture remains blocked; FINAL-01 visible/history/semantic permission acceptance remains open.

## Evidence actually recomputed

All 16 original source files matched their SHA-256 and original width/height. All 42 conditioned case files plus the fixed feature-row identity matched the pinned record ordering. The existing calibrated head was applied to stored features, reproducing every saved object and reviewed-negative measurement exactly: **native 14/21, half-source 13/21**. This is previously seen partial development support, not fresh model/camera performance, final-test accuracy or hydration measurement. No encoder session, proposal generation, photo decode, fit or training occurred.

Reviewed negative support: **0/18,266 native source pixels**, **0/18,308 half-source-equivalent pixels**. The half denominator differs because the partial polygon raster is resampled. UNKNOWN outside reviewed polygons stays UNKNOWN. No full-ROI Dice, full-image precision, clean-skin or clinical severity claim follows.

Hit rule remains >=3 active source-equivalent pixels AND >=10% of the reviewed polygon. Head threshold remains .50; optical field cutoff remains .04. The 3/116 retained pixels in C01/0 are a real residual signal but a miss under the frozen rule.

| Target | Source W×H | Proposal pixels / reviewed | Current head p | Native retained / reviewed | Half retained, result | First limiting stage |
|---|---|---:|---|---:|---|---|
| C00/0 (train, pul) | 640x640 | 185/207 | 0.352360 | 0/207 | 184, hit | fixed head / retained support |
| C00/1 (train, pul) | 640x640 | 192/235 | 0.422722 | 0/235 | 164, hit | fixed head / retained support |
| C01/0 (train, pul) | 640x640 | 62/116 | 0.360393, 0.531282 | 3/116 | 0, miss | fixed head / retained support |
| C01/1 (train, pul) | 640x640 | 0/148 | none | 0/148 | 84, hit | proposal insufficient |
| C02/1 (train, raw) | 458x457 | 2/74 | 0.185917 | 0/74 | 0, miss | proposal insufficient |
| C03/1 (train, raw) | 1080x1080 | 0/40 | none | 0/40 | 4, miss | proposal insufficient |
| C09/0 (validation, pul) | 640x640 | 0/185 | none | 0/185 | 0, miss | proposal insufficient |

Four targets are already below the hit rule in the saved final proposal (C01/1, C02/1, C03/1, C09/0); C02/1's two proposal pixels are additionally rejected by the head. Three have adequate proposal support but lose it at the fixed calibrated head: C00/0, C00/1 and C01/0 (59 pixels rejected, 3 retained). All represented components have an actual head feature row; no missing row or subsequent product filter was demonstrated by these records. Older stage-file head probabilities are not reported as current.

Processed/raw categories and frozen splits remain separate:

| Scope | Native | Half-source |
|---|---:|---:|
| TRAIN, processed PUL | 4/8 | 7/8 |
| TRAIN, dataset raw category | 3/5 | 2/5 |
| Seen validation, processed PUL | 3/4 | 2/4 |
| Seen validation, dataset raw category | 4/4 | 2/4 |

The dataset `raw` category is not independently verified natural provenance. Annotations are engineering visual material support, not expert biological dryness labels. Original rights limitations are retained in the local source ledger; this audit makes no new rights claim.

## Coordinate, crop and product boundary

The original `compare_native_dry_scale.py:46` writer serializes `sourceShape` as `[width,height]`. The initial audit reader wrongly reversed it; it failed on the non-square C02 source. Reading the writer and original image metadata established 458x457. The audit assertion was corrected to the actual schema and retained; no production coordinate bug or model gain is attributed to this audit fix.

All saved optical origins match the original scale record. Saved field dimensions match crop×factor, each crop is bounded within its SHA-verified source, and every reviewed polygon lies within the crop. Component rectangles and exact near/context crop boxes are included in the evidence. Source mapping is `source = origin + sampled/factor`. Current feature identity and fixed-head outputs match exactly. Some pinned context crops extend beyond the supplied optical crop and use its existing padding contract (e.g. C00/0 context x=-39); this explains the input boundary, but is not evidence that a real product mesh crop is incorrectly truncated. Altering context without identical source/payload proof would change the frozen feature contract and is not a warranted fix here.

All five sources containing these seven targets explicitly used an image-short-edge optical reference with **no full-face geometry**. Therefore same-source browser/camera/mesh/exclusion admission, anatomical numerator/denominator and final region/overview maps cannot be inferred from this optical replay. Missing payload does not automatically make a source out of scope. No old optical value is fabricated as a current API score. Native/half instability is retained as a model/proposal limitation, not cured by choosing the better scale per target.

Current product source was inspected: native masks/source origin, field×visible union, unique accepted source area, overview OR union, step=1 native maps, atomic score/map replacement and null-quality behavior remain intact. `local_health.py` still finalizes Karma **after** native dryness and optional V5 replacement. No code change means no method-version/history rewrite. This inspection does not replace the absent same-source product-admission evidence.

## Model and execution identity

- Calibrated head: `7f13c7cb4eb65a3fb44abf062563ee3aff605a6ef9ff3271c5e32e206fedb8e1`.
- ONNX encoder: `a93e5445326c8071cd4d013b6fde494d9054dd4842dacf97028ceaefc9eb1987`.
- Source encoder: `e50c812a76cb5003f426ae35a5b9aba4d8d8dd50a9f822d2a64046bac310143a`.
- Parity: `3f1bd96bb44041a80916168fa36c7ccc032598b1211f308b6e2dc081a5085490`.
- Fixed feature-row identity: `7c916c52e1364b83a20d679435b6e8299f1e301a415d050de6722fe48adeae22`.
- Audit record arithmetic: 2.890s; peak sampled RSS 52.38 MiB. This is not cache-free photo analysis latency. Offline cap250 MiB/reserve650 MiB; the separate 2500 MiB heavy model guard and 45s API deadline were not entered or changed.

The user's RAM recheck measured 1,556 MiB available at21:08:59UTC, below2500. No heavy inference was started. Existing records were sufficient for this finite diagnosis; there is no reason to wait for RAM for another unchanged model run.

## Preservation and remaining work

All 297 deployment file hashes, both launcher file hashes and existing BUILD_ID matched. Four normal launcher/backend/frontend/browser identities were verified (PID/start/executable/command, CWD or explicit browser profile). The foreground audit exited naturally; no temporary service, observer, lease or browser profile was created, no process was stopped, and no user record/profile was written. Normal TOGG remains open. No new build/typecheck/API run was needed because runtime files were unchanged. Previously completed runtime acceptance is not re-presented as new work.

Machine evidence: `docs/skin-dryness-closeout-20261017.json`; reproducible offline script: `scripts/skin-research/audit_dryness_seven_misses.py`. Full source/crop ledger and process preservation receipts remain outside Git under `cdc-progress/skin-dryness-closeout-20261017`.

Remaining concrete limits: the seven native optical misses, scale instability, and absent same-source real product anatomical admission. Fixing these would require separately authorized model/proposal/context work or actual same-source geometry evidence; this bounded task does not invent a repair. No new task, training, threshold search or data campaign starts.
