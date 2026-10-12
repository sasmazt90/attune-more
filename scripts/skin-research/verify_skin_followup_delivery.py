"""Owned shortcut, staged UTF-8 source bytes, served JS and actual v2 API."""
import hashlib,json,re,subprocess,urllib.request
from pathlib import Path
import psutil,pythoncom
from win32com.shell import shell
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/bag-label-followup-20261012';HOME=Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def get(url):
 with urllib.request.urlopen(url,timeout=15) as r:return r.read()
receipt=json.loads((ROOT/'.runtime/skin-bag-label-20261012-v2/source-receipt.json').read_text('utf-8-sig'));matches={name:sha(ROOT/name)==digest for name,digest in receipt.items()};assert all(matches.values())
build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text('utf8').strip();browser=json.loads((ROOT/'output/playwright/bag-label-followup-20261012/proof.json').read_text('utf8'));buildMatch=build==browser['buildId'];assert buildMatch
link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink);link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(HOME.parent/'TOGG Başlat.lnk'));shortcutMatch=Path(link.GetArguments().strip('"')).samefile(HOME/'start_togg.pyw');assert shortcutMatch
session=json.loads((HOME/'session.json').read_text('utf8'));normal=session['status']=='running' and not session['verification'];assert normal
frontendOwned=Path(psutil.Process(session['frontend_pid']).cwd()).resolve()==ROOT/'apps/vehicle-app';backendOwned=str(ROOT/'services/core-api').lower() in ' '.join(psutil.Process(session['backend_pid']).cmdline()).lower();assert frontendOwned and backendOwned
chunks={}
for route in ('/','/skin','/profile'):
 html=get('http://127.0.0.1:3000'+route).decode('utf8')
 for url in set(re.findall(r'(?:src|href)="([^" ]+\.js(?:\?[^" ]*)?)"',html)):
  if not url.startswith('/_next/'):continue
  file=ROOT/'apps/vehicle-app/.next'/url.split('?')[0].removeprefix('/_next/');served=hashlib.sha256(get('http://127.0.0.1:3000'+url)).hexdigest();local=sha(file);assert served==local;chunks[url]=dict(servedSHA256=served,localSHA256=local,matches=served==local)
assert chunks
p=json.loads((OUT/'36e4010b-v2-payload.json').read_text('utf8'));expected=json.loads((OUT/'36e4010b-normal-api.json').read_text('utf8'));request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',data=json.dumps(p).encode('utf8'),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=90) as r:actual=json.loads(r.read())
apiMatch=actual['measurements']==expected['measurements'] and actual['maps']==expected['maps'];assert apiMatch
bag=next(v for v in actual['measurements']['periorbital'] if v['id']=='bags');scopeMatch=bag['components']['samplingSupportVersion']=='tracked-center-closed-cells-v2';assert scopeMatch
model=ROOT/'services/core-api/models/skin-focused-degrees.onnx';loaded=[v['modelHash'] for v in actual['general'].get('modelInference',{}).values() if v.get('modelHash')];modelMatch=bool(loaded) and all(v==sha(model) for v in loaded);assert modelMatch
files=['appearance_analysis.py','instant_appearance.py','skin_general.py','skin_models.py','hosted_skin_type.py'];sourceHashes={n:sha(ROOT/'services/core-api'/n) for n in files}
committed={}
for path in ['services/core-api/'+n for n in files]:
 gitBytes=subprocess.check_output(['git','show',':'+path],cwd=ROOT);working=(ROOT/path).read_bytes();committed[path]=dict(gitIndexSHA256=hashlib.sha256(gitBytes).hexdigest(),workingSHA256=hashlib.sha256(working).hexdigest(),canonicalLFMatch=gitBytes==working.replace(b'\r\n',b'\n'));assert committed[path]['canonicalLFMatch'],'Indexed source drift'
evidence=dict(headAtVerification=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),buildId=build,buildMatchesBrowser=buildMatch,normalShortcutMatch=shortcutMatch,normalSession=normal,frontendOwned=frontendOwned,backendOwned=backendOwned,frontendSources=matches,servedJavaScript=chunks,actualAPIEqualsCaptured=apiMatch,samplingScopeMatch=scopeMatch,backendSourceSHA256=sourceHashes,modelFileSHA256=sha(model),loadedModelSHA256=sorted(set(loaded)),modelMatch=modelMatch,modelManifestSHA256=sha(ROOT/'services/core-api/models/skin-focused.json'),indexedSource=committed)
(OUT/'delivery.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(buildId=build,frontendMatches=sum(matches.values()),servedJSMatched=sum(v['matches'] for v in chunks.values()),normalShortcutMatch=shortcutMatch,actualAPIEqualsCaptured=apiMatch,modelMatch=modelMatch)))
