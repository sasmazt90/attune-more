// Isolated transport lifecycle regression; no live inference or E2E claim.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const source=fs.readFileSync('apps/vehicle-app/src/utils/demoCamera.ts','utf8')
 .replace("import {isCameraAllowed} from './attuneMode';",'const isCameraAllowed=()=>true;')
 .replace("import {translateText} from '../i18n/core';",'const translateText=x=>x;');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
async function receiver(){
 let ws,expired,clock=1,stops=0,ended=0,decodeHold=Promise.resolve();
 const track={stop(){stops++;},dispatchEvent(e){if(e.type==='ended')ended++;},requestFrame(){}};
 const stream={getTracks:()=>[track],getVideoTracks:()=>[track]};
 const element=()=>({style:{},append(){},showModal(){},remove(){}});
 const canvas={...element(),getContext:()=>({drawImage(){}}),captureStream:()=>stream};
 const sandbox={exports:{},process:{env:{NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE:'1'}},navigator:{userAgent:'AttuneCloudDemo/1'},
  fetch:async()=>({ok:true,json:async()=>({senderKey:'TEST_ONLY',receiverKey:'TEST_ONLY',sourceId:'source'})}),
  document:{createElement:tag=>tag==='canvas'?canvas:element(),body:{append(){}},documentElement:{dataset:{}}},
  location:{protocol:'http:',host:'test'},window:{addEventListener(){},removeEventListener(){}},
  WebSocket:class{constructor(){ws=this;}send(){}close(){}},performance:{now:()=>clock},
  setInterval:fn=>{expired=fn;return 1;},clearInterval(){},setTimeout:()=>2,clearTimeout(){},
  createImageBitmap:async()=>{await decodeHold;return {width:640,height:480,close(){}};},Blob,Event};
 vm.runInNewContext(js,sandbox);
 const acquired=sandbox.exports.acquireCamera({video:true});await new Promise(setImmediate);
 await ws.onmessage({data:JSON.stringify({sourceId:'source',sourceType:'remote-demo-camera',sequence:1})});
 await ws.onmessage({data:new Uint8Array([1])});await acquired;
 return {track,ws,hold(p){decodeHold=p;},meta(n){ws.onmessage({data:JSON.stringify({sourceId:'source',sourceType:'remote-demo-camera',sequence:n})});},advance(ms){clock+=ms;expired();},onTime(ms){for(let t=0;t<ms;t+=100){clock+=100;expired();}},state:()=>({stops,ended,source:sandbox.exports.demoCameraSource()})};
}
test('intentional consumer stop releases transport without reporting a camera failure',async()=>{
 const r=await receiver();r.track.stop();assert(r.state().stops>0);assert.equal(r.state().ended,0);assert.equal(r.state().source,undefined);
 r.ws.onclose();assert.equal(r.state().ended,0);
});
test('unexpected websocket disconnect still reports ended once',async()=>{
 const r=await receiver();r.ws.onclose();assert.equal(r.state().ended,1);assert.equal(r.state().source,undefined);r.ws.onerror();assert.equal(r.state().ended,1);
});
test('a late frame does not end the connection, but a source that has stopped does',async()=>{
 const r=await receiver();r.onTime(6900);assert.equal(r.state().ended,0,'Late, not lost');r.onTime(100);assert.equal(r.state().ended,1);assert.equal(r.state().source,undefined);
});
test('a long task on this thread is not a stalled source',async()=>{
 const r=await receiver();r.onTime(100);r.advance(9000);assert.equal(r.state().ended,0,'The thread was busy, the source was not silent');
 r.onTime(6900);assert.equal(r.state().ended,0);r.onTime(100);assert.equal(r.state().ended,1,'A source that stays silent afterwards still ends');
});
test('a frame arriving while the last one decodes is dropped, not fatal',async()=>{
 const r=await receiver();let release;r.hold(new Promise(done=>{release=done;}));
 r.meta(2);const decoding=r.ws.onmessage({data:new Uint8Array([1])}).catch(()=>{});
 r.meta(3);await r.ws.onmessage({data:new Uint8Array([1])});assert.equal(r.state().ended,0,'Only the newest frame matters');
 release();await decoding;r.meta(4);await r.ws.onmessage({data:new Uint8Array([1])});assert.equal(r.state().ended,0);assert.equal(r.state().source.sourceId,'source');
});
test('a frame with no metadata still ends the connection',async()=>{
 const r=await receiver();await r.ws.onmessage({data:new Uint8Array([1])});assert.equal(r.state().ended,1);
});
