"""Read-only source/tensor audit; never opens old test images for selection."""
import collections, json, platform, shutil, time
from pathlib import Path
from prepare_focused_data import ROOT,sha,TARGETS

OLD=ROOT/'audit-results/focused-skin-20261010'
NEW=OLD.parent/'skin-followup-20261011'
def write(name,value):
    p=NEW/name;p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(value,indent=2),'utf8');q.replace(p)
def main():
    import cv2,numpy as np,psutil,torch
    from PIL import Image,ImageDraw
    from train_focused_local import SIZE,setup,acne_tiles,tile_image,yolo_batch
    NEW.mkdir(exist_ok=True);m=json.loads((OLD/'learning-manifest.json').read_text())
    rows=m['rows'];splits=setup('acne');tiles=acne_tiles(splits['train'])
    boxes=np.array([b for t in tiles for b in t['boxes']]);size=boxes[:,2:]-boxes[:,:2]
    exposed={r['group'] for r in rows if r['split']=='test'}
    used={r['group'] for r in rows if r['eligible'] and r['split'] in ['train','validation']}
    eligible={r['group'] for r in rows if r['eligible']}
    write('exposure-ledger.json',dict(oldManifestSHA256=sha(OLD/'learning-manifest.json'),
        openedFinalSourceGroups=sorted(exposed),previousDevelopmentGroups=sorted(used),
        eligibleNeverUsedSourceGroups=sorted(eligible-used-exposed),independentFinalAvailable=False,
        reason='All currently eligible source groups were previously used in training, selection, or opened final evaluation. A new split of these groups is development only.',
        oldFinalImagesNotOpenedByThisAudit=True))
    write('hardware.json',dict(timestamp=time.time(),python=platform.python_version(),torch=str(torch.__version__),cuda=torch.cuda.is_available(),cudaDevices=torch.cuda.device_count(),physicalCPU=psutil.cpu_count(False),logicalCPU=psutil.cpu_count(),freeRAM=psutil.virtual_memory().available,diskFree=shutil.disk_usage(NEW).free,paidCompute=False))
    # Label overlay comes from exactly the BGR tensor delivered to YOLOX, not
    # from a different preview/crop. Faster input is the same pixels RGB/255.
    indices=np.unique(np.linspace(0,len(tiles)-1,12).astype(int));sheet=Image.new('RGB',(1152,4*420),(12,18,30));d=ImageDraw.Draw(sheet);evidence=[]
    for k,i in enumerate(indices):
        t=tiles[int(i)];x=tile_image(t);rgb=x.numpy().transpose(1,2,0)[:,:,::-1].astype(np.uint8);im=Image.fromarray(rgb);draw=ImageDraw.Draw(im)
        _,target=yolo_batch([t]);roundtrip=[]
        for box,z in zip(t['boxes'],target[0]):
            cls,cx,cy,w,h=z.tolist();back=[cx-w/2,cy-h/2,cx+w/2,cy+h/2];roundtrip.append(float(np.max(np.abs(np.array(back)-box))));draw.rectangle(box,outline='#00d2ef',width=2)
        assert max(roundtrip,default=0)<.0001 and x.shape==(3,384,384)
        a,b=k%3*384,k//3*420;sheet.paste(im,(a,b));d.text((a+5,b+386),f'Tile {int(i)} / {len(t["boxes"])} boxes / native 384',fill='white');d.text((a+5,b+402),t['row']['sha256'][:20],fill='white')
        evidence.append(dict(tile=int(i),sourceSHA256=t['row']['sha256'],group=t['row']['group'],rect=t['rect'],boxes=t['boxes'],tensorSHA256=__import__('hashlib').sha256(x.numpy().tobytes()).hexdigest(),maxBoxRoundtripError=max(roundtrip,default=0),yoloClass=0,fasterClass=1))
    sheet.save(NEW/'tensor-label-overlay.png');write('tensor-label-evidence.json',evidence)
    write('diagnosis.json',dict(nativeTileSize=384,stride=288,trainingPhotos=len(splits['train']),trainingTiles=len(tiles),labels=len(boxes),boxWidthPercentiles=np.percentile(size[:,0],[0,10,25,50,75,90,100]).tolist(),boxHeightPercentiles=np.percentile(size[:,1],[0,10,25,50,75,90,100]).tolist(),minimumSideBelow8Fraction=float((size.min(1)<8).mean()),minimumSideBelow4Fraction=float((size.min(1)<4).mean()),inputResize=False,classMapping={'archiveAcne':0,'YOLOXAcne':0,'FasterBackground':0,'FasterAcne':1},labelRoundtripPass=True,
        yolox={'status':'undertrained-one-epoch','curve':json.loads((OLD/'yolox/history.json').read_text()),'resumeAvailable':'weights only; legacy optimizer/order/RNG absent'},
        faster={'status':'no-validated-epoch','budget':json.loads((OLD/'fasterrcnn/runtime-budget-review.json').read_text()),'resumeAvailable':False},
        causes=['Budget checked only at epoch boundary in original run','Full native 2080 tiles and repeated image decode each step','CPU-only upper backbone/FPN backward; no GPU','Original intermediate checkpoint omitted optimizer/RNG/data cursor','Small foci may span less than finest 8-pixel feature stride','Training excludes empty tiles whose negative completeness is unknown'],
        architectureFinalPerformanceEstablished=False))
    # Complete objective visual quality review of DEVELOPMENT type photos.
    # No model prediction/correctness is shown or consulted.
    dev=[r for r in rows if r.get('typeEligible') and r['split'] in ['train','validation']]
    index=[]
    for start in range(0,len(dev),80):
        canvas=Image.new('RGB',(1280,8*156),(12,18,30));draw=ImageDraw.Draw(canvas)
        for k,r in enumerate(dev[start:start+80]):
            im=Image.open(r['absolutePath']).convert('RGB');im.thumbnail((124,124));x=k%10*128;y=k//10*156;canvas.paste(im,(x+(128-im.width)//2,y));draw.text((x+3,y+126),str(start+k),fill='white');draw.text((x+3,y+140),r['sha256'][:12],fill='white')
            index.append(dict(index=start+k,sha256=r['sha256'],group=r['group'],absolutePath=r['absolutePath'],crop=r['crop']))
        canvas.save(NEW/f'quality/{start//80:02d}.png') if (NEW/'quality').exists() else ((NEW/'quality').mkdir(),canvas.save(NEW/f'quality/{start//80:02d}.png'))
    write('quality/index.json',index)
    print(json.dumps(dict(out=str(NEW),devQualityPhotos=len(dev),sheets=(len(dev)+79)//80,diagnosis=json.loads((NEW/'diagnosis.json').read_text())['boxWidthPercentiles'])),flush=True)
if __name__=='__main__':main()
