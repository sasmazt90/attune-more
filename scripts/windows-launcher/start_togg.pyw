import ctypes
import hashlib
from ctypes import wintypes
import json
import msvcrt
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import psutil

TEST = "--verify-lifecycle" in sys.argv
HERE = Path(os.environ["ATTUNE_LAUNCHER_TEST_HOME"]) if TEST and "ATTUNE_LAUNCHER_TEST_HOME" in os.environ else Path(__file__).resolve().parent
HERE.mkdir(parents=True, exist_ok=True)
DELIVERY = HERE / 'deployment.json'
ROOT = Path(json.loads(DELIVERY.read_text('utf8'))['checkout']) if DELIVERY.is_file() else Path(__file__).resolve().parents[2]
HOST_SCRIPT = Path(__file__).resolve().parent / "backend_host.py"
URL = "http://127.0.0.1:3000"
PYTHON = Path(r"C:\Users\PC\AppData\Local\Programs\Python\Python311\python.exe")
NODE = Path(r"C:\nvm4w\nodejs\node.exe")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
TEST = "--verify-lifecycle" in sys.argv
PROFILE = HERE / ("chrome-verification-profile" if TEST else "chrome-profile")
API_URL = 'http://127.0.0.1:8311'


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):h.update(block)
    return h.hexdigest()


def verify_delivery():
    value=json.loads(DELIVERY.read_text('utf8'))
    if value['frontendOrigin']!=URL or value['apiPort']!=8311:
        raise RuntimeError('Launcher origin/API contract mismatch; existing data preserved.')
    if (ROOT/'apps/vehicle-app/.next/BUILD_ID').read_text().strip()!=value['BUILD_ID']:
        raise RuntimeError('Production build identity mismatch; no server started.')
    for row in value['files']:
        path=(ROOT/row['path']).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha256(path)!=row['sha256']:
            raise RuntimeError('Production source/asset identity mismatch; no server started.')
    for row in value['launcherFiles']:
        if sha256(HERE/row['name'])!=row['sha256']:raise RuntimeError('Launcher identity mismatch.')
    if json.loads((ROOT/'services/core-api/models/skin-type-hosted.json').read_text('utf8'))['enabled'] is not False:
        raise RuntimeError('Hosted skin type must remain disabled in this delivery.')
    return value


def identity(pid,role,process=None):
    process=process or psutil.Process(pid)
    return dict(pid=pid,role=role,started=process.create_time(),cwd=process.cwd(),commandSHA256=hashlib.sha256(json.dumps(process.cmdline()).encode()).hexdigest())


def process_matches(row):
    """Chrome can chdir after startup; executable/profile/argv remain immutable.
    All other owned roles retain exact CWD matching. Never infer ownership from
    an executable name, PID alone, or a substring inside arbitrary arguments.
    """
    try:
        role=row['role']
        if role not in ('launcher','backend','frontend','browser'):return False
        process=psutil.Process(row['pid'])
        actual=identity(row['pid'],role,process)
        if role!='browser':return actual==row and process.is_running()
        if {k:v for k,v in actual.items() if k!='cwd'}!={k:v for k,v in row.items() if k!='cwd'}:return False
        executable=Path(process.exe()).resolve()
        arguments=process.cmdline()
        if executable!=CHROME.resolve() or not arguments or Path(arguments[0]).resolve()!=executable:return False
        if arguments[1:]!=chrome_args(PROFILE)[1:]:return False
        return process.is_running()
    except (psutil.Error,OSError,KeyError,TypeError,ValueError):return False


def verified_owner(state,delivery):
    if state.get('workspace')!=str(ROOT) or state.get('BUILD_ID')!=delivery['BUILD_ID'] or state.get('sourceCommit')!=delivery['sourceCommit'] or state.get('profile')!=str(PROFILE) or state.get('url')!=URL:return False
    try:
        rows=state['processes']
        if len(rows)!=4 or {row['role'] for row in rows}!={'launcher','backend','frontend','browser'}:return False
        if any(row['pid']!=state.get(row['role']+'_pid') for row in rows):return False
        for row in rows:
            if not process_matches(row):return False
        actual=json.loads(fetch(API_URL+'/api/launcher/identity') or b'{}')
        return actual.get('sourceCommit')==delivery['sourceCommit'] and actual.get('BUILD_ID')==delivery['BUILD_ID'] and actual.get('hostedSkinTypeEnabled') is False
    except (psutil.Error,ValueError,OSError,KeyError):return False

class BasicLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

class IOCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                  "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

class ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
kernel.CreateJobObjectW.restype = wintypes.HANDLE
kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel.SetInformationJobObject.restype = wintypes.BOOL
kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel.AssignProcessToJobObject.restype = wintypes.BOOL
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL

class OwnedJob:
    def __init__(self):
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def add(self, process):
        if not kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(process._handle)):
            process.terminate()
            process.wait(timeout=5)
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            kernel.CloseHandle(self.handle)
            self.handle = None


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.read()
    except Exception:
        return None


def occupied(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_service(job, name, args, cwd, env, controlled_stdin=False):
    with (HERE / (name + ".log")).open("ab") as log:
        process = subprocess.Popen(args, cwd=str(cwd), env=env,
                                   stdin=subprocess.PIPE if controlled_stdin else subprocess.DEVNULL,
                                   stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    job.add(process)
    return process


def await_ready(url, process, name):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if fetch(url) is not None:
            return
        if process.poll() is not None:
            raise RuntimeError(name + " baslatilamadi. Ayrinti: " + str(HERE / (name + ".log")))
        time.sleep(0.5)
    raise RuntimeError(name + " zamaninda hazir olmadi. Ayrinti: " + str(HERE / (name + ".log")))


def chrome_args(profile):
    args = [str(CHROME), "--user-data-dir=" + str(profile), "--new-window", URL,
            "--disable-background-mode", "--no-first-run", "--no-default-browser-check"]
    if TEST or os.getenv('ATTUNE_LAUNCHER_OBSERVE')=='1':
        # Only the bounded verification launch exposes a random loopback debugging port.
        args += ["--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0"]
    return args


def write_state(state):
    temporary=HERE/('session.'+str(os.getpid())+'.tmp')
    temporary.write_text(json.dumps(state,indent=2),encoding='utf8')
    temporary.replace(HERE/'session.json')


def main():
    if not CHROME.is_file():
        raise RuntimeError("Google Chrome bulunamadi.")
    if not (ROOT / "apps/vehicle-app/.next/BUILD_ID").is_file():
        raise RuntimeError("Uretim derlemesi bulunamadi; proje dosyalarina dokunulmadi.")
    delivery=verify_delivery()
    with (HERE / "start.lock").open("a+b") as lock:
        # Reading the locked byte raises PermissionError on Windows on a second launch.
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            for _ in range(40):
                state=json.loads((HERE/'session.json').read_text('utf8'))
                if state.get('status')=='starting':time.sleep(.5);continue
                if state.get('status')=='running' and verified_owner(state,delivery):
                    handoff=subprocess.Popen(chrome_args(PROFILE),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    # A same-PID snapshot alone cannot prove this invocation
                    # passed validation. Emit a value-free positive reuse ack.
                    receipt=dict(invocationPID=os.getpid(),at=time.time(),sourceCommit=delivery['sourceCommit'],BUILD_ID=delivery['BUILD_ID'],backendPID=state['backend_pid'],frontendPID=state['frontend_pid'],launcherPID=state['launcher_pid'],browserPID=state['browser_pid'],browserObservedCwd=psutil.Process(state['browser_pid']).cwd(),handoffPID=handoff.pid,identityRule='role-specific-browser-v2')
                    temporary=HERE/('reuse.'+str(os.getpid())+'.tmp')
                    temporary.write_text(json.dumps(receipt,indent=2),'utf8');temporary.replace(HERE/'reuse-receipt.json')
                    return
                raise RuntimeError('Existing launcher ownership differs; no process stopped.')
            raise RuntimeError('Existing launcher is still starting; no duplicate service created.')
        if occupied(3000) or occupied(8311):
            raise RuntimeError("3000 veya 8311 portunda mevcut bir servis var. Kisa yol bu servisi kapatmaz veya sahiplenmez.")
        for process in psutil.process_iter(['name','cmdline']):
            if (process.info['name'] or '').lower()=='chrome.exe' and '--user-data-dir='+str(PROFILE) in (process.info['cmdline'] or []):
                raise RuntimeError('Normal Chrome profile already open outside this launcher; preserved.')
        env={key:value for key,value in os.environ.items() if not any(word in key.upper() for word in ('OPENAI_','ROBOFLOW','API_KEY','TOKEN','PASSWORD','SECRET'))}
        env["OPENAI_API_KEY"] = ""
        env["ATTUNE_LOAD_LOCAL_ENV"] = "0"
        env["ATTUNE_TRUSTED_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000"
        env["ATTUNE_DATA_DIR"] = str(HERE / "data")
        env.update(ATTUNE_EXPERIMENTAL_ACNE_V5='1',NEXT_PUBLIC_ATTUNE_ACNE_V5='1',NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8311',NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT='8311',NEXT_TELEMETRY_DISABLED='1',ATTUNE_LAUNCHER_DELIVERY=str(DELIVERY))
        job = OwnedJob()
        backend = frontend = browser = None
        state = {"status": "starting", "launcher_pid": os.getpid(), "profile": str(PROFILE), "url": URL,
                 "verification": TEST, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),"workspace":str(ROOT),"BUILD_ID":delivery['BUILD_ID'],"sourceCommit":delivery['sourceCommit']}
        write_state(state)
        try:
            backend = start_service(job, "backend", [str(PYTHON), str(HOST_SCRIPT),
                                     str(ROOT / "services/core-api")], ROOT, env, True)
            await_ready(API_URL+"/api/health", backend, "backend")
            frontend = start_service(job, "frontend", [str(NODE), str(ROOT / "node_modules/next/dist/bin/next"),
                                     "start", "--hostname", "127.0.0.1", "--port", "3000"], ROOT / "apps/vehicle-app", env)
            await_ready("http://127.0.0.1:3000/", frontend, "frontend")
            browser = subprocess.Popen(chrome_args(PROFILE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            job.add(browser)
            state.update(status="running", backend_pid=backend.pid, frontend_pid=frontend.pid, browser_pid=browser.pid)
            state['processes']=[identity(os.getpid(),'launcher'),identity(backend.pid,'backend'),identity(frontend.pid,'frontend'),identity(browser.pid,'browser')]
            write_state(state)
            # The dedicated profile keeps unrelated Chrome windows outside our process tree.
            while browser.poll() is None:
                if backend.poll() is not None or frontend.poll() is not None:
                    raise RuntimeError("TOGG servisi beklenmedik sekilde durdu; bu oturum kapatildi.")
                time.sleep(0.25)
        finally:
            if backend is not None and backend.poll() is None:
                try:
                    backend.stdin.write(b"stop\n")
                    backend.stdin.flush()
                    backend.wait(timeout=8)  # Uvicorn drains requests and closes storage operations.
                except (OSError, subprocess.TimeoutExpired):
                    pass
            job.close()  # Only descendants owned by this session are stopped.
            for process in (backend, frontend, browser):
                if process is not None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
            state.update(status="stopped", stopped_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
            write_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if TEST:
            write_state({"status": "error", "verification": True, "error": str(error)})
            raise SystemExit(1)
        from tkinter import Tk, messagebox
        window = Tk()
        window.withdraw()
        messagebox.showerror("TOGG baslatilamadi", str(error))
        window.destroy()
