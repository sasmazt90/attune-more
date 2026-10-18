"""Full component/context views and existing split fingerprint comparison."""
import hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
from native_flake_support import proposal_tile
from material_component_features import describe
sources=json.loads((OUT/'added-train-source-selection.json').read_text('utf8'));rows=json.loads((OUT/'added-components-unreviewed.json').read_text('utf8'))['rows']
old=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls'];tiles=[]
def tile(image,caption,size=(256,280)):
    im=Image.fromarray(image[:,:,::-1]);im.thumbnail((size[0],size[1]-24));out=Image.new('RGB',size,'#111');out.paste(im,(0,24));ImageDraw.Draw(out).text((2,2),caption,fill='white');return out
sheet=Image.new('RGB',(1024,1120),'#111')
for j,c in enumerate(old):sheet.paste(tile(cv2.imread(c['sourcePath']),f'C{c["controlIndex"]} {c["split"]} {c["sourceSHA256"][:8]}'),((j%4)*256,(j//4)*280))
sheet.save(OUT/'existing-label-source-context.png')
indices=[12,13,14,15,16,17,18,19,38,39,41,42,43,52,60,63,64,65,86,87,88,89,90,91,98,99,100,101,102,133,136,138,144,145,146,147,148,149,150,151,157,158,159,161,162,181,183,184,186,218,219,220]
cv2.setNumThreads(1);cache={}
for index in indices:
    r=rows[index];si=r['sourceIndex']
    if si not in cache:
        source=cv2.imread(sources[si]['absolutePath']);x,y=r['cropOrigin'];span=min(512,*source.shape[:2]);im=source[y:y+span,x:x+span];field=proposal_tile(im,r['coordinateScale']);ids,cc=describe(im,field,r['coordinateScale']);cache[si]=(im,ids)
    im,ids=cache[si];x,y,w,h=r['rect'];pad=max(8,int(16*r['coordinateScale']));a=max(0,x-pad);b=max(0,y-pad);c=min(im.shape[1],x+w+pad);d=min(im.shape[0],y+h+pad);preview=im[b:d,a:c].copy()
    mask=(ids[b:d,a:c]==r['componentId']).astype(np.uint8);contours=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0];cv2.drawContours(preview,contours,-1,(255,255,0),1);tiles.append(tile(preview,f'{index} S{si} complete component',(256,280)))
for start in range(0,len(tiles),16):
    sheet=Image.new('RGB',(1024,1120),'#111')
    for j,t in enumerate(tiles[start:start+16]):sheet.paste(t,((j%4)*256,(j//4)*280))
    sheet.save(OUT/f'full-component-context-{start//16}.png')
def phash(image):
    gray=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32);dct=cv2.dct(gray)[:8,:8];return dct>np.median(dct.ravel()[1:])
refs=[(c,phash(cv2.imread(c['sourcePath']))) for c in old];matches=[]
for i,r in enumerate(sources):
    p=phash(cv2.imread(r['absolutePath']))
    for c,q in refs:
        distance=int((p!=q).sum())
        if distance<=8:matches.append(dict(sourceIndex=i,oldControlIndex=c['controlIndex'],oldSplit=c['split'],distance=distance))
(OUT/'source-nearcopy-check.json').write_text(json.dumps(dict(matches=matches,scope='selected 22 versus preserved 16; full-image pHash<=8 plus manual contextual review; no person identity guarantee'),indent=2),'utf8')
print(json.dumps(matches))
