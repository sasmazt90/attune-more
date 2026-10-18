# Bounded robust dry/sag follow-up, 2026-10-13

Current baseline is `1f93e33289aed3ef3061adfe72597f5989d1bde0`; the attachment's older db3 baseline is not treated as current. **No further production algorithm is shipped.** Chin/overview sag v8, cheek v7 and dry v3 remain exact; other analysis sources, frontend, model and config hashes match the protected delivery.

Two new fixed hypotheses ran on the already selected local sources. This does not repeat the six previous failed trials or expand archives. No threshold search, training, model integration or hosted call. Selection adds only two previously visually inspected sag photos, closed before the 45-minute limit; both visibly smile and are not neutral acceptance positives.

| Hypothesis | Relevant positive support | Negative / regression | Decision / resources |
|---|---|---|---|
| Native DoG + robust median/MAD background | Natural partial 594aadd0 box at (194,326): 19 → 14 native candidate pixels | e1646fda reviewed forehead: 19 → 9 product pixels | Reject: loses partial positive support; 62.53s, sampled peak RSS 381.4 MiB |
| Native bright plate + robust background, extreme 1/2-pixel impulses removed | Processed 387e1700 first box: 0 → 80 candidates | Natural 0642d4ab product: 0 → 34 pixels | Reject: creates reviewed-negative support; 77.59s, sampled peak RSS 394.1 MiB |

Box counts are candidates in partial/weak annotation boxes, not labelled true-positive pixel counts or full ROI Dice. Exterior is unknown. Native before counts compare the old local native detector, whereas product before counts use the pinned normal v3 API output. These scopes are explicitly different. 387e1700 is processed with hand/cosmetic confounders; 594aadd0 is naturally photographed visible peeling with incomplete head and invalid product ROI. Neither becomes a complete-face acceptance example. c31892d1's earlier stage-by-stage loss diagnosis and source-coordinate layers remain preserved in the previous evidence; product v3 remains 0.066794 / 36 pixels.

The new robust trials identify the remaining failure more narrowly: thresholding fine DoG peaks still loses broad low-contrast peeling; replacing DoG with local bright prominence recovers broad fragments but accepts ordinary skin/reflection support. Native resolution and a robust background alone do not establish flake specificity. The rejected product overlays retain the exact false source pixels. No score floor, UI rounding change, copied raw candidates, or photo-specific rule is used.

## Actual normal automatic camera and history

Natural 55ec00b8 completed real browser MediaPipe → quality/FRONT pose → automatic camera capture → native crop → normal API → result → same-record history. Native YUV420 camera encoding preserves source dimensions without spatial/pose transforms; source file, camera bytes and captured pixel SHA are recorded separately. Request count 1, response count 1, hosted calls 0.

The visible smile/opening is a confounder, not a neutral sag positive. Chin/cheeks/overview return `null / EXPRESSION_OPEN_MOUTH_OR_SMILE`, show “—” and have no fabricated local map. This validates the full unavailable-result path, not sag detection success. 55ec00b8 utility mouth opening is just above 0.10; no guard was relaxed. e0da1a64 has unsupported FRONT yaw and visible smile. Existing a72ce06c fails the expression guard, b482028c complete-head framing, 3c472c6f unsupported side yaw; 515cc548 remains an API-only engineering replay with FRONT rejected. A neutral natural lower-fold positive across valid angles remains concretely open.

All seven new-result and history views use correct central Turkish labels. Raw dry values remain raw (overview 0.050109, UI ordinary 0%). Map x/y/step/photo associations and criterion/region clearing were checked; unavailable sag maps stay absent. Narrow and native Chrome 200% controls were reachable; history bytes unchanged. No old/new normalization or sampling contract changed, so previous v7/v8 separation remains. User records and the normal profile are not used by the isolated test profile.

Focused dry/sag/overview/reference regressions: 27 passed; typecheck passed. A separate production build validates the identical frontend sources; the functioning delivered build remains `S4upFfAkW8XUxxoM25UK5`. Normal shortcut ownership, 213 frontend source hashes, 18 served JavaScript hashes and 5 loaded-after-write backend source hashes passed. Both model/config hashes remain identical. PR #2 stays Draft; no main merge.

Machine evidence: `docs/dry-sag-robust-evidence-20261013.json`. Local full receipts/overlays: `audit-results/dry-sag-robust-followup-20261013`; browser evidence: `output/playwright/dry-sag-robust-followup-20261013`.
