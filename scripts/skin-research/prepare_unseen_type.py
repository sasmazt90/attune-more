"""Fetch only public CC0 image bytes; freeze as unused source holdout.

No training, candidate predictions, personal history, provider or paid calls.
Metadata, MD5/SHA and perceptual near-duplicates are checked before inclusion.
"""
import concurrent.futures,hashlib,json,re,time
from pathlib import Path
import requests,cv2,numpy as np
from PIL import Image,ImageDraw
from diagnose_followup import NEW,OLD,write
from prepare_focused_data import ROOT,phash,face_crop,sha
from clean_followup_quality import impulse
BASE='https://dataverse.telkomuniversity.ac.id'
def main():
    cv2.setNumThreads(1);started=time.monotonic();response=requests.get(BASE+'/api/datasets/5059',timeout=25)
    if response.status_code!=200:
        write('unseen-type/access-result.json',dict(status=response.status_code,url=response.url,sourceDownloaded=False,independentFinalAvailable=False,reason='Official public metadata endpoint unavailable in this environment; no authentication or access restriction bypass attempted.'))
        print('PUBLIC_SOURCE_UNAVAILABLE',response.status_code,flush=True);return
    meta=response.json();v=meta['data']['latestVersion'];assert v['license']=='CC0' and v['versionState']=='RELEASED' and not any(f['restricted'] for f in v['files']);write('unseen-type/metadata.json',meta)
    folder=NEW/'unseen-type/source';folder.mkdir(parents=True,exist_ok=True)
    def fetch(f):
        assert time.monotonic()-started<400,'FINITE_FETCH_BUDGET';df=f['dataFile'];name=Path(df['filename']).name;assert name==df['filename'] and f['directoryLabel'] in ['Normal','Dry','Oily','Combination'];path=folder/f'{df["id"]}-{name}'
        if not path.exists():
            r=requests.get(BASE+f'/api/access/datafile/{df["id"]}',timeout=25);r.raise_for_status();assert len(r.content)==df['filesize'];assert hashlib.md5(r.content).hexdigest()==df['md5'];path.write_bytes(r.content)
        assert hashlib.md5(path.read_bytes()).hexdigest()==df['md5'];return {**f,'absolutePath':str(path),'sha256':sha(path)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(fetch,v['files']))
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions
    detector=FaceLandmarker.create_from_options(FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task')),num_faces=2))
    original=json.loads((OLD/'learning-manifest.json').read_text())['rows'];known={r['sha256'] for r in original};known_hashes=[r['phash'] for r in original if 'phash' in r];rows=[];families={}
    for f in files:
        bgr=cv2.imread(f['absolutePath']);h,w=bgr.shape[:2];p=phash(bgr);near=any((p^q).bit_count()<=4 for q in known_hashes);faces=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))).face_landmarks;name=f['dataFile']['filename'];family=re.sub(r'(?i)^aug','',Path(name).stem);family=re.sub(r'(?i)\d+$','',family)
        # Conservative augmentation family: original and aug classes remain
        # grouped below by exact/pHash and visible identity engineering review.
        r=dict(path=name,absolutePath=f['absolutePath'],className=f['directoryLabel'].lower(),sha256=f['sha256'],phash=p,faceCount=len(faces),eligible=False,previousSourceOverlap=near or f['sha256'] in known,source='Telkom CC0 DOI 10.34820/FK2/QBGETA',split='unseen-final')
        if len(faces)==1:
            points=faces[0];crop=face_crop(points,w,h);a,b,c,d=crop;detail=float(cv2.Laplacian(cv2.cvtColor(bgr[b:d,a:c],cv2.COLOR_BGR2GRAY),cv2.CV_32F).var());noise=impulse(bgr[b:d,a:c]);complete=all(.005<pt.x<.995 and .005<pt.y<.995 for pt in [points[10],points[152],points[234],points[454]])
            r.update(crop=crop,detail=detail,noise=noise,impulseReviewRequired=noise>.004,visualQualityReviewRequired=True,landmarks=[dict(x=v.x,y=v.y,z=v.z) for v in points],eligible=not r['previousSourceOverlap'] and complete and detail>=4)
        rows.append(r)
    detector.close();sheet=Image.new('RGB',(1280,8*156),(12,18,30));d=ImageDraw.Draw(sheet)
    for k,r in enumerate(rows):
        im=Image.open(r['absolutePath']).convert('RGB');im.thumbnail((124,124));x=k%10*128;y=k//10*156;sheet.paste(im,(x,y));d.text((x+3,y+126),str(k),fill='white');d.text((x+3,y+140),'eligible' if r['eligible'] else 'excluded',fill='white')
    sheet.save(NEW/'unseen-type/source-review.png');write('unseen-type/prepared.json',dict(sourceLicense='CC0',sourceURL=BASE+'/dataset.xhtml?persistentId=doi:10.34820/FK2/QBGETA',files=len(rows),rows=rows,metadataSHA256=sha(NEW/'unseen-type/metadata.json'),predictionsOpened=False,selectionAllowed=False,personIndependent=False,augmentationFamiliesRequireReview=True,seconds=time.monotonic()-started));print(json.dumps(dict(files=len(rows),eligible=sum(r['eligible'] for r in rows),sourceReview=str(NEW/'unseen-type/source-review.png'))),flush=True)
if __name__=='__main__':main()
