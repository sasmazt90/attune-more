#!/usr/bin/env python3
"""Verify a downloaded Drive inventory and restore immutable production files.

Use a Cloud/Linux workspace. No credentials, downloads or deletion are performed.
Existing matching bytes are reused; existing mismatched bytes are never replaced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def contained(root,name):
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('PATH_OUTSIDE_ROOT')
    return path


def restore(inventory,backup_root,repository_root,runtime_root=None,apply=False):
    if apply and not inventory.get('complete'):raise ValueError('VERIFIED_COMPLETE_INVENTORY_REQUIRED')
    checked=[]
    for item in inventory['files']:
        source=contained(backup_root,item['backupPath'])
        if not source.is_file() or source.stat().st_size!=item['bytes'] or digest(source)!=item['sha256']:
            raise ValueError('BACKUP_FILE_INTEGRITY_MISMATCH')
        target=None
        if item.get('activeForRestore') is False:target=None
        elif item.get('repositoryPath'):target=contained(repository_root,item['repositoryPath'])
        elif item.get('runtimePath'):
            if runtime_root is None and apply:raise ValueError('RUNTIME_ROOT_REQUIRED')
            if runtime_root is not None:target=contained(runtime_root,item['runtimePath'])
        if target and target.exists() and digest(target)!=item['sha256']:raise ValueError('EXISTING_FILE_MISMATCH_NO_OVERWRITE')
        checked.append((source,target,item))
    # Validate everything before writing any file.
    for source,target,item in checked:
        if apply and target and not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            with source.open('rb') as incoming,target.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
            if digest(target)!=item['sha256']:raise ValueError('RESTORE_HASH_MISMATCH')
    return {'filesVerified':len(checked),'filesWithRestorePaths':sum(t is not None for _,t,_ in checked),
            'mode':'restored' if apply else 'audit-only','completeInventory':bool(inventory.get('complete'))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,required=True);parser.add_argument('--backup-root',type=Path,required=True)
    parser.add_argument('--repository-root',type=Path,required=True);parser.add_argument('--runtime-root',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    result=restore(json.loads(args.inventory.read_text()),args.backup_root,args.repository_root,args.runtime_root,args.apply)
    print(json.dumps(result))


if __name__=='__main__':main()
