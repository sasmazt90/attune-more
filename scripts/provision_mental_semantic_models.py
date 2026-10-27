#!/usr/bin/env python3
"""Download official immutable MiniLM/E5 snapshots for local, unpaid benchmarks.

Uses the environment proxy/policy unchanged. No inference API, mirrors, remote
compute, credentials discovery or trust_remote_code. LFS and Git blob hashes are
checked against official Hub metadata before accepting any file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
import requests

MODELS={'minilm':('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2','apache-2.0'),
        'e5':('intfloat/multilingual-e5-small','mit')}
FILES=('config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','sentence_bert_config.json')


def fetch(url,target,session):
    with session.get(url,stream=True,timeout=(15,90)) as response:
        if response.status_code!=200:raise ValueError('OFFICIAL_MODEL_DOWNLOAD_HTTP_'+str(response.status_code))
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            for chunk in response.iter_content(1024*1024):stream.write(chunk)


def provision(name,root):
    repository,license_id=MODELS[name]
    session=requests.Session()
    # The metadata response supplies the immutable revision and expected hashes.
    response=session.get('https://huggingface.co/api/models/'+repository,params={'blobs':'true'},timeout=30)
    if response.status_code!=200:raise ValueError('OFFICIAL_MODEL_METADATA_HTTP_'+str(response.status_code))
    metadata=response.json();revision=metadata['sha']
    if not re.fullmatch('[0-9a-f]{40}',revision) or metadata.get('cardData',{}).get('license')!=license_id:
        raise ValueError('OFFICIAL_REVISION_OR_LICENSE_MISMATCH')
    directory=root/name/revision;directory.mkdir(parents=True,exist_ok=True)
    siblings={r['rfilename']:r for r in metadata['siblings']}
    fingerprints={};expected={}
    for name in FILES:
        item=siblings[name];path=directory/name
        if not path.exists():fetch(f'https://huggingface.co/{repository}/resolve/{revision}/{name}',path,session)
        size=path.stat().st_size;sha256=hashlib.sha256();blob=hashlib.sha1();blob.update(f'blob {size}\0'.encode())
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):sha256.update(chunk);blob.update(chunk)
        if item.get('lfs'):
            if sha256.hexdigest()!=item['lfs']['sha256'] or size!=item['lfs']['size']:raise ValueError('OFFICIAL_LFS_HASH_MISMATCH')
            expected[name]={'sha256':item['lfs']['sha256'],'bytes':size}
        elif blob.hexdigest()!=item['blobId']:raise ValueError('OFFICIAL_GIT_BLOB_MISMATCH')
        else:expected[name]={'gitBlobSHA1':item['blobId'],'bytes':size}
        fingerprints[name]=sha256.hexdigest()
    manifest={'repository':repository,'revision':revision,'license':license_id,'files':fingerprints,'officialMetadataHashes':expected,
              'source':'https://huggingface.co/api/models/'+repository,'inference':'local-only','paidServices':False}
    (directory/'verified-model.json').write_text(json.dumps(manifest,indent=2)+'\n')
    session.close();return str(directory)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    failures=0
    for name in MODELS:
        try:print(json.dumps({'model':name,'directory':provision(name,args.root)}),flush=True)
        except requests.RequestException:
            print(json.dumps({'model':name,'status':'blocked','hostname':'huggingface.co','reason':'NETWORK_OR_PROXY_ERROR'}),flush=True);failures+=1
        except (ValueError,KeyError,OSError) as error:
            reason=str(error) if isinstance(error,ValueError) else type(error).__name__
            print(json.dumps({'model':name,'status':'blocked','reason':reason}),flush=True);failures+=1
    raise SystemExit(1 if failures else 0)
