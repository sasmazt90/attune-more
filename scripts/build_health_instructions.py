"""Approved general instructions only; exact existing Ahmet, cached once."""
import asyncio,hashlib,json,subprocess
from pathlib import Path
import edge_tts,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'apps/vehicle-app/public/audio/hearing-bank'
RAW=ROOT/'audit-results/combined-health-20261008/hearing-bank'
TEXTS={
 'dental-prepare':'Diş taraması için ağzınızı rahatça açın. Dişleriniz görünür olsun. Ağzınıza cisim sokmayın. Sağ ve sol pozları izleyin. Son çekimde dişlerinizi doğal, rahat kapanışta tutun.',
 'hearing-prepare':'Sessiz ortamda stereo kulaklık kullanın. Cihaz sesini düşük ve rahat bir seviyede tutun; test boyunca değiştirmeyin. Önce sol ve sağ kanalı doğrulayın. Saf ses duyduğunuzda Duydum düğmesine veya boşluk tuşuna basın. Gürültüde sayı testinde duyduğunuz üç sayıyı sırayla girin. Ses rahatsız ederse Durdur düğmesine basın.'}
async def main():
 OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
 entries=[]
 for code,text in TEXTS.items():
  mp3=RAW/f'{code}.mp3';file=OUT/f'{code}.wav'
  if not mp3.exists():await edge_tts.Communicate(text,'tr-TR-AhmetNeural',rate='-10%',pitch='-10Hz').save(str(mp3))
  subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-i',str(mp3),'-ac','1','-ar','48000','-c:a','pcm_s16le',str(file)],check=True)
  entries.append(dict(code=code,text=text,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),voice='tr-TR-AhmetNeural',rate='-10%',pitch='-10Hz',auditoryAcceptance='pending'))
 (OUT/'instructions.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),'utf8')
 print('fixed instruction assets ready',flush=True)
if __name__=='__main__':asyncio.run(main())
