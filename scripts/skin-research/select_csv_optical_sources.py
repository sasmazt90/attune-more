"""Eight source-diverse local TRAIN faces; selection never uses clinical age."""
import hashlib,json,psutil
from pathlib import Path
from PIL import Image,ImageDraw
from stream_skin_inventory import inventory_rows
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';buckets={};process=psutil.Process();peak=process.memory_info().rss/2**20
used={r['group'] for r in json.loads((OUT/'alternate-domain-selection.json').read_text('utf8'))}
for r in inventory_rows(ROOT/'audit-results/skin-selected-20261011/manifest.json'):
    peak=max(peak,process.memory_info().rss/2**20)
    if r['source']!='csv' or r['split']!='train' or r['width']<384 or r['height']<384 or r['group'] in used:continue
    bucket=int(r['sha256'][0],16)//2
    if bucket not in buckets or r['sha256']<buckets[bucket]['sha256']:buckets[bucket]={k:r[k] for k in ['source','absolutePath','sha256','group','family','split','width','height','rights']}
rows=[buckets[k] for k in sorted(buckets)];path=OUT/'csv-optical-selection.json';assert not path.exists();path.write_text(json.dumps(rows,indent=2),'utf8');sheet=Image.new('RGB',(4*300,2*324),'#111');draw=ImageDraw.Draw(sheet)
for i,r in enumerate(rows):
    source=Path(r['absolutePath']);assert hashlib.sha256(source.read_bytes()).hexdigest()==r['sha256'];im=Image.open(source).convert('RGB');im.thumbnail((300,300));x=i%4*300;y=i//4*324;sheet.paste(im,(x+(300-im.width)//2,y+24));draw.text((x+2,y+2),str(i)+' '+r['sha256'][:8],fill='white');im.close()
sheet.save(OUT/'csv-optical-review.png');(OUT/'csv-selection-resource.json').write_text(json.dumps(dict(metadataPeakRSSMiB=peak,photosResident=1,selected=len(rows),weakSkinTypeLabelUsedAsTruth=False)),'utf8');print(json.dumps(dict(selected=len(rows),peakRSSMiB=peak)))
