"""Normal existing LNK -> installed launcher -> clean source -> served build.
Closes only windows belonging to its verified product Chrome profile. Other
visible Chrome windows are inventoried and preserved. No user storage changes.
"""
import argparse,base64,hashlib,json,os,socket,subprocess,time,urllib.request
from pathlib import Path
import psutil,pythoncom,win32gui,win32process,win32con
from win32com.shell import shell
ROOT=Path(__file__).resolve().parents[1]
HOME=Path(r'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\.launcher')
parser=argparse.ArgumentParser();parser.add_argument('--output',default='audit-results/postmeeting/delivery.json');args=parser.parse_args()
LINK=HOME.parent/'TOGG Başlat.lnk';OUT=(ROOT/args.output).resolve();assert OUT.is_relative_to(ROOT/'audit-results');OUT.parent.mkdir(parents=True,exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
assert git('status','--porcelain')=='','Commit verified source before delivery proof'
head=git('rev-parse','HEAD');build=(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()
# WScript.CreateShortcut transliterates this host's Turkish path to a missing
# ASCII path. Native IPersistFile loads the actual Unicode LNK without editing it.
shortcut=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
shortcut.QueryInterface(pythoncom.IID_IPersistFile).Load(str(LINK))
target=shortcut.GetPath(0)[0];arguments=shortcut.GetArguments()
# The installed shortcut intentionally uses the existing 8.3 path. Compare
# filesystem identity instead of assuming its spelling matches the long path.
assert Path(arguments.strip('"')).samefile(HOME/'start_togg.pyw')
assert Path(target).name.lower()=='pythonw.exe'
installed=(HOME/'start_togg.pyw').read_text('utf8')
expected=(ROOT/'scripts/windows-launcher/start_togg.pyw').read_text('utf8').replace('ROOT = Path(__file__).resolve().parents[2]','ROOT = Path('+repr(str(ROOT))+')')
assert installed==expected
assert (HOME/'backend_host.py').read_bytes()==(ROOT/'scripts/windows-launcher/backend_host.py').read_bytes()
source={}
for rel in git('ls-files','apps/vehicle-app/src','services/core-api','scripts/windows-launcher','apps/vehicle-app/public/audio','third-party/combined-health','shared','package.json','package-lock.json','apps/vehicle-app/package.json').splitlines():
 source[rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
# The exported weights/diagnostics are loaded by Python, not compiled into Next.
# Keep source/build freshness strict for program code, banks and notices. The
# two generated model artifacts are instead checked by SHA and real inference.
model_artifacts={'services/core-api/models/dental-yolox-s.onnx','services/core-api/models/dental-yolox-s.json'}
assert (ROOT/'apps/vehicle-app/.next/BUILD_ID').stat().st_mtime>=max((ROOT/p).stat().st_mtime for p in source if p not in model_artifacts)
manifest=json.loads((ROOT/'apps/vehicle-app/.next/app-build-manifest.json').read_text())['pages']
chunks=sorted({p for route,paths in manifest.items() for p in paths}|{p.relative_to(ROOT/'apps/vehicle-app/.next').as_posix() for p in (ROOT/'apps/vehicle-app/.next/static/chunks').rglob('*.js')})
hashes={rel:hashlib.sha256((ROOT/'apps/vehicle-app/.next'/rel).read_bytes()).hexdigest() for rel in chunks}
def state():return json.loads((HOME/'session.json').read_text())
def wait(check,seconds=45):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  try:
   value=check()
   if value:return value
  except Exception:pass
  time.sleep(.2)
 raise AssertionError('Bounded lifecycle check timed out')
def free(port):
 with socket.socket() as s:s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))!=0
assert free(3000) and free(8000),'Refuse to adopt/stop another service'
def live_state():
 value=state()
 if value.get('status')!='running' or not all(psutil.pid_exists(value.get(k,-1)) for k in ['frontend_pid','backend_pid','browser_pid']):return None
 if free(3000) or free(8000):return None
 return value
def windows():
 rows=[]
 def collect(hwnd,_):
  if not win32gui.IsWindowVisible(hwnd):return
  pid=win32process.GetWindowThreadProcessId(hwnd)[1]
  try:
   if psutil.Process(pid).name().lower()=='chrome.exe':rows.append({'hwnd':hwnd,'pid':pid})
  except psutil.Error:pass
 win32gui.EnumWindows(collect,None);return rows
other=windows();os.startfile(str(LINK));running=wait(live_state)
assert running['url']=='http://127.0.0.1:3000' and Path(running['profile']).resolve()==(HOME/'chrome-profile').resolve()
assert Path(psutil.Process(running['frontend_pid']).cwd()).resolve()==ROOT/'apps/vehicle-app'
assert str(ROOT/'services/core-api').lower() in ' '.join(psutil.Process(running['backend_pid']).cmdline()).lower()
for rel,digest in hashes.items():
 with urllib.request.urlopen('http://127.0.0.1:3000/_next/'+rel,timeout=5) as response:assert hashlib.sha256(response.read()).hexdigest()==digest
for route in ['skin','vision','mental','dental','hearing','privacy','profile']:
 with urllib.request.urlopen('http://127.0.0.1:3000/'+route,timeout=5) as response:
  html=response.read().decode();assert all(rel in html for rel in manifest['/'+route+'/page'] if '/app/'+route+'/page-' in rel)
with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=5) as response:runtime=json.loads(response.read())
assert runtime['runtimeIsolated'] and runtime['runtimeVersions']=={'fastapi':'0.135.4','starlette':'1.3.1','aiohttp':'3.14.3','PIL':'12.3.0'}
guidance=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text('utf8'))
for entry in guidance['entries'].values():
 with urllib.request.urlopen('http://127.0.0.1:3000'+entry['url'],timeout=5) as response:assert hashlib.sha256(response.read()).hexdigest()==entry['sha256']
bank=json.loads((ROOT/'apps/vehicle-app/public/audio/hearing-bank/manifest.json').read_text('utf8'))
for entry in [*bank['digits'],bank['noise']]:
 with urllib.request.urlopen('http://127.0.0.1:3000'+entry['url'],timeout=5) as response:assert hashlib.sha256(response.read()).hexdigest()==entry['sha256']
model=json.loads((ROOT/'services/core-api/models/dental-yolox-s.json').read_text('utf8'))
assert hashlib.sha256((ROOT/'services/core-api/models/dental-yolox-s.onnx').read_bytes()).hexdigest()==model['modelHash']
# Public source fixture only: prove this installed normal launcher actually loads
# and runs the checkpoint, rather than merely checking a file on disk.
public=json.loads((ROOT/'audit-results/current-health-20261009/public-positive.json').read_text('utf8'));raw=Path(public['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==public['sourceSHA256']
fixture=json.dumps({'processingConsent':True,'photo':'data:image/jpeg;base64,'+base64.b64encode(raw).decode()}).encode()
request=urllib.request.Request('http://127.0.0.1:8000/api/local-health/dental-upload',data=fixture,headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request,timeout=30) as response:dental=json.loads(response.read())
assert dental['views'][0]['quality']['valid'] and dental['views'][0]['caries']['quality']=='valid'
assert dental['views'][0]['caries']['modelHash']==model['modelHash']
assert dental['views'][0]['caries']['type']=='trained_prediction'
assert dental['views'][0]['caries']['runtimeVersions']==model['additionalDiagnostics']['libraryVersions']
browser=psutil.Process(running['browser_pid']);assert '--user-data-dir='+str(HOME/'chrome-profile') in browser.cmdline()
os.startfile(str(LINK));time.sleep(2);assert state()['frontend_pid']==running['frontend_pid'] and state()['backend_pid']==running['backend_pid']
owned={browser.pid,*[p.pid for p in browser.children(recursive=True)]}
closed=[]
for row in windows():
 if row['pid'] in owned:win32gui.PostMessage(row['hwnd'],win32con.WM_CLOSE,0,0);closed.append(row)
assert closed,'No owned product window found'
wait(lambda:state().get('status')=='stopped');wait(lambda:free(3000) and free(8000))
preserved=[{**row,'preserved':bool(win32gui.IsWindow(row['hwnd']) and win32process.GetWindowThreadProcessId(row['hwnd'])[1]==row['pid'])} for row in other]
assert all(row['preserved'] for row in preserved),'Pre-existing Chrome window changed; inspect before claiming preservation'
os.startfile(str(LINK));reopened=wait(live_state)
for rel,digest in hashes.items():
 with urllib.request.urlopen('http://127.0.0.1:3000/_next/'+rel,timeout=5) as response:assert hashlib.sha256(response.read()).hexdigest()==digest
proof={'status':'PASS','sourceHead':head,'branch':git('branch','--show-current'),'buildId':build,'shortcut':str(LINK),'shortcutTarget':target,'shortcutArguments':arguments,'productRoot':str(ROOT),'sourceFileSHA256':source,'servedChunkSHA256':hashes,'routeChunks':manifest,'runtimeVersions':runtime['runtimeVersions'],'runtimeIsolated':True,'dentalModelHash':model['modelHash'],'actualNormalDentalModelInference':True,'dentalInferenceFixture':'public-intraoral-upload-not-physical-acceptance','guidanceVersion':guidance['version'],'guidanceServedHashesMatch':True,'digitBankVersion':bank['version'],'digitBankServedHashesMatch':True,'installedLauncherMatchesSource':True,'repeatUsesOwnedServices':True,'lastOwnedWindowStopsServices':True,'otherChromeWindows':preserved,'reopenedState':reopened,'leftRunning':True,'physicalCameraAcceptance':'OPEN','subjectiveSpeechAcceptance':'OPEN'}
OUT.write_text(json.dumps(proof,indent=2),'utf8');print(json.dumps({k:proof[k] for k in ['status','sourceHead','buildId','branch','productRoot','leftRunning']}))
