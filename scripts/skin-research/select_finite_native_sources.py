"""Six finite new face groups from the local inventory, before model results."""
import hashlib,json
from collections import defaultdict
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/material-runtime-followup-20261013';old=ROOT/'audit-results/dry-sag-source-census-20261013'
rows=json.loads((ROOT/'audit-results/skin-selected-20261011/manifest.json').read_text('utf8'))['rows'];groups=defaultdict(list)
for r in rows:
    if r['source']=='face':groups[r['group']].append(r)
used={r['group'] for r in json.loads((old/'contour-selection.json').read_text('utf8'))}
used|={g for r in json.loads((old/'census.json').read_text('utf8'))['priorSHA'] for g in r['groups']}
used|={r['group'] for r in json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/unseen-face-selection.json').read_text('utf8'))}
chosen=[]
for g in sorted(set(groups)-used):
    r=sorted(groups[g],key=lambda r:(-r['width']*r['height'],r['sha256']))[0]
    if r['width']<600 or r['height']<600:continue
    path=Path(r['absolutePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256'];chosen.append({**r,'finiteReviewIndex':len(chosen),'selectionReason':'unreviewed full-resolution local face group; no age/clinical label selection','reviewStatus':'UNREVIEWED'})
    if len(chosen)==6:break
assert not (OUT/'finite-source-selection.json').exists();(OUT/'finite-source-selection.json').write_text(json.dumps(chosen,indent=2),'utf8')
sheet=Image.new('RGB',(3*320,2*344),'#111');draw=ImageDraw.Draw(sheet)
for i,r in enumerate(chosen):
    im=Image.open(r['absolutePath']).convert('RGB');im.thumbnail((320,320));x=i%3*320;y=i//3*344;sheet.paste(im,(x+(320-im.width)//2,y+24));draw.text((x+2,y+2),str(i)+' '+r['sha256'][:8],fill='white')
sheet.save(OUT/'finite-source-review.png');print([(r['finiteReviewIndex'],r['sha256'][:8]) for r in chosen])
