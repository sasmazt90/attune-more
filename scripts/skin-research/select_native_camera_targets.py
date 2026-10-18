"""Finite alternate-domain TRAIN source review, never age/weak-label truth."""
import hashlib,json,time,threading
from pathlib import Path
from PIL import Image,ImageDraw
import psutil
from stream_skin_inventory import inventory_rows
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/native-camera-scope-20261013';OUT.mkdir(exist_ok=True);process=psutil.Process();peak=0.;done=threading.Event()
def observe():
    global peak
    while not done.wait(.05):peak=max(peak,process.memory_info().rss/2**20)
monitor=threading.Thread(target=observe,daemon=True);monitor.start()
manifest=ROOT/'audit-results/skin-selected-20261011/manifest.json';used=set()
for path in [ROOT/'audit-results/dry-sag-source-census-20261013/contour-selection.json',ROOT/'audit-results/dry-sag-source-census-20261013/dry-label-selection.json',ROOT/'audit-results/dry-sag-source-census-20261013/pul-selection.json',ROOT/'audit-results/dry-sag-component-followup-20261013/unseen-face-selection.json',ROOT/'audit-results/native-material-contour-20261013/added-train-source-selection.json']:
    used|={r['group'] for r in json.loads(path.read_text('utf8'))}
chosen=[]
for domain in ['csv','v11','clean3']:
    # Retain only small selection metadata, never all decoded annotations.
    eligible=sorted([{k:r[k] for k in ['source','absolutePath','sha256','group','family','split','width','height','rights']} for r in inventory_rows(manifest) if r['source']==domain and r['split']=='train' and r['group'] not in used and r['width']>=600 and r['height']>=600],key=lambda r:r['sha256'])
    if not eligible:continue
    ranks=[round(i*(len(eligible)-1)/7) for i in range(8)]
    for rank in ranks:
        row=eligible[rank]
        if row['group'] in used:continue
        used.add(row['group']);chosen.append({k:row[k] for k in ['source','absolutePath','sha256','group','family','split','width','height','rights']})
del eligible
path=OUT/'alternate-domain-selection.json';assert not path.exists();path.write_text(json.dumps(chosen,indent=2),'utf8')
for start in range(0,len(chosen),12):
    sheet=Image.new('RGB',(4*280,3*304),'#111');draw=ImageDraw.Draw(sheet)
    for j,row in enumerate(chosen[start:start+12]):
        source=Path(row['absolutePath']);assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256'];im=Image.open(source).convert('RGB');im.thumbnail((280,280));x=j%4*280;y=j//4*304;sheet.paste(im,(x+(280-im.width)//2,y+24));draw.text((x+2,y+2),str(start+j)+' '+row['sha256'][:8]+' '+row['source'],fill='white');im.close()
    sheet.save(OUT/f'alternate-domain-review-{start//12}.png')
done.set();monitor.join(1);(OUT/'alternate-domain-selection-receipt.json').write_text(json.dumps(dict(selected=len(chosen),selectionBeforeModelResults=True,selectionByAge=False,weakClassLabelsUsedAsTruth=False,maximumResidentSourcePhotos=1,metadataReadPeakRSSMiB=peak,wholeArchiveScanned=False,SCINDownloaded=False),indent=2),'utf8');print(json.dumps(dict(selected=len(chosen),peakRSSMiB=peak)))
