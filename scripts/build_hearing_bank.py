"""Once-only approved general Turkish digits, exact Edge profile; no user data."""
import asyncio,hashlib,json,subprocess,sys
from pathlib import Path
import edge_tts,imageio_ffmpeg,numpy as np
from scipy.io import wavfile
from scipy.ndimage import gaussian_filter1d
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'apps/vehicle-app/public/audio/hearing-bank'
RAW=ROOT/'audit-results/combined-health-20261008/hearing-bank'
WORDS=['sıfır','bir','iki','üç','dört','beş','altı','yedi','sekiz','dokuz']
def rms(p):return float(np.sqrt(np.mean(p*p)))
async def main():
 OUT.mkdir(exist_ok=True,parents=True);RAW.mkdir(exist_ok=True,parents=True)
 voices=await edge_tts.list_voices()
 if not any(v['ShortName']=='tr-TR-AhmetNeural' for v in voices):raise RuntimeError('EXACT_VOICE_UNAVAILABLE; no fallback')
 entries=[];pcm=[]
 for digit,text in enumerate(WORDS):
  mp3=RAW/f'{digit}.mp3';wave=RAW/f'{digit}.wav'
  if not mp3.exists():await edge_tts.Communicate(text,'tr-TR-AhmetNeural',rate='-10%',pitch='-10Hz').save(str(mp3))
  subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-i',str(mp3),'-ac','1','-ar','48000','-c:a','pcm_f32le',str(wave)],check=True)
  rate,p=wavfile.read(wave);p=p.astype(np.float32)
  active=np.flatnonzero(np.abs(p)>.015*float(np.max(np.abs(p))))
  if len(active)<2400:raise RuntimeError('EMPTY_OR_TOO_SHORT_DIGIT')
  p=p[max(0,int(active[0])-960):min(len(p),int(active[-1])+961)]
  original_rms=rms(p);p*=10**(-24/20)/original_rms
  if np.max(np.abs(p))>=.8:raise RuntimeError('EXCESSIVE_CREST_FACTOR')
  file=OUT/f'{digit}.wav';wavfile.write(file,rate,p);pcm.append(p)
  entries.append(dict(digit=digit,text=text,url=f'/audio/hearing-bank/{digit}.wav',sha256=hashlib.sha256(file.read_bytes()).hexdigest(),duration=len(p)/rate,rms=rms(p),peak=float(np.max(np.abs(p))),originalRMS=original_rms,clippedSamples=int(np.sum(np.abs(p)>=1))))
  print(f'digit {digit}: duration={len(p)/rate:.3f} RMS={rms(p):.5f}',flush=True)
 # One deterministic long-term speech-spectrum noise asset (no test synthesis).
 nfft=4096;spectra=[]
 for p in pcm:
  padded=np.pad(p,(0,nfft))
  for at in range(0,len(p),nfft//2):spectra.append(np.abs(np.fft.rfft(padded[at:at+nfft]*np.hanning(nfft)))**2)
 psd=gaussian_filter1d(np.mean(spectra,axis=0),2);psd[0]=0
 rng=np.random.default_rng(8102026);blocks=[]
 for _ in range(240):
  spectrum=np.sqrt(psd)*np.exp(1j*rng.uniform(0,2*np.pi,len(psd)))
  blocks.append(np.fft.irfft(spectrum,nfft))
 noise=np.concatenate(blocks).astype(np.float32);noise*=.0630957/rms(noise)
 path=OUT/'speech-shaped-noise.wav';wavfile.write(path,48000,noise)
 manifest=dict(version='ahmet-digits-20261008-v1',voice='tr-TR-AhmetNeural',rate='-10%',pitch='-10Hz',edgeTTSVersion=edge_tts.__version__,digits=entries,noise=dict(url='/audio/hearing-bank/speech-shaped-noise.wav',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),duration=len(noise)/48000,rms=rms(noise),peak=float(np.max(np.abs(noise)))),auditoryAcceptance='pending',clinicalValidation=False,meaning='experimental TTS bank, not clinical Turkish DIN',rmsWindow='whole trimmed digit with 20ms padding')
 (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
if __name__=='__main__':asyncio.run(main())
