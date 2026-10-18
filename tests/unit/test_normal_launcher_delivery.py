"""Focused launcher ownership/disabled-provider regressions; no external requests."""
import ctypes,hashlib,json,runpy,sys,types
from pathlib import Path
import pytest
import psutil  # Select the actual platform backend before any test-only bindings.
ROOT=Path(__file__).resolve().parents[2]

def load_launcher(monkeypatch, *, bind_native_stub=False):
 # These tests call the actual pure descriptor/identity functions, not a native
 # Windows launch. Fail loudly if a locking syscall is accidentally exercised.
 if sys.platform != 'win32' or bind_native_stub:
  native=types.ModuleType('msvcrt')
  def unavailable(*args):raise AssertionError('Native Windows operation needs a Windows lifecycle test')
  native.locking=unavailable
  monkeypatch.setitem(sys.modules,'msvcrt',native)
  # Binding argtypes/restype at import is harmless; a fake native operation
  # must never report success. The tested functions perform no Job syscalls.
  bindings=types.SimpleNamespace(**{name:unavailable for name in (
   'CreateJobObjectW','SetInformationJobObject','AssignProcessToJobObject','CloseHandle')})
  monkeypatch.setattr(ctypes,'WinDLL',lambda *args,**kwargs:bindings,raising=False)
 return runpy.run_path(str(ROOT/'scripts/windows-launcher/start_togg.pyw'))

def test_pure_loader_never_claims_native_windows_operations(monkeypatch):
 module=load_launcher(monkeypatch,bind_native_stub=True)
 assert callable(module['process_matches']) and callable(module['verify_delivery'])
 with pytest.raises(AssertionError,match='Native Windows operation'):
  module['kernel'].CloseHandle(None)

def test_hosted_disabled_even_with_photo_consent_and_key(monkeypatch):
 sys.path.insert(0,str(ROOT/'services/core-api'))
 import hosted_skin_type as H
 monkeypatch.setenv('ATTUNE_ROBOFLOW_API_KEY','test-only-not-a-key')
 monkeypatch.setattr(H,'get_inference_client',lambda *a,**kw:pytest.fail('Disabled provider attempted a request'))
 result=H.infer_hosted_type(None,True)
 assert result['limitationCode']=='HOSTED_CONFIG_DISABLED'
 assert result['value'] is None and result['quality']=='insufficient' and result['confidence'] is None
 assert H.infer_hosted_type(None,False)['limitationCode']=='HOSTED_INFERENCE_PERMISSION_DENIED'

def test_second_click_rejects_incomplete_owner_inventory_before_http(monkeypatch):
 module=load_launcher(monkeypatch)
 verify=module['verified_owner'];g=verify.__globals__
 delivery=dict(BUILD_ID='known',sourceCommit='source')
 state=dict(workspace=str(g['ROOT']),BUILD_ID='known',sourceCommit='source',profile=str(g['PROFILE']),url=g['URL'],processes=[dict(pid=123,role='frontend',started=1,cwd='expected',commandSHA256='expected')])
 monkeypatch.setitem(g,'fetch',lambda url:pytest.fail('Changed process owner reached HTTP reuse'))
 assert verify(state,delivery) is False

def test_source_hash_tamper_fails_closed(tmp_path,monkeypatch):
 module=load_launcher(monkeypatch)
 verify=module['verify_delivery'];g=verify.__globals__
 (tmp_path/'apps/vehicle-app/.next').mkdir(parents=True)
 (tmp_path/'apps/vehicle-app/.next/BUILD_ID').write_text('known')
 (tmp_path/'file.txt').write_text('tampered')
 descriptor=tmp_path/'deployment.json'
 descriptor.write_text(json.dumps(dict(frontendOrigin=g['URL'],apiPort=8311,BUILD_ID='known',files=[dict(path='file.txt',sha256=hashlib.sha256(b'original').hexdigest())])))
 monkeypatch.setitem(g,'ROOT',tmp_path);monkeypatch.setitem(g,'DELIVERY',descriptor)
 with pytest.raises(RuntimeError,match='identity mismatch'):verify()

def fake_owned_process(module,role='browser'):
 class Process:
  pid=321
  started=100.
  directory='initial-directory'
  executable=str(module['CHROME'])
  arguments=module['chrome_args'](module['PROFILE'])
  running=True
  def create_time(self):return self.started
  def cwd(self):return self.directory
  def exe(self):return self.executable
  def cmdline(self):return self.arguments
  def is_running(self):return self.running
 process=Process()
 return process,module['identity'](process.pid,role,process)

def test_browser_allows_only_cwd_transition(monkeypatch):
 module=load_launcher(monkeypatch)
 process,row=fake_owned_process(module)
 monkeypatch.setattr(module['psutil'],'Process',lambda pid:process)
 process.directory=str(module['CHROME'].parent/'132.0.6834.83')
 assert module['process_matches'](row) is True

@pytest.mark.parametrize('change',['exe','argv-exe','profile','app-url','extra-argument','forged-record-profile','forged-record-app-url','forged-record-extra-argument','start-time','pid-reuse'])
def test_browser_rejects_other_identity_changes(monkeypatch,change):
 module=load_launcher(monkeypatch)
 process,row=fake_owned_process(module)
 if change=='exe':process.executable=str(ROOT/'unrelated-chrome.exe')
 elif change=='argv-exe':process.arguments=[str(ROOT/'unrelated-chrome.exe')]+process.arguments[1:]
 elif change.endswith('profile'):process.arguments=[a if not a.startswith('--user-data-dir=') else '--user-data-dir=another-profile' for a in process.arguments]
 elif change.endswith('app-url'):
  # Both frozen app-mode and the checked-in ordinary-window form must reject
  # an altered target, including a forged matching recorded command hash.
  process.arguments=[('--app=http://127.0.0.1:9999' if a.startswith('--app=') else 'http://127.0.0.1:9999' if a==module['URL'] else a) for a in process.arguments]
 elif change.endswith('extra-argument'):process.arguments=process.arguments+['--arbitrary-string='+str(module['PROFILE'])]
 elif change=='start-time':process.started+=1
 elif change=='pid-reuse':process.running=False
 if change.startswith('forged-record-'):row['commandSHA256']=hashlib.sha256(json.dumps(process.arguments).encode()).hexdigest()
 monkeypatch.setattr(module['psutil'],'Process',lambda pid:process)
 assert module['process_matches'](row) is False

@pytest.mark.parametrize('role',['launcher','backend','frontend'])
def test_nonbrowser_cwd_stays_strict(monkeypatch,role):
 module=load_launcher(monkeypatch)
 process,row=fake_owned_process(module,role)
 monkeypatch.setattr(module['psutil'],'Process',lambda pid:process)
 assert module['process_matches'](row) is True
 process.directory='changed-directory'
 assert module['process_matches'](row) is False
