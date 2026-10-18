"""Immutable PUL and lower-contour census, excluding actual prior review groups.
Selection precedes photometric experiments; contact sheets are for human review.
"""
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013';OUT.mkdir(parents=True,exist_ok=True)
manifest=ROOT/'audit-results/skin-selected-20261011/manifest.json';rows=json.loads(manifest.read_text('utf8'))['rows']
prior={}
for name in ['dry-sag-product-20261013','dry-sag-native-followup-20261013','dry-sag-robust-followup-20261013']:
    folder=ROOT/'audit-results'/name
    for path in [*folder.glob('*index.json'),folder/'source-selection.json',folder/'additional-sag-selection.json']:
        if not path.exists():continue
        value=json.loads(path.read_text('utf-8-sig'))
        if not isinstance(value,list):continue
        for r in value:
            if isinstance(r,dict) and r.get('sha256'):prior.setdefault(r['sha256'],[]).append(str(path.relative_to(ROOT)))
prior_groups={r['group'] for r in rows if r['sha256'] in prior}
all_groups=defaultdict(list)
for r in rows:all_groups[r['group']].append(r)
pul=defaultdict(list);contour=defaultdict(list)
for r in rows:
    labels={a['label'].lower() for a in r['annotations']}
    if 'pul' in labels:pul[r['group']].append(r)
    if r['source']=='face' and labels&{'nasolabial_fold','marionette_line','mental_crease'}:contour[r['group']].append(r)
def representatives(groups):
    result=[]
    for group,members in sorted(groups.items()):
        if group in prior_groups:continue
        # Deterministic source representative, not selection by model success.
        r=sorted(members,key=lambda r:(-(r['width']*r['height']),r['path'],r['sha256']))[0]
        assert hashlib.sha256(Path(r['absolutePath']).read_bytes()).hexdigest()==r['sha256']
        alternatives=[dict(sha256=x['sha256'],path=x['absolutePath'],family=x['family'],naturalRGB=x.get('naturalRGB')) for x in all_groups[group] if x['sha256']!=r['sha256']]
        result.append({**r,'censusIndex':len(result),'groupAlternatives':alternatives,'reviewStatus':'unreviewed'})
    return result
selected={'pul':representatives(pul),'contour':representatives(contour)}
for kind,reps in selected.items():(OUT/(kind+'-selection.json')).write_text(json.dumps(reps,ensure_ascii=False,indent=2),'utf8')
def sheets(kind,reps):
    cell=256;cols=4;page_size=24
    for start in range(0,len(reps),page_size):
        page=reps[start:start+page_size];sheet=Image.new('RGB',(cols*cell,6*(cell+36)),'#111111');draw=ImageDraw.Draw(sheet)
        for index,r in enumerate(page):
            x=index%cols*cell;y=index//cols*(cell+36)
            im=Image.open(r['absolutePath']).convert('RGB');im.thumbnail((cell,cell))
            sheet.paste(im,(x+(cell-im.width)//2,y+36+(cell-im.height)//2))
            draw.text((x+3,y+2),f"{r['censusIndex']:03d} {r['sha256'][:8]} g:{r['group'][:8]}",fill='white')
            draw.text((x+3,y+17),f"{r['source']} {r['width']}x{r['height']}",fill='#bbbbbb')
        sheet.save(OUT/f'{kind}-sheet-{start//page_size:02d}.jpg',quality=95)
sheets('pul',selected['pul'])
receipt=dict(generatedUTC=datetime.now(timezone.utc).isoformat(),manifestSHA256=hashlib.sha256(manifest.read_bytes()).hexdigest(),priorSHA=[dict(sha256=k,reviewFiles=v,groups=sorted({r['group'] for r in rows if r['sha256']==k})) for k,v in sorted(prior.items())],
    pul=dict(photos=sum(map(len,pul.values())),groups=len(pul),previouslyReviewedGroups=len(set(pul)&prior_groups),remainingGroups=len(selected['pul'])),
    contour=dict(labels=['nasolabial_fold','marionette_line','mental_crease'],groups=len(contour),previouslyReviewedGroups=len(set(contour)&prior_groups),remainingGroups=len(selected['contour']),otherFaceGroupsOutsideThisLabeledScope=len({r['group'] for r in rows if r['source']=='face'}-set(contour))),
    humanReviewNotSubstitutedByQuality=True,selectionByOutcome=False)
(OUT/'census.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in receipt.items() if k!='priorSHA'}))
