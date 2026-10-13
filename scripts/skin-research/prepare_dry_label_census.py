"""Supplement raw/weak Dry-Skin sources without treating their tags as flaking truth."""
import hashlib,json
from collections import defaultdict
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
manifest=json.loads((ROOT/'audit-results/skin-selected-20261011/manifest.json').read_text('utf8'))['rows']
prior={g for r in json.loads((OUT/'census.json').read_text('utf8'))['priorSHA'] for g in r['groups']};groups=defaultdict(list)
for r in manifest:
    if any(a['label'].lower()=='dry-skin' for a in r['annotations']):groups[r['group']].append(r)
rows=[]
for group,members in sorted(groups.items()):
    if group in prior:continue
    row=sorted(members,key=lambda r:(-(r['width']*r['height']),r['path'],r['sha256']))[0]
    assert hashlib.sha256(Path(row['absolutePath']).read_bytes()).hexdigest()==row['sha256']
    rows.append({**row,'censusIndex':len(rows)})
(OUT/'dry-label-selection.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
for start in range(0,len(rows),24):
    page=rows[start:start+24];sheet=Image.new('RGB',(1024,6*292),'#111111');draw=ImageDraw.Draw(sheet)
    for j,r in enumerate(page):
        x=j%4*256;y=j//4*292;im=Image.open(r['absolutePath']).convert('RGB');im.thumbnail((256,256));sheet.paste(im,(x+(256-im.width)//2,y+36+(256-im.height)//2))
        draw.text((x+3,y+2),f"{r['censusIndex']:03d} {r['sha256'][:8]}",fill='white');draw.text((x+3,y+17),f"{r['width']}x{r['height']} {r['family'][:22]}",fill='#bbbbbb')
    sheet.save(OUT/f'dry-label-sheet-{start//24:02d}.jpg',quality=95)
(OUT/'dry-label-census.json').write_text(json.dumps(dict(totalPhotos=sum(map(len,groups.values())),totalGroups=len(groups),previousGroups=len(set(groups)&prior),remainingGroups=len(rows),labelDoesNotEstablishFlaking=True),indent=2),'utf8')
print(dict(groups=len(groups),previouslyReviewedGroups=len(set(groups)&prior),remainingGroups=len(rows),sheets=(len(rows)+23)//24))
