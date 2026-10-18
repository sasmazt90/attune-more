"""Actual Windows launcher ownership/lifecycle verification, isolated persistent profile.
Only the owned launcher/profile is closed. No normal profile permission is changed.
"""
import json,os,socket,subprocess,sys,tempfile,time,urllib.request
import psutil,win32con,win32gui,win32process
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
# Each acceptance run starts with its own empty test profile. Reopening inside
# the same run still proves persistence; no old or normal profile is removed.
HOME=Path(tempfile.mkdtemp(prefix='windows-launcher-current-',dir=ROOT/'audit-results'))
LAUNCHER=ROOT/'scripts/windows-launcher/start_togg.pyw';OUT=ROOT/'audit-results/windows-launcher.json'
env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')};env.update(ATTUNE_LAUNCHER_TEST_HOME=str(HOME),PYTHONUTF8='1')
results={};owned=[]
def port(p):
 with socket.socket() as s:return s.connect_ex(('127.0.0.1',p))==0
def wait(predicate,limit=60):
 end=time.monotonic()+limit
 while time.monotonic()<end:
  if predicate():return
  time.sleep(.2)
 raise TimeoutError('Owned lifecycle state did not arrive')
def state():
 try:return json.loads((HOME/'session.json').read_text())
 except:return {}
def debug_ready():
 try:return port(int((HOME/'chrome-verification-profile/DevToolsActivePort').read_text().splitlines()[0]))
 except (OSError,ValueError,IndexError):return False
def start():
 p=subprocess.Popen([sys.executable,str(LAUNCHER),'--verify-lifecycle'],cwd=ROOT,env=env,creationflags=subprocess.CREATE_NO_WINDOW);owned.append(p);return p
def owned_windows(browser_pid):
 browser=psutil.Process(browser_pid)
 assert '--user-data-dir='+str(HOME/'chrome-verification-profile') in browser.cmdline()
 pids={browser.pid,*[p.pid for p in browser.children(recursive=True)]};windows=[]
 def collect(hwnd,_):
  if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd)=='Chrome_WidgetWin_1' and win32process.GetWindowThreadProcessId(hwnd)[1] in pids:windows.append(hwnd)
 win32gui.EnumWindows(collect,None);return windows
def close_owned_windows(browser_pid):
 windows=owned_windows(browser_pid);assert windows,'No verified owned native Chrome window'
 for hwnd in windows:win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
assert not port(3000) and not port(8000),'Ports occupied: no other process adopted'
with sync_playwright() as pw:
 unrelated=pw.chromium.launch(channel='chrome',headless=False);other=unrelated.new_page();other.goto('about:blank')
 try:
  cold_started=time.monotonic()
  first=start();wait(lambda:state().get('status')=='running' and state().get('launcher_pid')==first.pid,limit=200)
  cold_ready_seconds=time.monotonic()-cold_started
  initial=state();active=HOME/'chrome-verification-profile/DevToolsActivePort';wait(debug_ready)
  wait(debug_ready);debug_port=int(active.read_text().splitlines()[0]);browser=pw.chromium.connect_over_cdp('http://127.0.0.1:'+str(debug_port));context=browser.contexts[0]
  page=context.pages[0];expect(page.get_by_role('button',name='Sağlık Merkezi',exact=True)).to_be_visible();page.goto(initial['url']+'/mental')
  expect(page.get_by_role('button',name='Görüşmeyi Başlat',exact=True)).to_be_visible();page.evaluate('localStorage.setItem("attune_launch_verification_marker","persistent-owned-test")')
  results['coldOpen']={'status':'PASS','state':initial,'buildId':(ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip(),'actualServicesAndBrowserReadySeconds':cold_ready_seconds}
  assert start().wait(timeout=15)==0;page.wait_for_timeout(800)
  assert state()['backend_pid']==initial['backend_pid'] and state()['frontend_pid']==initial['frontend_pid'];results['repeatedLaunch']='PASS'
  if len(context.pages)<2:
   control=browser.new_browser_cdp_session();control.send('Target.createTarget',{'url':initial['url']+'/mental','newWindow':True})
  wait(lambda:(page.wait_for_timeout(100),len(context.pages)>=2)[1])
  wait(lambda:len(owned_windows(initial['browser_pid']))>=2)
  win32gui.PostMessage(owned_windows(initial['browser_pid'])[-1],win32con.WM_CLOSE,0,0)
  time.sleep(.7);assert port(3000) and port(8000) and first.poll() is None;results['firstWindowCloseKeepsServices']='PASS'
  close_owned_windows(initial['browser_pid'])
  first.wait(timeout=20);wait(lambda:not port(3000) and not port(8000));assert not other.is_closed();results['lastWindowCloseOwnedCleanup']='PASS';results['unrelatedChromeUnaffected']='PASS'
  second=start();wait(lambda:state().get('status')=='running' and state().get('launcher_pid')==second.pid,limit=200)
  wait(debug_ready);debug_port=int(active.read_text().splitlines()[0]);browser=pw.chromium.connect_over_cdp('http://127.0.0.1:'+str(debug_port));context=browser.contexts[0];page=context.pages[0]
  page.goto(state()['url']+'/mental');assert page.evaluate('localStorage.getItem("attune_launch_verification_marker")')=='persistent-owned-test';results['persistentStorageAfterReopen']='PASS'
  close_owned_windows(state()['browser_pid'])
  second.wait(timeout=20);wait(lambda:not port(3000) and not port(8000))
  with socket.socket() as blocker:
   blocker.bind(('127.0.0.1',3000));blocker.listen();failed=start();assert failed.wait(timeout=15)==1;assert port(3000) and not port(8000);assert not other.is_closed();results['occupiedOtherAppPortSafe']='PASS'
  assert not port(3000) and not port(8000);results['noOrphanListeningPorts']='PASS'
  failure_home=HOME/'controlled-startup-failure';failure_home.mkdir(exist_ok=True)
  driver=failure_home/'driver.py'
  driver.write_text('import runpy,sys\nfrom pathlib import Path\nsys.argv.append("--verify-lifecycle")\nm=runpy.run_path('+repr(str(LAUNCHER))+')\nm["main"].__globals__["NODE"]=Path('+repr(str(failure_home/'missing-node.exe'))+')\ntry:m["main"]()\nexcept FileNotFoundError:raise SystemExit(7)\n',encoding='utf-8')
  failed=subprocess.Popen([sys.executable,str(driver)],env={**env,'ATTUNE_LAUNCHER_TEST_HOME':str(failure_home)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW);owned.append(failed)
  assert failed.wait(timeout=30)==7
  assert not port(3000) and not port(8000) and not other.is_closed();results['frontendStartupFailureCleansOwnedBackend']='PASS'
 finally:
  for p in owned:
   if p.poll() is None:p.terminate();p.wait(timeout=10)
  unrelated.close()
OUT.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False))
