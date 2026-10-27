"""Synthetic WAV/model/config fixtures only; never real inference or voice acceptance."""
import asyncio
import hashlib
import io
import json
from pathlib import Path
import sys
import wave
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/core-api'))
import main
import mental_neural_tts as neural


def wav_bytes(frames=2400):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x10\x00'*frames)
    return out.getvalue()

@pytest.fixture
def configuration(tmp_path):
    def item(name,data):
        p=tmp_path/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
        return {'path':name,'sha256':hashlib.sha256(data).hexdigest()}
    files={name:item('model/'+name,b'SYNTHETIC WEIGHT FIXTURE') for name in neural.REQUIRED_FILES}
    license_item=item('MODEL-LICENSE',b'MIT License\nResemble AI\nSYNTHETIC TEST EVIDENCE, NOT ACTUAL MODEL RIGHTS')
    model={'repository':neural.MODEL_REPO,'file':neural.MODEL_FILE,'sourceRevision':neural.SOURCE_REVISION,'revision':'0'*40,'license':'MIT','licenseURL':f'https://huggingface.co/{neural.MODEL_REPO}/blob/'+('0'*40)+'/LICENSE','licenseEvidence':license_item,'directory':'model','files':files}
    path=tmp_path/'config.json';config={'model':model,'conditioning':'official-default'};path.write_text(json.dumps(config));return path,config

@pytest.mark.parametrize('language',['tr','en','de'])
def test_verified_fixture_routing_and_tamper_rejection(configuration,language):
    path,config=configuration
    loaded=neural.load_configuration(path,language)
    assert loaded[2] is None and loaded[3]=={'id':'official-default','language':language}
    assert 'profiles' not in config
    (path.parent/'model/conds.pt').write_bytes(b'tampered default')
    with pytest.raises(ValueError,match='HASH_MISMATCH'):neural.load_configuration(path,language)

@pytest.mark.parametrize('fault',['weight','version','conditioningMode','conditioningMissing','tokenizer','conditioningHash'])
def test_unverified_resources_never_load(configuration,fault):
    path,c=configuration
    if fault=='weight':(path.parent/'model'/neural.MODEL_FILE).write_bytes(b'tampered')
    if fault=='version':c['model']['file']='t3_mtl23ls_v2.safetensors'
    if fault=='conditioningMode':c['conditioning']='external-reference'
    if fault=='conditioningMissing':(path.parent/'model/conds.pt').unlink()
    if fault=='tokenizer':(path.parent/'model/grapheme_mtl_merged_expanded_v1.json').write_bytes(b'tampered')
    if fault=='conditioningHash':c['model']['files']['conds.pt']['sha256']='0'*64
    path.write_text(json.dumps(c))
    with pytest.raises((ValueError,OSError)):neural.load_configuration(path,'en')


@pytest.mark.parametrize('fault',[None,'repository','license','url','code-license-only'])
def test_explicit_repository_metadata_license_evidence(configuration,fault):
    path,c=configuration
    text='# ResembleAI/chatterbox\n\n## Metadata\n- **License:** mit\n'
    if fault=='repository':text=text.replace('ResembleAI/chatterbox','another/model')
    if fault=='license':text=text.replace('mit','other')
    if fault=='code-license-only':text='MIT License\nResemble AI\nSource code only'
    evidence=path.parent/'MODEL-LICENSE';evidence.write_text(text)
    c['model']['licenseEvidence']['sha256']=hashlib.sha256(evidence.read_bytes()).hexdigest()
    c['model']['licenseEvidenceKind']='hf-repository-metadata'
    c['model']['licenseURL']='https://huggingface.co/'+neural.MODEL_REPO
    if fault=='url':c['model']['licenseURL']='https://another.example/model'
    path.write_text(json.dumps(c))
    if fault:
        with pytest.raises(ValueError):neural.load_configuration(path,'en')
    else:assert neural.load_configuration(path,'en')[2] is None


@pytest.mark.parametrize('fault',[None,'tamper','extra','missing','version','revision','outside'])
def test_actual_installed_source_fingerprints_accept_offline_install_and_reject_changes(monkeypatch,tmp_path,fault):
    root=tmp_path/'site';package=root/'chatterbox';package.mkdir(parents=True)
    f=package/'example.py';f.write_text('# explicit source-verification fixture\n')
    manifest={'sourceRevision':neural.SOURCE_REVISION,'packageVersion':'0.1.7',
              'files':{'chatterbox/example.py':hashlib.sha256(f.read_bytes()).hexdigest()}}
    path=tmp_path/'source.json';monkeypatch.setattr(neural,'SOURCE_MANIFEST',path)
    if fault=='revision':manifest['sourceRevision']='0'*40
    path.write_text(json.dumps(manifest))
    if fault=='tamper':f.write_text('# changed\n')
    if fault=='extra':(package/'extra.py').write_text('# unexpected executable module\n')
    if fault=='missing':f.unlink()
    if fault=='outside':
        f.unlink();outside=tmp_path/'outside.py';outside.write_text('# explicit source-verification fixture\n');f.symlink_to(outside)
    class Installed:
        version='0.1.7' if fault!='version' else '0.1.6'
        def locate_file(self,name):return root/name
    if fault:
        with pytest.raises((OSError,ValueError)):neural.verify_runtime_source(Installed())
    else:assert neural.verify_runtime_source(Installed())['filesVerified']==1

@pytest.mark.parametrize('language',['tr','en','de'])
def test_authenticated_actual_api_transports_fixture_wav_without_rewriting_text(monkeypatch,language):
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','x'*40)
    monkeypatch.setitem(main.vehicle_state,'driverAuthenticated',True);monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False);monkeypatch.setitem(main.vehicle_state,'vehicleParked',True)
    calls=[]
    async def generate(text,lang,permitted,disconnected):
        assert permitted();calls.append((text,lang));return wav_bytes()
    monkeypatch.setattr(neural,'generate',generate)
    with TestClient(main.app) as client:
        kwargs={'json':{'text':'Nonpersonal dynamic 1287 Straße İ','language':language,'speechConsent':True}}
        assert client.post('/api/mental/neural-speech?language='+language,**kwargs).status_code==401
        r=client.post('/api/mental/neural-speech?language='+language,headers={'Authorization':'Bearer '+'x'*40},**kwargs)
    assert r.status_code==200 and r.content==wav_bytes();assert r.headers['x-tts-locale']==main.LANGUAGES[language]
    assert r.headers['cache-control']=='no-store';assert len(calls)==1 and calls[0]==(kwargs['json']['text'],language)

@pytest.mark.parametrize('fault,status',[('consent',403),('mismatch',422),('moving',409),('unknownPark',409),('driver',409),('unconfigured',503)])
def test_api_rejects_before_inference(monkeypatch,fault,status):
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','x'*40);monkeypatch.delenv('ATTUNE_MENTAL_TTS_CONFIG',raising=False)
    for key,value in [('driverAuthenticated',True),('vehicleMoving',False),('vehicleParked',True)]:monkeypatch.setitem(main.vehicle_state,key,value)
    if fault=='moving':monkeypatch.setitem(main.vehicle_state,'vehicleMoving',True)
    if fault=='unknownPark':monkeypatch.setitem(main.vehicle_state,'vehicleParked',None)
    if fault=='driver':monkeypatch.setitem(main.vehicle_state,'driverAuthenticated',False)
    payload={'text':'Synthetic nonpersonal','language':'de' if fault=='mismatch' else 'en','speechConsent':fault!='consent'}
    with TestClient(main.app) as client:r=client.post('/api/mental/neural-speech?language=en',json=payload,headers={'Authorization':'Bearer '+'x'*40})
    assert r.status_code==status

@pytest.mark.parametrize('failure',['motion','disconnect','cancel','badAudio','success'])
def test_inference_process_cleanup_and_stale_output(monkeypatch,tmp_path,failure):
    config=tmp_path/'present.json';config.write_text('{}');monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG',str(config));monkeypatch.setenv('OPENAI_API_KEY','must-not-reach-worker');monkeypatch.setenv('ATTUNE_MENTAL_TTS_TOKEN','must-not-reach-worker')
    async def scenario():
        class Process:
            returncode=None;killed=False
            async def communicate(self,payload):
                assert json.loads(payload)['text']=='Nonpersonal dynamic İı'
                if failure in ('success','badAudio'):
                    self.returncode=0;return (wav_bytes() if failure=='success' else b'not WAV'),b''
                await asyncio.Event().wait()
            def kill(self):self.killed=True;self.returncode=-9
            async def wait(self):return self.returncode
        process=Process();checks=0
        async def spawn(*args,**kwargs):
            assert kwargs['env']['HF_HUB_OFFLINE']=='1';assert 'OPENAI_API_KEY' not in kwargs['env'];assert 'ATTUNE_MENTAL_TTS_TOKEN' not in kwargs['env'];return process
        monkeypatch.setattr(neural.asyncio,'create_subprocess_exec',spawn)
        def permitted():
            nonlocal checks
            checks+=1;return failure!='motion' or checks<3
        async def disconnected():return failure=='disconnect'
        task=asyncio.create_task(neural.generate('Nonpersonal dynamic İı','en',permitted,disconnected))
        if failure=='cancel':await asyncio.sleep(.01);task.cancel()
        if failure=='success':assert await task==wav_bytes()
        else:
            with pytest.raises((HTTPException,asyncio.CancelledError)):await task
        if failure in ('motion','disconnect','cancel'):assert process.killed
        assert neural._busy is False
    asyncio.run(scenario())


@pytest.mark.parametrize('failure',['disconnect','receive-error','handler-cancel'])
def test_request_observer_kills_actual_child_and_releases_slot(monkeypatch,tmp_path,failure):
    """Real process, labelled non-ML sleeper; ASGI event queue, no model weights."""
    path=tmp_path/'config.json';path.write_text('{}')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG',str(path))
    real_spawn=asyncio.create_subprocess_exec
    async def scenario():
        spawned=asyncio.Event();events=asyncio.Queue();process=None
        async def spawn(*args,**kwargs):
            nonlocal process
            process=await real_spawn(sys.executable,'-c','import sys,time;sys.stdin.buffer.read();time.sleep(30)',**kwargs)
            spawned.set();return process
        monkeypatch.setattr(neural.asyncio,'create_subprocess_exec',spawn)
        class Request:
            async def receive(self):
                event=await events.get()
                if isinstance(event,Exception):raise event
                return event
            async def is_disconnected(self):
                raise AssertionError('Pre-cancelled polling must not be used')
        task=asyncio.create_task(neural.generate_for_request('Nonpersonal process fixture','en',lambda:True,Request()))
        await asyncio.wait_for(spawned.wait(),2)
        if failure=='handler-cancel':task.cancel()
        else:await events.put(OSError('fixture closed connection') if failure=='receive-error' else {'type':'http.disconnect'})
        with pytest.raises((HTTPException,asyncio.CancelledError)):
            await asyncio.wait_for(task,2)
        assert process.returncode is not None and neural._busy is False
    asyncio.run(scenario())


@pytest.mark.parametrize('terminal', ['success-after-90', 'deadline', 'disconnect', 'motion'])
def test_extended_budget_still_kills_reaps_and_redacts(monkeypatch, tmp_path, caplog, terminal):
    """Virtual elapsed time plus a real non-ML child; no neural acceptance claim."""
    path = tmp_path / 'config.json'; path.write_text('{}')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG', str(path))
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_DIAGNOSTICS', '1')
    clock = [0]
    monkeypatch.setattr(neural, 'monotonic', lambda: clock[0])
    real_spawn = asyncio.create_subprocess_exec
    async def scenario():
        process = None
        progress = None
        checks = 0
        async def spawn(*args, **kwargs):
            nonlocal process, progress
            progress = Path(kwargs['env']['ATTUNE_MENTAL_TTS_PROGRESS'])
            progress.write_text(json.dumps([{'phase': 'inference', 'elapsedSeconds': 15,
                'cpuSeconds': 12, 'peakRSSKiB': 7000000, 'private': 'NEVER_LOG_USER_TEXT'}]))
            if terminal == 'success-after-90':
                # An explicit synthetic WAV, never a model-generated recording.
                code = 'import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(' + repr(wav_bytes()) + ')'
            else:
                code = 'import sys,time;sys.stdin.buffer.read();time.sleep(30)'
            process = await real_spawn(sys.executable, '-c', code, **kwargs)
            return process
        monkeypatch.setattr(neural.asyncio, 'create_subprocess_exec', spawn)
        def permitted():
            nonlocal checks
            checks += 1
            return terminal != 'motion' or checks < 4
        async def disconnected():
            clock[0] = 120 if terminal == 'success-after-90' else clock[0] + 61
            return terminal == 'disconnect' and clock[0] >= 122
        with caplog.at_level('INFO', logger='uvicorn.error'):
            if terminal == 'success-after-90':
                assert await neural.generate('NEVER_LOG_USER_TEXT', 'en', permitted, disconnected) == wav_bytes()
            else:
                with pytest.raises(HTTPException) as caught:
                    await neural.generate('NEVER_LOG_USER_TEXT', 'en', permitted, disconnected)
                assert caught.value.status_code == {'deadline': 504, 'disconnect': 499, 'motion': 409}[terminal]
                if terminal == 'deadline':
                    assert caught.value.detail == 'NEURAL_TTS_DEADLINE'
                    assert clock[0] >= neural.LIMITS['workerSeconds']
            assert process.returncode is not None
            assert not progress.parent.exists()
            assert neural._busy is False
        assert 'Neural worker timing' in caplog.text
        assert 'inference' in caplog.text
        for private in ('NEVER_LOG_USER_TEXT', str(path), str(progress)):
            assert private not in caplog.text
    asyncio.run(scenario())


@pytest.mark.parametrize('row', [None, {}, {'phase': 'PRIVATE_TEXT'},
    {'phase': 'inference', 'elapsedSeconds': float('nan'), 'cpuSeconds': 0, 'peakRSSKiB': 0},
    {'phase': 'inference', 'elapsedSeconds': 0, 'cpuSeconds': -1, 'peakRSSKiB': 0}])
def test_invalid_timing_data_never_enters_logs(tmp_path, row):
    path = tmp_path / 'progress.json'; path.write_text(json.dumps([row]))
    assert neural.worker_progress(path) == []


@pytest.mark.parametrize('fault', [None, 'hash', 'profileHash', 'outside', 'symlink', 'rate', 'short', 'truncated', 'missing'])
@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
def test_reference_profile_validates_bytes_format_and_containment(configuration, monkeypatch, tmp_path, fault, language):
    path, config = configuration
    ref = tmp_path / 'reference.wav'
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000 if fault == 'rate' else 22050)
        w.writeframes(b'\x10\x00' * (2205 if fault == 'short' else 22050 * 6))
    ref.write_bytes(out.getvalue()[:-200] if fault == 'truncated' else out.getvalue())
    fingerprint = hashlib.sha256(ref.read_bytes()).hexdigest()
    profile = {'id': 'female-calm-v1', 'referenceSha256': fingerprint,
               'generation': {'exaggeration': .35, 'cfg_weight': 0., 'temperature': .8}}
    if fault == 'profileHash': profile['referenceSha256'] = '0' * 64
    registry = tmp_path / 'profile.json'; registry.write_text(json.dumps(profile))
    monkeypatch.setattr(neural, 'VOICE_PROFILE', registry)
    config.update(conditioning='female-calm-v1', referenceAudio={'path': 'reference.wav', 'sha256': fingerprint})
    if fault == 'hash': ref.write_bytes(b'changed')
    if fault in ('outside', 'symlink'):
        outside = tmp_path.parent / (tmp_path.name + '-outside.wav'); outside.write_bytes(ref.read_bytes())
        if fault == 'outside': config['referenceAudio']['path'] = str(outside)
        else: ref.unlink(); ref.symlink_to(outside)
    if fault == 'missing': ref.unlink()
    path.write_text(json.dumps(config))
    if fault:
        with pytest.raises((ValueError, OSError, EOFError)): neural.load_configuration(path, language)
    else:
        loaded = neural.load_configuration(path, language)
        assert loaded[2] == ref and loaded[3]['id'] == 'female-calm-v1'
        assert loaded[3]['generation'] == profile['generation']
        # Client-style configuration cannot silently override the pinned recipe.
        config['generation'] = {'cfg_weight': .9}; path.write_text(json.dumps(config))
        assert neural.load_configuration(path, language)[3]['generation'] == profile['generation']


@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
@pytest.mark.parametrize('fault', [None, 'approval', 'entryApproval', 'profile', 'reference', 'settings'])
def test_dynamic_closing_requires_exact_reviewed_profile_and_explicit_approval(monkeypatch, tmp_path, language, fault):
    import mental_audio_identity as identity
    from fastapi import HTTPException
    target = tmp_path / 'apps/vehicle-app/public/audio/mental/v1'
    target.mkdir(parents=True)
    reference = tmp_path / 'fixture.wav'; reference.write_bytes(b'EXPLICIT NON-NEURAL TEST FIXTURE')
    fingerprint = hashlib.sha256(reference.read_bytes()).hexdigest()
    generation = {'exaggeration': .35, 'cfg_weight': 0., 'temperature': .8}
    manifest = {'speakerProfile': 'female-calm-v1', 'conditioningSha256': fingerprint,
                'generation': generation, 'sampleApproval': {'ownerApprovedAt': 'SYNTHETIC TEST APPROVAL ONLY'},
                'entries': [{'approvalStatus': 'approved'} for _ in range(9)]}
    if fault == 'approval': manifest['sampleApproval']['ownerApprovedAt'] = None
    if fault == 'entryApproval': manifest['entries'][0]['approvalStatus'] = 'synthesized-awaiting-listening-review'
    if fault == 'profile': manifest['speakerProfile'] = 'official-default'
    if fault == 'reference': manifest['conditioningSha256'] = '0' * 64
    if fault == 'settings': manifest['generation'] = {'cfg_weight': .9}
    (target / 'female-calm-v1-manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(identity, 'ROOT', tmp_path)
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG', 'explicit-fixture')
    monkeypatch.setattr(identity, 'load_configuration', lambda *a: ({}, tmp_path, reference,
        {'id': 'female-calm-v1', 'generation': generation}))
    if fault:
        with pytest.raises(HTTPException) as caught: identity.verify_speaker(language, 'female-calm-v1')
        assert caught.value.status_code == 503
    else: identity.verify_speaker(language, 'female-calm-v1')
    # A request naming the old speaker can never consume the new conditioning.
    with pytest.raises(HTTPException): identity.verify_speaker(language, 'official-default')


def test_omitting_profile_cannot_activate_unapproved_female_voice(monkeypatch, tmp_path):
    import mental_audio_identity as identity
    config = tmp_path / 'config.json'; config.write_text('{"conditioning":"female-calm-v1"}')
    monkeypatch.setenv('ATTUNE_MENTAL_TTS_CONFIG', str(config))
    calls = []
    def deny(language, profile):
        calls.append((language, profile)); raise HTTPException(503, 'STRUCTURED_SPEAKER_UNAVAILABLE')
    async def never(*args, **kwargs):
        raise AssertionError('Unapproved female voice must not launch a process')
    monkeypatch.setattr(identity, 'verify_speaker', deny)
    monkeypatch.setattr(neural.asyncio, 'create_subprocess_exec', never)
    async def disconnected(): return False
    with pytest.raises(HTTPException):
        asyncio.run(neural.generate('Explicit nonpersonal closing fixture', 'de', lambda: True, disconnected))
    assert calls == [('de', 'female-calm-v1')] and not neural._busy
