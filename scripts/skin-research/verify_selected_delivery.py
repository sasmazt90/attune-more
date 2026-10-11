"""Normal shortcut, staged source bytes, served JS and actual local model proof.

Only previously exposed licensed fixture API inputs; no history writes or reads.
"""
import hashlib,json,re,subprocess,urllib.request
from pathlib import Path
import psutil,pythoncom
from win32com.shell import shell
from selected_sources import ROOT,OUT,write,sha

HOME=Path('C:/Users/PC/Desktop/YENİ İŞ/Applications/7. TOGG/.launcher')
def get(url):
 with urllib.request.urlopen(url,timeout=15) as response:return response.read()
def main():
 stage=ROOT/'.runtime/skin-selected-build-20261011-v2'
 sources=json.loads((stage/'source-receipt.json').read_text('utf-8-sig'))
 assert all(sha(ROOT/file)==digest for file,digest in sources.items()),'BUILD_SOURCE_DRIFT'
 build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
 assert build=='7I50XxDSrr_93mzJbonbz'
 link=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
 link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(HOME.parent/'TOGG Başlat.lnk'))
 assert Path(link.GetArguments().strip('"')).samefile(HOME/'start_togg.pyw')
 session=json.loads((HOME/'session.json').read_text('utf8'));assert session['status']=='running' and not session['verification']
 assert Path(psutil.Process(session['frontend_pid']).cwd()).resolve()==ROOT/'apps/vehicle-app'
 assert str(ROOT/'services/core-api').lower() in ' '.join(psutil.Process(session['backend_pid']).cmdline()).lower()
 chunk_checks={}
 for route in ['/','/skin']:
  html=get('http://127.0.0.1:3000'+route).decode()
  for url in set(re.findall(r'(?:src|href)="([^" ]+\.js(?:\?[^" ]*)?)"',html)):
   if not url.startswith('/_next/'):continue
   path=ROOT/'apps/vehicle-app/.next'/url.split('?')[0].removeprefix('/_next/')
   actual=hashlib.sha256(get('http://127.0.0.1:3000'+url)).hexdigest();assert actual==sha(path)
   chunk_checks[url]=actual
 assert chunk_checks
 samples=[]
 for index in [0,1,3,5]:
  payload=json.loads((ROOT/f'audit-results/all-health-20261010/natural-skin/{index}-payload-private.json').read_text('utf8'));payload['processingConsent']=True
  request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/skin',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
  with urllib.request.urlopen(request,timeout=90) as response:result=json.loads(response.read())
  assert all('status' in v and 'calibrationVersion' in v and 'coverage' in v for v in result['general']['measurements'])
  write(f'product/front-{index}-normal-api.json',result)
  samples.append(dict(index=index,modelDiagnostics=result.get('modelDiagnostics'),modelInference=result['general'].get('modelInference'),type=result['general']['skinType'],measurements=result['general']['measurements']))
 manifest=ROOT/'services/core-api/models/skin-focused.json'
 loaded=[v['modelHash'] for sample in samples for v in (sample['modelInference'] or {}).values() if v.get('modelHash')]
 assert loaded and all(value==sha(ROOT/'services/core-api/models/skin-focused-degrees.onnx') for value in loaded),'ACTUAL_LOADED_MODEL_HASH_MISMATCH'
 evidence=dict(buildId=build,frontendSourceHashes=sources,frontendSourceFiles=len(sources),backendSourceHashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'services/core-api').glob('skin*.py')},appearanceSourceSHA256=sha(ROOT/'services/core-api/appearance_analysis.py'),headAtVerification=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),servedJavaScriptHashes=chunk_checks,normalShortcut=True,normalBackend=True,manifestSHA256=sha(manifest),acceptedModelFileSHA256=sha(ROOT/'services/core-api/models/skin-focused-degrees.onnx'),samples=samples,normalHistoryWritten=False,personalPhysicalAcceptance=False,userPhotoTraining=False,paidCalls=0)
 write('product/delivery.json',evidence)
 print(json.dumps(dict(buildId=build,normalShortcut=True,sourceFiles=len(sources),servedJavaScriptChunks=len(chunk_checks),manifestSHA256=evidence['manifestSHA256'],modelFileSHA256=evidence['acceptedModelFileSHA256'],modelDiagnostics=[s['modelDiagnostics'] for s in samples]),indent=2))
if __name__=='__main__':main()
