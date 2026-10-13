"""Owned read-only census helper; continuous mid-job ownership observation.

No model/data work or lease removal. Every response is parent/nonce bound. A
stalled census never means 'no AG': the parent fails closed on stale responses.
"""
import json,sys,time
from pathlib import Path
parent_pid=int(sys.argv[1]);parent_started=float(sys.argv[2]);nonce=sys.argv[3];leases=[Path(p) for p in json.loads(sys.argv[4])]
def diagnostic(stage):print(json.dumps(dict(kind='diagnostic',stage=stage,parentPid=parent_pid,parentStarted=parent_started,nonce=nonce)),flush=True)
diagnostic('child-started')
import psutil
from heavy_job_lease import ag_workers
diagnostic('imports-complete')
while True:
    try:
        parent=psutil.Process(parent_pid)
        if parent.create_time()!=parent_started:raise RuntimeError('Parent process creation mismatch')
        for path in leases:
            record=json.loads(path.read_text('utf8'))
            if record.get('nonce')!=nonce or record.get('pid')!=parent_pid or record.get('processStarted')!=parent_started:raise RuntimeError('Parent lease identity mismatch')
        diagnostic('census-start')
        workers=ag_workers();row=dict(ok=True,workers=workers)
    except FileNotFoundError:break # Parent released only its own lease.
    except psutil.NoSuchProcess:break
    except Exception as e:row=dict(ok=False,reason=str(e))
    row.update(parentPid=parent_pid,parentStarted=parent_started,nonce=nonce,observedAt=time.monotonic())
    print(json.dumps(row),flush=True)
    if not row['ok']:break
    time.sleep(.25)
