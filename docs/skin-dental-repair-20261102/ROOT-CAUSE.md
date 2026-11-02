# Skin / Dental functional restoration — 2026-11-02

Baseline: GitHub `main` = `ea92fb442da534a5fd700608898d3891e04baf88`, verified remotely before checkout. Work is isolated on `codex/skin-dental-repair-20261102`. No merge, main push, production deployment, installed-build overwrite, model replacement or paid GPU activation is part of this change.

| Previous behavior | Root cause | Change | Verification |
|---|---|---|---|
| Overview arrows disabled for one finding; other regions have no arrows when empty | The parent region callbacks were unused; header arrows paged findings | A shared, persistent `HealthResultNavigation` uses the parent's cyclic region callbacks. Findings have separately labelled internal controls | Six-region render/source contract regression; new WEB journey evidence is reported separately |
| Finding labels and leader lines absent | `SkinFindingCallouts` existed but the result view passed no callouts; a dated comment documented the earlier label removal | Reconnect the existing renderer through `sourceBoundCallouts`; require matching capture ID, pose and source dimensions; never invent lesion points | Cross-session, cross-pose, missing-marker and inconclusive source tests |
| A selected eye/T-zone finding can have no matching label on the region's default photo | Finding classifiers may decide on a side pose, but the region's display always selected its default pose | Select the admitted frame belonging to the selected finding/count source. Retain the same capture-ID/pose/dimension guard. Callout selection and card selection use that source together | Discovered in the new real WEB journey; dedicated same-session side-source and stale-frame regressions |
| Narrow photo column cannot use wide label gutters | The existing responsive fallback only rendered a row of labels | Numbered photo anchors have short connectors and matching numbered label buttons; wide gutters remain available without squeezing the photo | Browser layout/selection checks; actual evidence identifies which layout ran |
| An empty region can appear negative even without regional measurements | The empty state checked the entire scan, not whether this page had measured rows | Distinguish not measured, inconclusive, and measured with no supported finding at regional scope | Positive, negative, missing and inconclusive contract fixtures |
| Eye-corner reference rank displayed as a percentage | A `severity` field was formatted like an area/probability in overview, card and history | Show 0–100 reference rank/visibility score. Explain the eye-corner geometry calculation. Real area fractions retain percent units | Multilingual render checks and history-unit regression |
| Side profile heavily zoomed | The display crop tightly framed the regional mesh | Side profiles retain the accepted face frame; other regional frames retain at least 72% of the accepted context | Source identity remains unchanged; WEB crop evidence is reported separately |
| Reassessment action depends on an inconclusive finding | The rescan callback was exposed only inside the inconclusive-details dialog | Expose the existing callback as a persistent secondary result action | Final WEB journey checks reassessment cancellation and preservation of the accepted record |
| Dental requires checkbox plus Save button | Persistence was attached to a manual result action | Save once directly from the validated analysis-completion boundary, capturing immutable sources, stable result ID and epoch guard. No render/history effect writes | Storage tests plus real UI save/reopen/delete/cancel checks |
| Dental source looks pixelated when a small mouth ROI is enlarged | Display crop could be much smaller than the result column; image identity was removed from display props | Full/detail switch; wider source crop; cap physical display pixels to source crop pixels; retain and check `photoId` and dimensions | Pixel-scale/source-crop observations, actual UI overlays and saved-photo reopening |
| Skin and Dental result controls use different visual conventions | Separate result layouts and CSS tokens | Shared navigation contract, 52 px controls, cyan action/selection color, dark panels, 26 px result cards and responsive columns | WEB evidence and native build/lint; AAOS runtime is a separate acceptance gate |

## Existing components reused

`SkinFindingCallouts`, `SkinFacePanel`, `SkinFindingsPanel`, `SkinFindingCard`, `RecordHistory`, `DentalResults`, `appendHealthRecord`, the cross-tab records lock, separately permitted photo stores and atomic deletion journals are retained. Existing save/privacy mechanisms are used; numerical autosave neither grants photo retention nor enables cloud synchronization.

The restored portrait candidates come from the project's curated Drive `Assets/Characters/Module Shots` collection, dated 2026-10-31, rather than newly generated artwork. They have new asset names so they cannot reuse an old `approved-v3` cache key. The original images remain in the repository. A separate private delivery manifest records source IDs, exact sizes and hashes; final visual-reference confirmation belongs in the review evidence.

## Health Result design contract

Page heading → scrollable module tabs → persistent previous/current/next control → source photo and result card → module actions/history. Previous/next region/view controls remain present for zero, one, multiple, unmeasured and inconclusive findings. Navigation cycles through overview and all anatomical views. Internal finding pagination has distinct labels. All controls have keyboard focus and at least 52 px primary touch targets. Photo overlays use the same source-coordinate viewBox as the image.

Dental preserves Front, Anatomical Right, Anatomical Left and Bite, its coverage card, accumulation appearance, adult-policy caries candidates and contour-orientation measurements. Similar visual structure does not equate the modules' measurement semantics.

## Persistence boundary

Dental results are admitted only after result/source validation and at least one measured view. Each accepted result receives one UUID, and a per-result attempt guard prevents repeated writes. Epoch, current result ID, parked state and service consent are checked again under the records lock. Photo writes receive the sources belonging to that accepted result, rather than mutable captures from a later session. Separate photo permission, pixel verification, source association, quota behavior and deletion recovery are retained. Reopening, rerendering or deleting a displayed result does not invoke autosave.

The native AAOS host loads the web application from its configured loopback origin; these portraits are web assets, not embedded APK assets. The isolated APK uses application ID `more.attune.automotive.prototype.debug.repair20261102`; no accepted package was replaced. A successful APK build is not AAOS runtime or vehicle/OEM acceptance.
