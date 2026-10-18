"""Visualize stored frozen validation proposals; never open or tune on test."""
import argparse,json
from PIL import Image,ImageDraw
from prepare_focused_data import OUT,write,sha

def main(name):
    folder=OUT/name;result=json.loads((folder/'validation-predictions.json').read_text());threshold=result['metrics']['threshold']
    manifest=json.loads((OUT/'learning-manifest.json').read_text());sources={r['path']:r for r in manifest['rows']}
    rows=result['rows'][:12];sheet=Image.new('RGB',(1200,335*((len(rows)+3)//4)),(12,18,30));d=ImageDraw.Draw(sheet);samples=[]
    for i,row in enumerate(rows):
        r=sources[row['path']];im=Image.open(r['absolutePath']).convert('RGB');draw=ImageDraw.Draw(im);a,b,c,e=r['crop'];truth=[v['box'] for v in row['truth'] if v['classId']==0 and a<=sum(v['box'][::2])/2<=c and b<=sum(v['box'][1::2])/2<=e]
        preds=[p for p in row['predictions'] if p[4]>=threshold]
        for box in truth:draw.rectangle(box,outline=(80,235,100),width=2)
        for box in preds:draw.rectangle(box[:4],outline=(255,80,170),width=1)
        crop=im.crop(tuple(r['crop']));crop.save(folder/f'validation-review-{i}-native.png');crop.thumbnail((296,290));x=i%4*300;y=i//4*335;sheet.paste(crop,(x,y));d.text((x+3,y+293),f'validation {i}: truth {len(truth)}, proposals {len(preds)}',fill='white');d.text((x+3,y+309),'green=annotation pink=proposal',fill='#9ca3af');samples.append(dict(sha256=r['sha256'],group=r['group'],truth=len(truth),proposals=len(preds)))
    sheet.save(folder/'validation-review-sheet.png');checkpoint=folder/'selected.safetensors'
    write(name+'/validation-visual-review.json',dict(model=name,weightsSHA256=sha(checkpoint),threshold=threshold,samples=samples,protectedTestOpenedByReview=False,visualReviewComplete=False,thresholdNotChanged=True));print(name,'stored validation only',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name',choices=['yolox','fasterrcnn']);main(p.parse_args().name)
