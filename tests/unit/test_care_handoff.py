"""Provider handoff survives a page recreation without creating a booking."""
from test_care_appointments_mood import run


def test_recreated_page_recovers_only_pending_question_and_acknowledgement_clears_it(tmp_path):
    run(tmp_path, r"""
const H=load('careHandoff'), A=load('careAppointments');
const original='[{"id":"existing-booking"}]';
localStorage.setItem(A.CARE_APPOINTMENTS_KEY,original);
H.writeCareHandoff({specialty:'Eye care',providerName:'Directory',sourceType:'PUBLIC_SEARCH_ONLY',dateTime:'2030-01-01',bookingUrl:'https://example.com/private'},1000);
// Recreate the JS module as a new WebView/page would, keeping only device storage.
delete require.cache[require.resolve(dir+'/utils/careHandoff.js')];
const restored=require(dir+'/utils/careHandoff.js');
assert.deepEqual(restored.readCareHandoff(2000),{specialty:'Eye care',providerName:'Directory',sourceType:'PUBLIC_SEARCH_ONLY'});
assert.ok(!localStorage.getItem(H.CARE_HANDOFF_KEY).includes('bookingUrl'));
assert.ok(!localStorage.getItem(H.CARE_HANDOFF_KEY).includes('dateTime'));
assert.equal(localStorage.getItem(A.CARE_APPOINTMENTS_KEY),original);
restored.clearCareHandoff();
assert.equal(restored.readCareHandoff(3000),null);
assert.equal(localStorage.getItem(A.CARE_APPOINTMENTS_KEY),original);
""")


def test_stale_corrupt_and_unavailable_storage_do_not_restore_a_handoff(tmp_path):
    run(tmp_path, r"""
const H=load('careHandoff');
H.writeCareHandoff({specialty:'Eye care',providerName:'Directory'},1000);
assert.equal(H.readCareHandoff(1000+24*60*60*1000+1),null);
assert.equal(localStorage.getItem(H.CARE_HANDOFF_KEY),null);
localStorage.setItem(H.CARE_HANDOFF_KEY,'not json');
assert.equal(H.readCareHandoff(),null);
localStorage.setItem(H.CARE_HANDOFF_KEY,JSON.stringify({openedAt:Date.now(),specialty:[],providerName:'Bad'}));
assert.equal(H.readCareHandoff(),null);
globalThis.localStorage={getItem(){throw Error('denied')},setItem(){throw Error('denied')},removeItem(){throw Error('denied')}};
assert.doesNotThrow(()=>H.writeCareHandoff({specialty:'Eye care',providerName:'Directory'}));
assert.equal(H.readCareHandoff(),null);
assert.doesNotThrow(()=>H.clearCareHandoff());
""")
