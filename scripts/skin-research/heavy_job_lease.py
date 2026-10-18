"""Shared atomic compute lease; never stop another task or remove its lock."""
import hashlib,json,os,time,uuid,threading,math,subprocess,sys
from pathlib import Path
import psutil
from physical_memory import available_physical_bytes, PhysicalMemoryUnavailable
ROOT=Path(__file__).resolve().parents[2]
LOCK=ROOT.parent/'coordination-notes/heavy-compute.lock.json'
AG_LOCK=ROOT.parent/'heavy_job.lock'
AG_ROOT=(ROOT.parent/'attune-antigravity-skin').resolve()

class HeavyJobUnavailable(RuntimeError):pass


def available_physical_mib():
    try:return available_physical_bytes()/2**20
    except PhysicalMemoryUnavailable as error:
        raise HeavyJobUnavailable('Physical RAM unavailable; own work stopped') from error

def process_names(include_parents=False):
    if os.name!='nt':return [(p.pid,p.info['name'] or '',p.info['ppid']) if include_parents else (p.pid,p.info['name'] or '') for p in psutil.process_iter(['name','ppid'])]
    # Toolhelp returns a consistent PID/name snapshot without psutil's
    # NtQuerySystemInformation process/thread enumeration hot path.
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise HeavyJobUnavailable('Process snapshot unavailable')
    rows=[];entry=Entry();entry.dwSize=ctypes.sizeof(entry)
    try:
        found=kernel.Process32FirstW(handle,ctypes.byref(entry))
        while found:
            rows.append((int(entry.th32ProcessID),entry.szExeFile,int(entry.th32ParentProcessID)) if include_parents else (int(entry.th32ProcessID),entry.szExeFile))
            if len(rows)>8192:raise HeavyJobUnavailable('Process snapshot exceeds bounded inventory')
            found=kernel.Process32NextW(handle,ctypes.byref(entry))
        if ctypes.get_last_error()!=18:raise HeavyJobUnavailable('Incomplete process snapshot')
    finally:kernel.CloseHandle(handle)
    return rows

def ag_workers():
    result=[]
    for pid,name in process_names():
        if not any(n in name.lower() for n in ['python','node','ffmpeg']):continue
        try:
            if pid==os.getpid():continue
            p=psutil.Process(pid)
            cwd=Path(p.cwd()).resolve();arguments=p.cmdline();proof=None
            if cwd.is_relative_to(AG_ROOT):proof='resolved-process-cwd'
            elif '-c' not in arguments:
                # A string in inline Python code is not process ownership.
                # Only an actual script argument, resolved against its CWD,
                # can establish ownership when launched from a parent folder.
                scripts=[a for a in arguments[1:] if a.lower().endswith(('.py','.pyw'))]
                if scripts:
                    path=Path(scripts[0]);path=(path if path.is_absolute() else cwd/path).resolve()
                    if path.is_relative_to(AG_ROOT):proof='resolved-script-path'
            if proof:result.append(dict(pid=p.pid,started=p.create_time(),rssMiB=p.memory_info().rss/2**20,ownerProof=proof))
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied as e:raise HeavyJobUnavailable(f'Cannot establish process ownership for PID {pid}: AccessDenied') from e
    return result

def process_parent(pid):
    if os.name!='nt':return psutil.Process(pid).ppid()
    # psutil's Windows ppid() calls a global ppid_map/NtQuery inventory.
    # Query just this owned child handle instead; fail closed on permissions.
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_=[('exitStatus',wintypes.LONG),('peb',ctypes.c_void_p),('affinity',ctypes.c_size_t),('priority',wintypes.LONG),('pid',ctypes.c_size_t),('parent',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE;kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        error=ctypes.get_last_error()
        if error==87:raise psutil.NoSuchProcess(pid)
        if error==5:raise psutil.AccessDenied(pid)
        raise HeavyJobUnavailable('Owned process parent handle unavailable')
    native=ctypes.WinDLL('ntdll');native.NtQueryInformationProcess.argtypes=[wintypes.HANDLE,wintypes.ULONG,ctypes.c_void_p,wintypes.ULONG,ctypes.POINTER(wintypes.ULONG)];native.NtQueryInformationProcess.restype=wintypes.LONG
    try:
        info=Basic();returned=wintypes.ULONG()
        if native.NtQueryInformationProcess(handle,0,ctypes.byref(info),ctypes.sizeof(info),ctypes.byref(returned))!=0 or info.pid!=pid:raise HeavyJobUnavailable('Owned process parent identity unavailable')
        return int(info.parent)
    finally:kernel.CloseHandle(handle)

def read_lease(path):
    """Absence is distinct from an unreadable, partial or unverified lease."""
    try:
        with path.open(encoding='utf8') as file:
            raw=file.read(65537)
        if len(raw)>65536:raise ValueError('oversized lease')
        row=json.loads(raw)
        required=['pid','processStarted','workspace','jobId','nonce']
        if not isinstance(row,dict) or any(k not in row for k in required):raise ValueError('missing identity fields')
        if type(row['pid']) is not int or row['pid']<=0 or not isinstance(row['processStarted'],(float,int)) or not math.isfinite(row['processStarted']):raise ValueError('invalid process identity')
        if not isinstance(row['jobId'],str) or not row['jobId'] or not isinstance(row['nonce'],str) or len(row['nonce'])<16 or not Path(row['workspace']).is_absolute():raise ValueError('invalid lease identity')
        return row
    except FileNotFoundError:return None
    except (OSError,ValueError,TypeError) as e:raise HeavyJobUnavailable(f'Unverifiable lease at {path.name}; preserved, no heavy work') from e

def verify_process_identity(row):
    try:
        process=psutil.Process(row['pid'])
        if process.create_time()!=row['processStarted'] or Path(process.cwd()).resolve()!=Path(row['workspace']).resolve():raise HeavyJobUnavailable('Lease process creation/workspace mismatch; preserved')
    except psutil.NoSuchProcess as e:raise HeavyJobUnavailable('Stale foreign lease retained; no automatic takeover') from e
    except psutil.AccessDenied as e:raise HeavyJobUnavailable('Lease process AccessDenied; no heavy work') from e

class HeavyJobLease:
    def __init__(self,job,peak_mib=700,minimum_available_mib=1200,include_children=False,memory_metric='rss'):
        if memory_metric not in ['rss','private']:raise ValueError('Unknown memory budget metric')
        self.job=job;self.limit=peak_mib;self.minimum=minimum_available_mib;self.include_children=include_children;self.memory_metric=memory_metric;self.stop=threading.Event();self.peak=0.;self.private_peak=0.;self.monitor_error=None;self.last_check=0.;self.process=psutil.Process();self.nonce=uuid.uuid4().hex;self.owned=False;self.owned_paths=[];self.observer_state=None
    def own_children(self):
        pending=process_names(include_parents=True);owners={self.process.pid:self.process.create_time()};result=[]
        for _ in range(32):
            added=False
            for pid,_name,parent in pending:
                if pid in owners or parent not in owners:continue
                try:
                    process=psutil.Process(pid);birth=process.create_time()
                    if process_parent(pid)!=parent or birth<owners[parent]:continue
                    owners[pid]=birth;result.append(process);added=True
                except psutil.NoSuchProcess:continue
                except psutil.AccessDenied as e:raise HeavyJobUnavailable('Own descendant identity AccessDenied') from e
            if not added:return result
        raise HeavyJobUnavailable('Own descendant depth exceeds bounded inventory')
    def rss_mib(self):
        processes=[self.process]+(self.own_children() if self.include_children else [])
        if not self.include_children and hasattr(self,'observer') and self.observer.poll() is None:processes.append(psutil.Process(self.observer.pid))
        total=0
        for process in processes:
            try:total+=process.memory_info().rss
            except psutil.NoSuchProcess:continue
            except psutil.AccessDenied as e:raise HeavyJobUnavailable('Own child memory AccessDenied') from e
        return total/2**20
    def private_mib(self):
        processes=[self.process]+(self.own_children() if self.include_children else [])
        if not self.include_children and hasattr(self,'observer') and self.observer.poll() is None:processes.append(psutil.Process(self.observer.pid))
        total=0
        for process in processes:
            try:total+=process.memory_full_info().uss
            except psutil.NoSuchProcess:continue
            except psutil.AccessDenied as e:raise HeavyJobUnavailable('Own private memory AccessDenied') from e
        return total/2**20
    def __enter__(self):
        # Fixed order, both paths actually owned. Merely checking two separate
        # files would leave the check/create race with legacy AG callers open.
        for path in [LOCK,AG_LOCK]:
            row=read_lease(path)
            if row is not None:
                verify_process_identity(row)
                raise HeavyJobUnavailable(f'Existing shared lease retained at {path.name}; no takeover')
        available=available_physical_mib();workers=ag_workers()
        if available<self.minimum or workers:raise HeavyJobUnavailable(json.dumps(dict(reason='RESOURCE_OR_AG_BUSY',availableMiB=available,requiredMiB=self.minimum,AG=workers)))
        LOCK.parent.mkdir(exist_ok=True)
        identity=dict(schema='attune-dual-atomic-lease-v2',owner='CDC',pid=os.getpid(),processStarted=self.process.create_time(),startTime=self.process.create_time(),workspace=str(Path(self.process.cwd()).resolve()),jobId=self.job,nonce=self.nonce,commandSHA256=hashlib.sha256('\0'.join(self.process.cmdline()).encode()).hexdigest(),peakBudgetMiB=self.limit,memoryBudgetMetric=self.memory_metric,minimumAvailableMiB=self.minimum)
        try:
            for path in [LOCK,AG_LOCK]:
                fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(identity,f);f.flush();os.fsync(f.fileno())
                self.owned_paths.append(path)
        except (OSError,ValueError) as e:
            self.__exit__(None,None,None)
            raise HeavyJobUnavailable('Dual acquisition failed; only own complete leases released') from e
        self.owned=True;self.started=time.monotonic();self.identity=identity
        # Close the acquisition race before doing any heavy work. AG programs
        # not yet participating in the shared contract remain an explicit guard.
        try:self.verify_owned();workers=ag_workers()
        except BaseException:self.__exit__(None,None,None);raise
        if workers:self.__exit__(None,None,None);raise HeavyJobUnavailable('AG worker appeared during lease acquisition')
        try:self.start_owner_observer()
        except BaseException:self.__exit__(None,None,None);raise
        def observe():
            try:
                while not self.stop.wait(.1):
                    self.peak=max(self.peak,self.rss_mib())
                    if self.memory_metric=='private':self.private_peak=max(self.private_peak,self.private_mib())
            except Exception as e:self.monitor_error=str(e)
        self.monitor=threading.Thread(target=observe,daemon=True);self.monitor.start();return self
    def start_owner_observer(self):
        helper=Path(__file__).with_name('compute_owner_observer.py')
        self.observer=subprocess.Popen([sys.executable,str(helper),str(os.getpid()),str(self.process.create_time()),self.nonce,json.dumps([str(p) for p in self.owned_paths])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.ABOVE_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0)
        self.observer_birth=psutil.Process(self.observer.pid).create_time()
        def receive():
            try:
                for line in self.observer.stdout:
                    row=json.loads(line)
                    if row.get('parentPid')!=os.getpid() or row.get('parentStarted')!=self.process.create_time() or row.get('nonce')!=self.nonce:raise HeavyJobUnavailable('Observer identity mismatch')
                    if row.get('kind')=='diagnostic':self.observer_stage=row['stage']
                    else:self.observer_state=row
            except Exception as e:self.monitor_error=str(e)
        self.reader=threading.Thread(target=receive,daemon=True);self.reader.start();deadline=time.monotonic()+10
        while self.observer_state is None and not self.monitor_error and time.monotonic()<deadline:time.sleep(.01)
        if self.observer_state is None and self.observer.poll() is not None:
            error=self.observer.stderr.read(2048)
            raise HeavyJobUnavailable('Ownership observer exited before first census: '+error)
        self.verify_observation();self.verify_owned()
    def verify_observation(self):
        row=self.observer_state
        if self.monitor_error:raise HeavyJobUnavailable('Ownership observer failed: '+self.monitor_error)
        if row is None:raise HeavyJobUnavailable('Ownership observer unavailable: no first census at '+str(getattr(self,'observer_stage',None))+'; own work stopped')
        age=time.monotonic()-row['observedAt']
        if age>1 or age<-.05:raise HeavyJobUnavailable(f'Ownership observer stale: age {age:.3f}s; own work stopped')
        if not row.get('ok'):raise HeavyJobUnavailable('Ownership observer failed; own work stopped')
        if row.get('workers'):raise HeavyJobUnavailable('AG worker appeared; own work stopped cooperatively')
    def verify_owned(self):
        for path in [LOCK,AG_LOCK]:
            identity=read_lease(path)
            if identity is None or any(identity[k]!=self.identity[k] for k in ['pid','processStarted','workspace','jobId','nonce']):raise HeavyJobUnavailable('Lease identity changed; own work stopped')
            verify_process_identity(identity)
    def check(self):
        now=time.monotonic()
        if now-self.last_check<.25:return
        self.last_check=now;self.peak=max(self.peak,self.rss_mib())
        if self.monitor_error:raise HeavyJobUnavailable('Memory monitor failed; own work stopped: '+str(self.monitor_error))
        if self.memory_metric=='private':self.private_peak=max(self.private_peak,self.private_mib())
        self.verify_owned()
        available=available_physical_mib()
        budget_peak=self.private_peak if self.memory_metric=='private' else self.peak
        if budget_peak>self.limit or available<400:raise HeavyJobUnavailable(json.dumps(dict(reason='OWN_MEMORY_OR_RESERVE',metric=self.memory_metric,peakMiB=budget_peak,summedRSSMiB=self.peak,limitMiB=self.limit,availableMiB=available)))
        self.verify_observation()
    def __exit__(self,*args):
        self.stop.set()
        if hasattr(self,'monitor'):self.monitor.join(1)
        self.release_owned_paths()
        if hasattr(self,'observer'):
            if self.observer.poll() is None:
                try:self.observer.wait(timeout=2)
                except (OSError,subprocess.TimeoutExpired):
                    # Only this Popen's read-only helper handle can be stopped.
                    # Never terminate a trainer, AG process or unverified PID.
                    try:
                        if psutil.Process(self.observer.pid).create_time()==self.observer_birth:self.observer.terminate();self.observer.wait(timeout=2)
                    except (psutil.NoSuchProcess,psutil.AccessDenied,subprocess.TimeoutExpired):pass
            if hasattr(self,'reader'):self.reader.join(1)
        self.owned=False
    def release_owned_paths(self):
        for path in reversed(self.owned_paths):
            try:
                row=read_lease(path)
                if row is not None and row.get('nonce')==self.nonce and row.get('pid')==os.getpid() and row.get('processStarted')==self.process.create_time() and row.get('jobId')==self.job and Path(row['workspace']).resolve()==Path(self.process.cwd()).resolve():path.unlink()
            except (OSError,HeavyJobUnavailable,psutil.AccessDenied):pass
    def receipt(self):return dict(**self.identity,leasePaths=[str(p) for p in self.owned_paths],bothLeasesOwned=True,ownershipObservationMaxAgeSeconds=1,observerPid=getattr(getattr(self,'observer',None),'pid',None),observerProcessStarted=getattr(self,'observer_birth',None),peakMeasuredRSSMiB=self.peak,peakMeasuredPrivateMiB=self.private_peak if self.memory_metric=='private' else None,childRSSIncluded=self.include_children,elapsedSeconds=time.monotonic()-self.started,foreignProcessesStopped=False,monitorError=self.monitor_error)
