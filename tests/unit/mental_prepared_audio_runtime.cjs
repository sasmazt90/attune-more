/** Real prepared-utterance sequencing; synthesis and physical playback are absent. */
require('./ts_loader.js');const assert=require('assert/strict');
global.window=new EventTarget();global.localStorage={getItem:()=>null};
global.Audio=class{};
const manifest=require('../../apps/vehicle-app/public/audio/mental/v1/female-calm-v1-manifest.json');
manifest.joinApprovalStatus='approved';manifest.joinSilenceMs=1;
const clips=[manifest.entries.find(e=>e.language==='tr'&&e.variantId==='A-V01'),manifest.entries.find(e=>e.language==='tr'&&e.variantId==='B01-V01')];
for(const e of clips){e.approvalStatus='approved';e.sha256='a'.repeat(64);e.bytes=100;e.durationMs=200;}
const fixed=require.resolve('../../apps/vehicle-app/src/utils/fixedFileSpeech.ts');
let calls=[],controller,abortAfterFirst=false;
require.cache[fixed]={id:fixed,filename:fixed,loaded:true,exports:{playFixedSpeech:async(audio,clip,signal,current)=>{assert(current());assert.equal(clip.mimeType,'audio/wav');calls.push(clip.url);if(abortAfterFirst)controller.abort();return true;}}};
const {playPreparedMental}=require('../../apps/vehicle-app/src/utils/mentalPreparedSpeech.ts');
const text=clips.map(c=>c.exactScript).join(' '),ids=clips.map(c=>c.assetId);let focus=[];
window.addEventListener('attune-stream-focus',e=>focus.push(e.active));
async function run(script=text,assets=ids){calls=[];controller=new AbortController();return playPreparedMental(script,assets,controller.signal,()=>true,()=>{},()=>{});}
(async()=>{
 assert(await run());assert.deepEqual(calls,clips.map(c=>c.audioPath));assert.deepEqual(focus,[true,false]);
 assert.equal(await run('invented script'),false);assert.equal(calls.length,0);
 assert.equal(await run(text,['missing']),false);assert.equal(calls.length,0);
 clips[1].speakerProfile='other';assert.equal(await run(),false);assert.equal(calls.length,0);clips[1].speakerProfile='female-calm-v1';
 clips[0].approvalStatus='pending';assert.equal(await run(),false);assert.equal(calls.length,0);clips[0].approvalStatus='approved';
 abortAfterFirst=true;assert.equal(await run(),false);assert.equal(calls.length,1);
 console.log('PASS real A+B sequencing: exact scripts, approved assets, same speaker, WAV playback, utterance focus and cancellation before B; no dynamic-generation path');
})().catch(e=>{console.error(e);process.exitCode=1;});
