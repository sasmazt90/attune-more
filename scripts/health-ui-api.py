"""Real isolated backend. Existing credentials stay only in backend memory."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['ATTUNE_LOAD_LOCAL_ENV']='0'
os.environ['ATTUNE_EXPERIMENTAL_ACNE_V5']='1'
os.environ['ATTUNE_TRUSTED_ORIGINS']='http://127.0.0.1:3308'
os.environ['ATTUNE_DATA_DIR']=str(ROOT.parent/'cdc-progress/health-ui-consent-audio-followup-20261017/backend-data')
sys.path.insert(0,str(ROOT/'services/core-api'))
sys.path.insert(0,str(ROOT/'.runtime/edge-tts'))
def load_existing_configuration():
 # Explicitly authorized reuse of the existing configuration; no new secret file.
 config=ROOT.parent/'attune-live-test/.env.local'
 if config.is_file():
  for line in config.read_text('utf8').splitlines():
   name,separator,value=line.partition('=')
   if separator and name.strip() in ('OPENAI_API_KEY','OPENAI_MODEL','OPENAI_TTS_MODEL'):
    os.environ[name.strip()]=value.strip().strip('"').strip("'")
if __name__=='__main__':
 load_existing_configuration()
 import uvicorn
 uvicorn.run('main:app',host='127.0.0.1',port=8308,access_log=False)
