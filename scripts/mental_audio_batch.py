#!/usr/bin/env python3
"""Offline Chatterbox v3 production. Defaults to planning nine review samples.

Never approves audio or replaces an existing recording. Use the same verified
model configuration as the service, with no API keys or network in inference.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
from array import array
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_neural_tts import load_configuration, validate_wave, digest, SOURCE_REVISION, LIMITS, worker_progress

MANIFEST=ROOT/'apps/vehicle-app/public/audio/mental/v1/manifest.json'
PUBLIC=ROOT/'apps/vehicle-app/public'


def sample_entries(entries):
    return [e for e in entries if (e['questionNodeId'],e['variantId']) in
            {('A','A-V01'),('B01','B01-V01'),('B02','B02-V01')}]


def recipe(entry,model,conditioning):
    value={'text':entry['exactScript'],'language':entry['language'],'speakerProfile':entry['speakerProfile'],
           'conditioningSha256':conditioning,'modelRevision':model['revision'],'sourceRevision':SOURCE_REVISION,
           'seed':int(hashlib.sha256(entry['assetId'].encode()).hexdigest()[:8],16),'contentVersion':entry['contentVersion']}
    return value,hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def inspect_pcm(raw):
    validate_wave(raw)
    with wave.open(io.BytesIO(raw),'rb') as wav:
        count=wav.getnframes();rate=wav.getframerate();pcm=array('h',wav.readframes(count))
    if sys.byteorder!='little':pcm.byteswap()
    return {'durationMs':round(count/rate*1000),'sampleRate':rate,'bytes':len(raw),
            'peak':max(abs(s) for s in pcm)/32768,'rms':(sum(s*s for s in pcm)/len(pcm))**.5/32768,
            'clippedSamples':sum(abs(s)>=32760 for s in pcm)}


def produce(manifest,selected,config,python):
    scripts=json.loads((ROOT/'shared/mental/v1/content.json').read_text('utf-8'))
    expected={row['audioAssetId']:row for row in scripts['rows']}
    for entry in selected:
        row=expected.get(entry['assetId'])
        if not row or any(entry[a]!=row[b] for a,b in [('exactScript','exactText'),('language','language'),('speakerProfile','speakerProfile'),('contentVersion','contentVersion')]):
            raise ValueError('CONTENT_MANIFEST_MISMATCH')
    # Validate all configuration before consuming inference resources.
    configurations={lang:load_configuration(config,lang) for lang in {e['language'] for e in selected}}
    for _,directory,_,_ in configurations.values():
        if digest(directory/'conds.pt')!=manifest['conditioningSha256']:raise ValueError('SPEAKER_CONDITIONING_MISMATCH')
    env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2'}
    for key in list(env):
        if any(s in key.upper() for s in ('TOKEN','SECRET','API_KEY','PASSWORD')):env.pop(key,None)
    for entry in selected:
        configuration,_,_,_=configurations[entry['language']]
        settings,fingerprint=recipe(entry,configuration['model'],manifest['conditioningSha256'])
        target=(PUBLIC/entry['audioPath'].lstrip('/')).resolve()
        if not target.is_relative_to((PUBLIC/'audio/mental/v1').resolve()):raise ValueError('INVALID_AUDIO_PATH')
        if target.exists():
            if entry.get('recipeSha256')!=fingerprint or entry.get('sha256')!=digest(target):raise ValueError('EXISTING_ASSET_MISMATCH_NO_OVERWRITE')
            continue
        if entry['approvalStatus']=='approved':raise ValueError('APPROVED_ASSET_MISSING_NO_REGENERATION')
        payload={'config':str(Path(config).resolve()),'language':entry['language'],'text':entry['exactScript'],'seed':settings['seed']}
        started=perf_counter()
        with tempfile.TemporaryDirectory(prefix='mental-audio-production-') as diagnostic:
            progress=Path(diagnostic)/'progress.json'
            result=subprocess.run([python,str(ROOT/'services/core-api/mental_neural_worker.py')],input=json.dumps(payload,ensure_ascii=False).encode(),
                                  stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={**env,'ATTUNE_MENTAL_TTS_PROGRESS':str(progress)},timeout=LIMITS['workerSeconds'],check=True)
            phases=worker_progress(progress)
        telemetry={'elapsedSeconds':round(perf_counter()-started,3),'workerPhases':phases}
        metrics=inspect_pcm(result.stdout)
        target.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation protects previously generated or approved bytes.
        with target.open('xb') as stream:stream.write(result.stdout)
        entry.update({k:metrics[k] for k in ('durationMs','sampleRate','bytes')})
        entry.update(sha256=digest(target),recipeSha256=fingerprint,recipe=settings,qualityMetrics=metrics,productionTelemetry=telemetry,approvalStatus='synthesized-awaiting-listening-review')
        # Checkpoint after every clip; recoverable without regeneration.
        with tempfile.NamedTemporaryFile('w',dir=MANIFEST.parent,delete=False,encoding='utf-8') as stream:
            json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n');temporary=stream.name
        os.replace(temporary,MANIFEST)
        print(json.dumps({'assetId':entry['assetId'],'status':entry['approvalStatus'],'durationMs':metrics['durationMs']}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate',action='store_true',help='Explicitly run the existing offline worker; otherwise plan only.')
    parser.add_argument('--all',action='store_true',help='Requires recorded owner sample approval; outputs still need listening review.')
    parser.add_argument('--config',default=os.getenv('ATTUNE_MENTAL_TTS_CONFIG',str(ROOT/'tests/automotive/neural-runtime/config.json')))
    parser.add_argument('--python',default=os.getenv('ATTUNE_MENTAL_TTS_PYTHON',sys.executable))
    args=parser.parse_args()
    manifest=json.loads(MANIFEST.read_text('utf-8'))
    selected=manifest['entries'] if args.all else sample_entries(manifest['entries'])
    if args.all and (not manifest.get('sampleApproval',{}).get('ownerApprovedAt') or any(e['approvalStatus']!='approved' for e in sample_entries(manifest['entries']))):
        parser.error('Owner listening approval of representative samples is required before full production.')
    if args.all and json.loads((ROOT/'shared/mental/v1/content.json').read_text('utf-8'))['reviewStatus']!='approved':
        parser.error('Approved multilingual content is required before full production.')
    if not args.generate:
        print(json.dumps({'mode':'plan','count':len(selected),'samples':[e['assetId'] for e in selected],
                          'configExists':Path(args.config).is_file(),'auditoryApproval':'pending'},indent=2));return
    try:produce(manifest,selected,args.config,args.python)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        raise SystemExit('AUDIO_PRODUCTION_UNAVAILABLE_OR_INVALID: verify pinned runtime, model bundle, conditioning, and existing asset hashes; no approval was granted.') from None


if __name__=='__main__':main()
