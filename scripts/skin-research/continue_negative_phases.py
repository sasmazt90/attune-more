"""Continue after natural slices, finish source order, then fork a data phase.

Never terminates a trainer, changes an active checkpoint, installs a candidate,
or accesses user records. Each new phase preserves every persistent checkpoint.
"""
import argparse,concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
import psutil
from expanded_sources import ROOT,OUT,sha,write

def worker(kind,pid):
 script='train_expanded_detector.py' if kind=='yolox' else 'train_continuation_mask.py';folder=OUT/kind;new=OUT/('negative-yolox' if kind=='yolox' else 'negative-mask-continuation');log=OUT/f'{kind}-continuation-supervisor.log'
 if psutil.pid_exists(pid):
  process=psutil.Process(pid);assert script in ' '.join(process.cmdline()) and Path(process.cwd()).resolve()==ROOT.resolve(),'TRAINER_OWNERSHIP_MISMATCH'
  creation=process.create_time()
  while True:
   try:
    if not psutil.pid_exists(pid) or psutil.Process(pid).create_time()!=creation:break
   except psutil.NoSuchProcess:break
   time.sleep(10)
 with log.open('a',encoding='utf8') as stream:
  # A slice may end within an epoch. Consume its remaining persisted order
  # using the original ledger before adding any new row or changing scope.
  plan=json.loads((OUT/'negative-phase-dispatch-plan.json').read_text('utf8'))
  for name,expected in plan['files'].items():assert sha(ROOT/name)==expected,'FROZEN_DISPATCH_INPUT_CHANGED'
  generation=folder/(folder/'CURRENT').read_text('utf8');state=json.loads((generation/'state.json').read_text('utf8'))
  (folder/'PRESERVE_ALL_CHECKPOINTS').touch(exist_ok=True)
  if state['cursor'] or state['order']:
   command=[sys.executable,str(ROOT/'scripts/skin-research'/script),'--seconds','7200','--until-epoch',str(state['epoch']+1)]
   if kind=='mask-continuation':command.append('--refined-support')
   result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=stream)
   if result.returncode:raise RuntimeError('ORIGINAL_PHASE_RESUME_FAILED; checkpoint preserved')
  generation=folder/(folder/'CURRENT').read_text('utf8');state=json.loads((generation/'state.json').read_text('utf8'));assert not state['cursor'] and not state['order'],'PARENT_EPOCH_BOUNDARY_REQUIRED'
  write(kind+'/new-phase-dispatch.json',dict(parentCheckpoint=generation.name,parentModelSHA256=state['modelSHA256'],parentOptimizerSHA256=state['optimizerSHA256'],parentEpoch=state['epoch'],parentStep=state['step'],remainingSourceOrderConsumed=True,oldPhaseNotReportedAsFinal=True,newPhaseFolder=new.name))
  while not (new/'selection.json').exists():
   command=[sys.executable,str(ROOT/'scripts/skin-research'/script),'--seconds','14400','--negative-phase','--parent-checkpoint',generation.name]
   result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=stream)
   if result.returncode:raise RuntimeError('NEW_PHASE_FAILED; last complete checkpoint preserved')
   stop=json.loads((new/'stop.json').read_text('utf8')) if (new/'stop.json').exists() else {}
   if stop.get('reason')=='RESUMABLE_DISK_RESERVE':return dict(kind=kind,status='RESOURCE_LIMIT_RESUMABLE',reason=stop['reason'])
 subprocess.run([sys.executable,str(ROOT/'scripts/skin-research/update_acceptance_progress.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 decisions=json.loads((OUT/'label-function-current-decisions.json').read_text('utf8'))['rows'];keys=['acneDetector'] if kind=='yolox' else [key for key in decisions if key.endswith('Mask')]
 return dict(kind=kind,status='TRAINING_PHASE_COMPLETE',actualAcceptanceDecisions={key:decisions[key]['decision'] for key in keys},candidatePromotionPerformed=False)

def main():
 p=argparse.ArgumentParser();p.add_argument('--yolox-pid',type=int,required=True);p.add_argument('--mask-pid',type=int,required=True);a=p.parse_args();plan=OUT/'negative-phase-dispatch-plan.json'
 paths=[ROOT/'scripts/skin-research/train_expanded_detector.py',ROOT/'scripts/skin-research/train_continuation_mask.py',OUT/'negative-expanded-detector-data.json',OUT/'negative-expanded-mask-data.json']
 write(plan.name,dict(version='natural-slice-native-phase-continuation-v1',files={str(v.relative_to(ROOT)):sha(v) for v in paths},originalTrainerPIDs=dict(yolox=a.yolox_pid,mask=a.mask_pid),noTrainerTermination=True,noWeightReset=True,noActiveOrderMutation=True,noCandidatePromotion=True,persistentPhaseCheckpointsNeverDeleted=True,finalTestOpened=False,status='WAITING_FOR_ORIGINAL_NATURAL_SLICES'))
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  jobs=[pool.submit(worker,'yolox',a.yolox_pid),pool.submit(worker,'mask-continuation',a.mask_pid)]
  for job in concurrent.futures.as_completed(jobs):
   try:results.append(job.result())
   except Exception as error:results.append(dict(status='FAILED_RESUMABLE',error=str(error)))
   write('negative-phase-dispatch-result.json',dict(results=results,allCompleted=len(results)==2,userTestReady=False))
if __name__=='__main__':main()
