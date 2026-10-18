"""Isolated vehicle API; dental uses pinned local ONNX, no hosted service."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.update(ATTUNE_LOAD_LOCAL_ENV='0',ATTUNE_EXPERIMENTAL_ACNE_V5='1',ATTUNE_TRUSTED_ORIGINS='http://127.0.0.1:3310',ATTUNE_DATA_DIR=str(ROOT.parent/'cdc-progress/dental-technical-closeout-20261017/backend-data'))
sys.path.insert(0,str(ROOT/'services/core-api'))
sys.path.insert(0,str(ROOT/'.runtime/edge-tts'))
if __name__=='__main__':
 import uvicorn
 uvicorn.run('main:app',host='127.0.0.1',port=8310,access_log=False)
