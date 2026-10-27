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
