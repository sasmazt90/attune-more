#!/usr/bin/env python3
"""Checkpoint a non-secret Drive transfer inventory; network I/O uses Drive tools.

An upload ID is saved before independent retrieval. Only a size/SHA-256 verified
readback becomes a receipt. Existing IDs are reused; WAVs are never overwritten.
Keep the state directory on the Cloud workspace, outside the repository.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'apps/vehicle-app/public'
MANIFEST=PUBLIC/'audio/mental/v1/female-calm-v1-manifest.json'


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):
    temporary=path.with_suffix(path.suffix+'.new')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)


def load(path,default):
    return json.loads(path.read_text()) if path.exists() else default


class Inventory:
    def __init__(self,state):
        self.state=Path(state);self.folders=load(self.state/'folders.json',{})
        self.path=self.state/'inventory-progress.json';self.pending_path=self.state/'pending.json'
        self.inventory=load(self.path,{'complete':False,'files':[]});self.pending=load(self.pending_path,{})

    def item(self,path,backup,**extra):
        path=Path(path).resolve();folder=backup.rsplit('/',1)[0]
        if not path.is_file():raise ValueError('SOURCE_MISSING')
        return dict(sourcePath=str(path),backupPath=backup,fileName=path.name,parentFolderId=self.folders[folder]['id'],
                    bytes=path.stat().st_size,sha256=digest(path),**extra)

    def queue(self,limit):
        manifest=load(MANIFEST,{})
        generated=sum(bool(e.get('sha256')) for e in manifest['entries'])
        cache=load(self.state.parent/'mental-asr/review-cache.json',{'assets':{}})
        # Immutable snapshots survive interruptions between production checkpoints.
        snapshots=self.state/'outbox/snapshots';snapshots.mkdir(parents=True,exist_ok=True)
        for label,count,value in [('catalog',generated,manifest),('pronunciation',len(cache['assets']),cache)]:
            marker='last'+label.title()+'SnapshotBucket';bucket=count//25
            if bucket>self.inventory.get(marker,-1):
                path=snapshots/f'{label}-progress-{count:04d}.json'
                if not path.exists():write(path,value)
                self.inventory[marker]=bucket
        write(self.path,self.inventory)
        candidates=[]
        # Recover every earlier transfer source and pending ID before new work.
        for item in self.pending.values():
            if Path(item['sourcePath']).is_file():candidates.append(self.item(item['sourcePath'],item['backupPath'],**{
                k:item[k] for k in ('repositoryPath','runtimePath','assetId','activeForRestore') if k in item}))
        for path in sorted(self.state.glob('inventory-progress-*.json')):
            candidates.append(self.item(path,'snapshots/'+path.name))
        for path in sorted(self.state.glob('pronunciation-progress-*.json')):
            candidates.append(self.item(path,'snapshots/'+path.name))
        for path in sorted((self.state/'outbox').glob('*/*')):
            if not path.is_file():continue
            extra={}
            if path.parent.name=='closing-validation':extra['repositoryPath']='docs/mental-structured/closing-female-calm-v1/'+path.name
            targets={'female-calm-v1-manifest-final.json':'apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json',
                     'content-final.json':'shared/mental/v1/content.json',
                     'catalog-validation.json':'docs/mental-structured/catalog-validation.json'}
            if path.parent.name=='reports' and path.name in targets:extra['repositoryPath']=targets[path.name]
            candidates.append(self.item(path,path.parent.name+'/'+path.name,**extra))
        closing=ROOT/'docs/mental-structured/closing-female-calm-v1'
        for path in sorted(closing.glob('??-closing.wav')):
            candidates.append(self.item(path,'closing-validation/'+path.name,repositoryPath=str(path.relative_to(ROOT))))
        for entry in manifest['entries']:
            for recording,active in [(r,False) for r in entry.get('supersededRecordings',[])]+[(entry,True)]:
                if not recording.get('sha256'):continue
                path=PUBLIC/recording['audioPath'].lstrip('/')
                if digest(path)!=recording['sha256']:raise ValueError('CATALOG_SOURCE_HASH_MISMATCH')
                candidates.append(self.item(path,f"catalog/{entry['language']}/{path.name}",
                    repositoryPath=str(path.relative_to(ROOT)),assetId=entry['assetId'],activeForRestore=active))
        known={x['backupPath']:x for x in self.inventory['files']};result=[];seen=set()
        for item in candidates:
            key=item['backupPath']
            if key in seen:continue
            seen.add(key);old=known.get(key);pending=self.pending.get(key,{})
            if old and old['sha256']==item['sha256'] and old.get('retrievalVerified'):continue
            previous=old or pending
            if previous:
                changed=previous['sha256']!=item['sha256']
                if changed and item['fileName'].endswith('.wav'):raise ValueError('AUDIO_BACKUP_NO_OVERWRITE')
                item.update({k:previous[k] for k in ('driveFileId','driveURL') if k in previous})
                if changed:item['replaceMetadata']=True
            result.append(item)
            if len(result)>=limit:break
        return result

    def uploaded(self,item):
        key=item['backupPath'];old=self.pending.get(key)
        if old and old.get('driveFileId')!=item['driveFileId']:raise ValueError('DUPLICATE_UPLOAD_ID')
        self.pending[key]=item;write(self.pending_path,self.pending)

    def receipt(self,item):
        source=Path(item['sourcePath']);readback=Path(item['readbackPath'])
        if any(p.stat().st_size!=item['bytes'] or digest(p)!=item['sha256'] for p in (source,readback)):
            raise ValueError('READBACK_SHA256_OR_SIZE_MISMATCH')
        old=next((x for x in self.inventory['files'] if x['backupPath']==item['backupPath']),None)
        if old and old['sha256']!=item['sha256'] and (not item.get('replaceMetadata') or source.suffix=='.wav'):
            raise ValueError('BACKUP_NO_OVERWRITE')
        record={k:v for k,v in item.items() if k not in ('sourcePath','readbackPath','fileName','parentFolderId','replaceMetadata')}
        record.update(retrievalVerified=True,verifiedBy='independent-Drive-fetch-materialized-SHA256',verifiedAt=datetime.now(timezone.utc).isoformat())
        if old:self.inventory['files'].remove(old)
        self.inventory['files'].append(record);self.inventory['complete']=False;write(self.path,self.inventory)
        if len(self.inventory['files'])%25==0:
            snapshot=self.state/f"inventory-progress-{len(self.inventory['files']):04d}.json"
            if not snapshot.exists():write(snapshot,self.inventory)

    def status(self):
        manifest=load(MANIFEST,{})
        cache=load(self.state.parent/'mental-asr/review-cache.json',{'assets':{}})
        return dict(catalogGenerated=sum(bool(e.get('sha256')) for e in manifest['entries']),expected=414,
            screened=len(cache['assets']),driveFilesVerified=len(self.inventory['files']),complete=self.inventory.get('complete',False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',type=Path,required=True)
    p.add_argument('action',choices=('queue','uploaded','receipt','status'));p.add_argument('--limit',type=int,default=25);p.add_argument('--item')
    args=p.parse_args();inventory=Inventory(args.state)
    if args.action=='queue':result=inventory.queue(args.limit)
    elif args.action=='status':result=inventory.status()
    else:
        getattr(inventory,args.action)(json.loads(args.item));result=inventory.status()
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
