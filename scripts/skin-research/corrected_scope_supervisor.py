"""One owned worker per corrected phase, native checkpoint pause only."""
import datetime,json,os,shutil,subprocess,sys,time
from pathlib import Path
import psutil
from expanded_sources import ROOT,OUT,sha
from train_corrected_scope import PHASE,OLD
RUNTIME=ROOT/'.runtime/storage-20261011'

def write(name,value):
 p=RUNTIME/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,indent=2),'utf8');t.replace(p)

def main():
 for p in psutil.process_iter(['pid','cmdline','cwd']):
  args=p.info['cmdline'] or [];cmd=' '.join(args)
  if p.pid!=os.getpid() and args and Path(args[0]).name.lower() in ['python.exe','pythonw.exe','python3.exe'] and Path(p.info['cwd'] or '.').resolve()==ROOT and any(s in cmd for s in ['train_corrected_scope.py','train_continuation_mask.py','train_expanded_detector.py','corrected_scope_supervisor.py','resume-and-monitor.py']):raise RuntimeError('EXISTING_OWNED_TRAINER_OR_SUPERVISOR')
 if shutil.disk_usage(ROOT).free<6*1024**3:raise RuntimeError('START_RESERVE_NOT_MET')
 for phase in OLD.values():assert (OUT/phase/'STORAGE_PAUSE').exists(),'LEGACY_INCORRECT_SELECTION_RESTART_BLOCKED'
 jobs=[];logs=[]
 for kind,phase in PHASE.items():
  folder=OUT/phase
  if (folder/'selection.json').exists():continue
  if (folder/'CURRENT').exists():
   generation=folder/(folder/'CURRENT').read_text('utf8').strip();assert generation.resolve().parent==folder.resolve();s=json.loads((generation/'state.json').read_text('utf8'))
   assert s['identity']==sha(folder/'protocol.json') and sha(generation/'model.safetensors')==s['modelSHA256'] and sha(generation/'optimizer.safetensors')==s['optimizerSHA256'],'CORRECTED_CURRENT_INTEGRITY'
   protocol=json.loads((folder/'protocol.json').read_text('utf8'));assert protocol['codeSHA256']==sha(ROOT/'scripts/skin-research/train_corrected_scope.py'),'FROZEN_WORKER_CODE_CHANGED'
   assert all(sha(ROOT/'scripts/skin-research'/name)==digest for name,digest in protocol['consumedCodeSHA256'].items()),'FROZEN_CONSUMED_CODE_CHANGED'
  pause=folder/'STORAGE_PAUSE'
  if pause.exists():pause.unlink()
  streams=[(RUNTIME/f'{phase}.{s}.log').open('a',encoding='utf8') for s in ['stdout','stderr']];logs.extend(streams)
  args=[sys.executable,str(ROOT/'scripts/skin-research/train_corrected_scope.py'),'--kind',kind,'--seconds','14400']
  env={**os.environ,'TOGG_CHECKPOINT_RESERVE_BYTES':str(3*1024**3)}
  child=subprocess.Popen(args,cwd=ROOT,stdout=streams[0],stderr=streams[1],env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0);jobs.append(dict(kind=kind,phase=phase,pid=child.pid,process=child))
 write('resume-start.json',dict(at=datetime.datetime.now().astimezone().isoformat(),pid=os.getpid(),actualFreeBytes=shutil.disk_usage(ROOT).free,rollingStartReserveBytes=6*1024**3,phases=[{k:j[k] for k in ['kind','phase','pid']} for j in jobs],dispatch='corrected-versioned-scopes',noWeightReset=True,legacyPhasesPaused=True))
 while any(j['process'].poll() is None for j in jobs):
  free=shutil.disk_usage(ROOT).free
  if free<3*1024**3:
   for phase in PHASE.values():(OUT/phase/'STORAGE_PAUSE').touch(exist_ok=True)
  write('disk-monitor.json',dict(at=datetime.datetime.now().astimezone().isoformat(),freeBytes=free,checkpointDisk='C:',pauseRequested=free<3*1024**3,safePauseReserveBytes=3*1024**3,pollSeconds=60,supervisorPID=os.getpid(),phaseOwnership=[{k:j[k] for k in ['kind','phase','pid']} for j in jobs]));time.sleep(60)
 write('resume-results.json',dict(at=datetime.datetime.now().astimezone().isoformat(),results=[dict(phase=j['phase'],exitCode=j['process'].returncode,status='FINITE_PHASE_COMPLETE' if (OUT/j['phase']/'selection.json').exists() else 'STOPPED_RESUMABLE_REVIEW_REQUIRED') for j in jobs],userTestReady=False,candidatePromotionPerformed=False))
 for f in logs:f.close()

if __name__=='__main__':main()
