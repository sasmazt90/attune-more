#!/usr/bin/env python3
"""Reconcile required source hashes, independent receipts and final Drive listings.

The presence file is assembled from fresh Drive folder listings through connected
tools. This command performs no upload, deletion or network access. It never
turns an incomplete transfer into a completed backup.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re


def audit(inventory,required,presence,folders):
    rows=inventory['files'];by_path={r['backupPath']:r for r in rows}
    if len(by_path)!=len(rows) or len({r['driveFileId'] for r in rows})!=len(rows):raise ValueError('DUPLICATE_BACKUP_PATH_OR_DRIVE_ID')
    observed={row['id']:row for row in presence['files']};issues=[]
    if len({r['backupPath'] for r in required})!=len(required):raise ValueError('DUPLICATE_REQUIRED_BACKUP_PATH')
    known_ids={row['driveFileId'] for row in rows}
    for file_id in observed.keys()-known_ids:
        issues.append({'driveFileId':file_id,'issue':'Drive-file-missing-from-inventory'})
    for wanted in required:
        path=wanted['backupPath'];row=by_path.get(path)
        if not row:issues.append({'path':path,'issue':'missing-verified-receipt'});continue
        if row['bytes']!=wanted['bytes'] or row['sha256']!=wanted['sha256']:
            issues.append({'path':path,'issue':'source-receipt-mismatch'})
    for path,row in by_path.items():
        if not row.get('retrievalVerified') or not re.fullmatch('[0-9a-f]{64}',row.get('sha256','')) or row.get('bytes',0)<=0:
            issues.append({'path':path,'issue':'unverified-or-invalid-receipt'})
        current=observed.get(row['driveFileId']);parent=folders[path.rsplit('/',1)[0]]['id']
        if not current or parent not in current['parent_ids']:
            issues.append({'path':path,'issue':'missing-from-current-Drive-folder'})
        elif int(current['bytes'])!=row['bytes']:
            issues.append({'path':path,'issue':'Drive-size-changed'})
    active=[r for r in required if r.get('activeCatalog')]
    if len(active)!=414 or len({r['assetId'] for r in active})!=414:raise ValueError('EXPECTED_414_ACTIVE_CATALOG_RECORDINGS')
    return {'schema':'mental-drive-final-reconciliation-v1','complete':not issues,'requiredFiles':len(required),
        'verifiedInventoryFiles':len(rows),'inventoryBytes':sum(r['bytes'] for r in rows),'activeCatalogRecordings':len(active),
        'byLanguage':{lang:sum(r.get('language')==lang for r in active) for lang in ('tr','en','de')},
        'independentReadbackSHA256Required':True,'currentDrivePresenceCheckedAt':presence['checkedAt'],
        'verifiedAt':datetime.now(timezone.utc).isoformat(),'issues':issues,
        'controlFilePolicy':'Inventory and its integrity receipt are separate control files; no circular self-hash.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','required','presence','folders','report'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();report=audit(json.loads(a.inventory.read_text()),json.loads(a.required.read_text()),json.loads(a.presence.read_text()),json.loads(a.folders.read_text()))
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('complete','requiredFiles','verifiedInventoryFiles','activeCatalogRecordings')}))
    if not report['complete']:raise SystemExit('BACKUP_INCOMPLETE: see reconciliation report')


if __name__=='__main__':main()
