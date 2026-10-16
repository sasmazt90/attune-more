"""Isolated local experimental API. No key loading or remote photo processing."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['ATTUNE_EXPERIMENTAL_ACNE_V5']='1'
os.environ['ATTUNE_LOAD_LOCAL_ENV']='0'
os.environ['ATTUNE_TRUSTED_ORIGINS']='http://127.0.0.1:3305'
sys.path.insert(0,str(ROOT/'services/core-api'))
if __name__=='__main__':
 import uvicorn
 uvicorn.run('main:app',host='127.0.0.1',port=8305,access_log=False)
