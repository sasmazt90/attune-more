# QA-25: missed acne detections

**Status: the three reported misses are explained and addressed. Accuracy stays NOT VERIFIED.** No labelled ground truth exists for these photographs, so nothing here is a precision or recall figure. "Looks like a lesion" means a person looked at a close-up.

**Reported by the owner:** Character 49's chin and jaw lesions were not reported, its forehead count was too low, and Character 11's spots near the mouth and chin were not reported.

## How it was traced

`scripts/qa/realistic/skin_acne_trace.py` runs the deployed models on the owner's photographs and records every acne-class box each detector returned, before any rule, and then what each rule did to it. Overlays of each photo and close-ups of each recovered lesion are in the evidence folder.

This is only the separate finding pipeline. The V5 heading was not touched, and V5 boxes are not added to these counts.

## What was happening

| Possible cause | Found? | Evidence |
|---|---|---|
| Detected, then filtered by a region rule | **Yes, the main cause** | Character 49's chin: 4 boxes of 0.37 to 0.68 in the front photo. The region classifier scored the chin 0.24 against a threshold of 0.60, so the row was `notSeen` and its boxes were never shown, although the person scored 0.995 |
| Anatomical filter excluding valid skin | **Yes** | Hairline, the skin between the brows and the jaw lie outside all five research regions. Character 49's front photo lost 0.65 and 0.45 forehead boxes this way, and its side photos lost 0.68, 0.63, 0.61, 0.56, 0.39 and 0.37 |
| Same finding seen in another pose | **Yes** | Each region counted from one fixed photo. Boxes near the 0.35 limit come and go with the crop: the deployed run counted 1 forehead lesion in the front photo, where this trace of the same photo finds 3, and a side photo holds 3 more that could be counted |
| Confidence threshold too high | Not changed | Many boxes sit below 0.35. Lowering it was not justified, and no threshold moved |
| Subclass mapping | No defect | Types map as designed. A generic `Akne` box stays unspecified unless a typed box covers it |
| Assigned to the wrong photo | No defect | Markers carry the photo they were measured on |
| Display discarding valid findings | No separate defect | The screen shows every row marked `seen`. The loss happens before it |
| Duplicate counts | Not introduced | Counting stays one photo per region, and boxes centred inside a stronger box stay merged |

## What changed

All in `services/core-api/skin_findings_v1.py`. Models, thresholds, the research regions, classifier inputs and measured areas are unchanged.

1. **A positive person's region is shown when one photo marks at least 2 lesions there**, even if the region classifier passed over it. One box alone stays hidden, because it is often a highlight, as on Character 11's nose tip. The row carries `decidedBy: markedLesions`, so it can be told apart.
2. **A lesion on facial skin outside the research regions counts in the nearest region.** Eyes, brows, lips and anything off the face are refused.
3. **Each region is counted from the one photo showing the most**, with the facing photo on a tie. Still one photo, so nothing is counted twice.

Boxes alone never make a person positive. Without a positive person decision, nothing changes.

## Results on the owner's photographs

The first table is what the application itself reported on the release candidate, with landmarks from the browser and frames through each platform's camera path. "Before" is the previous candidate, `4bb51b3`.

| Region | Character 49 on AAOS, before | After | Character 11 on WEB, before | After |
|---|---|---|---|---|
| Forehead | 1 | **5** | 4 | 4 |
| Right cheek | 5 | 5 | 4 | 5 |
| Left cheek | 5 | 6 | 2 | 2 |
| Chin | Not shown | **4** | Not shown | **3** |
| Nose | Not shown | Not shown | Not shown | Not shown |

The next table is the direct trace, which uses Python landmarks on the supplied photos. It is the one the close-ups come from. The two can differ slightly, because detection varies with the crop.

| Region | Character 49 before | After | Character 11 before | After |
|---|---|---|---|---|
| Forehead | 3 | **5** | 5 | 5 |
| Right cheek | 4 | 5 | 4 | 5 |
| Left cheek | 4 | 5 | Not shown (score 0.49) | **3** |
| Chin | Not shown (score 0.24) | **4** | Not shown (score 0.30) | **2** |
| Nose | Not shown | Not shown | Not shown | Not shown |

## Which lesions were recovered, and false positives

Fourteen boxes were recovered, 8 on Character 49 and 6 on Character 11. By eye on the close-ups:

- **12 look like real lesions:** all 8 on Character 49, and Character 11's left-cheek nodule, left-cheek papule of 0.39, chin spot of 0.43 and chin cluster of 0.39.
- **2 are doubtful, and are probably false positives:** Character 11's jaw box of 0.38 looks like a skin fold or shadow, and its left-cheek box of 0.44 holds fine bumps with no clear single lesion.
- **A box is not always one lesion.** Character 11's chin box of 0.39 spans several small spots, so its count can be low.

**Controls.** Three other people's photo sets had no box at or above 0.35 at all, and stayed negative with person scores of 0.14, 0.31 and 0.06. Three sets is a small control, and these are not known to be free of acne.

**What the change risks.** Counts rise for people already positive, and a region with two false boxes now shows where it stayed hidden before. The classifier no longer has the final say on such a region. That is the accepted cost of not hiding visible lesions, and the owner can review it through `decidedBy`.

## Not addressed

- Lesions below the 0.35 limit stay unmarked. Several visible spots on both characters fall here.
- Detection varies with the crop, so the same photo can give slightly different counts between runs with different landmarks.
- No ground truth exists, so this cannot say how many lesions are really there.
