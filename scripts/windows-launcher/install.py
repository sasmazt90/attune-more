"""Install only the verified launcher source; preserve shortcut, profile and data."""
import argparse,json,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[2];source=Path(__file__).resolve().parent;dest=args.destination.resolve()
assert dest.name=='.launcher' and dest.parent.name=='7. TOGG','Expected explicitly approved TOGG launcher directory'
assert (root/'apps/vehicle-app/.next/BUILD_ID').is_file(),'Verified production build required'
proof=json.loads((root/'audit-results/windows-launcher.json').read_text(encoding='utf-8'))
assert proof['coldOpen']['buildId']==(root/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'Launcher proof must match the current build'
assert all(proof.get(key)=='PASS' for key in ['repeatedLaunch','firstWindowCloseKeepsServices','lastWindowCloseOwnedCleanup','persistentStorageAfterReopen','occupiedOtherAppPortSafe','frontendStartupFailureCleansOwnedBackend'])
assert dest.is_dir() and (dest/'start_togg.pyw').is_file(),'Existing launcher required'
suffix=time.strftime('%Y%m%d-%H%M%S')
for name in ['start_togg.pyw','backend_host.py']:
 target=dest/name;old=target.read_bytes();(dest/(name+'.followup-backup-'+suffix)).write_bytes(old)
 text=(source/name).read_text(encoding='utf-8')
 if name=='start_togg.pyw':text=text.replace('ROOT = Path(__file__).resolve().parents[2]','ROOT = Path('+repr(str(root))+')')
 target.write_text(text,encoding='utf-8')
print(json.dumps({'installedDirectory':str(dest),'buildId':proof['coldOpen']['buildId'],'shortcutModified':False,'profileDeleted':False,'dataDeleted':False}))
