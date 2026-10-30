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
import threading
import base64
import queue
from concurrent.futures import ThreadPoolExecutor
import wave
from array import array
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/core-api'))
from mental_neural_tts import load_configuration, validate_wave, digest, SOURCE_REVISION, LIMITS, worker_progress
from owned_python_process import OwnedProcessTree

MANIFEST=ROOT/'apps/vehicle-app/public/audio/mental/v1/manifest.json'
PUBLIC=ROOT/'apps/vehicle-app/public'


def sample_entries(entries):
    return [e for e in entries if (e['questionNodeId'],e['variantId']) in
            {('A','A-V01'),('B01','B01-V01'),('B02','B02-V01')}]


def recipe(entry,model,conditioning,generation=None,worker_mode=None):
    attempt=entry.get('generationAttempt',0)
    if type(attempt) is not int or not 0<=attempt<=4:raise ValueError('INVALID_GENERATION_ATTEMPT')
    seed_id=entry['assetId'] if not attempt else entry['assetId']+':repair:'+str(attempt)
    value={'text':entry['exactScript'],'language':entry['language'],'speakerProfile':entry['speakerProfile'],
           'conditioningSha256':conditioning,'modelRevision':model['revision'],'sourceRevision':SOURCE_REVISION,
           'seed':int(hashlib.sha256(seed_id.encode()).hexdigest()[:8],16),'contentVersion':entry['contentVersion']}
    if attempt:value['generationAttempt']=attempt
    if generation is not None:value['generation']=generation
    if worker_mode is not None:value['workerMode']=worker_mode
    return value,hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def inspect_pcm(raw):
    validate_wave(raw)
    with wave.open(io.BytesIO(raw),'rb') as wav:
        count=wav.getnframes();rate=wav.getframerate();pcm=array('h',wav.readframes(count))
    if sys.byteorder!='little':pcm.byteswap()
    return {'durationMs':round(count/rate*1000),'sampleRate':rate,'bytes':len(raw),
            'peak':max(abs(s) for s in pcm)/32768,'rms':(sum(s*s for s in pcm)/len(pcm))**.5/32768,
            'clippedSamples':sum(abs(s)>=32760 for s in pcm)}


class ResidentWorker:
    """Finite offline batch IPC with a per-clip deadline and bounded output."""
    def __init__(self, python, config, env):
        self.process=subprocess.Popen([python,str(ROOT/'services/core-api/mental_neural_batch_worker.py'),str(Path(config).resolve())],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env)
        self.owned=OwnedProcessTree(getattr(self.process,'pid',None))
        self.reader=None
    def request(self,payload):
        request={k:payload[k] for k in ('text','language','seed')}
        self.process.stdin.write(json.dumps(request,ensure_ascii=False).encode()+b'\n');self.process.stdin.flush()
        # Windows Python 3.11 cannot select anonymous subprocess pipes.
        # A bounded reader is released by killing/reaping the child on failure.
        response=queue.Queue(maxsize=1)
        def read():
            try:response.put(self.process.stdout.readline(12*1024*1024+1))
            except Exception:response.put(b'')
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        try:raw=response.get(timeout=LIMITS['workerSeconds'])
        except queue.Empty:
            self.close();raise ValueError('BATCH_CLIP_DEADLINE') from None
        self.reader.join()
        if not raw:
            self.close();raise ValueError('BATCH_WORKER_FAILED')
        if len(raw)>12*1024*1024:
            self.close();raise ValueError('BATCH_OUTPUT_TOO_LARGE')
        return base64.b64decode(json.loads(raw)['wav'],validate=True)
    def close(self):
        if self.process.poll() is None:
            if self.owned.root is not None:self.owned.terminate()
            else:self.process.kill()
        self.process.wait()
        if self.reader is not None:self.reader.join(timeout=5)
        self.process.stdin.close();self.process.stdout.close()


def authorize_full_production(manifest):
    if not manifest.get('sampleApproval',{}).get('ownerApprovedAt') or any(e['approvalStatus']!='approved' for e in sample_entries(manifest['entries'])):
        raise ValueError('OWNER_SAMPLE_APPROVAL_REQUIRED')
    if manifest['speakerProfile']=='female-calm-v1':
        authorization=manifest.get('productionAuthorization',{})
        if (not authorization.get('ownerAuthorizedAt') or authorization.get('remainingAssets')!=405
            or authorization.get('speakerProfile')!=manifest['speakerProfile']
            or authorization.get('conditioningSha256')!=manifest['conditioningSha256']
            or authorization.get('generation')!=manifest['generation'] or len(manifest['entries'])!=414):
            raise ValueError('FULL_CATALOG_AUTHORIZATION_REQUIRED')
    elif json.loads((ROOT/'shared/mental/v1/content.json').read_text('utf-8'))['reviewStatus']!='approved':
        raise ValueError('APPROVED_CONTENT_REQUIRED')


def produce(manifest,selected,config,python,manifest_path=MANIFEST,resident_workers=0):
    scripts=json.loads((ROOT/'shared/mental/v1/content.json').read_text('utf-8'))
    expected={(row['language'],row['questionNodeId'],row['variantId']):row for row in scripts['rows']}
    for entry in selected:
        row=expected.get((entry['language'],entry['questionNodeId'],entry['variantId']))
        if not row or any(entry[a]!=row[b] for a,b in [('exactScript','exactText'),('language','language'),('contentVersion','contentVersion')]):
            raise ValueError('CONTENT_MANIFEST_MISMATCH')
        expected_id=f"v1/{entry['language']}/{manifest['speakerProfile']}/{entry['questionNodeId']}/{entry['variantId']}"
        attempt=entry.get('generationAttempt',0)
        if type(attempt) is not int or not 0<=attempt<=4:raise ValueError('INVALID_GENERATION_ATTEMPT')
        expected_path='/audio/mental/'+expected_id+(f'-r{attempt}' if attempt else '')+'.wav'
        if entry['speakerProfile']!=manifest['speakerProfile'] or entry['assetId']!=expected_id or entry['audioPath']!=expected_path:
            raise ValueError('PROFILE_ASSET_MISMATCH')
    # Validate all configuration before consuming inference resources.
    configurations={lang:load_configuration(config,lang) for lang in {e['language'] for e in selected}}
    for _,directory,reference,profile in configurations.values():
        if profile['id']!=manifest['speakerProfile'] or digest(reference or directory/'conds.pt')!=manifest['conditioningSha256']:raise ValueError('SPEAKER_CONDITIONING_MISMATCH')
        if profile.get('generation')!=manifest.get('generation'):raise ValueError('GENERATION_PROFILE_MISMATCH')
    env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2'}
    for key in list(env):
        if any(s in key.upper() for s in ('TOKEN','SECRET','API_KEY','PASSWORD')):env.pop(key,None)
    lock=threading.Lock()
    def generate_entry(entry,resident=None):
        configuration,_,_,profile=configurations[entry['language']]
        mode=entry.get('recipe',{}).get('workerMode') if entry.get('sha256') else 'resident-model-v1' if resident else None
        settings,fingerprint=recipe(entry,configuration['model'],manifest['conditioningSha256'],profile.get('generation'),mode)
        target=(PUBLIC/entry['audioPath'].lstrip('/')).resolve()
        if not target.is_relative_to((PUBLIC/'audio/mental/v1').resolve()):raise ValueError('INVALID_AUDIO_PATH')
        if target.exists():
            if entry.get('recipeSha256')!=fingerprint or entry.get('sha256')!=digest(target):raise ValueError('EXISTING_ASSET_MISMATCH_NO_OVERWRITE')
            return
        if entry['approvalStatus']=='approved':raise ValueError('APPROVED_ASSET_MISSING_NO_REGENERATION')
        payload={'config':str(Path(config).resolve()),'language':entry['language'],'text':entry['exactScript'],'seed':settings['seed']}
        started=perf_counter()
        if resident:
            raw=resident.request(payload);phases=[]
        else:
            with tempfile.TemporaryDirectory(prefix='mental-audio-production-') as diagnostic:
                progress=Path(diagnostic)/'progress.json'
                result=subprocess.run([python,str(ROOT/'services/core-api/mental_neural_worker.py')],input=json.dumps(payload,ensure_ascii=False).encode(),
                                      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={**env,'ATTUNE_MENTAL_TTS_PROGRESS':str(progress)},timeout=LIMITS['workerSeconds'],check=True)
                phases=worker_progress(progress);raw=result.stdout
        telemetry={'elapsedSeconds':round(perf_counter()-started,3),'workerPhases':phases}
        metrics=inspect_pcm(raw)
        target.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation protects previously generated or approved bytes.
        with target.open('xb') as stream:stream.write(raw)
        with lock:
            entry.update({k:metrics[k] for k in ('durationMs','sampleRate','bytes')})
            entry.update(sha256=digest(target),recipeSha256=fingerprint,recipe=settings,qualityMetrics=metrics,productionTelemetry=telemetry,approvalStatus='synthesized-awaiting-validation')
            # Checkpoint each clip while serializing shared manifest updates.
            with tempfile.NamedTemporaryFile('w',dir=manifest_path.parent,delete=False,encoding='utf-8') as stream:
                json.dump(manifest,stream,ensure_ascii=False,indent=2);stream.write('\n');temporary=stream.name
            os.replace(temporary,manifest_path)
        print(json.dumps({'assetId':entry['assetId'],'status':entry['approvalStatus'],'durationMs':metrics['durationMs']}),flush=True)
    if not resident_workers:
        for entry in selected:generate_entry(entry)
        return
    if resident_workers not in (1,2):raise ValueError('BOUNDED_WORKER_COUNT_REQUIRED')
    def partition(index):
        resident=ResidentWorker(python,config,env)
        try:
            for entry in selected[index::resident_workers]:generate_entry(entry,resident)
        finally:resident.close()
    with ThreadPoolExecutor(max_workers=resident_workers) as pool:
        list(pool.map(partition,range(resident_workers)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate',action='store_true',help='Explicitly run the existing offline worker; otherwise plan only.')
    parser.add_argument('--all',action='store_true',help='Requires recorded owner sample approval; outputs still need listening review.')
    parser.add_argument('--profile',choices=('official-default','female-calm-v1'),default='official-default')
    parser.add_argument('--resident-workers',type=int,choices=(0,1,2),default=0,help='Task-only model reuse; never used by the live service.')
    parser.add_argument('--config',default=os.getenv('ATTUNE_MENTAL_TTS_CONFIG',str(ROOT/'tests/automotive/neural-runtime/config.json')))
    parser.add_argument('--python',default=os.getenv('ATTUNE_MENTAL_TTS_PYTHON',sys.executable))
    args=parser.parse_args()
    manifest_path=MANIFEST if args.profile=='official-default' else MANIFEST.with_name('female-calm-v1-manifest.json')
    manifest=json.loads(manifest_path.read_text('utf-8'))
    selected=manifest['entries'] if args.all else sample_entries(manifest['entries'])
    if args.all:
        try:authorize_full_production(manifest)
        except (ValueError,KeyError):parser.error('Explicit sample approval and matching full-catalog production authorization are required.')
    if not args.generate:
        print(json.dumps({'mode':'plan','count':len(selected),'samples':[e['assetId'] for e in selected],
                          'configExists':Path(args.config).is_file(),'auditoryApproval':'pending'},indent=2));return
    try:produce(manifest,selected,args.config,args.python,manifest_path,args.resident_workers)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):
        raise SystemExit('AUDIO_PRODUCTION_UNAVAILABLE_OR_INVALID: verify pinned runtime, model bundle, conditioning, and existing asset hashes. Existing recordings were not replaced.') from None


if __name__=='__main__':main()
