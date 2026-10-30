"""Finite trusted build tools: atomic Windows Job membership, commit cap and deadline.

Not a sandbox for trusted developers deliberately invoking raw node/next. No
breakaway, vendor changes, heap overrides, shell commands or unbounded fallback.
"""
import ctypes
from ctypes import wintypes as W
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


class GuardUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    wall_seconds: float
    job_commit_mib: int
    rss_lease_mib: int
    minimum_available_mib: int


# Latest measured build: 132.562s, 890.477MiB summed RSS, not private commit.
# The existing 1600MiB start/2100MiB RSS policy is retained. OS commit gets a
# separate 3GiB ceiling, to be validated with actual Job accounting.
PROFILES = {
    'build': Limits(600, 3072, 2100, 1600),
    'lint': Limits(180, 1536, 1200, 1600),
}


class BasicLimits(ctypes.Structure):
    _fields_ = [('ProcessTime', ctypes.c_longlong), ('JobTime', ctypes.c_longlong),
                ('Flags', W.DWORD), ('MinWS', ctypes.c_size_t),
                ('MaxWS', ctypes.c_size_t), ('ActiveLimit', W.DWORD),
                ('Affinity', ctypes.c_size_t), ('Priority', W.DWORD), ('Scheduling', W.DWORD)]


class IOCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOps', 'WriteOps', 'OtherOps', 'ReadBytes', 'WriteBytes', 'OtherBytes')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('Basic', BasicLimits), ('IO', IOCounters),
                ('ProcessMemory', ctypes.c_size_t), ('JobMemory', ctypes.c_size_t),
                ('PeakProcessMemory', ctypes.c_size_t), ('PeakJobMemory', ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [(n, ctypes.c_longlong) for n in ('User', 'Kernel', 'PeriodUser', 'PeriodKernel')] + [
        (n, W.DWORD) for n in ('Faults', 'TotalProcesses', 'ActiveProcesses', 'TerminatedProcesses')]


class Startup(ctypes.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR),
                ('title', W.LPWSTR)] + [(n, W.DWORD) for n in
                ('x', 'y', 'xsize', 'ysize', 'xchars', 'ychars', 'fill', 'flags')] + [
                ('show', W.WORD), ('reserved2size', W.WORD), ('reserved2', ctypes.c_void_p),
                ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class StartupEx(ctypes.Structure):
    _fields_ = [('start', Startup), ('attributes', ctypes.c_void_p)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class CompletionPort(ctypes.Structure):
    _fields_ = [('key', ctypes.c_void_p), ('port', W.HANDLE)]


def kernel_api():
    if os.name != 'nt':
        raise GuardUnavailable('Windows 10+ Job-list containment required; this finite operation was NOT started. Dev/watch unaffected.')
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([ctypes.c_void_p, W.LPCWSTR], W.HANDLE),
        'SetInformationJobObject': ([W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD], W.BOOL),
        'QueryInformationJobObject': ([W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.c_void_p], W.BOOL),
        'CloseHandle': ([W.HANDLE], W.BOOL),
        'TerminateJobObject': ([W.HANDLE, W.UINT], W.BOOL),
        'GetCurrentProcess': ([], W.HANDLE),
        'DuplicateHandle': ([W.HANDLE, W.HANDLE, W.HANDLE, ctypes.POINTER(W.HANDLE), W.DWORD, W.BOOL, W.DWORD], W.BOOL),
        'InitializeProcThreadAttributeList': ([ctypes.c_void_p, W.DWORD, W.DWORD, ctypes.POINTER(ctypes.c_size_t)], W.BOOL),
        'UpdateProcThreadAttribute': ([ctypes.c_void_p, W.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p], W.BOOL),
        'DeleteProcThreadAttributeList': ([ctypes.c_void_p], None),
        'CreateProcessW': ([W.LPCWSTR, W.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, W.BOOL, W.DWORD, ctypes.c_void_p, W.LPCWSTR, ctypes.POINTER(StartupEx), ctypes.POINTER(ProcessInfo)], W.BOOL),
        'ResumeThread': ([W.HANDLE], W.DWORD),
        'GetExitCodeProcess': ([W.HANDLE, ctypes.POINTER(W.DWORD)], W.BOOL),
        'WaitForSingleObject': ([W.HANDLE, W.DWORD], W.DWORD),
        'CreateIoCompletionPort': ([W.HANDLE, W.HANDLE, ctypes.c_size_t, W.DWORD], W.HANDLE),
        'GetQueuedCompletionStatus': ([W.HANDLE, ctypes.POINTER(W.DWORD), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_void_p), W.DWORD], W.BOOL),
        'GetFileType': ([W.HANDLE], W.DWORD),
        'PeekNamedPipe': ([W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p], W.BOOL),
    }
    for name, (args, result) in signatures.items():
        fn = getattr(k, name); fn.argtypes = args; fn.restype = result
    return k


def require(ok, operation):
    if not ok:
        raise GuardUnavailable(f'{operation} failed (Windows error {ctypes.get_last_error()}); no unbounded fallback')


class OwnerPipe:
    """Nonblocking lifetime check: no background reader/native-import deadlock."""
    def __init__(self):
        import msvcrt
        self.k=kernel_api();self.handle=W.HANDLE(msvcrt.get_osfhandle(sys.stdin.fileno()))
        require(self.k.GetFileType(self.handle)==3,'Require private lifetime pipe')

    def is_set(self):
        if self.k.PeekNamedPipe(self.handle,None,0,None,None,None):return False
        if ctypes.get_last_error() in (109,232):return True
        raise GuardUnavailable('Cannot verify bridge lifetime pipe; owned work stopped')


def run_job(argv, cwd, limits, *, env=None, stdout=None, stderr=None, cancel=None, check=None, started=None):
    """Shared actual OS boundary. Low test Limits exist only in this Python API.

    CreateProcess job-list membership is atomic, even if the supervisor dies
    between creation and ResumeThread. Only explicit stdio handles are inherited.
    """
    if not math.isfinite(limits.wall_seconds) or limits.wall_seconds <= 0 or type(limits.job_commit_mib) is not int or limits.job_commit_mib <= 0:
        raise ValueError('Invalid finite job limits')
    k = kernel_api(); argv = [str(a) for a in argv]; cwd = Path(cwd).resolve()
    if not argv or not Path(argv[0]).is_file() or not cwd.is_dir():
        raise ValueError('Require explicit executable and existing CWD')
    handles = []; job = port = None; attrs = None; attrs_ready = False; pi = ProcessInfo(); launched = False
    started_at = time.monotonic(); reason = 'setup'; exit_code = 125; peaks = 0; member_ids = set(); terminated = False
    events = []; result = {}; std_files = []; deadline_timer = None; deadline_fired = threading.Event(); deadline_record = {}
    try:
        job = k.CreateJobObjectW(None, None); require(job, 'CreateJobObject'); handles.append(job)
        limit = ExtendedLimits(); limit.Basic.Flags = 0x2000 | 0x200  # kill-on-close + whole-job committed memory
        limit.JobMemory = limits.job_commit_mib * 2**20
        require(k.SetInformationJobObject(job, 9, ctypes.byref(limit), ctypes.sizeof(limit)), 'Set Job commit/kill limits')
        installed=ExtendedLimits();require(k.QueryInformationJobObject(job,9,ctypes.byref(installed),ctypes.sizeof(installed),None),'Verify installed limits')
        require(installed.JobMemory==limit.JobMemory and installed.Basic.Flags & 0x2200 == 0x2200,'Verify Job memory/kill flags')
        port = k.CreateIoCompletionPort(W.HANDLE(-1), None, 0, 1); require(port, 'CreateIoCompletionPort'); handles.append(port)
        assoc = CompletionPort(None, port)
        require(k.SetInformationJobObject(job, 7, ctypes.byref(assoc), ctypes.sizeof(assoc)), 'Associate completion port')
        import msvcrt
        null = open(os.devnull, 'rb'); std_files.append(null)
        streams = [null, stdout or sys.stdout, stderr or sys.stderr]; inherited = []
        current = k.GetCurrentProcess()
        for stream in streams:
            duplicate = W.HANDLE(); source = msvcrt.get_osfhandle(stream.fileno())
            require(k.DuplicateHandle(current, W.HANDLE(source), current, ctypes.byref(duplicate), 0, True, 2), 'Duplicate explicit stdio')
            inherited.append(duplicate.value); handles.append(duplicate.value)
        size = ctypes.c_size_t()
        k.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        if not size.value:raise GuardUnavailable('Job-list process attributes unavailable')
        attrs = ctypes.create_string_buffer(size.value)
        require(k.InitializeProcThreadAttributeList(attrs, 2, 0, ctypes.byref(size)), 'Initialize process attributes')
        attrs_ready = True
        job_list = (W.HANDLE * 1)(job); handle_list = (W.HANDLE * 3)(*inherited)
        require(k.UpdateProcThreadAttribute(attrs, 0, 0x2000D, job_list, ctypes.sizeof(job_list), None, None), 'Atomic job-list attribute')
        require(k.UpdateProcThreadAttribute(attrs, 0, 0x20002, handle_list, ctypes.sizeof(handle_list), None, None), 'Explicit handle-list attribute')
        si = StartupEx(); si.start.cb = ctypes.sizeof(si); si.start.flags = 0x100
        si.start.stdin, si.start.stdout, si.start.stderr = inherited; si.attributes = ctypes.cast(attrs, ctypes.c_void_p)
        environment = dict(os.environ if env is None else env)
        block = ctypes.create_unicode_buffer('\0'.join(f'{key}={value}' for key,value in sorted(environment.items(), key=lambda item:item[0].upper())) + '\0\0')
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        # EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED | UNICODE_ENVIRONMENT | NO_WINDOW
        require(k.CreateProcessW(argv[0], command, None, None, True, 0x80000 | 4 | 0x400 | 0x8000000, block, str(cwd), ctypes.byref(si), ctypes.byref(pi)), 'CreateProcess atomically in Job')
        launched = True; handles.extend([pi.process, pi.thread]); member_ids.add(pi.pid)
        import psutil
        p = psutil.Process(pi.pid)
        identity = dict(pid=pi.pid, started=p.create_time(), executable=p.exe(), argvSHA256=hashlib.sha256(json.dumps(argv).encode()).hexdigest(), cwd=str(cwd))
        def expire():
            deadline_record['atSeconds']=time.monotonic()-started_at
            deadline_record['terminateSucceeded']=bool(k.TerminateJobObject(job,124))
            deadline_fired.set()
        # An independent watchdog still terminates the owned workload if a
        # cooperative RAM/ownership check stalls. Join before closing handles.
        deadline_timer=threading.Timer(max(0,limits.wall_seconds-(time.monotonic()-started_at)),expire)
        deadline_timer.daemon=True;deadline_timer.start()
        if started:started(identity)
        require(k.ResumeThread(pi.thread) != 0xFFFFFFFF, 'Resume bounded process')
        reason = 'running'; deadline = started_at + limits.wall_seconds
        while True:
            if deadline_fired.is_set():reason='wall-time-limit';exit_code=124;break
            ext = ExtendedLimits(); require(k.QueryInformationJobObject(job, 9, ctypes.byref(ext), ctypes.sizeof(ext), None), 'Query job memory')
            peaks = max(peaks, ext.PeakJobMemory)
            message = W.DWORD(); key = ctypes.c_size_t(); overlapped = ctypes.c_void_p()
            while k.GetQueuedCompletionStatus(port, ctypes.byref(message), ctypes.byref(key), ctypes.byref(overlapped), 0):
                if message.value == 6:member_ids.add(int(overlapped.value or 0))
                if message.value in (9, 10):events.append(message.value); reason = 'job-commit-limit'
            if reason == 'job-commit-limit':exit_code=137;break
            if cancel is not None and cancel.is_set():reason='cancelled';exit_code=130;break
            if time.monotonic() >= deadline:reason='wall-time-limit';exit_code=124;break
            if check:check()
            if deadline_fired.is_set():reason='wall-time-limit';exit_code=124;break
            wait = k.WaitForSingleObject(pi.process, 0)
            if wait == 0:
                code = W.DWORD(); require(k.GetExitCodeProcess(pi.process, ctypes.byref(code)), 'Read owned process exit')
                exit_code=int(code.value); reason='exit'
                accounting = Accounting(); require(k.QueryInformationJobObject(job,1,ctypes.byref(accounting),ctypes.sizeof(accounting),None),'Query final job accounting')
                # Process signalling can precede Job accounting on Windows.
                # Allow only a short bounded drain before declaring orphans.
                drain_until=time.monotonic()+.25
                while accounting.ActiveProcesses and time.monotonic()<drain_until:
                    time.sleep(.01)
                    require(k.QueryInformationJobObject(job,1,ctypes.byref(accounting),ctypes.sizeof(accounting),None),'Drain final job accounting')
                if accounting.ActiveProcesses:
                    reason='orphaned-descendants';exit_code=exit_code or 125
                break
            require(wait == 258, 'Wait owned process')
            time.sleep(.05)
    finally:
        if deadline_timer:deadline_timer.cancel();deadline_timer.join()
        try:
            if job and launched:
                # Job ownership is immutable; no CWD/name/PID census is used to kill.
                require(k.TerminateJobObject(job, exit_code or 125), 'Terminate remaining owned job members'); terminated=True
                end = time.monotonic()+5
                while True:
                    accounting=Accounting();require(k.QueryInformationJobObject(job,1,ctypes.byref(accounting),ctypes.sizeof(accounting),None),'Verify empty job')
                    if accounting.ActiveProcesses==0:break
                    if time.monotonic()>end:raise GuardUnavailable('Owned Job did not drain; kill-on-close retained')
                    time.sleep(.025)
                ext=ExtendedLimits();require(k.QueryInformationJobObject(job,9,ctypes.byref(ext),ctypes.sizeof(ext),None),'Final Job commit accounting');peaks=max(peaks,ext.PeakJobMemory)
                result.update(child=identity,memberPIDsObserved=sorted(member_ids),activeProcessesAfter=0,totalJobProcesses=accounting.TotalProcesses)
        finally:
            # Also applies if accounting/termination raises during unwinding.
            if attrs_ready:k.DeleteProcThreadAttributeList(attrs)
            for handle in reversed(handles):k.CloseHandle(handle)
            for stream in std_files:stream.close()
    result.update(exitCode=exit_code,reason=reason,seconds=time.monotonic()-started_at,wallLimitSeconds=limits.wall_seconds,jobCommitLimitMiB=limits.job_commit_mib,OSInstalledJobCommitBytes=installed.JobMemory,peakJobCommittedMiB=peaks/2**20,killOnClose=True,atomicJobAssignment=True,breakawayEnabled=False,explicitHandleInheritance=True,terminateJobCalled=terminated,jobHandlesClosed=True,jobLimitEvents=events,deadlineWatchdog=deadline_record)
    return result


def run_tool(mode, project=None, extra=(), *, receipt=None, owner_cancel=None, stdout=None, stderr=None):
    """Only supported production build/lint callers. Never invokes npm recursively."""
    kernel_api()  # fail before launching a lease or command on unsupported OS
    if mode not in PROFILES:raise ValueError('Only finite build/lint are guarded here')
    project=Path(project or ROOT/'apps/vehicle-app').resolve()
    if json.loads((project/'package.json').read_text('utf8'))['name']!='vehicle-app':raise ValueError('Expected vehicle-app project')
    node=os.environ.get('npm_node_execpath') or shutil.which('node')
    if not node:raise GuardUnavailable('Node executable not found; no command started')
    next_cli=ROOT/'node_modules/next/dist/bin/next'; limits=PROFILES[mode]
    sys.path.insert(0,str(ROOT/'scripts/skin-research'))
    from heavy_job_lease import HeavyJobLease
    def record_start(identity):
        if receipt:
            p=Path(receipt).with_suffix('.started.json');p.parent.mkdir(parents=True,exist_ok=True)
            t=p.with_suffix('.tmp');t.write_text(json.dumps(identity,indent=2),'utf8');t.replace(p)
    with HeavyJobLease('tooling-'+mode,peak_mib=limits.rss_lease_mib,minimum_available_mib=limits.minimum_available_mib,include_children=True,memory_metric='rss') as lease:
        result=run_job([node,str(next_cli),mode,*extra],project,limits,cancel=owner_cancel,check=lease.check,stdout=stdout,stderr=stderr,started=record_start)
        result.update(mode=mode,project=str(project),rssLease=lease.receipt(),nodeOptionsPreserved=True,nodeOptionsSHA256=hashlib.sha256(os.environ.get('NODE_OPTIONS','').encode()).hexdigest())
    if receipt:
        p=Path(receipt);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.tmp');t.write_text(json.dumps(result,indent=2),'utf8');t.replace(p)
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__,add_help=False);parser.add_argument('--guard-help',action='help');parser.add_argument('mode',choices=PROFILES);parser.add_argument('--project');parser.add_argument('--receipt');parser.add_argument('--owner-pipe',action='store_true');args,extra=parser.parse_known_args()
    try:
        cancelled=OwnerPipe() if args.owner_pipe else None
        result=run_tool(args.mode,args.project,extra,receipt=args.receipt,owner_cancel=cancelled)
        print('[finite-tool] '+json.dumps({k:result[k] for k in ('mode','exitCode','reason','seconds','peakJobCommittedMiB','jobCommitLimitMiB','activeProcessesAfter')}),file=sys.stderr)
        return result['exitCode'] if result['exitCode']<256 else 1
    except KeyboardInterrupt:
        print('Finite tool cancelled; owned Job closed.',file=sys.stderr);return 130
    except Exception as error:
        print('FINITE_TOOL_NOT_COMPLETED: '+str(error),file=sys.stderr);return 78


if __name__=='__main__':sys.exit(main())
