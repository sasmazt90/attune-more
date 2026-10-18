"""Pinned, hash-verified selected sources only. No model providers or uploads."""
import concurrent.futures,hashlib,json,tarfile,urllib.parse,zipfile
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit-results/combined-health-20261008'
YOLOX_REV='6ddff4824372906469a7fae2dc3206c7aa4bbaee'

def digest(path,algorithm):
 with path.open('rb') as file:return hashlib.file_digest(file,algorithm).hexdigest()

def stream(url,path,md5=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists() and (md5 is None or digest(path,'md5')==md5):return path
 temp=path.with_suffix(path.suffix+'.part')
 if md5:
  # Resume only this task's prior sequential prefix. Every range is validated,
  # then the complete artifact is independently hash checked before extraction.
  offset=temp.stat().st_size if temp.exists() else 0
  with requests.get(url,headers={'Range':'bytes=0-0'},stream=True,timeout=(30,60)) as response:
   response.raise_for_status();assert response.status_code==206
   size=int(response.headers['Content-Range'].split('/')[-1])
  assert offset<=size
  ranges=[(start,min(size-1,start+128*1024*1024-1)) for start in range(offset,size,128*1024*1024)]
  def part(bounds):
   start,end=bounds;piece=temp.with_name(temp.name+f'.{start}-{end}.chunk')
   if piece.exists() and piece.stat().st_size==end-start+1:return piece
   for attempt in range(3):
    try:
     with requests.get(url,headers={'Range':f'bytes={start}-{end}'},stream=True,timeout=(30,60)) as response:
      response.raise_for_status();assert response.status_code==206 and response.headers.get('Content-Range')==f'bytes {start}-{end}/{size}'
      with piece.open('wb') as file:
       for chunk in response.iter_content(1024*1024):file.write(chunk)
     assert piece.stat().st_size==end-start+1
     print(path.name,'verified byte range',start,end,flush=True);return piece
    except Exception:
     if attempt==2:raise
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:pieces=list(pool.map(part,ranges))
  with temp.open('ab') as file:
   import shutil
   for piece in pieces:
    with piece.open('rb') as source:shutil.copyfileobj(source,file)
  assert temp.stat().st_size==size and digest(temp,'md5')==md5,'Archive MD5 mismatch'
 else:
  with requests.get(url,stream=True,timeout=(30,120)) as response:
   response.raise_for_status()
   with temp.open('wb') as file:
    for chunk in response.iter_content(1024*1024):file.write(chunk)
 temp.replace(path);return path

def unzip(path,destination):
 destination.mkdir(exist_ok=True,parents=True)
 with zipfile.ZipFile(path) as archive:
  for item in archive.infolist():
   name=item.filename.replace('\\','/');target=(destination/name).resolve()
   assert target.is_relative_to(destination.resolve()) and not name.startswith('/') and ':' not in name
   if item.is_dir():target.mkdir(exist_ok=True,parents=True);continue
   target.parent.mkdir(exist_ok=True,parents=True)
   if not target.exists():
    with archive.open(item) as src,target.open('wb') as dst:
     import shutil
     shutil.copyfileobj(src,dst)

def dataset(f):
 path=stream(f['links']['self'],OUT/'dental'/f['key'],f['checksum'].split(':')[1])
 unzip(path,OUT/'dental'/path.stem)
 return {'name':f['key'],'url':f['links']['self'],'MD5':f['checksum'],'SHA256':digest(path,'sha256'),'bytes':path.stat().st_size}

def main():
 OUT.mkdir(exist_ok=True,parents=True);metadata_path=OUT/'dental/metadata.json'
 if not metadata_path.exists():
  response=requests.get('https://zenodo.org/api/records/14827784',timeout=(30,60));response.raise_for_status();meta=response.json()
  assert meta['id']==14827784 and meta['metadata']['license']['id']=='cc-by-4.0'
  metadata_path.parent.mkdir(exist_ok=True,parents=True);metadata_path.write_text(json.dumps(meta,indent=2),'utf8')
 else:meta=json.loads(metadata_path.read_text('utf8'))
 assert meta['id']==14827784 and meta['metadata']['license']['id']=='cc-by-4.0'
 expected={'Dataset.zip':'md5:89307871ac2f08f4a8f3a7da1f18db31','Benchmarking Dataset.zip':'md5:852520f16faf65f4704ee06bd82561fa'}
 files=[f for f in meta['files'] if f['key'] in expected]
 assert len(files)==2 and all(f['checksum']==expected[f['key']] for f in files)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:archives=list(pool.map(dataset,files))
 archive=stream(f'https://codeload.github.com/Megvii-BaseDetection/YOLOX/tar.gz/{YOLOX_REV}',OUT/'yolox/source.tar.gz')
 assert digest(archive,'sha256')=='103b59b2d679f2ab829e7f7bf348242c400efa925a4adb262cbf3dd375c4ec0c'
 destination=OUT/f'yolox/extracted/YOLOX-{YOLOX_REV}';destination.mkdir(exist_ok=True,parents=True)
 with tarfile.open(archive) as tar:
  for item in tar.getmembers():
   name='/'.join(item.name.split('/')[1:]);target=(destination/name).resolve()
   assert target.is_relative_to(destination.resolve())
   if item.issym() or item.islnk():continue  # Never materialize archive links
   if item.isdir():target.mkdir(exist_ok=True,parents=True)
   elif item.isfile():
    target.parent.mkdir(exist_ok=True,parents=True)
    with tar.extractfile(item) as source:target.write_bytes(source.read())
 manifest={'zenodoRecord':14827784,'datasetLicense':'CC BY 4.0','archives':archives,'yoloxRevision':YOLOX_REV,'yoloxCodeLicense':'Apache-2.0','sourceArchiveSHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'pretrainedWeightsDownloaded':False}
 (OUT/'source-manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
