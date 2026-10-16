# Acne human-review package (local; 2026-10-16)

This package is preparation for the next round of development. **The acne feature is not complete**, and acne stays disabled in production.
- Nothing was downloaded and no new labels were invented.
- Nothing is in Git or uploaded to any external service.
- The sealed Skin care v5 test is excluded. One TRAIN photo was dropped because its group overlaps that test (`summary.json`).

## Contents

There are 115 unique photos, all listed in `index.csv`.
- **TRAIN (80):** SmartSkinCare photos whose replayed product gate passed. The eyewear check is UNKNOWN.
- **DEV_HELDOUT20 (20):** the held-out development group. Use these labels only for evaluation, never for training. These photos are neither full product passes nor the independent final test.
- **REVIEWED_NEGATIVE (15):** TRAIN photos with a clean mask already reviewed by CDC, shown in green.

Each photo has its own folder under `photos/`:
- `source.*`: a byte-identical copy of the original. The SHA-256 is in `labels.json`.
- `overlay.jpg`: the existing labels drawn on the photo, for reference only. Do not draw on it.
- `labels.json`: the existing labels, plus the list of decisions you need to make.

## Overlay legend

| Colour | Meaning |
|---|---|
| Orange, thick, `P<id>` | Existing original Pimple box |
| Magenta, `C<id>` | Pimple box that conflicts with another class |
| Light blue, class abbreviation | Confounder label: Mole / Freckles / Pigmentation / Enlarged pores |
| Grey | Post acne / marks (scar or mark; UNKNOWN) |
| Yellow, `M<n>` | Step0 conf .30 candidate with no matching label. Status: UNKNOWN; it is neither acne nor negative. |
| White frame | Product crop |
| Green tint | Reviewed clean area (REVIEWED_NEGATIVE photos only) |
| Dark blue | Acne label from the source archive (on negative photos) |

## How to label: with the existing tool

The tool is `acne-appearance-capture.html`, copied unchanged from `scripts/skin-research/`. No new tool was written.

1. Open the html locally in a browser. It makes no network calls.
2. Choose the folder's `source.*` with **Dosya**. Keep `overlay.jpg` open next to it.
3. Draw rectangles, choosing a type for each. The tool does not import existing boxes, so redraw from the overlay.
   - **Görünür aday kutusu:** a confirmed or missing pimple. Pick a subtype (red, pale/white, skin-coloured) if one applies.
   - **İncelenmiş negatif alan:** reviewed clean skin, an existing box you decide is not acne, or a mole/freckle/pore confirmed as not acne.
   - **Belirsiz alan:** you cannot decide.
   - **Ölçülemeyen alan:** glare, hair or beard, blur, shadow.
4. Download the result with **Pikselsiz JSON indir**. Save the JSON next to the photo's folder. **Do not** use **Ayrı izinli PNG indir**.

Anything you do not draw stays UNKNOWN. It is never treated as negative.

**A decision for you first.** The tool asks for consent and rights records, and its own text says "do not open photos without a real permission record".
- These photos only have a publisher licence (CC BY 4.0, or the record in the CDC ledger). There is **no individual consent record** for any of them.
- Decide whether internal review of publisher-licensed photos is allowed under your rules.
- If it is, fill the fields honestly. Example: consent = `bireysel rıza yok – yayıncı lisansı CC BY 4.0`, rights = `<source archive + licence>`. Do not invent anything.

## Decisions to make per photo

These come from `labels.json` → `decisions`.

**Positive photos (TRAIN and DEV_HELDOUT20)**
1. `confirmEachPimpleBox`: is each P box a visible pimple? Yes → draw it as a candidate. No → mark it as a negative area. Unsure → mark it as an unclear area.
2. `resolveConflicts`: when a C box carries two classes, decide whether it is a pimple, a scar/mark or a mole. Do not silently rename it.
3. `confirmConfounderNotAcne`: is the confounder label that touches a pimple really not acne?
4. `reviewModelUnknownCandidates`: is each yellow M box a missed pimple or something else (pore, hair, glare, mole)?
5. Completeness: are all visible pimples inside the product crop boxed? Draw any missing ones as candidates.
6. Clean areas: mark the clearly clean skin areas as negative.
7. Mark the areas that cannot be measured.

**REVIEWED_NEGATIVE photos**
1. Is there really no visible pimple inside the green area? If there is one, draw it as a candidate; that means the mask is wrong.
2. Mark the areas that cannot be measured.
