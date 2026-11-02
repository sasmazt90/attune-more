# Legacy branch reconciliation

All comparisons use current `main` `ea92fb442da534a5fd700608898d3891e04baf88`. No old branch was merged or substituted for the current application. The private evidence package contains exact branch SHAs and path-level tree comparisons for all twelve requested branches.

| Branch / PR | Earlier implementation | Current main / equivalence | Missing behavior / reuse | Architecture conflict |
|---|---|---|---|---|
| `feat/skin-findings-routine-20261023`, PR #6 | Earlier findings, colored regions, suggestions and research/training records | Branch is divergent; PR #6 is still an open draft. Current main has later source-aware findings/card/history architecture | Reuse the current findings data model and suggestions, rather than merging the earlier UI | Research training jobs and prior metrics are not the active runtime bundle |
| `integrate/skin-cloud-claude-20261027`, PR #7 | Skin UI and evidence safeguards | Branch is an ancestor; PR #7 merged at `c1184d3` | Current components already contain the useful functionality. Restore missing integration links | Do not restore cloud candidates as active product models |
| `feat/skin-product-refinement` | Three-angle regional typing, source-aware presentation | Ancestor of main; evolved in current code | Preserve side-source association, privacy and negative/unmeasured distinctions | Replacing current region fusion with the old UI would regress later contracts |
| `feat/skin-type-dry-sag-antigravity` | Dry/sag, hosted/type, acne and periorbital experiments | Divergent research history; later main owns current regional bundle and appearance pipeline | Relevant techniques and limitations are audit inputs; no model or threshold replacement | Candidate paths, method versions and research output semantics differ |
| `work/skin-roadmap-20261023` | Offline anatomical filters and staging | Divergent; not a reason to merge old product files | Retain source-coordinate/anatomical evidence discipline | Staging is not an accepted deployed detector |
| `claude/acne-measurement-audit` | Offline acne support filtering | Divergent research | Compare provenance and scope; current local V5 verifier remains unchanged | No mixing research support masks into product measurements |
| `research/cdc-acne-verifier-v4-20261017` | Earlier acne verifier research | Divergent historical implementation | Validation methodology only; do not substitute it for the currently configured V5 path | Different model/protocol |
| `research/dental-technical-closeout-20261017` | Source-bound dental decoder and technical evidence | Ancestor of main | Current decoder, result validator, history/photo stores reused | No older result schema rollback |
| `fix/dental-flow-ui-20261027`, PR #10 | Capture, skip/partial views and Dental UI | Ancestor; PR #10 merged at `01884bd` | Retain four views, missing-view states and detailed metric cards | Only the newly requested save lifecycle and common result design change |
| `fix/dental-upload-alignment-feedback-20261027`, PR #11 | Uploaded-photo alignment explanation | Ancestor; PR #11 merged at `84ccea4` | Preserve upload-specific limitations and source validation | Do not imply bite validation for a single upload |
| `fix/final-health-e2e-acceptance-20261030`, PR #18 | Current source/consent and health flow fixes | Ancestor; PR #18 is now merged at `e23147b`, superseding its older open status | Preserve cancellation, strict result validation and later fixes | Old E2E evidence cannot accept this new patch |
| `codex/aaos15-oem-e2e-20261031`, PR #19 | Skin cold-start staging and AAOS/vision fixes | Ancestor; PR #19 merged as current main; relevant paths identical | Preserve analysis deadlines, staged model preparation, local CPU ownership and native guards | No timeout/quality relaxation or production launcher changes |

PR #17 is also merged (`f2a05df`), including preparation portrait/inset work. Its presence does not mean the later curated Module Shots assets are already bundled: the baseline still referenced `*-preparation-approved-v3.png`.

## Callout provenance

Historical commit `9154891` connected `SkinFindingCallouts` from the result screen. Current main retained that component but removed the callout props and carried a comment dated 2026-10-26 describing a no-label product decision. The current task explicitly requests labels and connectors again. The new integration reuses the existing renderer with stricter capture-ID/pose/dimension binding; it does not transplant the older loose landmark fallback.

The parent already owns cyclic region handlers and keyboard navigation. The result screen now consumes those handlers. This restores the missing connection without introducing another region state machine.
