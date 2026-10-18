"""Review frozen validation errors, without opening the protected test."""
import json
import numpy as np
from PIL import Image,ImageDraw
from prepare_focused_data import OUT,CLASSES,write,sha

def main():
    manifest=json.loads((OUT/'learning-manifest.json').read_text())
    rows=[r for r in manifest['rows'] if r['typeEligible'] and r['split']=='validation']
    previous=json.loads((OUT/'type-validation-review.json').read_text()) if (OUT/'type-validation-review.json').exists() else []
    reports=[]
    for name in ['resnet18','efficientnet_b0']:
        folder=OUT/name
        if not (folder/'selection.json').exists():continue
        selected=json.loads((folder/'selection.json').read_text());assert sha(folder/'selected.safetensors')==selected['weightsSHA256']
        logits=np.load(folder/'validation-logits.npy',allow_pickle=False);assert logits.shape==(len(rows),4)
        pred=logits.argmax(1);samples=[]
        for cls in CLASSES:
            indices=[i for i,r in enumerate(rows) if r['class']==cls and CLASSES[pred[i]]!=cls][:4]
            indices+=[i for i,r in enumerate(rows) if r['class']==cls and CLASSES[pred[i]]==cls][:2]
            samples+=indices
        sheet=Image.new('RGB',(960,270*((len(samples)+3)//4)),(12,18,30));draw=ImageDraw.Draw(sheet)
        for k,i in enumerate(samples):
            r=rows[i];image=Image.open(r['absolutePath']).convert('RGB').crop(tuple(r['crop']));image.thumbnail((232,218));x=k%4*240;y=k//4*270;sheet.paste(image,(x+(240-image.width)//2,y))
            draw.text((x+5,y+222),f"source label: {r['class']}",fill='white');draw.text((x+5,y+237),f"prediction: {CLASSES[pred[i]]}",fill='white');draw.text((x+5,y+252),'dataset labels; not expert diagnosis',fill='#9ca3af')
        sheet.save(folder/'validation-errors-review.png')
        prior=next((r for r in previous if r['model']==name and r['weightsSHA256']==selected['weightsSHA256']),{})
        reports.append({**prior,**dict(model=name,weightsSHA256=selected['weightsSHA256'],validation=selected['validation'],reviewSamples=[dict(sha256=rows[i]['sha256'],group=rows[i]['group'],label=rows[i]['class'],prediction=CLASSES[pred[i]]) for i in samples],protectedTestOpened=False,visualReviewComplete=prior.get('visualReviewComplete',False))})
    write('type-validation-review.json',reports);print(json.dumps([{k:r[k] for k in ['model','weightsSHA256','protectedTestOpened']} for r in reports]),flush=True)
if __name__=='__main__':main()
