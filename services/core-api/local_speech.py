"""Optional free, local eSpeak NG synthesis. No shell, network or stored health text."""
import asyncio
import shutil
from time import monotonic
from fastapi import HTTPException
from starlette.responses import StreamingResponse
from localization import current_language, LANGUAGES

_cache = (0.0, [])
BASE_VOICES = {'en':'en-us','de':'de'}

async def command(args, data=None, timeout=15):
    process = await asyncio.create_subprocess_exec(*args, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(data),timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode or not stdout or len(stdout)>8*1024*1024:
        raise RuntimeError('LOCAL_SYNTHESIS_UNAVAILABLE')
    return stdout

async def wave_bytes(text, language, gender):
    if language not in BASE_VOICES or gender not in ('male','female'):
        raise ValueError('UNSUPPORTED_LOCAL_VOICE')
    binary = shutil.which('espeak-ng')
    if not binary:
        raise RuntimeError('ESPEAK_NG_NOT_INSTALLED')
    voice = BASE_VOICES[language]+('+f3' if gender=='female' else '')
    return await command([binary,'--stdout','-v',voice,'-s','155','-p','50'],text.encode('utf-8'))

async def mp3_bytes(text, language, gender):
    encoder=shutil.which('ffmpeg')
    if not encoder:
        raise RuntimeError('FFMPEG_NOT_INSTALLED')
    raw=await wave_bytes(text,language,gender)
    return await command([encoder,'-v','error','-threads','1','-i','pipe:0','-ac','1',
        '-ar','24000','-codec:a','libmp3lame','-b:a','64k','-f','mp3','pipe:1'],raw)

async def available_local_voices(language=None):
    global _cache
    language=language or current_language()
    if language not in BASE_VOICES or not shutil.which('espeak-ng') or not shutil.which('ffmpeg'):
        return []
    if monotonic()-_cache[0]>300 or not _cache[1]:
        found=[]
        try:
            variants=(await command(['espeak-ng','--voices=variant'])).decode('utf8')
            for lang,base in BASE_VOICES.items():
                metadata=(await command(['espeak-ng','--voices='+('en' if lang=='en' else 'de')])).decode('utf8')
                rows=[line.split() for line in metadata.splitlines()[1:] if line.strip()]
                base_row=next((r for r in rows if len(r)>=5 and r[1]==base and r[2].endswith('/M') and r[4].startswith('gmw/')),None)
                if not base_row:continue
                for gender in ('male','female'):
                    if gender=='female' and not any('!v/f3' in line and '/F' in line for line in variants.splitlines()):continue
                    # Metadata alone does not prove an optional voice can synthesize.
                    try:
                        probe=await mp3_bytes('Test.',lang,gender)
                        if len(probe)<300:continue
                    except (RuntimeError,asyncio.TimeoutError,OSError):continue
                    found.append({'id':f'espeak:{lang}:{gender}',
                        'name':f'eSpeak NG {base_row[3]}' + (' / female3' if gender=='female' else ''),
                        'locale':LANGUAGES[lang],'gender':gender,'provider':'local','local':True,
                        'availability':'actual metadata and synthesis probe verified'})
            _cache=(monotonic(),found)
        except (RuntimeError,asyncio.TimeoutError,OSError):
            return []
    return [dict(row) for row in _cache[1] if row['locale']==LANGUAGES[language]]

async def response(text, voice_id, moving):
    language=current_language()
    if moving():raise HTTPException(409,'PARK_REQUIRED')
    choices=await available_local_voices(language)
    chosen=next((v for v in choices if v['id']==voice_id),None)
    if not chosen:raise HTTPException(503,'SELECTED_LOCAL_VOICE_UNAVAILABLE')
    try:
        raw=await mp3_bytes(text,language,chosen['gender'])
    except (RuntimeError,asyncio.TimeoutError,OSError):
        raise HTTPException(503,'LOCAL_SYNTHESIS_UNAVAILABLE') from None
    if moving():raise HTTPException(409,'PARK_REQUIRED')
    async def chunks():
        for at in range(0,len(raw),16384):
            if moving():return
            yield raw[at:at+16384]
            await asyncio.sleep(0)
    return StreamingResponse(chunks(),media_type='audio/mpeg',headers={
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-TTS-Voice':voice_id,
        'X-TTS-Locale':LANGUAGES[language],'X-TTS-Source':'new-local-synthesis'})
