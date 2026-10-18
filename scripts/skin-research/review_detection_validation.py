"""Frozen selected validation visualization; no training/test/tuning."""
from pathlib import Path
import json,torch
from PIL import Image,ImageDraw
import detection_pretrained_acne as candidate
run=candidate.run;OUT=candidate.OUT
selection=json.loads((OUT/'selection.json').read_text());manifest=json.loads((run.ROOT/'audit-results/acne-trained-20261010/annotations-private.json').read_text());rows,images=run.native.load_rows(manifest,'validation')
torch.set_num_threads(2);model=candidate.create();model.load_state_dict(torch.load(OUT/'selected.pt',weights_only=True));pred=run.predictions(model,rows,images)
metric=run.native.metrics(rows,pred,selection['threshold']);(OUT/'validation.json').write_text(json.dumps(dict(selection=selection,metrics=metric,protectedTestNotLoaded=True),indent=2),'utf8')
for row,image,proposals in zip(rows,images,pred):
 visible=[p for p in proposals if p['confidence']>=selection['threshold']];up,ug=run.native.matches(visible,row['boxes']);im=Image.fromarray(image);d=ImageDraw.Draw(im)
 for i,box in enumerate(row['boxes']):d.rectangle(box,outline='green' if i in ug else 'red',width=2)
 for i,p in enumerate(visible):d.rectangle(p['box'],outline='green' if i in up else 'magenta',width=1)
 im.save(OUT/f"validation-{row['index']}-review.png")
print(json.dumps({k:v for k,v in metric.items() if k!='details'},indent=2))
