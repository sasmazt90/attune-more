"""Pre-fit fixed local ROI controls. Labels are patch presence, not pixel masks."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-source-census-20261013';CONTROL=OUT/'flake-controls';CONTROL.mkdir(exist_ok=True)
pul=json.loads((OUT/'pul-selection.json').read_text('utf8'));natural=json.loads((OUT/'dry-label-selection.json').read_text('utf8'))
previous=json.loads((ROOT/'audit-results/dry-sag-native-followup-20261013/probe-selection.json').read_text('utf8'))
# Coordinates are visually inspected optical ROIs, fixed before classifier fitting.
# No bbox exterior is labelled. Each source group stays entirely in one split.
plan=[
 ('pul',2,'train',1,[340,320,160,160]),('pul',92,'train',1,[280,400,160,160]),
 ('raw',10,'train',1,[120,80,160,160]),('raw',42,'train',1,[350,560,160,160]),
 ('pul',73,'train',0,[410,310,160,160]),('pul',175,'train',0,[330,250,160,160]),
 ('raw',127,'train',0,[350,300,160,160]),('raw',171,'train',0,[330,120,160,160]),
 ('pul',112,'validation',1,[130,340,160,160]),('pul',159,'validation',1,[240,330,160,160]),
 ('raw',53,'validation',1,[100,140,160,160]),('raw',231,'validation',1,[320,390,160,160]),
 ('pul',196,'validation',0,[330,240,160,160]),('raw',147,'validation',0,[620,340,160,160]),
 ('old','0642d4ab','validation',0,[210,180,100,80]),('old','e1646fda','validation',0,[750,750,450,300]),
]
rows=[]
for kind,index,split,label,roi in plan:
    r=pul[index] if kind=='pul' else natural[index] if kind=='raw' else next(v for v in previous if v['sha256'].startswith(index))
    path=Path(r['absolutePath']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
    im=Image.open(path).convert('RGB');x,y,w,h=roi;assert 0<=x<x+w<=im.width and 0<=y<y+h<=im.height
    patch=im.crop((x,y,x+w,y+h));preview=patch.resize((384,384));d=ImageDraw.Draw(preview);d.text((4,4),f"{len(rows)} {r['sha256'][:8]} {split} {'flake presence' if label else 'no visible flake ROI'}",fill='red')
    preview.save(CONTROL/f'roi-{len(rows):02d}.png')
    rows.append(dict(controlIndex=len(rows),kind=kind,censusIndex=index,sourceSHA256=r['sha256'],sourcePath=str(path),group=r['group'],family=r['family'],rights=r.get('rights'),split=split,patchPresenceLabel=label,roi=roi,roiReviewed=False,labelAuthority='engineering visual local optical ROI; not expert diagnosis or full segmentation',outsideROI='unknown'))
train={r['group'] for r in rows if r['split']=='train'};validation={r['group'] for r in rows if r['split']=='validation'};assert not train&validation
receipt=dict(frozenUTC=datetime.now(timezone.utc).isoformat(),controls=rows,trainGroups=sorted(train),validationGroups=sorted(validation),personIdentityProtocol='unknown identities; source/group/visual-near-copy quarantine; no person-independent accuracy claim',acceptanceScope='reviewed ROI patch presence and local support; no pixel Dice/precision, clinical severity or general accuracy',modelFitted=False)
file=CONTROL/'controls.json';assert not file.exists(),'Frozen controls must not be replaced after fitting'
file.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
sheet=Image.new('RGB',(4*384,4*408),'#111111')
for i,r in enumerate(rows):sheet.paste(Image.open(CONTROL/f'roi-{i:02d}.png'),(i%4*384,i//4*408))
sheet.save(CONTROL/'roi-review.png')
print(dict(controls=len(rows),trainGroups=len(train),validationGroups=len(validation),modelFitted=receipt['modelFitted']))
