"""Source-coordinate diagnostic overlays; display resize never enters inference."""
import base64
import hashlib
import json

from acne_takeover_support import ROOT, OUT, read, digest, current_product_masks
from heavy_job_lease import HeavyJobLease


def main():
    pre={r['sha256']:r for r in read(OUT/'browser-preflight.json')['rows']}
    reports={name:read(OUT/('evaluation-'+name)/'summary.json') for name in ('step0','control','hard-negative')}
    rows={name:{r['sha256']:r for r in report['rows']} for name,report in reports.items()}
    selected=[s for s in rows['step0'] if s[:8] in ('55d380f7','36e4010b','2ed3716e')]
    receipt=[]
    with HeavyJobLease('CDC-acne-source-coordinate-evidence',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw
        for sha in selected:
            lease.check();a=pre[sha];photo=OUT/'product-inputs'/sha/'snapshot.png';before=digest(photo);image=cv2.imread(str(photo));pixel=hashlib.sha256(cv2.cvtColor(image,cv2.COLOR_BGR2RGBA).tobytes()).hexdigest()
            payload=dict(photo='data:image/png;base64,'+base64.b64encode(photo.read_bytes()).decode(),photoId=pixel,landmarks=a['alignment']['landmarks'],meshes=a['snapshot']['meshes'],exclusions=a['snapshot']['exclusions'],qualityValid=a['quality']['isValid'],conditions=dict(yaw=a['alignment']['yaw'],pitch=a['alignment']['pitch'],roll=a['alignment']['roll'],scaleRatio=a['alignment']['scaleRatio']))
            masks=current_product_masks(payload);h,w=image.shape[:2];origin=masks['origin'];scale=masks['scale']
            xx=np.floor((np.arange(w)+.5-origin[0])*scale).astype(int);yy=np.floor((np.arange(h)+.5-origin[1])*scale).astype(int)
            def native(mask):
                inside=(yy[:,None]>=0)&(xx[None,:]>=0)&(yy[:,None]<mask.shape[0])&(xx[None,:]<mask.shape[1]);return mask[yy.clip(0,mask.shape[0]-1)[:,None],xx.clip(0,mask.shape[1]-1)[None,:]].astype(bool)&inside
            support=native(masks['acne_skin']);hair=native(masks['hair']);holes=native(masks['acne_exclusion']);rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB);overlay=rgb.copy()
            for mask,color in ((support,[0,180,80]),(hair,[170,0,200]),(holes,[255,40,20])):overlay[mask]=(overlay[mask]*.5+np.array(color)*.5).astype(np.uint8)
            panes=[]
            def pane(array,title,boxes=(),color='lime'):
                im=Image.fromarray(array);d=ImageDraw.Draw(im)
                for box in boxes:d.rectangle(box,outline=color,width=max(1,round(w/500)))
                f=min(400/w,440/h);im=im.resize((round(w*f),round(h*f)));canvas=Image.new('RGB',(420,480),'#202020');canvas.paste(im,((420-im.width)//2,30));ImageDraw.Draw(canvas).text((8,8),title,fill='white');return canvas
            base=rows['step0'][sha]
            panes.append(pane(rgb,'Source labels (outside UNKNOWN)',base['truth'],'yellow'))
            panes.append(pane(overlay,'Exact product support / hair / holes'))
            panes.append(pane(rgb,'Step0 NMS .30 (native source)',[v['box'] for v in base['trace']['nmsCandidates']],'orange'))
            for name in ('step0','control','hard-negative'):
                r=rows[name][sha];boxes=[[b['x'],b['y'],b['x']+b['width'],b['y']+b['height']] for b in r['finalCandidates']]
                panes.append(pane(rgb,name+' final: hit='+str(len(r['pairs']))+' FP='+str(r['cleanFP']),boxes))
            board=Image.new('RGB',(1260,960))
            for index,im in enumerate(panes):board.paste(im,((index%3)*420,(index//3)*480))
            target=OUT/('product-trace-'+sha[:8]+'.png');board.save(target)
            receipt.append(dict(sha256=sha,displayFile=target.name,sourceShape=[w,h],sourceOrigin=origin,sourceScale=scale,actualSnapshotMeshes=bool(a['snapshot']['meshes']),exactProductMasks=True,pixelPhotoId=pixel,displayOnlyResize=True,originalSourceUnchanged=before==digest(photo)))
    (OUT/'product-trace-render.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt))


if __name__=='__main__':main()
