"""New native proposals associated with existing labels; no relabeling or fit."""
import hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-dry-scale-20261013'
sys.path.insert(0,str(ROOT/'services/core-api'))
from native_flake_support import proposal_tile,PARAMETERS,VERSION
from component_flake_gate import components,masks
import component_flake_gate as C
cv2.setNumThreads(1)
labels=ROOT/'audit-results/dry-sag-component-followup-20261013/object-labels.json';controls=json.loads(labels.read_text('utf8'))['controls']
comparisons=json.loads((OUT/'independent-v3-comparison.json').read_text('utf8'))['rows']
protocol=OUT/'native-gate-protocol.json';assert not protocol.exists()
protocol.write_text(json.dumps(dict(reason='Proposal now captures 17/21 native materials and 7/8 familiar validation; high pore/reflection support requires component separation, not missing-proposal rescue',labelsSHA256=hashlib.sha256(labels.read_bytes()).hexdigest(),proposalVersion=VERSION,fit='one L2=1 logistic, p>=.5, max60 Newton iterations; original eight geometric/ring descriptors',labelAssignment='>=50% component inside existing material or reviewed-negative mask; any UNKNOWN overlap excluded; no source/group split crossing',acceptance='Preserve existing single-MSER object hits, improve familiar object capture; reviewed negatives within prior optical limit; no meaningful new product false map',independentFinalTest=False),indent=2),'utf8')
rows=[];tiles=[]
for control,comparison in zip(controls,comparisons):
 a,b=comparison['cropOrigin'];x,y,w,h=control['roi'];s=comparison['referenceSpan']/640;pad=max(64,int(np.ceil(40*s)));source=cv2.imread(control['sourcePath']);c=min(source.shape[1],x+w+pad);d=min(source.shape[0],y+h+pad);crop=source[b:d,a:c];gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
 field=proposal_tile(crop,s);original=C.proposal;C.proposal=lambda g:field
 try:raw,ids,cc=components(gray)
 finally:C.proposal=original
 known,_=masks(source.shape[:2],control);known={k:v[b:d,a:c] for k,v in known.items()}
 for component in cc:
  xx,yy,ww,hh=component['rect'];mask=ids[yy:yy+hh,xx:xx+ww]==component['nativeComponentId'];area=component['sourcePixels']
  overlap={k:float((mask&(v[yy:yy+hh,xx:xx+ww]>0)).sum()/area) for k,v in known.items()}
  label=1 if overlap['visible-material']>=.5 else 0 if overlap['reviewed-non-flake']>=.5 else None
  if overlap['unknown']>0:label=None
  if label is None:continue
  features=list(component['features']);features[0]=float(np.log1p(area/(s*s)))
  entry={**component,'componentIndex':len(rows),'controlIndex':control['controlIndex'],'sourceSHA256':control['sourceSHA256'],'group':control['group'],'split':control['split'],'kind':control['kind'],'coordinateScale':s,'sourceCropOrigin':[a,b],'features':features,'label':label,'overlap':overlap,'reviewed':False};rows.append(entry)
  cx,cy=component['centroid'];a0=max(0,int(cx)-20);b0=max(0,int(cy)-20);im=crop[b0:b0+40,a0:a0+40,::-1].copy();m=ids[b0:b0+40,a0:a0+40]==component['nativeComponentId'];im[m]=(.6*im[m]+.4*np.array([0,255,255])).astype(np.uint8);tile=Image.new('RGB',(160,190),'#111');tile.paste(Image.fromarray(im).resize((160,160)),(0,30));ImageDraw.Draw(tile).text((2,2),f'{entry["componentIndex"]} C{control["controlIndex"]} L{label} {control["split"]}\n{area}px',fill='white');tiles.append(tile)
for start in range(0,len(tiles),32):
 sheet=Image.new('RGB',(640,1520),'#111')
 for j,t in enumerate(tiles[start:start+32]):sheet.paste(t,(160*(j%4),190*(j//4)))
 sheet.save(OUT/f'native-gate-review-{start//32}.png')
(OUT/'native-gate-unreviewed.json').write_text(json.dumps(dict(rows=rows,features=C.FEATURES,labelsSHA256=hashlib.sha256(labels.read_bytes()).hexdigest(),fitExecuted=False),indent=2),'utf8')
print(json.dumps(dict(components=len(rows),pages=(len(rows)+31)//32,train=sum(r['split']=='train' for r in rows),validation=sum(r['split']=='validation' for r in rows))))
