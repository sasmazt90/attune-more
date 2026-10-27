"""Reassemble immutable binary evidence parts with size and SHA256 validation."""
import argparse,hashlib,json
from pathlib import Path


def reassemble(index,output):
    index=Path(index);output=Path(output);data=json.loads(index.read_text())
    if data.get('format')!='binary-concatenation-sha256-v1':raise ValueError('UNKNOWN_BUNDLE_FORMAT')
    if output.exists():raise FileExistsError(output)
    parts=[];seen=set()
    for part in data['parts']:
        name=part['path']
        if not name or Path(name).name!=name or '/' in name or '\\' in name or ':' in name or name in ('.','..') or name in seen:
            raise ValueError('UNSAFE_OR_DUPLICATE_PART_PATH')
        seen.add(name);raw=(index.parent/name).read_bytes()
        if len(raw)!=part['bytes'] or hashlib.sha256(raw).hexdigest()!=part['sha256']:raise ValueError('PART_IDENTITY_MISMATCH')
        parts.append(raw)
    raw=b''.join(parts)
    if len(raw)!=data['bytes'] or hashlib.sha256(raw).hexdigest()!=data['sha256']:raise ValueError('BUNDLE_IDENTITY_MISMATCH')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(raw)
    return dict(bytes=len(raw),sha256=data['sha256'],parts=len(parts))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(reassemble(a.index,a.output)))
