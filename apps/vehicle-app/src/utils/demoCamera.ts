import {isCameraAllowed} from './attuneMode';
/** Explicit remote demo input. Local/native camera behavior remains the default. */
export type DemoSource={sourceType:'remote-demo-camera';sourceId:string;sequence:number};
let source:DemoSource|undefined;
export const demoCameraSource=()=>source?{sourceType:source.sourceType,sourceId:source.sourceId}:undefined;

export async function acquireCamera(constraints:MediaStreamConstraints):Promise<MediaStream>{
 if(process.env.NEXT_PUBLIC_ATTUNE_REMOTE_CAPTURE!=='1'||!navigator.userAgent.includes('AttuneCloudDemo/1'))return navigator.mediaDevices.getUserMedia(constraints);
 const response=await fetch('/bridge/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({processingConsent:true})});
 if(!response.ok)throw new Error('Remote demo capture unavailable');
 const pair=await response.json();
 return new Promise((resolve,reject)=>{
  const dialog=document.createElement('dialog');
  const label=document.createElement('p');label.textContent='Remote demo camera · Uzak demo kamerası · Remote-Demokamera';
  const instruction=document.createElement('p');instruction.textContent='aaos.sasmaz.digital/capture → pairing code / eşleştirme kodu / Kopplungscode';
  const code=document.createElement('textarea');code.readOnly=true;code.value=pair.senderKey;code.style.width='100%';
  const cancel=document.createElement('button');cancel.textContent='Cancel / İptal / Abbrechen';
  dialog.append(label,instruction,code,cancel);document.body.append(dialog);dialog.showModal();
  const canvas=document.createElement('canvas'),context=canvas.getContext('2d');
  const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/bridge/receiver`);ws.binaryType='arraybuffer';
  let stream:MediaStream|undefined,done=false,busy=false,lastFrame=0,metadata:DemoSource|undefined;
  const cleanup=()=>{if(done)return;done=true;clearInterval(timer);clearTimeout(waiting);window.removeEventListener('pagehide',onPageHide);window.removeEventListener('attune-privacy',onPrivacy);window.removeEventListener('storage',onPrivacy);ws.close();dialog.remove();source=undefined;if(stream)for(const track of stream.getTracks()){track.stop();track.dispatchEvent(new Event('ended'));}else reject(new Error('Remote camera cancelled, expired or disconnected'));};
  const timer=setInterval(()=>{if(lastFrame&&performance.now()-lastFrame>=750)cleanup();},100);
  const waiting=setTimeout(cleanup,120000);
  ws.onopen=()=>ws.send(JSON.stringify({key:pair.receiverKey,consent:true}));
  ws.onclose=cleanup;ws.onerror=cleanup;cancel.onclick=cleanup;dialog.oncancel=cleanup;
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
    if(!stream){stream=canvas.captureStream(0);for(const track of stream.getTracks()){const stop=track.stop.bind(track);track.stop=()=>{stop();cleanup();};}dialog.remove();clearTimeout(waiting);resolve(stream);}
    (stream.getVideoTracks()[0] as MediaStreamTrack & {requestFrame:()=>void}).requestFrame();
   }catch{cleanup();}finally{busy=false;}
  };
 });
}
