"""Shared atomic compute lease; never stop another task or remove its lock."""
import hashlib,json,os,time,uuid,threading
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2]
LOCK=ROOT.parent/'coordination-notes/heavy-compute.lock.json'
AG_ROOT=(ROOT.parent/'attune-antigravity-skin').resolve()

class HeavyJobUnavailable(RuntimeError):pass

def ag_workers():
    result=[]
    for p in psutil.process_iter(['pid','name','create_time']):
        if 'python' not in (p.info['name'] or '').lower():continue
        try:
            if p.pid==os.getpid():continue
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
        except (psutil.NoSuchProcess,psutil.AccessDenied):continue
    return result

class HeavyJobLease:
    def __init__(self,job,peak_mib=700,minimum_available_mib=1200,include_children=False):
        self.job=job;self.limit=peak_mib;self.minimum=minimum_available_mib;self.include_children=include_children;self.stop=threading.Event();self.peak=0.;self.last_check=0.;self.process=psutil.Process();self.nonce=uuid.uuid4().hex;self.owned=False
    def rss_mib(self):
        processes=[self.process]+(self.process.children(recursive=True) if self.include_children else [])
        total=0
        for process in processes:
            try:total+=process.memory_info().rss
            except (psutil.NoSuchProcess,psutil.AccessDenied):continue
        return total/2**20
    def __enter__(self):
        available=psutil.virtual_memory().available/2**20;workers=ag_workers()
        if available<self.minimum or workers:raise HeavyJobUnavailable(json.dumps(dict(reason='RESOURCE_OR_AG_BUSY',availableMiB=available,requiredMiB=self.minimum,AG=workers)))
        LOCK.parent.mkdir(exist_ok=True)
        identity=dict(owner='CD',pid=os.getpid(),processStarted=self.process.create_time(),jobId=self.job,nonce=self.nonce,commandSHA256=hashlib.sha256('\0'.join(self.process.cmdline()).encode()).hexdigest(),peakBudgetMiB=self.limit,minimumAvailableMiB=self.minimum)
        try:
            fd=os.open(LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise HeavyJobUnavailable('Existing shared lease retained; no stale/foreign lock removed')
        with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(identity,f);f.flush();os.fsync(f.fileno())
        self.owned=True;self.started=time.monotonic();self.identity=identity
        # Close the acquisition race before doing any heavy work. AG programs
        # not yet participating in the shared contract remain an explicit guard.
        if ag_workers():self.__exit__(None,None,None);raise HeavyJobUnavailable('AG worker appeared during lease acquisition')
        def observe():
            while not self.stop.wait(.1):self.peak=max(self.peak,self.rss_mib())
        self.monitor=threading.Thread(target=observe,daemon=True);self.monitor.start();return self
    def check(self):
        now=time.monotonic()
        if now-self.last_check<.25:return
        self.last_check=now;self.peak=max(self.peak,self.rss_mib())
        identity=json.loads(LOCK.read_text('utf8'))
        if identity['pid']!=os.getpid() or identity['processStarted']!=self.process.create_time() or identity['jobId']!=self.job or identity['nonce']!=self.nonce:raise HeavyJobUnavailable('Lease identity changed; own work stopped')
        available=psutil.virtual_memory().available/2**20
        if self.peak>self.limit or available<400:raise HeavyJobUnavailable(json.dumps(dict(reason='OWN_RSS_OR_RESERVE',peakMiB=self.peak,limitMiB=self.limit,availableMiB=available)))
        if ag_workers():raise HeavyJobUnavailable('AG worker appeared; own work stopped cooperatively')
    def __exit__(self,*args):
        self.stop.set()
        if hasattr(self,'monitor'):self.monitor.join(1)
        if self.owned:
            try:
                row=json.loads(LOCK.read_text('utf8'))
                if row.get('nonce')==self.nonce and row.get('pid')==os.getpid() and row.get('processStarted')==self.process.create_time():LOCK.unlink()
            except FileNotFoundError:pass
        self.owned=False
    def receipt(self):return dict(**self.identity,peakMeasuredRSSMiB=self.peak,childRSSIncluded=self.include_children,elapsedSeconds=time.monotonic()-self.started,foreignProcessesStopped=False)
