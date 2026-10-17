"""Isolated, keyless API using only the already verified fixed vision bank."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['ATTUNE_LOAD_LOCAL_ENV']='0'
os.environ['ATTUNE_TRUSTED_ORIGINS']='http://127.0.0.1:3306'
sys.path.insert(0,str(ROOT/'services/core-api'))
if __name__=='__main__':
 import uvicorn
 uvicorn.run('main:app',host='127.0.0.1',port=8306,access_log=False)
