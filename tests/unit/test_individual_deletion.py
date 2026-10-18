"""Durable per-record deletion, legacy preservation and backend ownership."""
import json
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services/core-api'))
import main
import session_memory as memory

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(memory, 'SESSIONS_FILE', tmp_path / 'sessions.json')
    monkeypatch.setattr(memory, 'DELETIONS_FILE', tmp_path / 'deletions.json')
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', False)
    return TestClient(main.app)

def create(api, text):
    response = api.post('/api/mental/sessions', json={'summaryText': text, 'recurringThemes': [], 'saveMentalSummaries': True})
    assert response.status_code == 200
    return response.json()

def test_backend_exact_delete_and_idempotent_retry(api):
    a, b = create(api, 'Synthetic A'), create(api, 'Synthetic B')
    assert a['sessionId'] != b['sessionId']
    for _ in range(2):
        response = api.request('DELETE', '/api/mental/sessions/' + a['sessionId'], json={'deletionToken': a['deletionToken']})
        assert response.json() == {'deleted': True}
    assert [r['sessionId'] for r in api.get('/api/mental/sessions').json()] == [b['sessionId']]
    assert 'Synthetic A' not in memory.SESSIONS_FILE.read_text(encoding='utf-8')
    assert 'Synthetic A' not in memory.DELETIONS_FILE.read_text(encoding='utf-8')

def test_other_owner_cannot_delete_and_capability_is_not_listed(api):
    a, b = create(api, 'Synthetic A'), create(api, 'Synthetic B')
    assert api.request('DELETE', '/api/mental/sessions/' + b['sessionId'], json={'deletionToken': a['deletionToken']}).status_code == 404
    rows = api.get('/api/mental/sessions').json()
    assert len(rows) == 2 and all('deletionToken' not in row for row in rows)

def test_legacy_backend_unowned_record_is_preserved(api):
    memory.SESSIONS_FILE.write_text(json.dumps([{'sessionId': 'men-001', 'summaryText': 'Legacy unchanged'}]), encoding='utf-8')
    before = memory.SESSIONS_FILE.read_bytes()
    assert api.request('DELETE', '/api/mental/sessions/men-001', json={'deletionToken': '0' * 64}).status_code == 404
    assert memory.SESSIONS_FILE.read_bytes() == before

def test_delete_requires_park_and_trusted_origin(api, monkeypatch):
    row = create(api, 'Synthetic A'); url = '/api/mental/sessions/' + row['sessionId']; data = {'deletionToken': row['deletionToken']}
    assert api.request('DELETE', url, json=data, headers={'Origin': 'https://untrusted.invalid'}).status_code == 403
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', True)
    assert api.request('DELETE', url, json=data).status_code == 409
    assert len(api.get('/api/mental/sessions').json()) == 1

def test_backend_write_failure_is_not_reported_success(api, monkeypatch):
    row = create(api, 'Synthetic A')
    def failed(*_args): raise OSError('controlled disk failure')
    monkeypatch.setattr(memory.SessionMemoryManager, '_write', failed)
    response = api.request('DELETE', '/api/mental/sessions/' + row['sessionId'], json={'deletionToken': row['deletionToken']})
    assert response.status_code == 503 and len(api.get('/api/mental/sessions').json()) == 1

NODE = r'''
const fs=require('fs'),ts=require('typescript'),assert=require('assert');
const {dir,category}=JSON.parse(fs.readFileSync(0,'utf8'));
for(const name of ['attuneMode','healthRecords']) fs.writeFileSync(dir+'/'+name+'.js',ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText);
const map=new Map();let failKey=null;
global.localStorage={getItem:k=>map.has(k)?map.get(k):null,setItem:(k,v)=>{if(k===failKey){failKey=null;throw Error('CONTROLLED_QUOTA');}map.set(k,String(v));},removeItem:k=>map.delete(k)};
global.window={dispatchEvent:()=>{},location:{search:''}};Object.defineProperty(global,'navigator',{value:{locks:{request:async(_name,fn)=>fn()}},configurable:true});global.crypto=require('crypto').webcrypto;
const H=require(dir+'/healthRecords.js');
const keys={vision:['togg_health_vision_history','togg_health_latest_vision'],skin:['togg_health_skin_history','togg_health_latest_skin'],mental:['togg_health_mental_history','togg_health_latest_mental'],dental:['attune_dental_history_v1','attune_dental_latest_v1'],hearing:['attune_hearing_history_v1','attune_hearing_latest_v1']}[category];
const old={date:'2026-10-03T10:00:00Z',summaryText:'Legacy untouched',themes:['kitap'],completed:true,consented:true,schemaVersion:2};
map.set(keys[0],JSON.stringify([old,{...old,id:'new',summaryText:'Other untouched'}]));map.set(keys[1],JSON.stringify(old));
(async()=>{
const rows=await H.prepareHealthRecords(category);assert(rows[0].id);assert.equal(rows.length,2);assert.equal(rows[0].summaryText,old.summaryText);assert.deepEqual(H.readHealthRecords(category),rows);
const before=new Map(map);failKey=keys[0];
 await assert.rejects(H.deleteHealthRecord(category,rows[0].id));assert.deepEqual(map,before);
 await H.deleteHealthRecord(category,rows[0].id);assert.equal(H.readHealthRecords(category).length,1);assert.equal(H.readHealthRecords(category)[0].id,'new');assert.equal(JSON.parse(map.get(keys[1])).id,'new');
 // Simulate interrupted multi-key write and reopening; durable journal recovers originals.
 const saved=map.get(keys[0]);map.set(H.RECORD_JOURNAL,JSON.stringify({[keys[0]]:saved}));map.set(keys[0],'[]');assert.equal((await H.prepareHealthRecords(category)).length,1);assert(!map.has(H.RECORD_JOURNAL));
 await H.deleteHealthRecord(category,'new');assert.equal(H.readHealthRecords(category).length,0);assert(!map.has(keys[1]));
 await assert.rejects(H.appendHealthRecord(category,{id:'media',image:'data:image/png;base64,AAAA'}),/Ham medya/);assert.equal(H.readHealthRecords(category).length,0);
 await assert.rejects(H.appendHealthRecord(category,{id:'revoked'}, {},()=>false));assert.equal(H.readHealthRecords(category).length,0);
 map.set(keys[0],'unreadable legacy');const invalid=map.get(keys[0]);assert.throws(()=>H.readHealthRecords(category));assert.equal(map.get(keys[0]),invalid);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''

@pytest.mark.parametrize('category', ['vision', 'skin', 'mental', 'dental', 'hearing'])
def test_client_legacy_ids_delete_rollback_reopen_and_no_raw_media(tmp_path, category):
    subprocess.run(['node', '-e', "require('./tests/unit/ts_loader.js');require('./tests/unit/skin_photo_numeric_stub.cjs');\n"+NODE], input=json.dumps({'dir': str(tmp_path), 'category': category}), text=True, check=True, cwd=Path(__file__).resolve().parents[2])
