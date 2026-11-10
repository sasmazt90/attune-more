/** Web vehicle-state polling interval: 1 s, 250 ms while an app audio stream owns output. */
require('./ts_loader.js');
const assert=require('assert/strict');
const {vehiclePollInterval,streamFocusTracker,VEHICLE_POLL_MS,VEHICLE_POLL_DURING_AUDIO_MS}=require('../../apps/vehicle-app/src/utils/vehiclePolling.ts');
assert.equal(VEHICLE_POLL_MS,1000);assert.equal(VEHICLE_POLL_DURING_AUDIO_MS,250);
assert.equal(vehiclePollInterval(0),1000);assert.equal(vehiclePollInterval(1),250);assert.equal(vehiclePollInterval(3),250);
let first=0;const t=streamFocusTracker(()=>first++);
const focus=(owner,active)=>{const e=new Event('attune-stream-focus');e.owner=owner;e.active=active;return e;};
const a={},b={};
t.listener(focus(a,true));assert.equal(first,1,'first owner triggers an immediate read');assert.equal(t.owners.size,1);
t.listener(focus(b,true));assert.equal(first,1,'a second owner does not');t.listener(focus(a,false));assert.equal(t.owners.size,1);
t.listener(focus(b,false));assert.equal(t.owners.size,0);assert.equal(vehiclePollInterval(t.owners.size),1000,'back to 1 s');
t.listener(new Event('attune-stream-focus'));assert.equal(t.owners.size,0,'events without an owner are ignored');
const src=require('fs').readFileSync('apps/vehicle-app/src/context/VehicleContext.tsx','utf8');
assert(src.includes("vehiclePollInterval(streams.owners.size)")&&src.includes("addEventListener('attune-stream-focus', streams.listener)")&&!src.includes('setInterval(refresh, 1000)'));
console.log('PASS vehicle polling: 1 s, 250 ms while app audio owns output, immediate read when audio starts');
