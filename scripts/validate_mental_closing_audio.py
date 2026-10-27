#!/usr/bin/env python3
"""Exercise the real authenticated closing-speech endpoint with synthetic facts.

Explicit --generate performs local neural inference. Run after catalog workers
exit. No analysis provider, private transcript, persistent token or paid API is
used. Existing proof WAVs are never replaced. ASR/encoder review is separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/core-api'))
from validate_mental_audio import inspect_wave, atomic_json, fingerprint

TEXTS={
    'tr':'İş baskısını ve uykunuzu konuştuk. Kısa yürüyüşlerin size iyi geldiğini söylediniz. Kendinize zaman ayırabilirsiniz.',
    'en':'We discussed work pressure and sleep. You said short walks help. You can give yourself time.',
    'de':'Wir haben über Arbeitsdruck und Schlaf gesprochen. Kurze Spaziergänge helfen Ihnen. Sie dürfen sich Zeit nehmen.',
}


def generate(config,python,output):
    from fastapi.testclient import TestClient
    import main
    from mental_audio_identity import verify_speaker
    from mental_neural_tts import load_configuration
    output.mkdir(parents=True,exist_ok=True)
    report_path=output/'verification.json'
    report=json.loads(report_path.read_text()) if report_path.exists() else {
        'schema':'mental-real-closing-validation-v1','profile':'female-calm-v1',
        'facts':'Synthetic nonpersonal scenario: work pressure, sleep and helpful short walks.',
        'endpoint':'/api/mental/neural-speech','inference':'real-pinned-official-Chatterbox-V3',
        'seedPolicy':'live-endpoint-upstream-default','privateUserTranscripts':False,
        'limitations':['Matching conditioning/settings verifies the selected configuration, not independent biometric identity.',
            'Pronunciation and descriptive speaker-encoder results are recorded separately.'], 'recordings':[]}
    os.environ['ATTUNE_MENTAL_TTS_FEMALE_CONFIG']=str(config.resolve())
    # Preserve the venv launcher path: resolving its symlink loses pyvenv.cfg.
    os.environ['ATTUNE_MENTAL_TTS_PYTHON']=str(python.absolute())
    os.environ['ATTUNE_MENTAL_TTS_TOKEN']=secrets.token_urlsafe(40)
    os.environ['ATTUNE_LOAD_LOCAL_ENV']='0'
    main.vehicle_state.update(driverAuthenticated=True,vehicleMoving=False,vehicleParked=True)
    client=TestClient(main.app)
    for language,text in TEXTS.items():
        path=output/f'{language}-closing.wav'
        old=next((r for r in report['recordings'] if r['language']==language),None)
        if old:
            if old['text']!=text or fingerprint(path)!=old['sha256']:raise ValueError('EXISTING_PROOF_MISMATCH_NO_OVERWRITE')
            continue
        if path.exists():raise ValueError('UNRECORDED_PROOF_NO_OVERWRITE')
        verify_speaker(language,'female-calm-v1')
        configuration,_,reference,profile=load_configuration(config,language)
        started=perf_counter()
        response=client.post('/api/mental/neural-speech?language='+language,
            headers={'Authorization':'Bearer '+os.environ['ATTUNE_MENTAL_TTS_TOKEN']},
            json={'text':text,'language':language,'speechConsent':True,'speakerProfile':'female-calm-v1'})
        if response.status_code!=200:raise ValueError(f'REAL_CLOSING_ENDPOINT_FAILED_{language}_{response.status_code}: '+response.text[:200])
        expected={'x-tts-source':'chatterbox-multilingual-v3','x-tts-speaker-profile':'female-calm-v1',
                  'x-tts-locale':{'tr':'tr-TR','en':'en-US','de':'de-DE'}[language],'cache-control':'no-store'}
        if any(response.headers.get(k)!=v for k,v in expected.items()):raise ValueError('CLOSING_RESPONSE_CONTRACT_MISMATCH')
        with path.open('xb') as stream:stream.write(response.content)
        metrics,issues=inspect_wave(path)
        row={'language':language,'text':text,'file':path.name,'sha256':fingerprint(path),
             'textSHA256':hashlib.sha256(text.encode()).hexdigest(),'metrics':metrics,'issues':issues,
             'elapsedSeconds':round(perf_counter()-started,3),'responseHeaders':expected,
             'conditioningSHA256':fingerprint(reference),'generation':profile['generation'],
             'modelRevision':configuration['model']['revision'],'sourceRevision':configuration['model']['sourceRevision']}
        report['recordings'].append(row);atomic_json(report_path,report)
        print(json.dumps({'language':language,'status':'real-endpoint-generated','durationMs':metrics['durationMs'],'issues':issues}),flush=True)
    return report


def screen(output,asr_root):
    from validate_mental_audio import Recognizer, pronunciation
    report_path=output/'verification.json';report=json.loads(report_path.read_text())
    if len(report['recordings'])!=3:raise ValueError('ALL_REAL_CLOSING_RECORDINGS_REQUIRED')
    for provenance,key in [('provenance.json','pronunciationScreen'),('provenance-large-v3.json','secondaryPronunciationScreen')]:
        recognizer=Recognizer(asr_root,provenance,threads=2)
        report[key+'Verifier']=recognizer.provenance
        for row in report['recordings']:
            path=output/row['file']
            if fingerprint(path)!=row['sha256']:raise ValueError('CLOSING_PROOF_HASH_CHANGED')
            row[key]=pronunciation(row['text'],recognizer.transcribe(path,row['language']),row['language'])
            atomic_json(report_path,report)
        del recognizer
        import gc
        gc.collect()
    report['configurationBindingVerified']=all(row['responseHeaders']['x-tts-speaker-profile']=='female-calm-v1' for row in report['recordings'])
    report['pronunciationScreenPassed']=all(row['secondaryPronunciationScreen']['status']!='review-required' for row in report['recordings'])
    atomic_json(report_path,report)
    print(json.dumps({k:report[k] for k in ('configurationBindingVerified','pronunciationScreenPassed')}))


def encoder_diagnostics(config,output):
    """Descriptive comparison with the pinned generator's encoder; no threshold."""
    from mental_neural_tts import load_configuration,verify_runtime_source
    _,directory,reference,profile=load_configuration(config,'en');source=verify_runtime_source()
    import socket
    def offline(*a,**kw):raise OSError('CLOSING_REVIEW_NETWORK_DISABLED')
    socket.socket.connect=socket.socket.connect_ex=socket.socket.sendto=offline
    import librosa
    import numpy as np
    import torch
    from chatterbox.models.voice_encoder import VoiceEncoder
    torch.set_num_threads(2);encoder=VoiceEncoder()
    encoder.load_state_dict(torch.load(directory/'ve.pt',map_location='cpu',weights_only=True));encoder.eval()
    def embed(path):
        waveform,_=librosa.load(path,sr=16000)
        vector=encoder.embeds_from_wavs([waveform],sample_rate=16000)[0]
        return vector/np.linalg.norm(vector)
    ref=embed(reference);manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json').read_text())
    report_path=output/'verification.json';report=json.loads(report_path.read_text());vectors={}
    for row in report['recordings']:
        path=output/row['file']
        if fingerprint(path)!=row['sha256']:raise ValueError('CLOSING_PROOF_HASH_CHANGED')
        vector=embed(path);vectors[row['language']]=vector;comparisons=[]
        for entry in manifest['entries']:
            if entry['language']!=row['language'] or entry['variantId'] not in ('B01-V01','B02-V01'):continue
            sample=ROOT/'apps/vehicle-app/public'/entry['audioPath'].lstrip('/')
            if fingerprint(sample)!=entry['sha256']:raise ValueError('APPROVED_SAMPLE_HASH_CHANGED')
            comparisons.append({'assetId':entry['assetId'],'cosine':round(float(vector@embed(sample)),6)})
        row['descriptiveEncoderComparison']={'referenceCosine':round(float(vector@ref),6),'approvedQuestionCosines':comparisons}
    report['encoderDiagnostics']={'encoderSHA256':fingerprint(directory/'ve.pt'),'source':source,
        'crossLanguageClosingCosines':[{'left':a,'right':b,'cosine':round(float(vectors[a]@vectors[b]),6)} for a,b in [('tr','en'),('tr','de'),('en','de')]],
        'interpretation':'Descriptive only: generator-owned encoder, no calibrated identity threshold or independent biometric claim.'}
    atomic_json(report_path,report)
    print(json.dumps({'encoderDiagnostics':'recorded','recordings':len(report['recordings'])}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--python',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    action=p.add_mutually_exclusive_group();action.add_argument('--generate',action='store_true');action.add_argument('--screen',action='store_true');action.add_argument('--encoder-diagnostics',action='store_true')
    p.add_argument('--asr-root',type=Path);args=p.parse_args()
    if args.encoder_diagnostics:encoder_diagnostics(args.config,args.output);return
    if args.screen:
        if not args.asr_root:p.error('--screen requires --asr-root')
        screen(args.output,args.asr_root);return
    if not args.generate:
        print(json.dumps({'mode':'plan','syntheticFacts':True,'texts':TEXTS},ensure_ascii=False));return
    generate(args.config,args.python,args.output)


if __name__=='__main__':main()
