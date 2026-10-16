# Frozen v1 vs v3 on the 15-photo positive supplement — single comparison (2026-10-16)

Research only. No training, calibration, threshold, NMS, mask or pose change; v1 stays the default; product acne stays
`accepted:false, file:null`. Review level: AI engineering review, not expert verification. Licence / photo rights unchanged.

**Exposure:** all 15 photos were in the 2026-10-15 Step0 TEST_CROSS_SOURCE inference. This is **not** an unused or independent
test, and person independence is not verified. The old label-scaled boxes from that run were not reused; inputs went through the
current product photo path. Source boxes in the package manifest were not shown or used as labels.

## Order (each step committed before the next)
2043063 protocol + fixed list + hashes (v1 b6fa6c05…, v3 94d18abb…, Step0 18e94a95… = frozen-models.json; ZIP and all 15 photo hashes verified)
→ 3c0c… preflight → 75dd934 labels and mask hashes (before inference) → one inference → score.

## Product preflight (unchanged gates)
5 of 15 pass: P003 (LEFT capture), P025, P050, P097 (FRONT), P069 (LEFT capture).
10 rejected and not evaluated: POSE — P049, P053, P077, P078, P092, P100, P102; BLURRY — P058, P089; BLURRY+POSE — P103.

## Labels (frozen before inference)
30 TARGET, 47 UNCERTAIN, 5 SCAR_PIGMENT on the 5 photos (P003 2, P025 8, P050 10, P069 6, P097 4 targets). Low resolution
(face width 253–370 px) makes many spots UNCERTAIN. All targets lie inside the reviewed mask. For the 2 side captures the product
analyses only the exposed cheek, so targets elsewhere count as misses for all three rows alike.

## Result (one Step0 run per photo; v1 and v3 on the same candidates/features; r = 0.03 face width, one-to-one matching)
| | Step0 + old filter | v1 | v3 |
|---|---|---|---|
| photos / targets | 5 / 30 | 5 / 30 | 5 / 30 |
| targets found | 13 (43%) | 13 (43%) | 13 (43%) |
| points | 31 | 31 | 30 |
| false on reviewed skin (mean / median per photo) | 9 (1.8 / 2) | 9 (1.8 / 2) | 8 (1.6 / 2) |
| duplicate | 3 | 3 | 3 |
| on UNCERTAIN | 6 | 6 | 6 |
| non-skin / outside review | 0 | 0 | 0 |

- **v3 vs v1: 0 targets lost, 0 gained.** v3 removed 1 point that v1 kept (P069, left cheek, probability 0.043): a false point on reviewed skin.
  v1 removed nothing on this set. False v3 − v1 = −1 (photo bootstrap 95% CI −3 … 0).
- Per photo (found / false, Step0 = v1 → v3): P003 1/0 → 1/0; P025 3/2 → 3/2; P050 3/2 → 3/2; P069 4/4 → 4/3; P097 2/1 → 2/1.
  Found target ids identical for all three: P003 P1; P025 P2 P4 P6; P050 P3 P12 P14; P069 P1 P3 P4 P8; P097 P1 P5.
- FRONT (3 photos, 22 targets): found 8/8/8, false 5/5/5. Side captures (2 photos, 8 targets): found 5/5/5, false 4/4/3.
- v3 gave noticeably lower probabilities than v1 to several kept true matches (lowest kept v3 probability 0.066 at threshold 0.044),
  so the margin is small; no point near a target was removed.
- Cost: chain median 0.81 s per photo; peak RSS 371 MiB.

## Separate reference tables (not pooled)
- Old DEV (108 targets): Step0 71 / 96 false; v1 70 / 78; v3 68 / 60 — v3 lost 3 targets vs v1 there.
- B negative reference (17 photos, 0 targets; reused frozen result, no re-inference): false 5 / 4 / 2.

## Answer
On these 5 evaluable supplementary positive photos, v3's lower false-point count did **not** cost any target that v1 found
(0 lost, 0 gained), and it removed 1 false point. With 5 photos, 30 targets and a single removed point, this neither confirms nor
refutes the DEV finding of 2–3 lost targets; it is not product acceptance or independent evidence. Remaining concrete limit: only
5 of 15 photos pass the unchanged product preflight, and target preservation on a larger, truly unused positive set is still unmeasured.

Before/after images (local only, not in Git): audit-results/acne-pos-supplement/figures/P003|P025|P050|P069|P097-step0-v1-v3.jpg
