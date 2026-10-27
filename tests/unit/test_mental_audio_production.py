"""Production authorization, immutable audio and offline screening regressions."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import wave
import pytest

ROOT=Path(__file__).resolve().parents[2]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

@pytest.mark.parametrize('fault',[None,'approval','authorization','reference','settings','count'])
def test_full_production_requires_matching_explicit_owner_authorization(fault):
    batch=module('mental_audio_batch')
    manifest=json.loads((ROOT/'apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json').read_text())
    if fault=='approval':manifest['sampleApproval']['ownerApprovedAt']=None
    if fault=='authorization':manifest['productionAuthorization'].pop('ownerAuthorizedAt')
    if fault=='reference':manifest['productionAuthorization']['conditioningSha256']='0'*64
    if fault=='settings':manifest['productionAuthorization']['generation']={'cfg_weight':.9}
    if fault=='count':manifest['entries'].pop()
    if fault:
        with pytest.raises(ValueError):batch.authorize_full_production(manifest)
    else:batch.authorize_full_production(manifest)


def test_owner_approved_recordings_and_original_comparison_remain_immutable():
    review=module('validate_mental_audio')
    for name in ('female-approved-recordings.json','female-comparison-baseline.json'):
        baseline=json.loads((ROOT/'docs/mental-structured'/name).read_text())
        for path,sha in baseline['sha256'].items():assert review.fingerprint(ROOT/path)==sha


def test_pronunciation_screen_retains_formal_address_and_does_not_certify_prosody():
    review=module('validate_mental_audio')
    assert review.pronunciation('Okay.','OK!','en')['status']=='match'
    assert review.pronunciation('Nasıl hissettiniz?','NASIL HİSSETTİNİZ?','tr')['status']=='match'
    assert review.pronunciation('Wie fühlen Sie sich?','Wie fühlen sich?','de')['status']=='review-required'
    assert review.pronunciation('How did you feel?','How did you sleep?','en')['status']=='review-required'


def test_pcm_screen_detects_clipping_silence_and_truncation(tmp_path):
    review=module('validate_mental_audio')
    def fixture(name,pcm):
        out=io.BytesIO()
        with wave.open(out,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm)
        path=tmp_path/name;path.write_bytes(out.getvalue());return path
    silence=fixture('silence.wav',b'\0\0'*2400)
    assert 'silent-or-too-quiet' in review.inspect_wave(silence)[1]
    clipped=fixture('clipped.wav',b'\xff\x7f'*2400)
    assert review.inspect_wave(clipped)[0]['clippedSamples']==2400
    clipped.write_bytes(clipped.read_bytes()[:-100])
    with pytest.raises(ValueError):review.inspect_wave(clipped)


def test_resident_worker_protocol_is_bounded_and_closes_actual_child(monkeypatch,tmp_path):
    batch=module('mental_audio_batch');real_popen=subprocess.Popen
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x10\x00'*2400)
    code='import sys,json,base64\nfor line in sys.stdin:\n r=json.loads(line);assert set(r)=={"language","text","seed"};print(json.dumps({"wav":base64.b64encode('+repr(out.getvalue())+').decode()}),flush=True)\n'
    def spawn(args,**kw):return real_popen([sys.executable,'-c',code],**kw)
    monkeypatch.setattr(batch.subprocess,'Popen',spawn)
    resident=batch.ResidentWorker(sys.executable,tmp_path/'config.json',{})
    try:
        for language in ('tr','en','de'):
            raw=resident.request({'language':language,'text':'Explicit nonpersonal fixture','seed':42,'config':'never-transmitted-in-request'})
            assert raw==out.getvalue()
    finally:resident.close()
    assert resident.process.poll() is not None


def test_backup_restore_verifies_every_file_before_writes_and_never_overwrites(tmp_path):
    restore=module('restore_mental_audio')
    backup=tmp_path/'drive';backup.mkdir();repo=tmp_path/'repo';repo.mkdir()
    data=b'EXPLICIT NONPERSONAL BACKUP FIXTURE';path=backup/'A.wav';path.write_bytes(data)
    import hashlib
    item={'backupPath':'A.wav','repositoryPath':'public/A.wav','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    inventory={'complete':False,'files':[item]}
    with pytest.raises(ValueError,match='COMPLETE_INVENTORY'):restore.restore(inventory,backup,repo,apply=True)
    inventory['complete']=True
    assert restore.restore(inventory,backup,repo,apply=True)['filesVerified']==1
    assert (repo/'public/A.wav').read_bytes()==data
    (repo/'public/A.wav').write_bytes(b'existing different bytes')
    with pytest.raises(ValueError,match='NO_OVERWRITE'):restore.restore(inventory,backup,repo,apply=True)
    assert (repo/'public/A.wav').read_bytes()==b'existing different bytes'
    item['backupPath']='../outside.wav'
    with pytest.raises(ValueError,match='OUTSIDE_ROOT'):restore.restore(inventory,backup,repo)


def test_model_part_restore_checks_all_hashes_before_reassembly(tmp_path):
    restore=module('reassemble_mental_runtime')
    import hashlib
    chunks=[b'NON-MODEL TEST PART ONE',b'NON-MODEL TEST PART TWO'];rows=[]
    for i,data in enumerate(chunks):
        name=f'part-{i}';(tmp_path/name).write_bytes(data)
        rows.append({'index':i,'filename':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    complete=b''.join(chunks)
    manifest={'parts':rows,'part_count':2,'original_zip_bytes':len(complete),'original_zip_sha256':hashlib.sha256(complete).hexdigest()}
    target=tmp_path/'restored.zip';restore.reassemble(manifest,tmp_path,target)
    assert target.read_bytes()==complete
    (tmp_path/'part-0').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='PART_INTEGRITY'):restore.reassemble(manifest,tmp_path,tmp_path/'never-created.zip')
    assert not (tmp_path/'never-created.zip').exists()
