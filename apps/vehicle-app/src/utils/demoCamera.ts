import {isCameraAllowed} from './attuneMode';
import {translateText} from '../i18n/core';
/** Explicit remote demo input. Local/native camera behavior remains the default. */
export type DemoSource={sourceType:'remote-demo-camera';sourceId:string;sequence:number};
let source:DemoSource|undefined;
// See the comments in acquireCamera.
const STALLED_SOURCE_MS=7000,STALE_DECODE_MS=750;
export const demoCameraSource=()=>source?{sourceType:source.sourceType,sourceId:source.sourceId}:undefined;

export async function acquireCamera(constraints:MediaStreamConstraints):Promise<MediaStream>{
 if(process.env.NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE!=='1'||!navigator.userAgent.includes('AttuneCloudDemo/1'))return navigator.mediaDevices.getUserMedia(constraints);
 const response=await fetch('/bridge/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({processingConsent:true})});
 if(!response.ok)throw new Error(translateText('Uzak demo kamerası kullanılamıyor.'));
 const pair=await response.json();
 return new Promise((resolve,reject)=>{
  const dialog=document.createElement('dialog');
  const label=document.createElement('p');label.textContent=translateText('Uzak demo kamerası');
  const instruction=document.createElement('p');instruction.textContent=translateText('aaos.attunemore.sasmaz.digital/capture sayfasına bu eşleştirme kodunu girin.');
  const code=document.createElement('textarea');code.readOnly=true;code.value=pair.senderKey;code.style.width='100%';
  const cancel=document.createElement('button');cancel.textContent=translateText('İptal');
  // Demo-only pairing step, in the application's colours.
  dialog.style.cssText='background:#0c1424;color:#f3f7fc;border:1px solid rgba(255,255,255,.2);border-radius:16px;padding:20px;width:min(32rem,90vw)';
  code.style.cssText='width:100%;margin:12px 0;padding:10px;border-radius:10px;background:#05090f;color:#f3f7fc;border:1px solid rgba(255,255,255,.2)';
  cancel.style.cssText='min-height:44px;min-width:44px;padding:0 16px;border-radius:12px;border:1px solid rgba(255,255,255,.2)';
  dialog.append(label,instruction,code,cancel);document.body.append(dialog);dialog.showModal();
  const canvas=document.createElement('canvas'),context=canvas.getContext('2d');
  const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/bridge/receiver`);ws.binaryType='arraybuffer';
  let stream:MediaStream|undefined,done=false,busy=false,lastFrame=0,metadata:DemoSource|undefined;
  // MediaStreamTrack.stop() is consumer cleanup, not an unexpected source-ended event.
  const cleanup=(notifyEnded=true,reason='ended')=>{if(done)return;done=true;document.documentElement.dataset.attuneCameraEnd=reason;clearInterval(timer);clearTimeout(waiting);window.removeEventListener('pagehide',onPageHide);window.removeEventListener('attune-privacy',onPrivacy);window.removeEventListener('storage',onPrivacy);ws.close();dialog.remove();source=undefined;if(stream)for(const track of stream.getTracks()){track.stop();if(notifyEnded)track.dispatchEvent(new Event('ended'));}else reject(new Error(translateText('Uzak demo kamerası iptal edildi, süresi doldu veya bağlantısı kesildi.')));};
  // The connection ends only when frames have stopped. It outlasts the bridge's own limits, so the bridge normally
  // ends first and says why. A late frame is not a lost camera: pages use only new frames, and stop trusting the
  // preview after 750 ms without one. A long task on this thread says nothing about the source, so the next on-time
  // check starts from where this thread resumed.
  let lastTick=performance.now();
  const timer=setInterval(()=>{const now=performance.now(),starved=now-lastTick>=350;lastTick=now;if(starved){if(lastFrame)lastFrame=Math.max(lastFrame,now);return;}if(lastFrame&&now-lastFrame>=STALLED_SOURCE_MS)cleanup(true,'source-stalled');},100);
  const waiting=setTimeout(()=>cleanup(true,'pairing-timed-out'),120000);
  ws.onopen=()=>ws.send(JSON.stringify({key:pair.receiverKey,consent:true}));
  ws.onclose=()=>cleanup(true,'bridge-closed');ws.onerror=()=>cleanup(true,'socket-error');cancel.onclick=()=>cleanup(true,'cancelled');dialog.oncancel=()=>cleanup(true,'cancelled');
  const onPrivacy=()=>{if(!isCameraAllowed())cleanup(true,'not-allowed');};window.addEventListener('attune-privacy',onPrivacy);window.addEventListener('storage',onPrivacy);
  const onPageHide=()=>cleanup(true,'page-hidden');window.addEventListener('pagehide',onPageHide,{once:true});
  ws.onmessage=async event=>{
   if(done)return;
   if(typeof event.data==='string'){
    try{const next=JSON.parse(event.data);if(next.sourceId!==pair.sourceId||next.sourceType!=='remote-demo-camera'||!Number.isInteger(next.sequence)||next.sequence<1||(source&&next.sequence<=source.sequence))throw Error();metadata=next;}catch{cleanup(true,'bad-metadata');}return;
   }
   // This thread can fall behind the source. Only the newest frame matters, so an extra one is dropped, not fatal.
   if(busy){metadata=undefined;return;}
   if(!metadata){cleanup(true,'frame-without-metadata');return;}busy=true;
   const capturedMetadata=metadata;metadata=undefined;
   const received=performance.now();
   try{
    const bitmap=await createImageBitmap(new Blob([event.data],{type:'image/png'}));
    // A frame that took too long to decode is stale. Never show it; the limit above still catches a stalled source.
    if(done||performance.now()-received>=STALE_DECODE_MS){bitmap.close();return;}
    if(!context||bitmap.width>1920||bitmap.height>1080)throw Error();
    if(stream&&(canvas.width!==bitmap.width||canvas.height!==bitmap.height))throw Error();
    canvas.width=bitmap.width;canvas.height=bitmap.height;context.drawImage(bitmap,0,0);bitmap.close();source=capturedMetadata;lastFrame=performance.now();
    if(!stream){stream=canvas.captureStream(0);for(const track of stream.getTracks()){const stop=track.stop.bind(track);track.stop=()=>{stop();cleanup(false);};}dialog.remove();clearTimeout(waiting);resolve(stream);}
    (stream.getVideoTracks()[0] as MediaStreamTrack & {requestFrame:()=>void}).requestFrame();
   }catch{cleanup(true,'bad-frame');}finally{busy=false;}
  };
 });
}
