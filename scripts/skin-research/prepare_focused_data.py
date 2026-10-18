"""Prepare supplied local corpora without reading user photos or history.

Source/hash/perceptual components are not person identities. Final degree-test
groups are also excluded from type-backbone training and model selection.
"""
from pathlib import Path
import collections, hashlib, json, re, zipfile, random, time
import cv2, numpy as np

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'audit-review/skin-source-verification/focused'
OUT=ROOT/'audit-results/focused-skin-20261010'
CLASSES=['normal','dry','oily','combination']
ARCHIVES={'skin-18criteria-v1.zip':'8f2bebd6b97bdd3acd06a42798babbd377b7937db362a734586ff5fb3d0ea4a1',
          'eye-training-v2.zip':'03afd248006874f714a1b39210801be70918cf96e669084c5776a6590ca73f03'}
TARGETS=['acne','blackheads','whiteheads','pores','oil','irritation','sensitivity','redness','lines','bags','dark','foreheadLines','elasticity','dry','darkSpots','postAcne','tone','freckles']

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()
def write(name,value):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf8');temp.replace(path)
def phash(image):
    gray=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(32,32)).astype(np.float32)
    dct=cv2.dct(gray)[:8,:8];return sum(int(v)<<i for i,v in enumerate((dct>np.median(dct.ravel()[1:])).ravel()))
def source_name(name):
    name=Path(name).stem.split('.rf.')[0]
    name=re.sub(r'^(normal|dry|oily|combination)[_-]+','',name,flags=re.I)
    return re.sub(r'[-_]copy(?:[-_]\d+)?','',name,flags=re.I).lower()

def extract():
    for name,expected in ARCHIVES.items():
        path=SOURCE/name;assert sha(path)==expected,'SOURCE_HASH_MISMATCH'
        target=OUT/'sources'/name.removesuffix('.zip');target.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                destination=(target/item.filename).resolve()
                assert destination.is_relative_to(target.resolve()),'ARCHIVE_PATH_ESCAPE'
                if not destination.exists():archive.extract(item,target)
    write('source-rights.json',dict(archives=ARCHIVES,skin=dict(source='https://www.kaggle.com/datasets/killa92/facial-skin-analysis-and-type-classification',license='publisher-declared Apache-2.0'),eye=dict(source='https://universe.roboflow.com/skin-condition-detection/skin-condition-detection_merged/dataset/2',license='CC-BY-4.0'),changes='quality filtering, source grouping, split rebuild, native face crops; original annotations retained',expertProtocolVerified=False,personIndependent=False))

def group(rows):
    parents=list(range(len(rows)))
    def root(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    def join(a,b):parents[root(b)]=root(a)
    keys={};buckets=collections.defaultdict(list)
    for i,row in enumerate(rows):
        for key in ('sha256','sourceName'):
            value=(key,row[key])
            if value in keys:join(i,keys[value])
            else:keys[value]=i
        candidates=set()
        for band in range(5):candidates.update(buckets[(band,(row['phash']>>(13*band))&8191)])
        for j in candidates:
            if (row['phash']^rows[j]['phash']).bit_count()<=4:join(i,j)
        for band in range(5):buckets[(band,(row['phash']>>(13*band))&8191)].append(i)
    components=collections.defaultdict(list)
    for i in range(len(rows)):components[root(i)].append(i)
    for ids in components.values():
        signature=min(rows[i]['sha256'] for i in ids)
        u=int(hashlib.sha256(('focused-split-20261010:'+signature).encode()).hexdigest()[:8],16)/2**32
        split='train' if u<.7 else 'validation' if u<.85 else 'test'
        for i in ids:rows[i].update(group=signature,split=split)
    return components

def face_crop(points,width,height):
    # Same arithmetic as cameraStability.cameraCrop, in original pixel space.
    p=np.array([[v.x,v.y] for v in points[:468]])
    lo=p.min(0);hi=p.max(0);size=hi-lo
    start=np.maximum(0,lo-size*np.array([.32,.35]));end=np.minimum(1,hi+size*np.array([.32,.16]))
    return [max(0,int(np.floor(start[0]*width))),max(0,int(np.floor(start[1]*height))),min(width,int(np.ceil(end[0]*width))),min(height,int(np.ceil(end[1]*height)))]

def prepare():
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker,FaceLandmarkerOptions
    model=ROOT/'apps/vehicle-app/public/mediapipe/models/face_landmarker.task'
    options=FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model)),num_faces=2)
    joins=json.loads((SOURCE/'skin-label-image-joins.json').read_text())['matched']
    grades={row['image']:row for row in joins}
    rows=[];start=time.monotonic()
    sources=[('skin',OUT/'sources/skin-18criteria-v1', 'publisher-declared Apache-2.0'),('eye',OUT/'sources/eye-training-v2','CC-BY-4.0')]
    with FaceLandmarker.create_from_options(options) as detector:
        for corpus,base,license in sources:
            cached=OUT/(corpus+'-quality-cache.json')
            completed=json.loads(cached.read_text()) if cached.exists() else []
            seen={r['path'] for r in completed}
            files=sorted(p for p in base.rglob('*') if p.suffix.lower() in ['.png','.jpg','.jpeg'])
            for index,path in enumerate(files):
                relative=path.relative_to(base).as_posix()
                if relative in seen:continue
                raw=path.read_bytes();image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
                item=dict(path=relative,absolutePath=str(path),corpus=corpus,license=license,sourceName=source_name(path.name),sha256=hashlib.sha256(raw).hexdigest(),qualityDecision='undecodable',eligible=False)
                if image is not None:
                    h,w=image.shape[:2];item.update(width=w,height=h,phash=phash(image))
                    rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
                    result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
                    item['faceCount']=len(result.face_landmarks)
                    if len(result.face_landmarks)==1:
                        landmarks=result.face_landmarks[0];crop=face_crop(landmarks,w,h);a,b,c,d=crop
                        pixels=image[b:d,a:c];gray=cv2.cvtColor(pixels,cv2.COLOR_BGR2GRAY)
                        detail=float(cv2.Laplacian(gray,cv2.CV_32F).var());face=np.array([[p.x*w,p.y*h] for p in landmarks[:468]])
                        faceWidth=float(np.ptp(face[:,0]));item.update(crop=crop,landmarks=[dict(x=p.x,y=p.y,z=p.z) for p in landmarks],faceWidth=faceWidth,blur=detail)
                        complete=all(0.005<p.x<.995 and .005<p.y<.995 for p in [landmarks[10],landmarks[152],landmarks[234],landmarks[454]])
                        item['qualityDecision']='eligible-single-face' if complete and faceWidth>=100 and detail>=4 else 'partial-or-low-detail-face'
                        item['eligible']=item['qualityDecision']=='eligible-single-face'
                    else:item['qualityDecision']='no-single-face'
                    if corpus=='skin':
                        item['class']=next((name for name in CLASSES if '/'+name+'/' in '/'+relative),None)
                        join=grades.get(relative)
                        if join:
                            # Explicit spreadsheet schema: both versions use C..T;
                            # Q differs in heading but remains dark pigment target.
                            values=[];masks=[]
                            for column,target in zip('CDEFGHIJKLMNOPQRST',TARGETS):
                                try:value=float(join['grades'][column])
                                except (KeyError,ValueError,TypeError):value=None
                                valid=value is not None and np.isfinite(value) and 0<=value<=5
                                values.append(value if valid else None);masks.append(valid)
                            item.update(grades=values,gradeMask=masks,gradeSource=join['split'])
                    else:
                        labels=path.parent.parent/'labels'/(path.stem+'.txt');annotations=[]
                        if labels.exists():
                            for line in labels.read_text().splitlines():
                                v=list(map(float,line.split()));cls=int(v[0]);xy=v[1:]
                                assert cls in [0,1,2] and all(np.isfinite(x) and 0<=x<=1 for x in xy)
                                if len(xy)==4:
                                    cx,cy,bw,bh=xy;ann=dict(classId=cls,kind='box',box=[(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h])
                                else:
                                    assert len(xy)>=6 and len(xy)%2==0
                                    p=np.array(xy).reshape(-1,2)*[w,h];unique=np.unique(p,axis=0)
                                    rectangle=len(unique)==4 and len(np.unique(p[:,0]))==2 and len(np.unique(p[:,1]))==2
                                    ann=dict(classId=cls,kind='rectangular-polygon' if rectangle else 'polygon',polygon=p.tolist(),box=[*p.min(0),*p.max(0)])
                                annotations.append(ann)
                        item['annotations']=annotations
                completed.append(item)
                if index%50==0:
                    write(corpus+'-quality-cache.json',completed);print(corpus,index,len(files),'seconds',round(time.monotonic()-start),flush=True)
            write(corpus+'-quality-cache.json',completed);rows.extend(completed)
    readable=[r for r in rows if 'phash' in r];components=group(readable)
    conflicts=[]
    for ids in components.values():
        labels={readable[i].get('class') for i in ids if readable[i].get('class')}
        if len(labels)>1:
            conflicts.append(dict(group=readable[ids[0]]['group'],classes=sorted(labels),paths=[readable[i]['path'] for i in ids]))
            for i in ids:readable[i]['typeExcluded']='conflicting-source-class-labels'
    degreeTest={r['group'] for r in readable if r.get('grades') and r['split']=='test'}
    for r in readable:
        r['typeEligible']=r['corpus']=='skin' and r['eligible'] and not r.get('typeExcluded') and r['group'] not in degreeTest
        r['degreeEligible']=r['corpus']=='skin' and r['eligible'] and bool(r.get('grades'))
        if r['group'] in degreeTest:r['typeExcluded']='protected-degree-test-group'
    assert all(len({r['split'] for r in readable if r['group']==g})==1 for g in {r['group'] for r in readable})
    write('dataset-manifest.json',dict(seed=20261010,classes=CLASSES,targets=TARGETS,cropVersion='camera-crop-v1',landmarkModelSHA256=sha(model),personIndependent=False,phashDistance=4,rows=readable,conflicts=conflicts,protectedDegreeTestGroups=sorted(degreeTest),gradeSchema={'columns':'C..T','invalidValuePolicy':'per-target mask; preserve all other labels','Q':'train dark spots / validation pigmentation'},counts=dict(before=dict(collections.Counter(r['corpus'] for r in rows)),quality=dict(collections.Counter((r['corpus']+':'+r['qualityDecision']) for r in rows)),type=dict(collections.Counter(r['split']+':'+r['class'] for r in readable if r['typeEligible'])),degree=dict(collections.Counter(r['split'] for r in readable if r['degreeEligible'])),eye=dict(collections.Counter(r['split'] for r in readable if r['corpus']=='eye' and r['eligible'])))))
    print('Manifest ready',flush=True)

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);extract();prepare()
