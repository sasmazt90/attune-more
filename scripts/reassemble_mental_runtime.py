#!/usr/bin/env python3
"""Reassemble the existing verified Drive model parts in a Cloud workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def reassemble(manifest,parts_root,target):
    parts=sorted(manifest['parts'],key=lambda p:p['index'])
    if len(parts)!=manifest['part_count'] or len({p['index'] for p in parts})!=len(parts):raise ValueError('INCOMPLETE_PART_SET')
    for item in parts:
        path=(parts_root/item['filename']).resolve()
        if not path.is_relative_to(parts_root.resolve()) or path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('PART_INTEGRITY_MISMATCH')
    if target.exists():
        if target.stat().st_size==manifest['original_zip_bytes'] and digest(target)==manifest['original_zip_sha256']:return target
        raise ValueError('EXISTING_ARCHIVE_MISMATCH_NO_OVERWRITE')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out:
        for item in parts:
            with (parts_root/item['filename']).open('rb') as source:shutil.copyfileobj(source,out,1024*1024)
    if target.stat().st_size!=manifest['original_zip_bytes'] or digest(target)!=manifest['original_zip_sha256']:
        raise ValueError('REASSEMBLED_ARCHIVE_MISMATCH')
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--parts-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(reassemble(json.loads(a.manifest.read_text()),a.parts_root,a.output))
