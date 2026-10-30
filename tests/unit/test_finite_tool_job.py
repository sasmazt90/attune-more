"""Small real Windows subprocess controls; no parser exhaustion or app requests.

Low fixture limits use only the Python API, never production CLI overrides.
"""
import ctypes,hashlib,json,os,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/tooling'))
from finite_job import Limits,run_job
import psutil
OUT=Path(os.environ['ATTUNE_GUARD_TEST_DIR']) if 'ATTUNE_GUARD_TEST_DIR' in os.environ else None


def record(file,role):
 p=psutil.Process();row=dict(role=role,pid=p.pid,started=p.create_time(),exe=p.exe(),cwd=p.cwd(),argvSHA256=hashlib.sha256(json.dumps(p.cmdline()).encode()).hexdigest())
 with file.open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\n')


def records(file):
 if not file.exists():return []
 return [json.loads(x) for x in file.read_text('utf8').splitlines() if x]


def fixture(mode,file):
 record(file,mode)
 if mode=='normal':print('NORMAL_OUT',flush=True);print('NORMAL_ERR',file=sys.stderr,flush=True);return 7
 if mode=='env':print(os.environ.get('NODE_OPTIONS',''));return 0
 if mode=='sleep':time.sleep(30);return 0
 if mode=='breakaway':
  try:subprocess.Popen([sys._base_executable,'-c','pass'],creationflags=0x1000000)
  except OSError:print('BREAKAWAY_DENIED',flush=True);return 0
  return 9
 if mode in ['tree','orphan']:
  subprocess.Popen([sys._base_executable,__file__,'fixture','branch',str(file)],creationflags=subprocess.CREATE_NO_WINDOW)
  end=time.monotonic()+3
  while len(records(file))<3 and time.monotonic()<end:time.sleep(.02)
  if mode=='orphan':return 0
  time.sleep(30);return 0
 if mode=='branch':
  os.chdir(os.environ['TEMP'])
  subprocess.Popen([sys._base_executable,__file__,'fixture','sleep',str(file)],creationflags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP)
  time.sleep(30);return 0
 if mode in ['memory','aggregate','aggregate-child']:
  k=ctypes.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong];k.VirtualAlloc.restype=ctypes.c_void_p
  allocated=[]
  for i in range(128 if mode=='memory' else 24):
   address=k.VirtualAlloc(None,1024**2,0x3000,4)
   if not address:return 42
   allocated.append(address)
  if mode=='aggregate':
   subprocess.Popen([sys._base_executable,__file__,'fixture','aggregate-child',str(file)],creationflags=subprocess.CREATE_NO_WINDOW)
   time.sleep(30)
  if mode=='aggregate-child':time.sleep(30)
  return 0
 if mode=='supervisor':
  result=run_job([sys._base_executable,__file__,'fixture','tree',str(file)],ROOT,Limits(15,192,0,0))
  return result['exitCode']
 raise ValueError(mode)


@unittest.skipUnless(os.name=='nt','Windows Job Object execution required')
class RealFiniteJob(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  global OUT
  if OUT is None:
   cls.disposable=tempfile.TemporaryDirectory(prefix='attune-finite-job-');OUT=Path(cls.disposable.name);cls.addClassCleanup(cls.disposable.cleanup)
  else:
   OUT.mkdir(parents=True,exist_ok=True);OUT=Path(tempfile.mkdtemp(prefix='finite-run-',dir=OUT))
 def setUp(self):
  OUT.mkdir(parents=True,exist_ok=True);self.file=OUT/(self._testMethodName+'.jsonl');self.result=None
  self.assertFalse(self.file.exists(),'Do not overwrite completed fixture')
 def assert_closed(self):
  for row in records(self.file):
   end=time.monotonic()+3
   while time.monotonic()<end:
    try:
     if psutil.Process(row['pid']).create_time()!=row['started']:break
    except psutil.NoSuchProcess:break
    time.sleep(.03)
   else:self.fail('Exact owned fixture survived: '+str(row['pid']))
 def run_case(self,mode,wall=10,memory=192,**kw):
  with (OUT/(self._testMethodName+'.stdout')).open('w',encoding='utf8') as out,(OUT/(self._testMethodName+'.stderr')).open('w',encoding='utf8') as err:
   self.result=run_job([sys._base_executable,__file__,'fixture',mode,str(self.file)],ROOT,Limits(wall,memory,0,0),stdout=out,stderr=err,**kw)
  (OUT/(self._testMethodName+'.result.json')).write_text(json.dumps(self.result,indent=2),'utf8');self.assert_closed();self.assertEqual(self.result['activeProcessesAfter'],0);return self.result
 def test_normal_exit_output(self):
  r=self.run_case('normal');self.assertEqual(r['exitCode'],7);self.assertEqual(r['reason'],'exit')
  self.assertIn('NORMAL_OUT',(OUT/(self._testMethodName+'.stdout')).read_text('utf8'));self.assertIn('NORMAL_ERR',(OUT/(self._testMethodName+'.stderr')).read_text('utf8'))
 def test_timeout_nested_changed_cwd(self):
  r=self.run_case('tree',wall=1.5);self.assertEqual(r['reason'],'wall-time-limit');self.assertGreaterEqual(r['totalJobProcesses'],3)
 def test_orphan(self):
  r=self.run_case('orphan');self.assertEqual(r['reason'],'orphaned-descendants');self.assertEqual(r['exitCode'],125);self.assertGreaterEqual(r['totalJobProcesses'],3)
 def test_commit_memory(self):
  r=self.run_case('memory',memory=48);self.assertIn(r['exitCode'],[42,137]);self.assertEqual(r['OSInstalledJobCommitBytes'],48*2**20);self.assertGreater(r['peakJobCommittedMiB'],10)
  # PeakJobMemoryUsed is observed accounting, not an exact maximum guarantee.
  # Verify real allocation denial/notification and the installed OS limit.
 def test_cancel(self):
  cancel=threading.Event();timer=threading.Timer(1,cancel.set);timer.start()
  try:r=self.run_case('tree',cancel=cancel);self.assertEqual(r['reason'],'cancelled');self.assertEqual(r['exitCode'],130)
  finally:timer.cancel();timer.join()
 def test_aggregate_job_commit(self):
  r=self.run_case('aggregate',memory=64);self.assertEqual(r['reason'],'job-commit-limit');self.assertEqual(r['OSInstalledJobCommitBytes'],64*2**20);self.assertGreaterEqual(r['totalJobProcesses'],3)
 def test_watchdog_during_stalled_cooperative_check(self):
  r=self.run_case('sleep',wall=.6,check=lambda:time.sleep(1.2));self.assertEqual(r['reason'],'wall-time-limit');self.assertTrue(r['deadlineWatchdog']['terminateSucceeded']);self.assertLess(r['deadlineWatchdog']['atSeconds'],.9)
 def test_supervisor_hard_exit(self):
  child=subprocess.Popen([sys._base_executable,__file__,'fixture','supervisor',str(self.file)],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);birth=psutil.Process(child.pid).create_time()
  try:
   end=time.monotonic()+12
   while len(records(self.file))<4 and time.monotonic()<end:time.sleep(.03)
   self.assertGreaterEqual(len(records(self.file)),4)
  finally:
   if child.poll() is None:
    self.assertEqual(psutil.Process(child.pid).create_time(),birth);child.terminate();child.wait(timeout=5)
  self.assert_closed()
 def test_breakaway_denied(self):
  r=self.run_case('breakaway');self.assertEqual(r['exitCode'],0);self.assertIn('BREAKAWAY_DENIED',(OUT/(self._testMethodName+'.stdout')).read_text('utf8'))
 def test_node_options_preserved(self):
  value='--max-old-space-size=333 --trace-warnings';r=self.run_case('env',env={**os.environ,'NODE_OPTIONS':value});self.assertEqual(r['exitCode'],0);self.assertEqual((OUT/(self._testMethodName+'.stdout')).read_text('utf8').strip(),value)


if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='fixture':sys.exit(fixture(sys.argv[2],Path(sys.argv[3])))
 unittest.main()
