"""Public held-out sources with original labels and actual frozen predictions.

Examples deliberately include successful localization, extra predictions and
missed minority labels. They are illustrative extrema, not new acceptance data.
"""
import hashlib,json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit-results/combined-health-20261008/dental-training'


def main():
    import train_dental_yolox as training
    # Annotation evidence only; reuse installed Pillow rather than introduce a
    # plotting dependency into the product or change the frozen evaluator.
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    manifest=json.loads((ROOT/'services/core-api/models/dental-yolox-s.json').read_text('utf8'))
    inventory=json.loads((OUT/'dataset-split.json').read_text('utf8'))
    items=[row for row in inventory['rows'] if row['split']=='test']
    predictions=json.loads((OUT/'heldout-predictions.json').read_text('utf8'))
    threshold=manifest['confidenceThreshold'];classes=manifest['classes']
    assert len(items)==len(predictions)==manifest['evaluation']['images']
    stats=[training.metrics([item],[candidates],threshold,len(classes))['classes'] for item,candidates in zip(items,predictions,strict=True)]
    used=set();selected=[]
    criteria=[('Most matched labels',lambda i:sum(c['truePositive'] for c in stats[i])),
              ('Most extra predictions',lambda i:sum(c['falsePositive'] for c in stats[i])),
              ('Most missed minority labels',lambda i:stats[i][1]['falseNegative']),
              ('First remaining held-out source',lambda i:-i)]
    for label,score in criteria:
        index=max((i for i in range(len(items)) if i not in used),key=score)
        used.add(index);selected.append((label,index))
    proof=[]
    for number,(label,index) in enumerate(selected,1):
        item=items[index];path=Path(item['path']);source=path.read_bytes()
        assert hashlib.sha256(source).hexdigest()==item['sha256']
        image=Image.fromarray(cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB))
        scale=min(800/image.width,550/image.height)
        image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
        panels=[image.copy(),image.copy()]
        def annotate(panel,box,label,color):
            draw=ImageDraw.Draw(panel);x0,y0,x1,y1=(float(v)*scale for v in box)
            draw.rectangle((x0,y0,x1,y1),outline=color,width=2)
            tx=max(0,min(panel.width-70,x0));ty=max(0,min(panel.height-16,y0))
            text_bounds=draw.textbbox((tx,ty),label,font=small)
            draw.rectangle(text_bounds,fill=color);draw.text((tx,ty),label,font=small,fill='black')
        for cls,x,y,w,h in item['boxes']:
            annotate(panels[0],[x,y,x+w,y+h],classes[cls],'#28ee8d')
        kept=sorted((p for p in predictions[index] if p[4]*p[5]>=threshold),key=lambda p:p[4]*p[5],reverse=True)
        matched={cls:set() for cls in range(len(classes))}
        for p in kept[:30]:
            cls=int(p[6]);truth=[[x,y,x+w,y+h] for c,x,y,w,h in item['boxes'] if c==cls]
            best=max(((training.iou(p[:4],box),j) for j,box in enumerate(truth) if j not in matched[cls]),default=(0,-1))
            correct=best[0]>=.5
            if correct:matched[cls].add(best[1])
            color='#00d8eb' if correct else '#ff983c'
            annotate(panels[1],p[:4],f'{classes[cls]} {p[4]*p[5]:.2f}',color)
        counts='; '.join(f'{classes[c["classIndex"]]} TP={c["truePositive"]}, FP={c["falsePositive"]}, FN={c["falseNegative"]}' for c in stats[index])
        evidence=Image.new('RGB',(max(1100,2*image.width+36),image.height+116),'#f6f8fa')
        draw=ImageDraw.Draw(evidence)
        draw.text((12,8),label,font=font,fill='black')
        draw.text((12,32),counts+' | IoU .5; fixed threshold '+str(threshold),font=font,fill='black')
        draw.text((12,62),'Original dataset labels: green',font=small,fill='black')
        draw.text((image.width+24,62),f'Frozen: cyan matched / orange extra; top {min(30,len(kept))}/{len(kept)}',font=small,fill='black')
        evidence.paste(panels[0],(12,84));evidence.paste(panels[1],(image.width+24,84))
        draw.text((12,image.height+90),'CC BY 4.0 public dataset; display scaled uniformly. Illustrative extrema, not camera/clinical acceptance.',font=small,fill='black')
        destination=OUT/f'heldout-example-{number}.png';evidence.save(destination)
        proof.append(dict(selection=label,heldoutIndex=index,sourceSHA256=item['sha256'],group=item['group'],
                          modelHash=manifest['modelHash'],threshold=threshold,classCounts=stats[index],
                          output=str(destination.relative_to(ROOT)),outputSHA256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                          totalPredictions=len(kept),drawnPredictions=min(30,len(kept))))
    (OUT/'heldout-visual-evidence.json').write_text(json.dumps(dict(
        status='PASS',examples=proof,selectionScope='illustrative extrema and first remaining source; not population accuracy',
        datasetLicense='CC-BY-4.0',source='https://zenodo.org/records/14827784',
        userCamera=False,clinicalValidation=False),indent=2),'utf8')
    print(json.dumps(proof))


if __name__=='__main__':main()
