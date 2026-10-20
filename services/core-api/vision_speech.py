"""Bounded Edge streaming with exact profiles and disconnect cleanup.
The vision route accepts fixed instructions only; mental text requires consent.
"""
import asyncio
import unicodedata
import hashlib,json
from pathlib import Path
from time import monotonic
import edge_tts
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from tts_profiles import VISION_TTS_PROFILE, MENTAL_WELLBEING_TTS_PROFILE
from tts_profiles import SpeechProfile
from localization import current_language, LANGUAGES, translate
VOICE=VISION_TTS_PROFILE.voice
PROMPTS={
 'prepare':'Kamera hazırlanıyor. İki gözünüz açık, yüzünüz görüntüde olsun. Bulunduğunuz mesafeyi koruyun.',
 'right':'Sağ gözünüzü test ediyoruz. Sağ gözünüz açık kalsın. Sol gözünüzü kapatın veya örtün. Açık gözünüzle harf alanına bakın.',
 'left':'Sol gözünüzü test ediyoruz. Sol gözünüz açık kalsın. Sağ gözünüzü kapatın veya örtün. Açık gözünüzle harf alanına bakın.',
 'letter':'Harfi söyler misiniz? O harfle başlayan bir kelime de kullanabilirsiniz.',
 'orientation':'Harfin hangi yöne dönük olduğunu söyler misiniz?',
 'reverse':'Baş aşağı mı, aynalı mı?',
 'repeat':'Ekrandaki harfi ve yönünü söyleyin.',
 'first':'Harf alanına bakın. Harfi ve yönünü istediğiniz sırada söyleyin. Yön ile birlikte, gördüğünüz harfle başlayan bir kelime söyleyebilirsiniz. Harf görünüyorsa yönergenin bitmesini beklemeniz gerekmez.',
 'next1':'Şimdi sıradaki harfi söyleyin.',
 'next2':'Lütfen bu harfi aynı şekilde okuyun.',
 'next3':'Yanıtınız kaydedildi. Sıradaki harfe geçiyoruz.',
 'position':'Başlangıç mesafenizi koruyun. Harf alanına bakabilirsiniz.',
 'approach':'Biraz yaklaşın.',
 'recede':'Biraz geriye gidin.',
 'pose':'Başlangıç mesafenizi koruyun. Harf alanına bakabilirsiniz.',
 'framing':'Alın ve çeneniz kadrajda kalacak şekilde yüzünüzü ortalayın.',
 'light':'Yüzünüzü daha iyi aydınlatın.',
 'bright':'Yüzünüzdeki parlamayı azaltın.',
 'blur':'Kamera netliğini ve yüz aydınlatmasını kontrol edin.',
 'motion':'Kısa süre başınızı sabit tutun.',
 'face':'Yüzünüzü kameraya gösterin.',
 'preparing':'Konumunuz doğrulanıyor. Kısa süre sabit durun.',
 'ready':'Konum hazır.',
 'camera':'Kameranın önünde, iyi ışıkta durun.',
 'eye':'Test edilen göz açık, diğer göz kapalı veya örtülü kalmalı.',
 'uncertain':'Göz örtüsünü veya göz açıklığını kontrol edemiyorum.',
 'paused':'Görev duraklatıldı. Devam et diyerek sürdürebilirsiniz.',
 'complete':'Harf tanıma görevi tamamlandı.'
}
class OwnedSpeechResponse(StreamingResponse):
 async def __call__(self,scope,receive,send):
  try:await super().__call__(scope,receive,send)
  finally:await self.provider_iterator.aclose()

_catalogue=(0.,frozenset())
FIXED_BANK=Path(__file__).resolve().parents[2]/'apps/vehicle-app/public/audio/vision-speech'
async def response(code,moving,voice_id=None):
 if code not in PROMPTS:raise HTTPException(status_code=422,detail='FIXED_INSTRUCTION_REQUIRED')
 if moving():raise HTTPException(status_code=409,detail='PARK_REQUIRED')
 if current_language()!='tr' or voice_id:
  profile=await localized_profile(VISION_TTS_PROFILE,voice_id)
  return await speech_response(translate(PROMPTS[code]),profile,moving)
 manifest=FIXED_BANK/'manifest.json'
 if manifest.exists():
  # These are the existing fixed prompts, generated once by the same approved
  # Edge voice. Cache identity is checked against text/profile/actual bytes;
  # a stale or damaged cache cannot silently become another voice or text.
  try:
   entry=json.loads(manifest.read_text('utf8'))['entries'][code]
   assert entry['text']==PROMPTS[code] and entry['file']==code+'.mp3'
   assert (entry['voice'],entry['rate'],entry['pitch'])==(VISION_TTS_PROFILE.voice,VISION_TTS_PROFILE.rate,VISION_TTS_PROFILE.pitch)
   raw=(FIXED_BANK/entry['file']).read_bytes()
   assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
  except (OSError,KeyError,ValueError,TypeError,AssertionError):
   raise HTTPException(status_code=503,detail='FIXED_VISION_SPEECH_UNAVAILABLE') from None
  async def cached():
   for start in range(0,len(raw),16384):
    if moving():return
    yield raw[start:start+16384]
    await asyncio.sleep(0)
  iterator=cached()
  result=OwnedSpeechResponse(iterator,media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-TTS-Voice':VISION_TTS_PROFILE.voice,'X-TTS-Rate':VISION_TTS_PROFILE.rate,'X-TTS-Pitch':VISION_TTS_PROFILE.pitch,'X-TTS-Source':'verified-fixed-cache','X-Content-Type-Options':'nosniff'})
  result.provider_iterator=iterator
  return result
 # An installation without the bank uses the original exact-profile provider
 # path and its explicit failure. There is no alternate voice or silent audio.
 return await speech_response(PROMPTS[code],VISION_TTS_PROFILE,moving)

async def mental_response(text,moving,voice_id=None):
 # Fixed exports do not confer live TTS availability. Read only the owner's
 # explicit provider ID; never infer Katja/Stefan from a desktop voice name.
 bank=Path(__file__).resolve().parents[2]/'apps/vehicle-app/public/audio/user-approved/tr-en-de-20261020-v1/manifest.json'
 try:
  data=json.loads(bank.read_text('utf8'));language=current_language()
  mapping=next(m for m in data['activeGuidanceMappings'] if m['language']==language and m['module']=='Mental Health' and m['eventId']=='guidance:mental-entry')
  recording=next(r for r in data['recordings'] if r['recordingId']==mapping['recordingId'])
  exact=recording['providerVoiceId']
 except (OSError,ValueError,KeyError,StopIteration,TypeError):
  raise HTTPException(status_code=503,detail='APPROVED_MENTAL_VOICE_CONTRACT_UNAVAILABLE') from None
 if moving():raise HTTPException(status_code=409,detail='PARK_REQUIRED')
 if not exact:raise HTTPException(status_code=503,detail='EXACT_FEMALE_DYNAMIC_VOICE_UNVERIFIED')
 if voice_id and voice_id!=exact:raise HTTPException(status_code=422,detail='EXACT_APPROVED_MENTAL_VOICE_REQUIRED')
 # Ada is explicitly en-GB with application locale en-US. speech_response
 # still verifies the exact ID against the real catalogue before synthesis.
 profile=SpeechProfile(exact,MENTAL_WELLBEING_TTS_PROFILE.rate,MENTAL_WELLBEING_TTS_PROFILE.pitch)
 return await speech_response(text,profile,moving)

async def available_voices():
 try:
  voices=await asyncio.wait_for(edge_tts.list_voices(),12)
 except Exception:
  raise HTTPException(status_code=503,detail='VOICE_CATALOGUE_UNAVAILABLE') from None
 locale=LANGUAGES[current_language()]
 return [v for v in voices if v.get('Locale','').casefold()==locale.casefold()]

async def localized_profile(default,voice_id=None):
 voices=await available_voices()
 if voice_id:
  voices=[v for v in voices if v.get('ShortName')==voice_id]
 if not voices:raise HTTPException(status_code=503,detail='SELECTED_LOCALE_VOICE_UNAVAILABLE')
 return SpeechProfile(voices[0]['ShortName'],default.rate,default.pitch)

async def speech_response(text,profile,moving):
 global _catalogue
 iterator=None;stage="catalogue"
 # Normalize once for the whole utterance; transport frames never trigger a
 # second voice request. No hidden language hints, extra text or MP3 joins.
 text=unicodedata.normalize('NFC',text).strip()
 try:
  if monotonic()-_catalogue[0]>300 or not _catalogue[1]:
   voices=await asyncio.wait_for(edge_tts.list_voices(),12)
   _catalogue=(monotonic(),frozenset(v['ShortName'] for v in voices))
  if profile.voice not in _catalogue[1]:raise HTTPException(status_code=503,detail='EXACT_MICROSOFT_VOICE_UNAVAILABLE:'+profile.voice)
  if moving():raise HTTPException(status_code=409,detail='PARK_REQUIRED')
  stage="synthesis";started=monotonic();iterator=edge_tts.Communicate(text,profile.voice,rate=profile.rate,pitch=profile.pitch,connect_timeout=5,receive_timeout=15).stream()
  while True:
   item=await asyncio.wait_for(anext(iterator),18)
   if item['type']=='audio':first=item['data'];break
  if moving():raise HTTPException(status_code=409,detail='PARK_REQUIRED')
 except Exception as error:
  if iterator:await iterator.aclose()
  if isinstance(error,HTTPException):raise
  category={'stage':stage,'type':type(error).__name__,'upstreamStatus':getattr(error,'status',None)}
  import logging
  logging.getLogger('attune.speech').warning('speech_unavailable %s',json.dumps(category))
  raise HTTPException(status_code=503,detail={'code':'MICROSOFT_SPEECH_UNAVAILABLE',**category}) from None
 async def body():
  try:
   if not moving():yield first
   while True:
    try:part=await asyncio.wait_for(anext(iterator),18)
    except StopAsyncIteration:return
    if moving():return
    if part['type']=='audio':yield part['data']
  except Exception as error:
   import logging
   logging.getLogger('attune.speech').warning('speech_stream_failed type=%s status=%s',type(error).__name__,getattr(error,'status',None))
   raise RuntimeError('MICROSOFT_SPEECH_STREAM_FAILED') from None
  finally:await iterator.aclose()
 result=OwnedSpeechResponse(body(),media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-TTS-Voice':profile.voice,'X-TTS-Rate':profile.rate,'X-TTS-Pitch':profile.pitch,'X-Content-Type-Options':'nosniff','Server-Timing':f'tts_first;dur={(monotonic()-started)*1000:.1f}'})
 result.provider_iterator=iterator
 return result
