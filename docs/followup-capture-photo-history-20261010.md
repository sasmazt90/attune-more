# Capture and photo-history follow-up — 10 October 2026

This is a partial engineering delivery, not final user/clinical acceptance. Acne misses/false candidates remain open. The original user profile and numerical records are preserved; no new paid provider calls or voice/model-weight changes.

## Dental camera

The old front/side estimates used dimensionless nose offsets that changed with expression. The actual MediaPipe facial transform now supplies dental-only rotation in radians; skin and eyes retain their prior gates. Side views use 15 degrees as the minimum, with the existing maximum/pitch/roll limits. Analysis and native mouth quality use the original source frame, independent of preview crop/zoom.

Enamel visibility now uses supported columns across the native inner-mouth aperture, so dark mouth cavity height cannot dilute visible teeth. Warm ivory enamel is not also tongue support. Pink tissue classification requires the existing tissue saturation floor: a low-saturation pink illumination cast on enamel must not count as tissue. Resolution, opening, sharpness, light, clipped reflection, tongue and 1.4-second consecutive stability checks remain active. Backend and camera use the same native support; static dental uploads retain their previous palette.

Four licensed photographed views ran through production camera acquisition, actual MediaPipe, quality/pose, stability, capture and the local trained ONNX. Different participants are used; this is controller proof, not a four-pose physical test on one person. Negative controls deliberately blur/cover/clip the source and are never positive captures or clinical examples. Their backend reasons are respectively BLURRY; TEETH_NOT_VISIBLE/LIGHT_INVALID/BLURRY; and those plus SALIVA_OR_GLARE.

Camera method is dental-visible-v2. ONNX hash is eafaca8139e4447b1aa64375156aa47764affd91cf0594392b896ea78463bf03; weights and inference threshold unchanged. Existing upload method remains dental-visible-upload-v2.

## Durable skin photos

An independent Privacy & Permissions preference defaults OFF. It does not inherit temporary processing or numeric-history permission. Explicitly permitted new records save opaque source PNGs, pose, six meshes and source-bound local maps in IndexedDB, separate from numeric history. Numeric association and SHA-256 payload integrity are checked; typed map arrays survive reload. Missing historical photos are never reconstructed.

Limits are 32 MiB per record and 128 MiB total. Writes are single transactions, preserve earlier records on failure and do not evict them to make space. Acquisition cancellation/currentness and permission/record association are rechecked around hashing and the transaction. Numeric records survive photo-save errors. A record deletion removes its photos; photo revocation removes all stored photos while retaining numeric history. The local wipe clears both stores under the existing record lock. The controlled wipe check deliberately returns 503 on the shared-backend wipe request to avoid deleting the user's mental-session history; it proves local deletion and truthful partial status, not shared-backend wipe acceptance.

Three actual production scans survive complete browser close/relaunch, including the oldest outside the prior two-scan RAM cache. All six region/source/map associations, deletion and revocation are checked. Unit checks cover canceled writes, quota/size/total-budget abortion, corruption, typed arrays, record association and default-off behavior.

## Acne remains open

Product detection is deterministic CV, not a lesion-trained model: 320-face-pixel normalization, red center-surround at two scales, texture/baseline conjunction, compact connected components, anatomical ownership and skin/hair/occlusion exclusions. Resizing loses small detail; the red conjunction misses pale/nonred appearances; generic blackhat hair exclusion can remove dark round features. Beard antialiasing, moles, broad redness, pore texture and mask borders can create confounders.

The verified change is the local fill: the card/count, bounding circles and pixel fill now derive from the same real component list (appearance-cv-4). Count remains candidate-count; confidence is never severity. This does not close detection misses or false positives.

A separate native/640-face-pixel red/white compact-center alternative was developed on a separate source and synthetic confounders. Held-out annotations were frozen before prediction; test subjects were not used for threshold/model fitting. Two alternative detailed public sources had 12 selected appearance targets each. Old vs rejected alternative: source 03 TP 0→1, FN 12→11, FP in explicitly marked negative areas 0→2; teenager TP 0→2, FN 12→10, marked-area FP 0→0. Other candidates remain ungraded (13→36 and 3→5). These are limited manually selected appearance targets, not dermatologist lesion labels or full sensitivity/specificity. Both are outside capture-pose acceptance and are ROI engineering comparisons, not successful skin scans. The alternative was rejected and is absent from product code.

Six new Commons sources plus a CC0 teenager and a historical Wellcome image were examined. Torso/partial/no-face/extreme-side or historical-color cases were excluded from capture acceptance. A 280-frame NASA interview search also yielded no acceptable dental-positive frame; its actual rejection traces are retained locally. Earlier seven failed SCIN cases are not recycled as new success evidence.

Model/data rights were audited separately from code labels. ACNE04's original release restricts use to academic purposes; reuploaded CC BY labels do not supersede this. Tinny-Robot/acne declares Apache project licensing but does not identify training-image provenance/rights. Glowlytics declares MIT and ONNX availability but does not identify the acne training-data source/rights. Neither was imported into the product. The concrete missing input for a trained replacement is a verifiable commercially permitted weight/data lineage and sufficiently detailed, independent localized facial evaluation data. The checked candidates do not supply it; this is not a claim that no suitable model can exist.

Primary references:
- https://github.com/xpwu95/LDL (original academic-use restriction)
- https://huggingface.co/Tinny-Robot/acne (project license vs absent data provenance)
- https://huggingface.co/mufasabrownie/glowlytics-skin-models/blob/main/README.md (MIT/card, undocumented acne dataset origin)

## Fixture rights and attribution

No source photos or user images are committed. Ignored local artifacts preserve original/download and rights-page hashes. Geometry-only EXIF orientation/aspect fitting/letterbox and camera YUV roundtrip are declared; no generated face detail or cosmetic color enhancement.

Dental: NASA Eileen Collins portrait (NASA imagery policy); Basile Morin, Laughing woman with teeth, CC BY-SA 4.0; Ángelo González, Siberian woman portrait, CC BY 2.0; David Shankbone, Julia Roberts 2011 Shankbone 3 (cropped), CC BY 3.0.

Acne: Roshu Bangal, Acne vulgaris on a very oily skin, CC BY-SA 4.0; Sedef94, Acne Vulgaris xəstəliyi and Üzdə düyünlü və kistik sızanaqlar 01/03/06/11, CC BY-SA 4.0; NikosLikomitros, Teenager with acne, CC0; Wellcome Collection, Acne Vulgaris Wellcome L0070353, CC BY 4.0. Shared-alike derived audit images retain their source license. These photos are engineering fixtures and imply no endorsement.

## Verification and scope

42 focused checks, TypeScript and production build passed. Current-build camera, negative-source, persistent-photo and actual native-browser 200% checks are separately recorded in ignored audit-results/followup-closure-20261010. Production source/UI evidence is not relabeled from an older build. Existing eye answer memory/order/size, hearing counters/cancel/idempotent storage, source RGB/background and six meshes, Ahmet/Emel audio assets, carousel/menu/footer implementations are retained. No new physical/clinical or auditory acceptance is claimed. Known seven development high findings remain disclosed in docs/live-test-followup.md; this patch makes no new security-closure claim.

PR #2 remains Draft on fix/live-test-followup; no merge to main. Final SHA, BUILD_ID, served chunk/model/audio matching and exact current evidence appear in the local delivery report.
