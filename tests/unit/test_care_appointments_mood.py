"""QA-01 mood language, QA-13 appointment store, QA-14 region, QA-15 local time. Production TS, no mocks of the logic."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/core-api'))
BOOTSTRAP = r"""
const fs=require('fs'),assert=require('assert/strict');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
const store=new Map();
globalThis.localStorage={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
globalThis.window={addEventListener(){},removeEventListener(){},dispatchEvent(){return true;}};
globalThis.Event=class{constructor(t){this.type=t;}};
const load=require('./tests/unit/ts_source_loader.cjs')(dir);
"""


def run(tmp_path, script):
    done = subprocess.run(['node', '-e', BOOTSTRAP + script], cwd=ROOT, input=json.dumps({'dir': str(tmp_path).replace('\\', '/')}), capture_output=True, text=True, encoding='utf8')
    assert done.returncode == 0, done.stdout + done.stderr


def test_english_prose_stays_english_and_codes_follow_the_language(tmp_path):
    run(tmp_path, r"""
const H=load('mentalHistory');
assert.equal(H.translateMood('The user is feeling stressed and tired.','en'),'The user is feeling stressed and tired.');
assert.equal(H.translateMood('You seemed relaxed.','en'),'You seemed relaxed.');
assert.equal(H.translateMood('Trend: STRESSED','en'),'Trend: tense');
assert.equal(H.translateMood('Trend: RELAXED','de'),'Trend: entspannt');
assert.equal(H.translateMood('Eğilim: STRESSED','tr'),'Eğilim: gergin');
""")


def test_appointment_save_edit_delete_stays_local_and_keeps_address_for_in_person_only(tmp_path):
    run(tmp_path, r"""
const A=load('careAppointments');
const draft={specialty:'Dermatoloji',provider:'Dr. Weber',localDateTime:'2030-03-05T14:30',type:'IN_PERSON',address:'Hauptstr. 1'};
assert.equal(A.appointmentProblem({...draft,provider:' '}),'Doktor veya kurum adını yazın.');
assert.equal(A.appointmentProblem({...draft,localDateTime:''}),'Tarih ve saati girin.');
assert.equal(A.appointmentProblem({...draft,specialty:''}),'Branş seçin.');
const saved=A.saveAppointment(draft);
assert.equal(A.readAppointments().length,1);
assert.equal(saved.address,'Hauptstr. 1');
assert.ok(!('url' in saved)&&!('bookingUrl' in saved));
const edited=A.saveAppointment({...draft,type:'ONLINE',provider:'Dr. Weber online'},saved.id);
assert.equal(edited.id,saved.id);assert.equal(edited.createdAt,saved.createdAt);
assert.ok(!('address' in edited),'Online appointments carry no address');
assert.equal(A.readAppointments().length,1,'Editing does not duplicate');
A.deleteAppointment(saved.id);
assert.deepEqual(A.readAppointments(),[]);
assert.throws(()=>A.saveAppointment({...draft,provider:''}));
""")


def test_appointment_time_is_the_wall_clock_entered_in_the_local_format(tmp_path):
    run(tmp_path, r"""
const A=load('careAppointments');
for(const zone of ['UTC','Europe/Berlin','America/New_York']){
 process.env.TZ=zone;
 assert.match(A.formatAppointmentTime({localDateTime:'2030-03-05T14:30'},'en-US'),/2:30/);
 assert.match(A.formatAppointmentTime({localDateTime:'2030-03-05T14:30'},'de-DE'),/14:30/);
}
assert.match(A.formatAppointmentTime({localDateTime:'2030-03-05T14:30'},'tr-TR'),/5 Mar 2030/);
const now=new Date('2030-03-01T00:00').getTime(),row=(id,t)=>({id,localDateTime:t});
const order=A.sortAppointments([row('past','2030-02-01T10:00'),row('later','2030-04-01T10:00'),row('soon','2030-03-02T10:00')],now).map(r=>r.id);
assert.deepEqual(order,['soon','later','past']);
""")


def test_region_is_an_explicit_choice_and_never_a_default(tmp_path):
    run(tmp_path, r"""
const A=load('careAppointments');
assert.equal(A.readCareRegion(),'');
A.writeCareRegion('Berlin');assert.equal(A.readCareRegion(),'Berlin');
localStorage.setItem(A.CARE_REGION_KEY,'Nowhere');assert.equal(A.readCareRegion(),'');
A.writeCareRegion('');assert.equal(localStorage.getItem(A.CARE_REGION_KEY),null);
""")
    source = (ROOT / 'apps/vehicle-app/src/app/care/page.tsx').read_text('utf8')
    assert "preferredCity: region" in source and "preferredCity: 'İstanbul'" not in source


def test_region_required_without_a_city_and_no_provider_call(monkeypatch):
    import care_provider as cp
    from fastapi.testclient import TestClient
    import main

    def forbidden(*args, **kwargs):
        raise AssertionError('provider called without a region')
    monkeypatch.setattr(cp, 'get_care_provider', forbidden)
    monkeypatch.setitem(main.vehicle_state, 'vehicleMoving', False)
    monkeypatch.setitem(main.vehicle_state, 'vehicleParked', True)
    response = TestClient(main.app).post('/api/care/match', json={'specialty': 'Dermatoloji'})
    assert response.status_code == 200
    assert response.json()['status'] == 'REGION_REQUIRED' and response.json()['matchedSlots'] == []


def test_region_selects_the_directory_for_that_country():
    import care_provider as cp
    assert {row['sourceId'] for row in cp.public_handoff_result('Dermatoloji', 'Berlin')['slots']} == {'doctolib'}
    assert {row['sourceId'] for row in cp.public_handoff_result('Dermatoloji', 'München')['slots']} == {'doctolib'}
    assert {row['sourceId'] for row in cp.public_handoff_result('Dermatoloji', 'İzmir')['slots']} == {'doktortakvimi', 'doktorsitesi'}
    assert cp.public_handoff_result('Odyoloji', 'Berlin')['status'] == 'EMPTY_RESULT'
