# Belirginlik (severity) regressors — re-fit and saved (2026-10-26)

Exporter: `export_sev.py` (research recipes `sev_final.py` / `sev_bands.py`, cached embeddings, no new data).
Parity: `sev_parity.py` / `sev_parity.json` (production crops + embedder vs research cache: max |diff| 0.0 on 6 rated persons;
identical percentiles). Machine-readable numbers: `REPORT_sev.json`.

## Reproduction

| id | positives (rated 1/2/3) | α | ρ fixed-α re-run (recorded) | ρ nested re-run (recorded) |
|---|---|---|---|---|
| eyeBags | 48 (20/20/8) | 1000 | 0.6245 (0.62) | 0.5757 (0.5757) |
| darkCircles — research-selected combo, **not exported** | 54 (17/26/11) | 1000, w=1 | 0.7162 (0.72) | 0.7466 (0.7466) |
| darkCircles — **exported: embedding-only arm** | 54 | 1000 | 0.6987 | 0.6550 (0.6550, `emb` arm) |
| hoodedEyelids | 31 (11/17/3) | 300 | 0.7312 (0.73) | 0.6946 (0.6946) |
| crowsFeet | 45 (24/14/7) | 1000 | 0.7048 (0.70) | 0.6734 (0.6734) |
| foreheadLines | 34 (12/14/8) | 300 | 0.6038 (0.60) | 0.5979 (0.5979) |
| acneMarks | 38 (10/20/8) | 300 | 0.4196 (0.42) | 0.4063 (0.4063) |

Fixed-α = `sev_bands.py` protocol (α fixed afterwards, 20×5-fold; slightly optimistic, the handoff number).
Nested = `sev_final.py` (α chosen in inner 4-fold CV). coldSore: no model (ρ too low). downturnedCorners: not defined.

darkCircles: the research-selected model uses a DINOv2 logit column from `rf/dino_logit_index.json`, which no saved
script produces; the best re-derivation reached r=0.972 (not equal), so that input would have an unknown definition.
The research's own embedding-only arm is exported instead and flagged (`selectedInResearch:false`).

## Input contract

Rows = (view, crop) embeddings (front + 20° sides; a side photo gives only its camera-facing crop):
eyeBags/darkCircles under_L,under_R (4 rows); hoodedEyelids lid_L,lid_R (4); crowsFeet corner_L,corner_R (4);
foreheadLines forehead (3); acneMarks cheek_L,cheek_R,jaw (7). Feature = plain mean of all rows; prediction =
coef·((x−mean)/scale)+intercept; score = midrank percentile among pooled out-of-fold predictions of rated positives
(20 repeats × KFold(5)). Missing row → no score (research persons always had every row).
Production computes the same prediction from per-photo row terms (`skin_findings_severity.row_terms` / `from_terms`;
the Ridge model is linear in the row mean), verified equal to the direct computation on K-217 for all 6 models.

## Caveats

Ground truth = Claude's blind 1–3 ratings of synthetic positives, not a dermatologist. Percentile is relative to 31–54
synthetic positives and is shown only when the classifier marks the finding as seen. Use nested ρ (0.58 / 0.66 / 0.69 /
0.67 / 0.60 / 0.41). hoodedEyelids has only 3 "belirgin" ratings; acneMarks mainly separates the top band. Severity at
production LEFT/RIGHT angles is untested. Served models are fitted on 100 % of positives, the reference on 80 % folds
(slight shrinkage difference, not quantified).

## Files (sha256)

| file | sha256 |
|---|---|
| findings-v2/severity/eyeBags.json | b140e5a91eeb185d8febb71328d03a2c9e43148cce29d2f8f36b02bd2ba4b692 |
| findings-v2/severity/darkCircles.json | 144531cf334f751e8a1c548552cdfb71c96c332bd513af44ca28c259ddf08b23 |
| findings-v2/severity/hoodedEyelids.json | 346cc675ea0c910d760ef71a5acc8464521b11402b3a74195880f417140ef603 |
| findings-v2/severity/crowsFeet.json | bb44af67b2db8b2490694ed10fda6911888e588f6de556ca6899a6121cc126de |
| findings-v2/severity/foreheadLines.json | 239300f8168979be8c16b5bdbf4e63a28c1686a9095f3861d68fa161fa1676ec |
| findings-v2/severity/acneMarks.json | c6a9088c5f0dfa85eae5daa5087c0393fe63abf56718732244757150e9b5a4da |
