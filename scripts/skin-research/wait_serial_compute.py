"""Bounded own wait, then one leased worker; never suspend an AG process."""
import argparse,json,time,subprocess,sys
import psutil
from heavy_job_lease import ag_workers,LOCK
parser=argparse.ArgumentParser();parser.add_argument('--wait-seconds',type=int,default=600);parser.add_argument('script');args=parser.parse_args();deadline=time.monotonic()+args.wait_seconds;last=None
while time.monotonic()<deadline:
    workers=ag_workers();free=psutil.virtual_memory().available/2**20;state=(bool(workers),LOCK.exists(),free>=1300)
    if state!=last:print(json.dumps(dict(waiting=True,AG=workers,lockPresent=state[1],availableMiB=free)),flush=True);last=state
    if not workers and not LOCK.exists() and free>=1300:
        raise SystemExit(subprocess.call([sys.executable,args.script]))
    time.sleep(5)
print(json.dumps(dict(status='RESOURCE_BLOCKED',AG=ag_workers(),availableMiB=psutil.virtual_memory().available/2**20,foreignProcessesChanged=False)),flush=True);raise SystemExit(3)
