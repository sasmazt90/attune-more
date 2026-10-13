"""Unchanged production delivery: normal shortcut, loaded code, served JS and models."""
import argparse,hashlib,json,re,subprocess,urllib.request
from pathlib import Path
import psutil,pythoncom
from win32com.shell import shell
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/dry-sag-robust-followup-20261013'
parser=argparse.ArgumentParser();parser.add_argument('--response',type=Path);parser.add_argument('--camera',type=Path);parser.add_argument('--out',type=Path);args=parser.parse_args()
OUT=args.out or OUT;OUT.mkdir(parents=True,exist_ok=True)
assert OUT.resolve().is_relative_to((ROOT/'audit-results').resolve())
LAUNCHER=Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def get(url):
    with urllib.request.urlopen(url,timeout=15) as response:return response.read()
session=json.loads((LAUNCHER/'session.json').read_text('utf8'));assert session['status']=='running' and not session['verification']
link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(LAUNCHER.parent/'TOGG Başlat.lnk'))
shortcut=Path(link.GetArguments().strip('"')).samefile(LAUNCHER/'start_togg.pyw');assert shortcut
front=psutil.Process(session['frontend_pid']);back=psutil.Process(session['backend_pid'])
front_owned=Path(front.cwd()).resolve()==ROOT/'apps/vehicle-app';back_owned=str(ROOT/'services/core-api').lower() in ' '.join(back.cmdline()).lower();assert front_owned and back_owned
build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip()
browser=json.loads((args.camera or ROOT/'output/playwright'/OUT.name/'camera-receipt.json').read_text('utf8'));assert build==browser['buildId']
previous=json.loads((ROOT/'.runtime/skin-dry-sag-native-final-20261013/source-receipt.json').read_text('utf-8-sig'))
front_sources={path:sha(ROOT/path)==digest for path,digest in previous.items()};assert all(front_sources.values())
backend_files=['appearance_analysis.py','instant_appearance.py','skin_general.py','skin_models.py','hosted_skin_type.py'];backend={}
for name in backend_files:
    path='services/core-api/'+name;working=(ROOT/path).read_bytes();committed=subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT)
    matches=committed==working.replace(b'\r\n',b'\n');fresh=back.create_time()>=(ROOT/path).stat().st_mtime
    assert matches and fresh,(path,matches,fresh)
    backend[path]=dict(workingSHA256=sha(ROOT/path),headCanonicalSHA256=hashlib.sha256(committed).hexdigest(),canonicalMatches=matches,loadedAfterSourceWrite=fresh)
chunks={}
for route in ('/','/skin','/profile'):
    html=get('http://127.0.0.1:3000'+route).decode('utf8')
    for url in set(re.findall(r'(?:src|href)="([^" ]+\.js(?:\?[^" ]*)?)"',html)):
        if not url.startswith('/_next/'):continue
        path=ROOT/'apps/vehicle-app/.next'/url.split('?')[0].removeprefix('/_next/')
        served=hashlib.sha256(get('http://127.0.0.1:3000'+url)).hexdigest();local=sha(path);assert served==local
        chunks[url]=dict(servedSHA256=served,localSHA256=local,matches=served==local)
assert chunks
model=sha(ROOT/'services/core-api/models/skin-focused-degrees.onnx');config=sha(ROOT/'services/core-api/models/skin-focused.json')
assert model=='65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3'
assert config=='accc9ff193030bccde572ded39b1878fc7919e33daf62f2ac560c3357a83abfb'
response=json.loads((args.response or OUT/'55ec00b8-automatic-api.json').read_text('utf8'))
runtime=response.get('modelRuntime') or response.get('general',{}).get('modelRuntime')
assert runtime,'Missing runtime evidence is not model-load success'
degrees=runtime['degrees'];used=response.get('general',{}).get('modelInference',{}).get('degrees')
assert degrees['fileHashVerified'] and degrees['sessionLoaded'] and degrees['loadedModelHash']==model
if degrees['usedInResponse']:
    assert degrees['status']=='used' and used and used['modelHash']==degrees['loadedModelHash']
else:
    assert degrees['status']=='not-used' and not used
model_runtime=dict(diskHashMatchesPin=model=='65936939048730950c8561f39546d048862ee6ec2efef04878d56d19c1dc0bf3',fileHashVerified=degrees['fileHashVerified'],sessionLoaded=degrees['sessionLoaded'],loadedModelHash=degrees['loadedModelHash'],usedInResponse=degrees['usedInResponse'],status=degrees['status'],responseModelHash=used.get('modelHash') if used else None)
sag=next(r for r in response['general']['measurements'] if r['id']=='sag');dry=next(r for r in response['general']['measurements'] if r['id']=='dry')
assert sag['normalizationVersion']=='contour-fold-lower-chin-visible-region-v8' and dry['normalizationVersion']=='eligible-flake-luma-union-v3'
receipt=dict(headAtVerification=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),buildId=build,normalShortcut=shortcut,normalSession=session['status'],frontendOwned=front_owned,backendOwned=back_owned,frontendSources=front_sources,backendSources=backend,servedJavaScript=chunks,modelSHA256=model,configSHA256=config,actualAutomaticSourceMatches=browser['sourceMatches'],actualSagNormalization=sag['normalizationVersion'],actualDryNormalization=dry['normalizationVersion'])
receipt['modelRuntime']=model_runtime
(OUT/'delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(head=receipt['headAtVerification'],buildId=build,frontendSourcesMatch=sum(front_sources.values()),servedJSMatch=len(chunks),backendSourceMatches=len(backend),normalShortcut=shortcut)))
