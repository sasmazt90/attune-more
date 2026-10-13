# Dry and lower-chin follow-up, 2026-10-13

Baseline `db3e11ba5630fb270c4d49f96e1ea7ea107aff98`. Delivered BUILD_ID `S4upFfAkW8XUxxoM25UK5`. Commit is resolved from this file’s Git history; final normal-shortcut source/index/served-JS receipt remains in the local audit directory.

The implemented fix is limited to chin sag appearance: the normal mentolabial crease is no longer its fold target. The lower interior chin path requires independent image-edge support at the anatomical face silhouette, paired with the nearest contour support rather than an unrelated regional mean. Card, region map and overview still use unique observed eligible centers. Cheek v7 calculations/maps, bags v5/sampling v3, lines v4/impulse sampling, dark v4 and other methods remain unchanged. Missing visibility/quality stays unavailable. No photo/hash rule, fixed score, score floor, pose override, new training or new model.

## Actual results and limits

| Source / scope | Before | After | Source map pixels before / after |
|---|---:|---:|---:|
| 515cc548, prior natural lower-face diagnostic; automatic FRONT rejected | 29.355062 | 2.466456 | 353 / 66 |
| d3e8bb60, existing transformed/speckled FRONT replay, not natural camera acceptance | 0.015954 | 0.000000 | 13 / 0 |
| 0642d4ab, completed automatic FRONT, dry | 0.000000 | 0.000000 | 0 / 0 |
| 0642d4ab, completed automatic FRONT, sag | 0.000000 | 0.000000 | 0 / 0 |

The 515 cheek method remains identical to v7. Removing the ordinary chin contribution changes the overview to 2.466456; this is a scope correction, not improved clinical severity calibration or general sag accuracy. 05619d0a remains ambiguous, not a confirmed negative. The natural a72ce06c source passes RIGHT MediaPipe/capture conditions but the unchanged expression guard returns `EXPRESSION_OPEN_MOUTH_OR_SMILE` (smile geometry approximately -0.0838). No tolerance was widened. b482028c fails complete-head framing; 3c472c6f has unsupported yaw. Qualified neutral natural positive automatic FRONT/RIGHT/LEFT delivery remains open. Different people or rotated photos were not combined into a three-angle success.

## Dryness remains open

Product dry v3 is preserved: c31892d1 0.066794 → 0.066794, 36 → 36 map pixels. UI rounding remains ordinary integer rounding; no artificial 1% floor. Rejected hypotheses never entered the normal product.

Source selection closed within the first 45 minutes. The local manifest contains 687 PUL photos / 255 grouping families; 45 representatives were visually screened, alongside 20 Dry-Skin-tagged candidates, 12 local dry-negative photos, 18 fold candidates, 12 extra face candidates and 12 existing contour controls. This is bounded inspected scope, not inspection of all 687 originals or 255 independent people. PUL files are publisher CLAHE-tagged/processed sources, with visual enhancement and provenance review limits; their local support is not natural whole-face acceptance. Hands/nails and possible cosmetic peeling are confounders in 387e1700 / aaec14eb.

594aadd0 has visibly irregular white peeling but is a partial face: real browser snapshot fails `INVALID_ROI`; local evidence cannot be presented as whole-face success. e1646fda’s Dry-Skin label is not accepted as peeling truth: its inspected forehead shows pore/specular texture. Only the explicitly reviewed forehead rectangle is used as a flaking-negative ROI; outside remains unknown. Rights are publisher-declared / individual-photo review pending where recorded; all work was local, with no photo upload. No suitable natural complete-face flaking positive was found within the bounded selection.

c31892d1 is processed diagnosis evidence. At crop origin (110,63), scale 0.9563557506383936: native post-LBP/contrast candidates 1209; normalized DoG 1203, after LBP 1158, after contrast 830, after dark ring 517, components before anatomy 266, after source visibility 203, final anatomical/component support 36, encoded source map 36. Downsampling changes fine candidates, but many lost candidates are lashes/brows/hair boundaries or eye/earring reflections outside the target. Component size/compactness and contrast also reject visible peeling fragments. Coordinates/step/PNG support passed the actual API raster check; restoring every lost candidate would restore non-target signals. Representative local layers and source-aligned chin tracking are retained in the ignored audit folder.

| Dry hypothesis | Recorded effect | Decision |
|---|---|---|
| Native-only source-pixel components | e164 reviewed pore ROI 19 → 42 active pixels; some fine local candidates recovered, broad peeling missed | Reject |
| Local saturation-drop probe | Pore/specular peaks also desaturate; weak discriminator | Reject before deployment |
| Native two-scale coherent edges | 0642 natural negative gains 159 pixels; 36 gains support | Reject |
| Two-scale plus compact dark focus | 0642 still gains 123 pixels | Reject |
| Single-native plus compact focus | Pore ROI 19 → 38; 387 visible broad peeling still missed | Reject |
| Native local-RMS prominence | Selected positive local support and product maps become zero | Reject |

Counts in source boxes indicate candidate support only. The separate padded local probe includes 12 pixels of context (unknown outside the box) and uses controlled shrink when no valid product frame exists; these counts are not claimed product tensors or inside-box positives. No full-mask pixel precision/recall or Dice is inferred; Dry-Skin labels were not converted to flaking masks, and polygon/box outside was not made healthy negative. The remaining engineering issue is reliable bright peeling versus pore/reflection discrimination with connected low-contrast peeling support. A native input alone does not solve it; background statistics including the candidate can suppress true peeling. No architecture/dataset blame or unvalidated replacement is used.

## Runtime and history

A native-size YUV420 video fixture from the real 0642d4ab source completed the normal browser automatic single-FRONT scan, real MediaPipe, quality/pose, product crop, API, result and same-record history flow. The conversion is required camera encoding, not a spatial transform or pose adjustment; source-file SHA and captured PNG pixel SHA are separately recorded. The 515 result is a real normal API replay/history fixture, not a completed automatic positive scan. Twelve additional pinned photo payloads matched source/API; RIGHT/LEFT snapshots show only the visible cheek, and unsupported quality remains null.

New chin and overview v8 split from old v7 in both history scopes; unchanged cheek v7 and dry v3 remain comparable. Old records are not rewritten/recomputed. Actual map coordinates, step, photo ID, closed supported cells, exclusions, region/criterion clearing, all seven views/Turkish labels, narrow window and native Chrome 200% were verified in an isolated profile. Original photo/background/design/voices and normal user profile records are preserved. Hosted skin-type permission remains off in tests; no consent-true request was sent.

Validation: 37 focused tests passed; the subsequent direct-caller parity guard passed the 21 affected dry/sag/periorbital tests (subset, not 58 distinct tests). Typecheck and production build passed. Nine prior pinned inputs preserve 270 unrelated measurement pairs and all unrelated maps; twelve current photo payloads retain dry/cheek measurements and maps. Existing model/manifest SHA-256 remain `65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3` / `accc9ff193030bccde572ded39b1878fc7919e33daf62f2ac560c3357a83abfb`.

Trials are finite sequential CPU runs; wall durations and source pixel scope are in the machine JSON. Per-trial peak RSS was not sampled and is explicitly unknown. A timestamped global CPU/RAM/disk snapshot is included, without attributing other workloads to this task. No long training, archive expansion, paid call or AG source/process mutation.

Machine evidence: `docs/dry-sag-native-evidence-20261013.json`. Detailed local evidence: `audit-results/dry-sag-native-followup-20261013`; browser screenshots: `output/playwright/dry-sag-native-followup-20261013`. Partial positives, transformed regressions, weak labels and unknown areas remain distinguished.
