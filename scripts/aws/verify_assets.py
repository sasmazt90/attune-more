#!/usr/bin/env python3
"""Verify reviewed path/size/hash asset manifests without downloading or replacing models."""
import argparse
import hashlib
import json
from pathlib import Path

def verify(root, entries):
    results=[]
    for entry in entries:
        path=(root/entry['path']).resolve()
        if not path.is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError('Asset path escapes bundle')
        item={'path':entry['path'],'status':'BLOCKED'}
        if not path.is_file():item['reason']='MISSING'
        else:
            digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
            item.update(bytes=path.stat().st_size,sha256=digest)
            if item['bytes']==entry['bytes'] and digest==entry['sha256']:item['status']='VERIFIED'
            else:item['reason']='HASH_OR_SIZE_MISMATCH'
        results.append(item)
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report={'assets':verify(a.root,json.loads(a.manifest.read_text())['assets']),'inference':'NOT_RUN'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['assets'] and all(r['status']=='VERIFIED' for r in report['assets']) else 2)
