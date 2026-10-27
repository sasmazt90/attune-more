"""Prepare fixed validation-only crops from a pinned baseline; no network calls.

Creates JPEG95 base64 payloads and an inference manifest. Source images stay in
place. Run hosted inference with each manifest model, confidence=.05, overlap=.5;
save manifest row plus response in <name>.json, then bundle and evaluate.
"""
import argparse,base64,gzip,hashlib,io,json,zipfile
from pathlib import Path
from PIL import Image
from detector_tiling import corner_tiles


def prepare(archive,baseline,out):
    bundle=json.loads(gzip.decompress(Path(baseline).read_bytes()))
    rows={json.loads(r['rawJSON'])['source']['cocoImageId']:json.loads(r['rawJSON']) for r in bundle['records'] if r['split']=='valid'}
    failures=[26,144,19]
    selected=failures+sorted((i for i in rows if i not in failures),key=lambda i:hashlib.sha256(rows[i]['source']['filename'].encode()).hexdigest())[:3]
    out=Path(out);out.mkdir(parents=True,exist_ok=False);manifest=[]
    with zipfile.ZipFile(archive) as z:
        data=json.loads(z.read('valid/_annotations.coco.json'));images={i['id']:i for i in data['images']}
        for image_id in selected:
            im=images[image_id];raw=z.read('valid/'+im['file_name']);img=Image.open(io.BytesIO(raw)).convert('RGB')
            if img.size!=(im['width'],im['height']):raise ValueError('SOURCE_DIMENSION_MISMATCH')
            for n,(x,y,w,h) in enumerate(corner_tiles(im['width'],im['height'])):
                buffer=io.BytesIO();img.crop((x,y,x+w,y+h)).save(buffer,format='JPEG',quality=95)
                payload=buffer.getvalue();stem=f'{image_id}-{n}'
                (out/(stem+'.b64')).write_text(base64.b64encode(payload).decode())
                manifest.append(dict(name=stem,imageId=image_id,tile=[x,y,w,h],sha256=hashlib.sha256(payload).hexdigest(),sourceSHA256=hashlib.sha256(raw).hexdigest(),source=rows[image_id]['source'],model=rows[image_id]['requestedModel'],package=rows[image_id]['resolvedModel']['model_package_id']))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['archive','baseline','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=prepare(a.archive,a.baseline,a.output)
    print(json.dumps({'tiles':len(r),'images':len({x['imageId'] for x in r}),'split':'valid'}))
