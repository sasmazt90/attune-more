"""Download trained Roboflow weights with the user's key (read from staged .env; key never printed)."""
import re,sys,os,json
from roboflow import Roboflow
env=sys.argv[1]; out=sys.argv[2]; jobs=json.loads(sys.argv[3])  # [[project,version,modelId],...]
k=re.search(r'ROBOFLOW_API_KEY\s*=\s*(\S+)',open(env,encoding='utf-8-sig').read()).group(1)
ws=Roboflow(api_key=k).workspace('tolgar-sasmaz')
for proj,ver,mid in jobs:
  v=ws.project(proj).version(int(ver)); ms=[m for m in v.models() if getattr(m,'model_id','').endswith(mid)] or v.models()
  d=os.path.join(out,f'{proj}-v{ver}-{mid.split("-")[-2] if "-" in mid else mid}'); os.makedirs(d,exist_ok=True)
  try: p=ms[0].download(location=d); print('OK',proj,p,os.path.getsize(p))
  except Exception as e: print('ERR',proj,type(e).__name__,str(e)[:300])
