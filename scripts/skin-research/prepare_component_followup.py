"""Freeze one component experiment and a bounded genuinely unseen face selection."""
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-component-followup-20261013';OUT.mkdir(parents=True,exist_ok=True)
OLD=ROOT/'audit-results/dry-sag-source-census-20261013'
control=OLD/'flake-controls/controls-reviewed.json';c=json.loads(control.read_text('utf8'))
protocol=dict(frozenUTC=datetime.now(timezone.utc).isoformat(),baselineSHA='492949747554bd06ce06bb5ac2994949e54f4deb',fixedControlsSHA256=hashlib.sha256(control.read_bytes()).hexdigest(),changedVariable='native connected-component descriptors and explicitly reviewed material-object labels instead of 96px patch presence',proposalChanged=False,sourceGrayChanged=False,model='one L2-regularized logistic component gate; fixed p>=0.5; existing NumPy only',features=['logArea','elongation','fill','circularity','solidity','ringContrast','gradientDirectionCoherence','darkAdjacentFraction'],fitParameters=dict(regularization=1.,iterations=60),
    labels=dict(authority='engineering visible optical material/pores/reflection, not clinical diagnosis',positive='partial visible-material polygon only',negative='explicitly reviewed local pore/reflection support only',outsideReviewedAreas='unknown'),
    acceptance=dict(objectHit='>=3 original pixels and >=10% of reviewed positive material polygon; not pixel Dice/precision',proposalCeiling='Count missing proposals in the full object denominator; classify generator vs gate misses separately',positivePreservation='Retain every baseline-hit validation object and every proposal-hit thin-flake validation object',negativeSupport='At least 25% lower reviewed-negative active optical area than unchanged native proposal; no individual negative ROI above production-v3 optical area',product='Same accepted support for region/overview/map, same anatomical denominators, source colors unchanged, no duplicate pixels; real positive anatomy localization required',scale='Record native and half-resolution behavior separately; do not treat rescaled photo as new person'),
    sourceGroups='Original train/validation groups retained; no patch/source crosses splits; no person-independent claim',longTraining=False,productionActivationAllowed=False)
target=OUT/'protocol.json';assert not target.exists(),'Do not overwrite the pre-trial protocol';target.write_text(json.dumps(protocol,ensure_ascii=False,indent=2),'utf8')
tiles=[]
for r in c['controls']:
    path=Path(r['sourcePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sourceSHA256']
    x,y,w,h=r['roi'];im=Image.open(path).convert('RGB').crop((x,y,x+w,y+h));im=im.resize((w*4,h*4));d=ImageDraw.Draw(im)
    for a in range(0,w,20):d.line((a*4,0,a*4,h*4),fill=(0,170,200),width=1);d.text((a*4+2,2),str(a),fill='cyan')
    for b in range(20,h,20):d.line((0,b*4,w*4,b*4),fill=(0,170,200),width=1);d.text((2,b*4+2),str(b),fill='cyan')
    im.save(OUT/f'control-{r["controlIndex"]:02d}-source-grid.png')
    tile=Image.new('RGB',(330,354),'#111');small=im.copy();small.thumbnail((330,330));tile.paste(small,(0,24));ImageDraw.Draw(tile).text((3,3),f'C{r["controlIndex"]} {r["split"]} {r["sourceSHA256"][:8]}',fill='white');tiles.append(tile)
for start in range(0,len(tiles),8):
    sheet=Image.new('RGB',(4*330,2*354),'#111')
    for j,t in enumerate(tiles[start:start+8]):sheet.paste(t,(j%4*330,j//4*354))
    sheet.save(OUT/f'component-source-review-{start//8}.png')
manifest=ROOT/'audit-results/skin-selected-20261011/manifest.json';rows=json.loads(manifest.read_text('utf8'))['rows'];groups=defaultdict(list)
for r in rows:
    if r['source']=='face':groups[r['group']].append(r)
contour={r['group'] for r in rows if r['source']=='face' and {a['label'].lower() for a in r['annotations']}&{'nasolabial_fold','marionette_line','mental_crease'}}
prior={g for r in json.loads((OLD/'census.json').read_text('utf8'))['priorSHA'] for g in r['groups']}
outside=set(groups)-contour;unseen=sorted(outside-prior)
indices=np.linspace(0,len(unseen)-1,min(96,len(unseen)),dtype=int);chosen=[]
for index in indices:
    members=groups[unseen[index]];r=sorted(members,key=lambda r:(-(r['width']*r['height']),r['path'],r['sha256']))[0]
    assert hashlib.sha256(Path(r['absolutePath']).read_bytes()).hexdigest()==r['sha256']
    chosen.append({**r,'censusIndex':len(chosen),'selectionRank':int(index),'reviewStatus':'unreviewed'})
(OUT/'unseen-face-selection.json').write_text(json.dumps(chosen,ensure_ascii=False,indent=2),'utf8')
(OUT/'selection-receipt.json').write_text(json.dumps(dict(manifestSHA256=hashlib.sha256(manifest.read_bytes()).hexdigest(),faceGroups=len(groups),outsidePriorContourLabelScope=len(outside),previouslyReviewedOutsideThatScope=len(outside&prior),eligibleUnseenGroups=len(unseen),selectedGroups=len(chosen),remainingUnreviewedGroups=len(unseen)-len(chosen),selection='96 evenly spaced group-hash ranks; largest native representative, before pose, visual labels or model results; no exclusion for missing contour label',rightsUnchanged=True),indent=2),'utf8')
print(json.dumps(dict(frozenProtocolSHA256=hashlib.sha256(target.read_bytes()).hexdigest(),selectedFaceGroups=len(chosen),remainingUnreviewed=len(unseen)-len(chosen))))
