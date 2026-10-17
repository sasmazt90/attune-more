import {observeAppPlayback,speechMuted} from './playbackMeter';
/** One MP3 provider response -> ordered MSE buffer -> actual HTML audio events.
 * A stream is never converted to a full Blob. Unsupported formats fail visibly.
 */
export function streamSpeech(audio:HTMLAudioElement,response:Response,signal:AbortSignal,current:()=>boolean,observe:(stage:string,bytes?:number)=>void=()=>{}) {
  const hearingOwns=()=>{try{return Number(localStorage.getItem('attune_hearing_audio_focus'))>Date.now();}catch{return false;}};
  if(speechMuted())throw new Error('Seslendirme kapalı.');
  if(hearingOwns())throw new Error('İşitme testi ses çıkışını kullanıyor.');
  window.dispatchEvent(new Event('attune-guidance-cancel')); // Actual assistant responses retain their own lifecycle; cancel only fixed guidance.
  if(!response.body || !response.headers.get('content-type')?.startsWith('audio/mpeg') || !MediaSource.isTypeSupported('audio/mpeg')) throw new Error('Streaming audio unsupported');
  const source=new MediaSource(),url=URL.createObjectURL(source),reader=response.body.getReader();
  let buffer:SourceBuffer|null=null,closed=false,playStarted=false;
  const unmeter=observeAppPlayback(audio);
  const speechOwner={};const publishFocus=(active:boolean)=>{const event=new Event('attune-stream-focus') as Event & {owner:object;active:boolean};event.owner=speechOwner;event.active=active;window.dispatchEvent(event);};publishFocus(true);
  const cancelled=()=>closed||signal.aborted||!current();
  const abortError=()=>new DOMException('Playback cancelled','AbortError');
  const wait=(target:EventTarget,event:string)=>new Promise<void>((resolve,reject)=>{
    if(cancelled()){reject(abortError());return;}
    const clear=()=>{target.removeEventListener(event,done);target.removeEventListener('error',fail);signal.removeEventListener('abort',fail);local.signal.removeEventListener('abort',fail);};
    const done=()=>{clear();cancelled()?reject(abortError()):resolve();};
    const fail=()=>{clear();reject(cancelled()?abortError():new Error('Media buffer'));};
    target.addEventListener(event,done,{once:true});target.addEventListener('error',fail,{once:true});signal.addEventListener('abort',fail,{once:true});local.signal.addEventListener('abort',fail,{once:true});
  });
  const local=new AbortController();
  // Direct cancellation (mute/route) must also wake sourceopen/updateend waits.
  const cancel=()=>{closed=true;detachFocus();local.abort();void reader.cancel().catch(()=>{});if(buffer?.updating&&source.readyState==='open'){try{buffer.abort();}catch{}}};
  const detachFocus=()=>{unmeter();publishFocus(false);window.removeEventListener('attune-audio-focus',audioFocus);window.removeEventListener('storage',audioFocus);audio.removeEventListener('ended',detachFocus);audio.removeEventListener('error',detachFocus);};
  audio.addEventListener('ended',detachFocus,{once:true});audio.addEventListener('error',detachFocus,{once:true});
  const audioFocus=()=>{if(hearingOwns()){audio.pause();cancel();}};
  window.addEventListener('attune-audio-focus',audioFocus);window.addEventListener('storage',audioFocus);
  signal.addEventListener('abort',cancel,{once:true});
  const opened=wait(source,'sourceopen');audio.preload='auto';audio.src=url;audio.load();
  const finished=(async()=>{
    try {
      await opened;if(cancelled())throw abortError();
      buffer=source.addSourceBuffer('audio/mpeg');buffer.mode='sequence';
      let total=0;
      const read=async()=>{const part=await reader.read();observe(part.done?'body-end':'chunk',part.value?.byteLength);return part;};
      let pending=read();void pending.catch(()=>{});
      for(;;){
        const part=await pending;if(cancelled())throw abortError();
        if(part.done)break;
        // One-chunk lookahead overlaps network reads with SourceBuffer updates.
        pending=read();void pending.catch(()=>{});
        total+=part.value.byteLength;if(total>8*1024*1024)throw new Error('Speech output too large');
        const updated=wait(buffer,'updateend');buffer.appendBuffer(part.value as Uint8Array<ArrayBuffer>);
        // Start the native play promise immediately. It naturally waits for a
        // complete decodable MP3 frame; do not wait for the full HTTP body.
        if(!playStarted){playStarted=true;observe('play-request');void audio.play().catch(()=>{if(!cancelled()){cancel();audio.dispatchEvent(new Event('error'));}});}
        await updated;
      }
      if(!total||cancelled())throw abortError();
      if(source.readyState==='open')source.endOfStream();
    } catch(error) {cancel();throw error;}
    finally {signal.removeEventListener('abort',cancel);reader.releaseLock();}
  })();
  return {url,cancel,finished};
}
