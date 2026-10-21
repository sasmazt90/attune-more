import {getLanguage,t} from './core';
import {selectSystemVoice,voicePreference} from './voices';
import {mentalVoiceIdentity,mentalVoicePreference,selectMentalSystemVoice} from './mentalVoices';
import {speechMuted} from '../utils/playbackMeter';
export function systemSpeech(text:string,signal:AbortSignal,current:()=>boolean,onStart:()=>void=()=>{},personal=false):Promise<boolean>{
 const language=getLanguage(),preference=voicePreference(language);
 if(typeof speechSynthesis==='undefined'||typeof SpeechSynthesisUtterance==='undefined')return Promise.resolve(false);
 const voice=selectSystemVoice(speechSynthesis.getVoices(),language,preference);
 if(!voice||(personal&&!voice.localService&&!preference.onlineConsent))return Promise.resolve(false);
 return speakSystemText(t(text,language),voice,signal,current,onStart);
}

/** Dynamic replies stay byte-for-byte text: no fixed clip or demo substitution. */
export async function mentalSystemSpeech(text:string,signal:AbortSignal,current:()=>boolean,onStart:()=>void=()=>{}):Promise<boolean>{
 if(typeof speechSynthesis==='undefined'||typeof SpeechSynthesisUtterance==='undefined'||signal.aborted||!current())return false;
 const language=getLanguage();
 if(!selectMentalSystemVoice(speechSynthesis.getVoices(),language,mentalVoicePreference(language))){
  await new Promise<void>(resolve=>{let done=false;const finish=()=>{if(done)return;done=true;clearTimeout(timer);speechSynthesis.removeEventListener('voiceschanged',changed);signal.removeEventListener('abort',finish);resolve();};const changed=()=>{if(selectMentalSystemVoice(speechSynthesis.getVoices(),language,mentalVoicePreference(language)))finish();};const timer=setTimeout(finish,4000);speechSynthesis.addEventListener('voiceschanged',changed);signal.addEventListener('abort',finish,{once:true});changed();});
 }
 if(signal.aborted||!current()||language!==getLanguage())return false;
 const voice=selectMentalSystemVoice(speechSynthesis.getVoices(),language,mentalVoicePreference(language));
 if(!voice)return false;
 const owner={},publish=(active:boolean)=>{const event=new Event('attune-stream-focus') as Event & {owner:object;active:boolean};event.owner=owner;event.active=active;window.dispatchEvent(event);};
 const continued=()=>{const preference=mentalVoicePreference(language);return current()&&(voice.localService||preference.onlineConsent===true)&&(!preference.voiceId||preference.voiceId===voice.voiceURI);};
 publish(true);try{return await speakSystemText(text,voice,signal,continued,()=>{window.dispatchEvent(new CustomEvent('attune-mental-system-voice',{detail:{name:voice.name,voiceURI:voice.voiceURI,locale:voice.lang,gender:'female',genderSource:mentalVoiceIdentity(voice)?.source,local:voice.localService}}));onStart();});}finally{publish(false);}
}

function speakSystemText(text:string,voice:SpeechSynthesisVoice,signal:AbortSignal,current:()=>boolean,onStart:()=>void):Promise<boolean>{
 const language=getLanguage();
 const permitted=()=>{try{return !signal.aborted&&current()&&!speechMuted()&&!document.hidden&&getLanguage()===language&&Number(localStorage.getItem('attune_hearing_audio_focus')||0)<=Date.now();}catch{return false;}};
 return new Promise(resolve=>{
  if(!permitted()){resolve(false);return;}
  const utterance=new SpeechSynthesisUtterance(text);utterance.lang=voice.lang;utterance.voice=voice;
  let done=false,started=false;let timer:ReturnType<typeof setInterval>;
  const finish=(played:boolean)=>{if(done)return;done=true;clearInterval(timer);clearTimeout(deadline);signal.removeEventListener('abort',abort);document.removeEventListener('visibilitychange',changed);window.removeEventListener('attune-guidance-muted',changed);window.removeEventListener('attune-locale-media-cancel',abort);window.removeEventListener('attune-audio-focus',changed);utterance.onend=utterance.onerror=utterance.onstart=null;if(!played){try{speechSynthesis.cancel();}catch{}}resolve(played);};
  const abort=()=>finish(false),deadline=setTimeout(abort,60000);
  const changed=()=>{if(!permitted())abort();};
  signal.addEventListener('abort',abort,{once:true});document.addEventListener('visibilitychange',changed);window.addEventListener('attune-guidance-muted',changed);window.addEventListener('attune-locale-media-cancel',abort);window.addEventListener('attune-audio-focus',changed);
  timer=setInterval(changed,100);
  utterance.onstart=()=>{if(permitted()){started=true;onStart();}else abort();};
  utterance.onend=()=>finish(started&&permitted());utterance.onerror=abort;
  try{speechSynthesis.cancel();speechSynthesis.speak(utterance);}catch{abort();}
 });
}
