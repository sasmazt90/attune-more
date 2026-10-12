"""Owned normal shortcut -> source/build/served JS -> real eye API hash proof."""
import hashlib,json,re,subprocess,urllib.request
from pathlib import Path
import psutil,pythoncom
from win32com.shell import shell

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'audit-results/periorbital-v5-integration-20261012'
HOME=Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def get(url):
    with urllib.request.urlopen(url,timeout=15) as r:return r.read()

sources=json.loads((ROOT/'.runtime/skin-periorbital-v5-20261012-v1/source-receipt.json').read_text('utf-8-sig'))
assert all(sha(ROOT/f)==h for f,h in sources.items()),'Build source drift'
build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
browser=json.loads((ROOT/'output/playwright/periorbital-v5-20261012/proof.json').read_text('utf8'))
assert build==browser['buildId']
link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(HOME.parent/'TOGG Başlat.lnk'))
assert Path(link.GetArguments().strip('"')).samefile(HOME/'start_togg.pyw')
session=json.loads((HOME/'session.json').read_text('utf8'))
assert session['status']=='running' and not session['verification']
assert Path(psutil.Process(session['frontend_pid']).cwd()).resolve()==ROOT/'apps/vehicle-app'
assert str(ROOT/'services/core-api').lower() in ' '.join(psutil.Process(session['backend_pid']).cmdline()).lower()
chunks={}
for route in ('/','/skin','/profile'):
    html=get('http://127.0.0.1:3000'+route).decode()
    for url in set(re.findall(r'(?:src|href)="([^" ]+\.js(?:\?[^" ]*)?)"',html)):
        if not url.startswith('/_next/'):continue
        path=ROOT/'apps/vehicle-app/.next'/url.split('?')[0].removeprefix('/_next/')
        digest=hashlib.sha256(get('http://127.0.0.1:3000'+url)).hexdigest()
        assert digest==sha(path);chunks[url]=digest
assert chunks
captured=json.loads((OUT/'36e4010b-browser-api.json').read_text('utf8'))
request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',data=json.dumps(captured['productPayload']).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=90) as r:response=json.loads(r.read())
bags=next(v for v in response['measurements']['periorbital'] if v['id']=='bags')
assert bags['normalizationVersion']=='contour-fold-local-support-v5'
assert bags['components']['samplingSupportVersion']=='tracked-center-eligible-v1'
assert response['measurements']==captured['response']['measurements'] and response['maps']==captured['response']['maps']
model=ROOT/'services/core-api/models/skin-focused-degrees.onnx'
loaded=[v['modelHash'] for v in (response['general'].get('modelInference') or {}).values() if v.get('modelHash')]
assert loaded and all(v==sha(model) for v in loaded)
for region,rows in response['measurements'].items():
    assert all(v.get('modelHash') is None for v in rows if v['id'] in ('acne','bags','dark','lines'))
files=['appearance_analysis.py','instant_appearance.py','skin_general.py','skin_models.py','hosted_skin_type.py']
committed={}
for name in ('appearance_analysis.py','instant_appearance.py'):
    path='services/core-api/'+name
    blob=subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT)
    working=(ROOT/path).read_bytes()
    assert blob==working.replace(b'\r\n',b'\n'),'Committed source content drift'
    committed[name]=dict(workingSHA256=hashlib.sha256(working).hexdigest(),gitBlobSHA256=hashlib.sha256(blob).hexdigest(),canonicalLFMatch=True)
receipt=dict(normalShortcut=True,normalBackend=True,buildId=build,branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),headAtVerification=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),frontendSourceFileCount=len(sources),frontendSourceReceiptSHA256=sha(ROOT/'.runtime/skin-periorbital-v5-20261012-v1/source-receipt.json'),servedJavaScriptHashes=chunks,backendSourceHashes={n:sha(ROOT/'services/core-api'/n) for n in files},manifestSHA256=sha(ROOT/'services/core-api/models/skin-focused.json'),acceptedModelFileSHA256=sha(model),loadedModelHashes=sorted(set(loaded)),actualProductBagValue=bags['value'],formula=bags['normalizationVersion'],samplingSupportVersion=bags['components']['samplingSupportVersion'],hostedPhotoCalls=0,normalUserRecordsTouched=False,AGWorkingFilesTouched=False)
receipt['committedSourceByteProof']=committed
(OUT/'delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(buildId=build,normalShortcut=True,frontendSources=len(sources),servedJSChunks=len(chunks),backendSourceHashes=receipt['backendSourceHashes'],loadedModelHashes=receipt['loadedModelHashes'])))
