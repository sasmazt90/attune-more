/** App-owned OUTPUT only. No microphone, recorder, gain, or duplicate output path. */
let context:AudioContext|undefined,frame=0;
const graphs=new WeakMap<HTMLMediaElement,{source:MediaElementAudioSourceNode;analyser:AnalyserNode;connected:boolean;data:Uint8Array<ArrayBuffer>}>();
const active=new Set<HTMLMediaElement>();
const pcm=new Set<{context:AudioContext;analyser:AnalyserNode;data:Uint8Array<ArrayBuffer>}>();
let values:number[]=Array(18).fill(0);
const listeners=new Set<()=>void>();
export const speechMuted=()=>typeof window!=='undefined'&&(window as Window & {attuneOutputMuted?:boolean}).attuneOutputMuted===true;
export function setSpeechMuted(value:boolean){(window as Window & {attuneOutputMuted?:boolean}).attuneOutputMuted=value;}
function publish(next:number[]){if(next.every((v,i)=>v===values[i]))return;values=next;for(const listener of listeners)listener();}
export const meterSnapshot=()=>values;
export function subscribeMeter(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener);};}
function sample(){
 frame=0;const bars=Array(18).fill(0);
 for(const audio of active){const graph=graphs.get(audio);if(!graph||audio.paused||audio.ended||audio.muted||speechMuted()||context?.state!=='running')continue;
  graph.analyser.getByteTimeDomainData(graph.data);
  for(let b=0;b<18;b++){let energy=0;const start=Math.floor(b*graph.data.length/18),end=Math.floor((b+1)*graph.data.length/18);for(let i=start;i<end;i++)energy+=((graph.data[i]-128)/128)**2;bars[b]=Math.max(bars[b],Math.sqrt(energy/(end-start))*audio.volume);}
 }
 for(const graph of pcm){if(graph.context.state!=='running'||speechMuted())continue;graph.analyser.getByteTimeDomainData(graph.data);for(let b=0;b<18;b++){let energy=0;const start=Math.floor(b*graph.data.length/18),end=Math.floor((b+1)*graph.data.length/18);for(let i=start;i<end;i++)energy+=((graph.data[i]-128)/128)**2;bars[b]=Math.max(bars[b],Math.sqrt(energy/(end-start)));}}
 publish(bars);if(active.size||pcm.size)frame=requestAnimationFrame(sample);
}
/** Replaces a single direct destination edge; never adds a second audible path. */
export function observeOutputNode(context:AudioContext,node:AudioNode){const analyser=context.createAnalyser();analyser.fftSize=512;node.connect(analyser);analyser.connect(context.destination);const graph={context,analyser,data:new Uint8Array(512)};pcm.add(graph);if(!frame)frame=requestAnimationFrame(sample);return()=>{pcm.delete(graph);node.disconnect();analyser.disconnect();if(!active.size&&!pcm.size){cancelAnimationFrame(frame);frame=0;publish(Array(18).fill(0));}};}
export function observeAppPlayback(audio:HTMLAudioElement){
 let disposed=false;
 const playing=async()=>{
  if(disposed||speechMuted())return;
  try{
   context??=new AudioContext();await context.resume();
   if(disposed||audio.paused||audio.ended||speechMuted()||context.state!=='running')return;
   let graph=graphs.get(audio);
   if(!graph){const source=context.createMediaElementSource(audio),analyser=context.createAnalyser();analyser.fftSize=512;graph={source,analyser,connected:false,data:new Uint8Array(512)};graphs.set(audio,graph);}
   if(!graph.connected){graph.source.connect(graph.analyser);graph.analyser.connect(context.destination);graph.connected=true;}
   active.add(audio);if(!frame)frame=requestAnimationFrame(sample);
  }catch{stop();} // A denied AudioContext leaves native playback alone.
 };
 const stop=()=>{
  active.delete(audio);const graph=graphs.get(audio);
  if(graph?.connected){graph.source.disconnect();graph.analyser.disconnect();graph.connected=false;}
  if(!active.size&&!pcm.size){cancelAnimationFrame(frame);frame=0;publish(Array(18).fill(0));void context?.suspend().catch(()=>{});}
 };
 for(const event of ['pause','ended','error','emptied','waiting'])audio.addEventListener(event,stop);
 audio.addEventListener('playing',playing);
 const mute=()=>{if(speechMuted())stop();};window.addEventListener('attune-guidance-muted',mute);
 return()=>{disposed=true;stop();audio.removeEventListener('playing',playing);for(const event of ['pause','ended','error','emptied','waiting'])audio.removeEventListener(event,stop);window.removeEventListener('attune-guidance-muted',mute);};
}
if(typeof window!=='undefined')window.addEventListener('pagehide',event=>{cancelAnimationFrame(frame);frame=0;active.clear();publish(Array(18).fill(0));if(event.persisted)void context?.suspend();else{void context?.close();context=undefined;}});
