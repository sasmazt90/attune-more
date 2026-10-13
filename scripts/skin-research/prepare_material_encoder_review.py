"""Finite added TRAIN components from existing reviewed source inventories."""
import hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-material-contour-20261013';OUT.mkdir(exist_ok=True)
CENSUS=ROOT/'audit-results/dry-sag-source-census-20261013';sys.path.insert(0,str(ROOT/'services/core-api'))
from native_flake_support import proposal_tile,VERSION
from material_component_features import describe,component_crops
cv2.setNumThreads(1)
old=json.loads((ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json').read_text('utf8'))['controls'];used={r['group'] for r in old};sources=[]
for domain,counts in [('pul',{'F':6,'P':3,'C':2,'H':2}),('dry-label',{'F':4,'P':3,'C':2})]:
    inventory=json.loads((CENSUS/(domain+'-selection.json')).read_text('utf8'));review=json.loads((CENSUS/(domain+'-visual-review.json')).read_text('utf8'))['records']
    for code,count in counts.items():
        for r in [r for r in review if r['observationCode']==code and r['group'] not in used][:count]:
            i=r.get('censusIndex',r.get('index'));source=inventory[i];assert source['sha256']==r['sha256'];used.add(r['group']);sources.append({**source,'reviewDomain':domain,'reviewIndex':i,'reviewCode':code,'split':'train'})
selection=OUT/'added-train-source-selection.json';assert not selection.exists();selection.write_text(json.dumps(sources,indent=2),'utf8')
tiles=[];rows=[];overview=[]
for si,row in enumerate(sources):
    data=Path(row['absolutePath']).read_bytes();assert hashlib.sha256(data).hexdigest()==row['sha256'];source=cv2.imread(row['absolutePath']);h,w=source.shape[:2]
    # Existing reviewed source is opened once at native scale. A bounded central
    # window supplies candidates for visual review, not positive pixel truth.
    span=min(512,h,w);x0=max(0,(w-span)//2);y0=max(0,(h-span)//2);image=source[y0:y0+span,x0:x0+span];metric=min(h,w)/640
    field=proposal_tile(image,metric);ids,components=describe(image,field,metric)
    # Spatial diversity plus area diversity; no class predictions or validation.
    selected=[];seen=set()
    for c in sorted(components,key=lambda r:r['area'],reverse=True):
        cell=tuple((np.array(c['centroid'])//(span/3)).astype(int))
        if cell not in seen:selected.append(c);seen.add(cell)
        if len(selected)>=8:break
    for c in sorted(components,key=lambda r:r['area']):
        if c not in selected:selected.append(c)
        if len(selected)>=12:break
    for c in selected:
        crops,boxes=component_crops(image,c,metric);cx,cy=c['centroid'];a=max(0,int(cx)-32);b=max(0,int(cy)-32);patch=image[b:min(span,b+64),a:min(span,a+64),::-1].copy();mask=ids[b:b+patch.shape[0],a:a+patch.shape[1]]==c['componentId'];patch[mask]=(.65*patch[mask]+.35*np.array([0,255,255])).astype(np.uint8)
        entry=dict(**c,index=len(rows),sourceIndex=si,sourceSHA256=row['sha256'],group=row['group'],split='train',domain=row['reviewDomain'],sourceReviewCode=row['reviewCode'],cropOrigin=[x0,y0],coordinateScale=metric,label=None,reviewed=False,cropBoxes=boxes)
        rows.append(entry);tile=Image.new('RGB',(200,224),'#111');tile.paste(Image.fromarray(patch).resize((200,200)),(0,24));ImageDraw.Draw(tile).text((2,2),f'{entry["index"]} S{si} {row["reviewCode"]} {c["area"]}px',fill='white');tiles.append(tile)
    im=Image.fromarray(source[:,:,::-1]);im.thumbnail((256,256));tile=Image.new('RGB',(256,280),'#111');tile.paste(im,(0,24));ImageDraw.Draw(tile).text((2,2),f'S{si} {row["reviewDomain"]} {row["reviewCode"]} {row["sha256"][:8]}',fill='white');overview.append(tile)
for collection,prefix,per,width,height in [(tiles,'train-components',20,200,224),(overview,'train-sources',20,256,280)]:
    for start in range(0,len(collection),per):
        sheet=Image.new('RGB',(5*width,4*height),'#111')
        for j,tile in enumerate(collection[start:start+per]):sheet.paste(tile,((j%5)*width,(j//5)*height))
        sheet.save(OUT/(prefix+f'-{start//per}.png'))
(OUT/'added-components-unreviewed.json').write_text(json.dumps(dict(rows=rows,proposalVersion=VERSION,sourceGroups=len(sources),fitExecuted=False),indent=2),'utf8')
print(json.dumps(dict(sources=len(sources),components=len(rows),pages=(len(rows)+19)//20)))
