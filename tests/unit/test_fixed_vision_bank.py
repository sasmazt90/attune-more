"""Genuine exact fixed bank, no provider request and no silent substitution."""
import hashlib,json,sys
from pathlib import Path
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/core-api'))
import main,vision_speech

def test_fixed_bank_all_text_profiles_bytes_and_offline_delivery(monkeypatch):
    manifest=json.loads((vision_speech.FIXED_BANK/'manifest.json').read_text('utf8'))
    assert set(manifest['entries'])==set(vision_speech.PROMPTS)
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    monkeypatch.setattr(vision_speech.edge_tts,'Communicate',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Fixed bank dispatched provider')))
    monkeypatch.setattr(vision_speech,'_catalogue',(0.,frozenset()))
    client=TestClient(main.app)
    for code,text in vision_speech.PROMPTS.items():
        row=manifest['entries'][code];raw=(vision_speech.FIXED_BANK/row['file']).read_bytes()
        assert row['text']==text and len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
        assert (row['voice'],row['rate'],row['pitch'])==('tr-TR-AhmetNeural','-10%','-10Hz')
        reply=client.post('/api/vision/speech',json={'text':code,'cloudConsent':True})
        assert reply.status_code==200 and reply.content==raw
        assert reply.headers['x-tts-source']=='verified-fixed-cache' and reply.headers['x-tts-voice']=='tr-TR-AhmetNeural'

def test_corrupt_or_wrong_profile_bank_fails_without_dispatch(monkeypatch,tmp_path):
    source=json.loads((vision_speech.FIXED_BANK/'manifest.json').read_text('utf8'))
    row=source['entries']['right'];raw=(vision_speech.FIXED_BANK/row['file']).read_bytes()
    monkeypatch.setattr(vision_speech,'FIXED_BANK',tmp_path)
    monkeypatch.setitem(main.vehicle_state,'vehicleMoving',False)
    monkeypatch.setattr(vision_speech.edge_tts,'Communicate',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Damaged bank fallback')))
    (tmp_path/row['file']).write_bytes(raw+b'corrupt')
    (tmp_path/'manifest.json').write_text(json.dumps(source),'utf8')
    client=TestClient(main.app)
    assert client.post('/api/vision/speech',json={'text':'right','cloudConsent':True}).status_code==503
    (tmp_path/row['file']).write_bytes(raw)
    source['entries']['right']={**row,'voice':'unapproved-voice'}
    (tmp_path/'manifest.json').write_text(json.dumps(source),'utf8')
    assert client.post('/api/vision/speech',json={'text':'right','cloudConsent':True}).status_code==503

def test_local_models_equal_pinned_package_and_exact_download_hashes():
    root=Path(__file__).resolve().parents[2];folder=root/'apps/vehicle-app/public/mediapipe'
    manifest=json.loads((folder/'manifest.json').read_text())
    assert manifest['sdkVersion']=='1.0.1' and not manifest['modelChange'] and not manifest['thresholdChange']
    for entry in manifest['files']:
        raw=(folder/entry['path']).read_bytes()
        assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
        if entry['path'].startswith('wasm/'):
            assert raw==(root/'node_modules/@mediapipe/tasks-vision'/entry['path']).read_bytes()
