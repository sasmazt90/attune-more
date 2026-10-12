"""Load the existing AG key into this backend process only; never copy it."""
import os
from pathlib import Path

def load_existing_backend_key():
    if os.getenv('ATTUNE_LOAD_LOCAL_ENV')!='1':return False
    source=Path(__file__).resolve().parents[2].parent/'attune-antigravity-skin/.env.local'
    try:lines=source.read_text('utf-8-sig').splitlines()
    except OSError:return False
    for line in lines:
        name,separator,value=line.partition('=');name=name.strip()
        if separator and name in ('ATTUNE_ROBOFLOW_API_KEY','ROBOFLOW_API_KEY'):
            value=value.strip().strip('"').strip("'")
            if value and not os.environ.get(name):os.environ[name]=value
    return bool(os.environ.get('ATTUNE_ROBOFLOW_API_KEY') or os.environ.get('ROBOFLOW_API_KEY'))
