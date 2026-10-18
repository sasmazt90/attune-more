"""Read-only acceptance follow-through for a running, owned continuation dispatcher.

Training completion never implies model acceptance. No process is interrupted,
no model is installed, and no final-test pixels or personal records are read.
"""
import argparse,json,time,subprocess,sys
from pathlib import Path
import psutil
from expanded_sources import OUT,ROOT,write



def main(pid):
 process=psutil.Process(pid)
 assert 'continue_negative_phases.py' in ' '.join(process.cmdline()) and Path(process.cwd()).resolve()==ROOT.resolve()
 created=process.create_time()
 while True:
  try:
   alive=psutil.pid_exists(pid) and psutil.Process(pid).create_time()==created
  except psutil.NoSuchProcess:alive=False
  if not alive:break
  time.sleep(30)
 dispatch=OUT/'negative-phase-dispatch-result.json'
 result=json.loads(dispatch.read_text('utf8')) if dispatch.exists() else {'allCompleted':False,'results':[]}
 for script in ['record_actual_coverage.py','update_acceptance_progress.py','record_expanded_progress.py']:
  subprocess.run([sys.executable,str(ROOT/'scripts/skin-research'/script)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 decisions=json.loads((OUT/'label-function-current-decisions.json').read_text('utf8'))['rows']
 actual={key:value['decision'] for key,value in decisions.items() if key=='acneDetector' or key.endswith('Mask')}
 write('continuation-final-acceptance.json',dict(version='actual-continuation-label-function-decisions-v1',trainingDispatchResults=[{key:value for key,value in row.items() if key not in ['accepted','acceptanceEvaluationStillRequired']} for row in result['results']],dispatchFinished=result.get('allCompleted',False),actualDecisions=actual,promotionPerformed=False,finalTestOpened=False))
 print('Continuation evaluated from actual completed evidence; no automatic promotion',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--supervisor-pid',type=int,required=True);main(parser.parse_args().supervisor_pid)
