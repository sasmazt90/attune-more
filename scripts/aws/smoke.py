#!/usr/bin/env python3
"""Finite, authenticated HTTP availability probe. It is not analysis acceptance."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import httpx

p=argparse.ArgumentParser()
p.add_argument('--web',required=True)
p.add_argument('--aaos',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
for url in (a.web,a.aaos):
    v=urlsplit(url)
    if v.scheme!='https' or v.username or v.password or v.query or v.fragment:
        raise SystemExit('Exact HTTPS origins required')
checks=[];start=time.monotonic()
with httpx.Client(timeout=8,auth=(os.environ['ATTUNE_DEMO_USER'],os.environ['ATTUNE_DEMO_PASSWORD']),follow_redirects=False) as client:
    for origin,path in [(a.web,p) for p in ['/api/health','/skin','/vision','/dental','/hearing','/mental']]+[(a.aaos,'/vnc.html'),(a.aaos,'/capture')]:
        try:
            r=client.get(origin+path)
            checks.append({'url':origin+path,'status':r.status_code,'available':r.status_code==200})
        except httpx.HTTPError as e:
            checks.append({'url':origin+path,'available':False,'error':type(e).__name__})
    for origin in [a.web,a.aaos]:
        with httpx.Client(timeout=8,follow_redirects=False) as unauth:
            for path in (['/','/api/health'] if origin==a.web else ['/vnc.html','/capture','/bridge/sender']):
                try:
                    code=unauth.get(origin+path).status_code
                    checks.append({'url':origin+path,'unauthenticatedDenied':code in [401,403]})
                except httpx.HTTPError as e:
                    checks.append({'url':origin+path,'unauthenticatedDenied':False,'error':type(e).__name__})
report={'checks':checks,'seconds':round(time.monotonic()-start,2),'analysisAcceptance':'NOT_RUN',
        'nativeRuntimeAcceptance':'NOT_RUN','modelExecution':'NOT_RUN'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if all(c.get('available',c.get('unauthenticatedDenied',False)) for c in checks) else 1)
