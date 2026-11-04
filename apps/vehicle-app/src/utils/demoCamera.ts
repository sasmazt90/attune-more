import {isCameraAllowed} from './attuneMode';
import {translateText} from '../i18n/core';
/** Explicit remote demo input. Local/native camera behavior remains the default. */
export type DemoSource={sourceType:'remote-demo-camera';sourceId:string;sequence:number};
let source:DemoSource|undefined;
export const demoCameraSource=()=>source?{sourceType:source.sourceType,sourceId:source.sourceId}:undefined;

export async function acquireCamera(constraints:MediaStreamConstraints):Promise<MediaStream>{
 if(process.env.NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE!=='1'||!navigator.userAgent.includes('AttuneCloudDemo/1'))return navigator.mediaDevices.getUserMedia(constraints);
 const response=await fetch('/bridge/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({processingConsent:true})});
 if(!response.ok)throw new Error(translateText('Uzak demo kamerası kullanılamıyor.'));
 const pair=await response.json();
 return new Promise((resolve,reject)=>{
  const dialog=document.createElement('dialog');
  const label=document.createElement('p');label.textContent=translateText('Uzak demo kamerası');
  const instruction=document.createElement('p');instruction.textContent=translateText('aaos.sasmaz.digital/capture sayfasına bu eşleştirme kodunu girin.');
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
  const cleanup=(notifyEnded=true)=>{if(done)return;done=true;clearInterval(timer);clearTimeout(waiting);window.removeEventListener('pagehide',onPageHide);window.removeEventListener('attune-privacy',onPrivacy);window.removeEventListener('storage',onPrivacy);ws.close();dialog.remove();source=undefined;if(stream)for(const track of stream.getTracks()){track.stop();if(notifyEnded)track.dispatchEvent(new Event('ended'));}else reject(new Error(translateText('Uzak demo kamerası iptal edildi, süresi doldu veya bağlantısı kesildi.')));};
  const timer=setInterval(()=>{if(lastFrame&&performance.now()-lastFrame>=750)cleanup();},100);
  const waiting=setTimeout(()=>cleanup(),120000);
  ws.onopen=()=>ws.send(JSON.stringify({key:pair.receiverKey,consent:true}));
  ws.onclose=()=>cleanup();ws.onerror=()=>cleanup();cancel.onclick=()=>cleanup();dialog.oncancel=()=>cleanup();
  const onPrivacy=()=>{if(!isCameraAllowed())cleanup();};window.addEventListener('attune-privacy',onPrivacy);window.addEventListener('storage',onPrivacy);
  const onPageHide=()=>cleanup();window.addEventListener('pagehide',onPageHide,{once:true});
  ws.onmessage=async event=>{
   if(done)return;
   if(typeof event.data==='string'){
    try{const next=JSON.parse(event.data);if(next.sourceId!==pair.sourceId||next.sourceType!=='remote-demo-camera'||!Number.isInteger(next.sequence)||next.sequence<1||(source&&next.sequence<=source.sequence))throw Error();metadata=next;}catch{cleanup();}return;
   }
   if(busy||!metadata){cleanup();return;}busy=true;
   const capturedMetadata=metadata;metadata=undefined;
   const received=performance.now();
   try{
    const bitmap=await createImageBitmap(new Blob([event.data],{type:'image/png'}));
    if(done||performance.now()-received>=750){bitmap.close();cleanup();return;}
    if(!context||bitmap.width>1920||bitmap.height>1080)throw Error();
    if(stream&&(canvas.width!==bitmap.width||canvas.height!==bitmap.height))throw Error();
    canvas.width=bitmap.width;canvas.height=bitmap.height;context.drawImage(bitmap,0,0);bitmap.close();source=capturedMetadata;lastFrame=performance.now();
    if(!stream){stream=canvas.captureStream(0);for(const track of stream.getTracks()){const stop=track.stop.bind(track);track.stop=()=>{stop();cleanup(false);};}dialog.remove();clearTimeout(waiting);resolve(stream);}
    (stream.getVideoTracks()[0] as MediaStreamTrack & {requestFrame:()=>void}).requestFrame();
   }catch{cleanup();}finally{busy=false;}
  };
 });
}
