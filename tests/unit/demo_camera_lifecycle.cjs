// Isolated transport lifecycle regression; no live inference or E2E claim.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const source=fs.readFileSync('apps/vehicle-app/src/utils/demoCamera.ts','utf8')
 .replace("import {isCameraAllowed} from './attuneMode';",'const isCameraAllowed=()=>true;')
 .replace("import {translateText} from '../i18n/core';",'const translateText=x=>x;');
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
async function receiver(){
 let ws,expired,clock=1,stops=0,ended=0;
 const track={stop(){stops++;},dispatchEvent(e){if(e.type==='ended')ended++;},requestFrame(){}};
 const stream={getTracks:()=>[track],getVideoTracks:()=>[track]};
 const element=()=>({style:{},append(){},showModal(){},remove(){}});
 const canvas={...element(),getContext:()=>({drawImage(){}}),captureStream:()=>stream};
 const sandbox={exports:{},process:{env:{NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE:'1'}},navigator:{userAgent:'AttuneCloudDemo/1'},
  fetch:async()=>({ok:true,json:async()=>({senderKey:'TEST_ONLY',receiverKey:'TEST_ONLY',sourceId:'source'})}),
  document:{createElement:tag=>tag==='canvas'?canvas:element(),body:{append(){}}},
  location:{protocol:'http:',host:'test'},window:{addEventListener(){},removeEventListener(){}},
  WebSocket:class{constructor(){ws=this;}send(){}close(){}},performance:{now:()=>clock},
  setInterval:fn=>{expired=fn;return 1;},clearInterval(){},setTimeout:()=>2,clearTimeout(){},
  createImageBitmap:async()=>({width:640,height:480,close(){}}),Blob,Event};
 vm.runInNewContext(js,sandbox);
 const acquired=sandbox.exports.acquireCamera({video:true});await new Promise(setImmediate);
 await ws.onmessage({data:JSON.stringify({sourceId:'source',sourceType:'remote-demo-camera',sequence:1})});
 await ws.onmessage({data:new Uint8Array([1])});await acquired;
 return {track,ws,advance(ms){clock+=ms;expired();},onTime(ms){for(let t=0;t<ms;t+=100){clock+=100;expired();}},state:()=>({stops,ended,source:sandbox.exports.demoCameraSource()})};
}
test('intentional consumer stop releases transport without reporting a camera failure',async()=>{
 const r=await receiver();r.track.stop();assert(r.state().stops>0);assert.equal(r.state().ended,0);assert.equal(r.state().source,undefined);
 r.ws.onclose();assert.equal(r.state().ended,0);
});
test('unexpected websocket disconnect still reports ended once',async()=>{
 const r=await receiver();r.ws.onclose();assert.equal(r.state().ended,1);assert.equal(r.state().source,undefined);r.ws.onerror();assert.equal(r.state().ended,1);
});
test('unchanged 750 ms freshness limit still ends a stalled remote source',async()=>{
 const r=await receiver();r.onTime(700);assert.equal(r.state().ended,0,'Still fresh before the limit');r.onTime(100);assert.equal(r.state().ended,1);assert.equal(r.state().source,undefined);
});
test('a long task on this thread is not a stalled source',async()=>{
 const r=await receiver();r.onTime(100);r.advance(2000);assert.equal(r.state().ended,0,'The thread was busy, the source was not silent');
 r.onTime(700);assert.equal(r.state().ended,0);r.onTime(100);assert.equal(r.state().ended,1,'A source that stays silent afterwards still ends');
});
