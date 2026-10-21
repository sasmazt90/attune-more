"""Generate NEW EN/DE assets with free local tools; refuse every existing output.

Run in Cloud with Python 3.11, espeak-ng and ffmpeg. This never generates TR audio.
The output is explicit new synthesis, not an approved recording or clinical bank.
"""
import argparse
import asyncio
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
from local_speech import available_local_voices, mp3_bytes, wave_bytes, command

def sha(data):return hashlib.sha256(data).hexdigest()
def normalized(value):return ' '.join(value.split())

async def generate(stage):
    import numpy as np
    target=ROOT/'apps/vehicle-app/public/audio/localized'
    if target.exists() or stage.exists():raise RuntimeError('REFUSE_TO_OVERWRITE_EXISTING_AUDIO')
    catalog=json.loads((ROOT/'shared/localization/messages.json').read_text())
    by_source={normalized(m['tr']):m for m in catalog.values()}
    guidance=json.loads((ROOT/'apps/vehicle-app/public/audio/guidance/manifest.json').read_text())['entries']
    prompts=json.loads((ROOT/'shared/localization/vision-prompts.json').read_text())
    for language in ('en','de'):
        for text in [e['text'] for e in guidance.values()]+list(prompts.values()):
            row=by_source.get(normalized(text))
            if not row or not row.get(language):raise RuntimeError('TRANSLATED_FIXED_TEXT_REQUIRED: '+text)
    actual=[]
    for language in ('en','de'):actual+=await available_local_voices(language)
    if len(actual)!=4:raise RuntimeError('FOUR_ACTUALLY_SYNTHESIZABLE_LOCALE_GENDER_PROFILES_REQUIRED')
    stage.mkdir(parents=True)
    version='localized-espeak-20261020-v1'
    result={'version':version,'source':'new-local-synthesis','auditoryAcceptance':'pending',
        'engine':subprocess.check_output(['espeak-ng','--version'],text=True).splitlines()[0],
        'encoder':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],
        'originalApprovedAudioModified':False,'voices':{},'hearing':{}}
    def write(path,data):
        file=stage/path;file.parent.mkdir(parents=True,exist_ok=True)
        with file.open('xb') as stream:stream.write(data)
        return {'url':'/audio/localized/'+path.as_posix(),'bytes':len(data),'sha256':sha(data)}
    for voice in actual:
        language=voice['locale'].split('-')[0];gender=voice['gender']
        profile={**voice,'scope':'new translated synthesis; original approved recordings unchanged',
            'speedWordsPerMinute':155,'pitch':50,'guidance':{},'vision':{}}
        for kind,texts in [('guidance',{key:e['text'] for key,e in guidance.items()}),('vision',prompts)]:
            for key,source in texts.items():
                text=by_source[normalized(source)][language]
                raw=await mp3_bytes(text,language,gender)
                path=Path('v1')/language/gender/kind/(key+'.mp3')
                profile[kind][key]={'text':text,'sourceTextSha256':sha(source.encode()),**write(path,raw)}
        result['voices'].setdefault(language,{})[gender]=profile
    words={'en':['zero','one','two','three','four','five','six','seven','eight','nine'],
           'de':['null','eins','zwei','drei','vier','fünf','sechs','sieben','acht','neun']}
    original=json.loads((ROOT/'apps/vehicle-app/public/audio/hearing-bank/manifest.json').read_text())
    for language in ('en','de'):
        bank={'version':version+'-'+language+'-male','locale':language,'voice':'espeak:'+language+':male',
            'source':'new-local-synthesis','auditoryAcceptance':'pending','clinicalValidity':'unverified',
            'gender':'male','engine':result['engine'],'digits':[],'noise':original['noise']}
        for digit,text in enumerate(words[language]):
            raw=await wave_bytes(text,language,'male')
            pcm=await command(['ffmpeg','-v','error','-threads','1','-i','pipe:0','-ar','48000',
                '-ac','1','-f','s16le','pipe:1'],raw)
            values=np.frombuffer(pcm,dtype='<i2').astype(np.float64)/32768
            rms=float(np.sqrt(np.mean(values**2)))
            if rms<=0 or not np.isfinite(values).all():raise RuntimeError('SILENT_SYNTHESIS')
            # Engineering RMS normalization only. The existing mixing/scoring protocol is untouched.
            values*=10**(-24/20)/rms
            if np.max(np.abs(values))>=.98:raise RuntimeError('DIGIT_CLIPPING_RISK')
            encoded=np.rint(values*32767).astype('<i2').tobytes();out=io.BytesIO()
            with wave.open(out,'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(48000);stream.writeframes(encoded)
            path=Path('v1')/language/'hearing'/(str(digit)+'.wav');payload=out.getvalue()
            bank['digits'].append({'digit':digit,'text':text,'duration':len(values)/48000,
                'rms':float(np.sqrt(np.mean((np.frombuffer(encoded,dtype='<i2')/32768)**2))),
                'peak':float(np.max(np.abs(np.frombuffer(encoded,dtype='<i2')/32768))),
                'clippedSamples':0,**write(path,payload)})
        path=Path('v1')/language/'hearing/manifest.json'
        result['hearing'][language]=write(path,(json.dumps(bank,ensure_ascii=False,indent=2)+'\n').encode())
    with (stage/'manifest.json').open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    # Copy only once after all profiles, bytes and translation preconditions succeeded.
    shutil.copytree(stage,target,dirs_exist_ok=False)
    print(json.dumps({'status':'generated-new-assets','files':sum(f.is_file() for f in target.rglob('*')),
        'bytes':sum(f.stat().st_size for f in target.rglob('*') if f.is_file()),'profiles':[v['id'] for v in actual],
        'auditoryAcceptance':'pending','originalTRFilesModified':False},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',type=Path,required=True)
    args=parser.parse_args();asyncio.run(generate(args.stage))
