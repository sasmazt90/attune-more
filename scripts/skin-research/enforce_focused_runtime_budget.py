"""Operational ceiling for the already-started CPU baseline, no retraining.

The original epoch-boundary 3600-second check allowed an overrun. This separate
ceiling was added during execution, not presented as a predeclared training rule.
Only the identified owned training process may be stopped. Existing files stay.
"""
import argparse, json, time
from pathlib import Path
import psutil

p=argparse.ArgumentParser();p.add_argument('pid',type=int);p.add_argument('--seconds',type=int,default=7200)
args=p.parse_args();root=Path(__file__).resolve().parents[2]
out=root/'audit-results/focused-skin-20261010/fasterrcnn'
proc=psutil.Process(args.pid);command=proc.cmdline()
assert any('train_focused_local.py' in v for v in command) and 'fasterrcnn' in command
assert Path(proc.cwd()).resolve()==root.resolve()
started=proc.create_time();deadline=started+args.seconds
report=dict(pid=args.pid,processStartedAt=started,originalEpochBoundaryBudgetSeconds=3600,
            operationalCeilingSeconds=args.seconds,ceilingAddedDuringRun=True,
            protectedSelectionThresholdsUnchanged=True,normalAppsTouched=False)
path=out/'runtime-budget-review.json'
def save():path.write_text(json.dumps(report,indent=2),'utf8')
save()
while proc.is_running() and proc.status()!=psutil.STATUS_ZOMBIE:
    if (out/'selected.safetensors').exists():
        report.update(validatedCheckpointBeforeCeiling=True,stopped=False,
                      remainingStage='frozen one-pass protected test; no further epoch under original boundary check')
        save();break
    if time.time()>=deadline:
        # PID reuse or a different process must never be terminated.
        assert proc.create_time()==started and proc.cmdline()==command
        report.update(validatedCheckpointBeforeCeiling=False,stopped=True,
                      elapsedSeconds=time.time()-started,cpuSeconds=sum(proc.cpu_times()[:2]),
                      rssBytes=proc.memory_info().rss,reason='NO_VALIDATED_EPOCH_WITHIN_OPERATIONAL_CEILING',
                      filesPreserved=[v.name for v in out.iterdir() if v.is_file()],
                      protectedTestOpened=False,trainedCheckpointExists=False,
                      inMemoryPartialWeightsLost=True)
        save();proc.terminate();proc.wait(timeout=30);break
    time.sleep(min(30,max(1,deadline-time.time())))
else:
    report.update(stopped=False,processEnded=True,validatedCheckpointExists=(out/'selected.safetensors').exists());save()
print(json.dumps(report),flush=True)
