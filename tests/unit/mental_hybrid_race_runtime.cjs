/** Controlled clock decisions, never a real performance measurement. */
require('./ts_loader.js');const assert=require('assert/strict');
const {chooseHybridTurn}=require('../../apps/vehicle-app/src/utils/mentalHybridRace.ts');
const tick=async()=>{for(let n=0;n<10;n++)await Promise.resolve();};
class Clock{nowMs=1000;next=0;jobs=new Map();now=()=>this.nowMs;set=(fn,ms)=>{const id=++this.next;this.jobs.set(id,{at:this.nowMs+ms,fn});return id;};clear=id=>this.jobs.delete(id);async advance(ms){const end=this.nowMs+ms;for(;;){const next=[...this.jobs].filter(([,x])=>x.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;this.nowMs=next[1].at;this.jobs.delete(next[0]);next[1].fn();await tick();}this.nowMs=end;await tick();}}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
(async()=>{
 let count=0;
 for(const scenario of ['personal','deadline','early-error','boundary','late','cancel','consent','drive','closing','missing-prepared']){
  const c=new Clock(),controller=new AbortController(),p=deferred(),f=deferred();let valid=true,signals={},events=[];
  const result=chooseHybridTurn({receivedAt:1000,signal:controller.signal,current:()=>valid,clock:c,observe:s=>events.push(s),personal:s=>{signals.p=s;return p.promise;},prepared:s=>{signals.f=s;return f.promise;}});const outcome=result.catch(e=>e.message);await tick();
  if(scenario!=='missing-prepared'){f.resolve('catalog');await tick();}
  if(scenario==='personal'){await c.advance(2999);p.resolve('whole-playable-personal');await tick();assert.deepEqual(await outcome,{path:'personal',value:'whole-playable-personal'});assert(signals.f.aborted);}
  else if(scenario==='early-error'){await c.advance(120);p.reject(Error('provider'));await tick();assert.equal((await outcome).path,'prepared');assert.equal(c.now(),1120);}
  else if(['cancel','consent','drive','closing'].includes(scenario)){await c.advance(2900);if(scenario==='cancel'||scenario==='closing')controller.abort();else valid=false;await c.advance(100);assert.equal(await outcome,null);assert(signals.p.aborted&&signals.f.aborted);assert.equal(events.length,0);}
  else{await c.advance(3000);p.resolve('too-late');await tick();if(scenario==='missing-prepared')assert.equal(await outcome,'HYBRID_PREPARED_NOT_READY');else {assert.deepEqual(await outcome,{path:'prepared',value:'catalog'});assert(signals.p.aborted);assert.equal(events.length,1);}}
  controller.abort();assert.equal(c.jobs.size,0);count++;
 }
 // T0 is immutable even if the task is scheduled late; exactly-at-deadline is prepared.
 {const c=new Clock();await c.advance(3000);const ctrl=new AbortController();let resolvePersonal;const out=chooseHybridTurn({receivedAt:1000,signal:ctrl.signal,current:()=>true,clock:c,personal:()=>Promise.resolve('text-and-URL-only'),prepared:()=>Promise.resolve('ready-recording')});await tick();assert.equal((await out).path,'prepared');ctrl.abort();count++;}
 {const c=new Clock(),ctrl=new AbortController(),p=deferred(),f=deferred();const result=chooseHybridTurn({receivedAt:1000,signal:ctrl.signal,current:()=>true,clock:c,personal:()=>p.promise,prepared:()=>f.promise});await tick();f.resolve('prepared');await tick();const deadlineJob=[...c.jobs].find(([,j])=>j.at===4000);c.jobs.delete(deadlineJob[0]);c.nowMs=3999.5;deadlineJob[1].fn();await tick();assert(!ctrl.signal.aborted);p.resolve('before-deadline');await tick();assert.equal((await result).path,'personal');ctrl.abort();count++;}
 console.log(`PASS ${count} controlled-clock hybrid decisions: <3000 whole playable personal, deadline/early error prepared, exact boundary single winner, late discard, cancellation and unavailable prepared failure`);
})().catch(e=>{console.error(e);process.exitCode=1;});
