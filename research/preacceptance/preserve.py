import hashlib, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args]).decode('utf-8').strip()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def snapshot():
    result={'repositories':{}}
    for name in ['togg-health-mvp','attune-live-test','attune-dependency-prototype','attune-biome-feasibility']:
        root=ROOT/name
        paths=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
        result['repositories'][name]={'head':git(root,'rev-parse','HEAD'),'status':git(root,'status','--porcelain'),
            'trackedHashes':{p:sha(root/p) for p in paths if p and (root/p).is_file()}}
    product=ROOT/'attune-live-test'
    manifest=json.loads((product/'audit-results/uat-closure-20261003/preservation-before-final.json').read_text())
    result['ledgers']={p:sha(product/p) for p in manifest['preservedLedgerHashes']}
    result['environmentFileHash']=sha(product/'.env.local')
    folders=list(Path('C:/Users/PC/Desktop').glob('*/Applications/7. TOGG'))
    assert len(folders)==1
    folder=folders[0]
    result['shortcut']={p.name:sha(p) for p in folder.glob('*.lnk')}
    result['installedLauncher']={p.name:sha(p) for p in (folder/'.launcher').glob('*.py*') if p.is_file()}
    result['buildId']=(product/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
    return result

out=Path(sys.argv[1]);current=snapshot();out.write_text(json.dumps(current,indent=2),encoding='utf-8')
if len(sys.argv)>2:
    initial=json.loads(Path(sys.argv[2]).read_text())
    assert current==initial,'Preservation difference; inspect before reporting'
    print(json.dumps({'preservation':'PASS','ledgers':len(current['ledgers']),'repositories':4,'shortcutAndLauncherUnchanged':True,'buildId':current['buildId']}))
else:print(json.dumps({'snapshot':'PASS','repositories':4,'ledgers':len(current['ledgers'])}))
