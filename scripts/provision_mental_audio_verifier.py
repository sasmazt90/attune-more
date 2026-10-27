#!/usr/bin/env python3
"""Restore the checksum-pinned offline audio verifier; never a TTS model.

Official Sherpa release artifacts, published SHA-256/size, bounded extraction.
No credentials or paid inference. Model files remain outside the repository.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

MODELS={
 'small':('486a46afbb7ba798507190ffe02fea2dd726049af212e774537efac6afb210a6',639387718),
 'large-v3':('2d0e134b3b5fc4a0533baf24a0c9d473b629aa47f030af0a165a05f461df7a03',1068482488),
}

def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def provision(root,model):
 root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
 expected,size=MODELS[model];name=f'sherpa-onnx-whisper-{model}';archive=root/(name+'.tar.bz2')
 url='https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/'+archive.name
 if not archive.exists():
  partial=archive.with_suffix(archive.suffix+'.partial')
  with urllib.request.urlopen(url,timeout=60) as incoming,partial.open('xb') as out:
   count=0
   while chunk:=incoming.read(4*1024*1024):
    count+=len(chunk)
    if count>size:raise ValueError('VERIFIER_DOWNLOAD_TOO_LARGE')
    out.write(chunk)
  if partial.stat().st_size!=size or digest(partial)!=expected:raise ValueError('VERIFIER_ARCHIVE_HASH_MISMATCH')
  partial.rename(archive)
 if archive.stat().st_size!=size or digest(archive)!=expected:raise ValueError('EXISTING_VERIFIER_ARCHIVE_MISMATCH')
 directory=root/name
 if not directory.exists():
  with tarfile.open(archive) as source:
   for member in source.getmembers():
    target=(root/member.name).resolve()
    if not target.is_relative_to(directory) or member.issym() or member.islnk() or not (member.isdir() or member.isfile()):raise ValueError('UNSAFE_VERIFIER_ARCHIVE')
   source.extractall(root,filter='data')
 files={model+'-encoder.int8.onnx',model+'-decoder.int8.onnx',model+'-tokens.txt'}
 record={'repository':'k2-fsa/sherpa-onnx','releaseURL':'https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models',
  'archive':archive.name,'archiveSHA256':expected,'archiveBytes':size,'recognizerVersion':'1.12.26','modelDirectory':name,
  'encoderFile':model+'-encoder.int8.onnx','decoderFile':model+'-decoder.int8.onnx','tokensFile':model+'-tokens.txt',
  'files':{f:digest(directory/f) for f in sorted(files)},'purpose':'offline pronunciation screening only; no TTS replacement','paidServices':False}
 path=root/('provenance.json' if model=='small' else 'provenance-large-v3.json')
 if path.exists():
  old=json.loads(path.read_text())
  if old['archiveSHA256']!=expected or old['files']!=record['files']:raise ValueError('EXISTING_VERIFIER_PROVENANCE_MISMATCH')
 else:path.write_text(json.dumps(record,indent=2)+'\n')
 return path

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--model',choices=MODELS,default='small')
 args=parser.parse_args();print(provision(args.root,args.model))
