"""Read-only registry, installed product graph and lock audit; no install or fixes."""
import datetime, hashlib, json, os, shutil, subprocess, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'research/preacceptance';PRODUCT=ROOT.parent/'attune-live-test'
OUT.mkdir(parents=True,exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
def run(name,args,cwd):
    p=subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (OUT/(name+'.json')).write_bytes(p.stdout)
    (OUT/(name+'.stderr.txt')).write_bytes(p.stderr)
    return {'exitCode':p.returncode,'sha256':hashlib.sha256(p.stdout).hexdigest()}
npm=shutil.which('npm.cmd');assert npm
proof={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceHead':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip(),'installPerformed':False,'candidateApplied':False,'runs':{}}
proof['runs']['fullAudit']=run('audit-full',[npm,'audit','--json'],ROOT)
proof['runs']['productionAudit']=run('audit-production',[npm,'audit','--omit=dev','--json'],ROOT)
proof['runs']['installedProductTree']=run('installed-product-tree',[npm,'ls','--all','--json'],PRODUCT)
proof['runs']['affectedPaths']=run('affected-paths',[npm,'ls','braces','micromatch','fast-glob','chokidar','eslint','eslint-config-next','@next/eslint-plugin-next','--all','--json'],PRODUCT)
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'attune-readonly-review','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
names=['braces','micromatch','fast-glob','chokidar','tailwindcss','eslint','eslint-config-next','@next/eslint-plugin-next','eslint-plugin-react','eslint-plugin-import','eslint-plugin-jsx-a11y','eslint-plugin-react-hooks','@typescript-eslint/eslint-plugin','next']
metadata={}
for name in names:
    p=get('https://registry.npmjs.org/'+name.replace('/','%2f'))
    def stable(v):return all(x.isdigit() for x in v.split('.')) and len(v.split('.'))==3
    versions=sorted([v for v in p['versions'] if stable(v)],key=lambda v:tuple(map(int,v.split('.'))))
    selected={p['dist-tags']['latest']}
    if name in ['next','eslint-config-next','@next/eslint-plugin-next']:selected.add([v for v in versions if v.startswith('15.')][-1])
    if name=='eslint':selected.update([v for v in versions if v.startswith(m+'.')][-1] for m in ['8','9'])
    if name=='tailwindcss':selected.add([v for v in versions if v.startswith('3.')][-1])
    metadata[name]={'source':'https://registry.npmjs.org/'+name,'distTags':p['dist-tags'],'versions':{v:{k:p['versions'][v].get(k) for k in ['version','dependencies','peerDependencies','peerDependenciesMeta','engines','deprecated']}|{'publishedAt':p.get('time',{}).get(v)} for v in sorted(selected)}}
(OUT/'registry-metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
advisory=get('https://api.github.com/advisories/GHSA-vfj7-8cjw-p6xm')
(OUT/'official-advisory.json').write_text(json.dumps(advisory,indent=2),encoding='utf-8')
lock=json.loads((ROOT/'package-lock.json').read_text())
paths={k:v for k,v in lock['packages'].items() if k.rsplit('node_modules/',1)[-1] in ['braces','micromatch','fast-glob','chokidar','tailwindcss','eslint','eslint-config-next','@next/eslint-plugin-next']}
(OUT/'affected-lock-entries.json').write_text(json.dumps(paths,indent=2),encoding='utf-8')
proof['fullAudit']=json.loads((OUT/'audit-full.json').read_text())['metadata']['vulnerabilities']
proof['productionAudit']=json.loads((OUT/'audit-production.json').read_text())['metadata']['vulnerabilities']
proof['patchedVersions']=[x.get('first_patched_version') for x in advisory.get('vulnerabilities',[])]
(OUT/'dependency-proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
print(json.dumps(proof))
