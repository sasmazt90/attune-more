"""Native representative/augmentation alternatives; no new extraction or resizing in analysis."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013'
selection=json.loads((OUT/'pul-selection.json').read_text('utf8'));rows=[];tiles=[]
for index in (32,92,112):
    r=selection[index]
    choices=[dict(path=r['absolutePath'],sha256=r['sha256'],naturalRGB=r.get('naturalRGB')),*r['groupAlternatives']]
    for position,row in enumerate(choices):
        path=Path(row['path']);data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256']
        image=Image.open(path).convert('RGB');size=image.size;image.thumbnail((256,256));tile=Image.new('RGB',(256,286),'#111');tile.paste(image,((256-image.width)//2,0));ImageDraw.Draw(tile).text((3,259),f'PUL {index} variant {position} {size}\n{row["sha256"][:8]} CLAHE provenance',fill='white');tiles.append(tile)
        rows.append(dict(censusIndex=index,group=r['group'],variant=position,sourceSHA256=row['sha256'],sourcePath=str(path),sourceWidth=size[0],sourceHeight=size[1],naturalRGB=row['naturalRGB'],rights=r['rights']))
sheet=Image.new('RGB',(4*256,4*286),'#111')
for i,tile in enumerate(tiles):sheet.paste(tile,(i%4*256,i//4*286))
sheet.save(OUT/'pul-alternatives.jpg')
(OUT/'pul-alternative-selection.json').write_text(json.dumps(dict(records=rows,reviewed=False,sheetSHA256=hashlib.sha256((OUT/'pul-alternatives.jpg').read_bytes()).hexdigest()),ensure_ascii=False,indent=2),'utf8')
print(dict(variants=len(rows),groups=3))
