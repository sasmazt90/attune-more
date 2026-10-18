"""Read-only verification of this delivery, its actual served assets and protected trees."""
import hashlib,json,subprocess
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'cdc-progress/health-ui-consent-audio-followup-20261017'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(tree,*args):return subprocess.check_output(['git','-C',str(tree),*args],text=True).strip()
build=json.loads((OUT/'build-receipt.json').read_text('utf8'))
assert (ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()==build['BUILD_ID']
served=[]
for row in build['files']:
    path=row['path'].replace('\\','/');assert sha(ROOT/path)==row['sha256'],path
    if path.startswith('apps/vehicle-app/.next/static/'):
        suffix=path.split('.next/static/',1)[1]
        response=requests.get('http://127.0.0.1:3308/_next/static/'+suffix,timeout=10)
        assert response.status_code==200 and hashlib.sha256(response.content).hexdigest()==row['sha256']
        assert b'mentalProbe' not in response.content and b'ControlledRecognition' not in response.content
        served.append({'path':suffix,'bytes':len(response.content),'sha256':row['sha256']})
assert len(served)>20
for row in json.loads((OUT/'local-assets.json').read_text('utf8')):assert sha(ROOT/row['path'])==row['sha256'],row['path']
protected=[]
for name,expected in [
 ('attune-live-test','5f11c111e3f6547e6420ddf37db477190d232f10'),
 ('attune-cdc-acne-v5-integration','2637d1b3a342d333b43a40d53e195e8374c8691d'),
 ('attune-cdc-vision-technical-20261017','1cdb95ebdddd3a2fd4b83cca7408a1ae6cd3b502'),
 ('attune-cdc-mental-technical-20261017','eead4b23d92dc40887a3ed223628b2e1297cddea'),
 ('attune-antigravity-skin','d90ff95434c44b4e73ae77a7f1d5d6b2e167c987'),
 ('attune-claude-acne-audit','e6db3e1fc775b5cdbd09d63858993b2d55eb588f')]:
    tree=ROOT.parent/name;head=git(tree,'rev-parse','HEAD');status=git(tree,'status','--porcelain')
    assert head==expected
    if name!='attune-live-test':assert not status
    protected.append({'checkout':name,'commit':head,'status':status})
previous=json.loads((OUT.parent/'mental-technical-closeout-20261017/start.json').read_text('utf-8-sig'))
source_docs=[]
for name,expected in previous['sourceTaskFiles'].items():
    actual=sha(ROOT.parent/'attune-live-test'/name);assert actual==expected
    source_docs.append({'path':name,'sha256':actual,'matchesPrecedingFrozenSnapshot':actual==expected})
methods=[]
for path in (ROOT/'services/core-api').glob('*.py'):
    if path.name in ['main.py','vision_speech.py','mental_provider.py','mental_context.py']:continue
    rel=path.relative_to(ROOT).as_posix()
    original=subprocess.run(['git','show','2637d1b:'+rel],cwd=ROOT,capture_output=True)
    if original.returncode==0:
        assert original.stdout.replace(b'\r\n',b'\n')==path.read_bytes().replace(b'\r\n',b'\n'),rel
        methods.append({'path':rel,'sha256':sha(path)})
manifest=ROOT/'services/core-api/models/skin-focused.json'
original_manifest=subprocess.check_output(['git','show','2637d1b:services/core-api/models/skin-focused.json'],cwd=ROOT)
assert json.loads(original_manifest)==json.loads(manifest.read_text('utf8'))
old_guidance=json.loads(subprocess.check_output(['git','show','eead4b2:apps/vehicle-app/public/audio/guidance/manifest.json'],cwd=ROOT))
new_guidance=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text('utf8'))
assert all(new_guidance['entries'][k]==v for k,v in old_guidance['entries'].items() if k!='mental-entry')
config=requests.get('http://127.0.0.1:8308/api/local-health/skin/acne-v5-config',timeout=10).json()
assert config['enabled'] and config['productionAccepted'] is False
test_status=requests.get('http://127.0.0.1:8308/__test__/ledger',timeout=10).status_code
assert test_status==404
value={'BUILD_ID':build['BUILD_ID'],'servedJS':served,'servedJSCount':len(served),'sourceHashesVerified':len(build['files']),
       'preservedMethods':methods,'protected':protected,'sourceTaskFiles':source_docs,'acnePreview':config,
       'globalSkinManifestUnchanged':True,'otherGuidanceEntriesUnchanged':True,'fixtureEndpointStatus':test_status}
temporary=OUT/'served-protection-receipt.tmp';temporary.write_text(json.dumps(value,indent=2),'utf8');temporary.replace(OUT/'served-protection-receipt.json')
print(json.dumps({'BUILD_ID':build['BUILD_ID'],'servedJS':len(served),'sourceFiles':len(build['files']),'preservedMethods':len(methods),'protectedTrees':len(protected)}))
