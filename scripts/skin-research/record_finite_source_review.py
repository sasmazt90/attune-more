"""Record actual finite contact inspection before native inference."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';rows=json.loads((OUT/'finite-source-selection.json').read_text('utf8'))
for i,row in enumerate(rows):
    row.update(naturalSinglePhoto=i==1,neutralLowerFace=False,verifiedContourPositive=False,reviewReason='visible multi-photo collage/black artificial occlusion; no natural contour acceptance' if i!=1 else 'single outdoor photograph; visible open smile, cap/eye shadow and partial lower contour; not a neutral sag positive')
(OUT/'finite-source-review.json').write_text(json.dumps(dict(rows=rows,inspected=6,usableNeutralContourPositive=0,remainingInventoryNotClaimedReviewed=True,clinicalLabelsNotInferred=True),indent=2),'utf8')
(OUT/'new-photo-selection.json').write_text(json.dumps([rows[1]],indent=2),'utf8')
