"""Prepare exact existing model/runtime bytes and fixed approved Ahmet text.
No training, personal data, alternate voice, paid API or unbounded retries.
Staging is private until every asset/hash/profile is verified.
"""
from pathlib import Path
import asyncio,hashlib,json,sys,urllib.request,time,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'audit-results/all-health-20261010/local-assets';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'services/core-api'))
from vision_speech import PROMPTS
from tts_profiles import VISION_TTS_PROFILE as PROFILE
import edge_tts

def sha(data):return hashlib.sha256(data).hexdigest()
def download(url):
 with urllib.request.urlopen(url,timeout=40) as response:return response.read()

def models():
 folder=OUT/'mediapipe';(folder/'wasm').mkdir(parents=True,exist_ok=True);(folder/'models').mkdir(exist_ok=True)
 files=[]
 for path in (ROOT/'node_modules/@mediapipe/tasks-vision/wasm').iterdir():
  if path.suffix not in ('.js','.wasm'):continue
  target=folder/'wasm'/path.name;shutil.copyfile(path,target)
  files.append(dict(path='wasm/'+path.name,sha256=sha(target.read_bytes()),bytes=target.stat().st_size,source='@mediapipe/tasks-vision@1.0.1/wasm/'+path.name,license='Apache-2.0'))
 for name in ('face_landmarker','hand_landmarker'):
  url=f'https://storage.googleapis.com/mediapipe-models/{name}/{name}/float16/1/{name}.task'
  raw=download(url);target=folder/'models'/(name+'.task');target.write_bytes(raw)
  if name=='face_landmarker':assert sha(raw)==sha((ROOT/'audit-results/skin-capabilities-20261008/scin/face_landmarker.task').read_bytes())
  files.append(dict(path='models/'+name+'.task',sha256=sha(raw),bytes=len(raw),source=url,license='Apache-2.0'))
 card='https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf'
 raw=download(card);(OUT/'hand-model-card.pdf').write_bytes(raw)
 manifest=dict(sdkVersion='1.0.1',files=files,handModelCard=dict(url=card,sha256=sha(raw)),modelChange=False,thresholdChange=False)
 (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');print(json.dumps(dict(modelsPrepared=len(files),bytes=sum(f['bytes'] for f in files))),flush=True)

async def speech():
 folder=OUT/'vision-speech';folder.mkdir(exist_ok=True);entries={};events=[]
 manifest=dict(version='fixed-vision-Ahmet-1',voice=PROFILE.voice,rate=PROFILE.rate,pitch=PROFILE.pitch,entries=entries)
 for code,text in PROMPTS.items():
  path=folder/(code+'.mp3');started=time.monotonic();attempts=0
  if path.exists() and (folder/'manifest.json').exists():
   old=json.loads((folder/'manifest.json').read_text());entry=old['entries'].get(code)
   if entry and entry['text']==text and entry['sha256']==sha(path.read_bytes()):entries[code]=entry;continue
  while True:
   attempts+=1
   try:
    # Edge's clock/signature state is process-global. The preceding generation
    # got intermittent 403 after successful utterances. Use one fresh bounded
    # official CLI process per fixed utterance; never an alternate voice.
    result=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','edge_tts','--voice='+PROFILE.voice,'--rate='+PROFILE.rate,'--pitch='+PROFILE.pitch,'--text='+text,'--write-media='+str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=35)
    if result.returncode:raise RuntimeError('EDGE_FIXED_GENERATION_FAILED')
    break
   except Exception as error:
    events.append(dict(code=code,attempt=attempts,failure=type(error).__name__))
    if attempts>=2:raise
    await asyncio.sleep(3)
  raw=path.read_bytes();assert len(raw)>1000
  entries[code]=dict(text=text,file=code+'.mp3',sha256=sha(raw),bytes=len(raw),voice=PROFILE.voice,rate=PROFILE.rate,pitch=PROFILE.pitch)
  events.append(dict(code=code,attempts=attempts,bytes=len(raw),seconds=round(time.monotonic()-started,3)))
  (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8');(OUT/'speech-generation.json').write_text(json.dumps(dict(fixedNonpersonalText=True,paidCalls=0,events=events,auditoryAcceptance=False),indent=2),'utf8')
  print(json.dumps(events[-1]),flush=True)
  await asyncio.sleep(.5)
 assert len(entries)==len(PROMPTS)

if __name__=='__main__':
 if sys.argv[1]=='models':models()
 elif sys.argv[1]=='speech':asyncio.run(speech())
 else:raise ValueError('Choose models or speech')
