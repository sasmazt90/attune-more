import {getLanguage,LOCALES,t} from './core';
import {selectSystemVoice,voicePreference} from './voices';
import {speechMuted} from '../utils/playbackMeter';
export function systemSpeech(text:string,signal:AbortSignal,current:()=>boolean,onStart:()=>void=()=>{},personal=false):Promise<boolean>{
 const language=getLanguage(),preference=voicePreference(language);
 if(typeof speechSynthesis==='undefined'||typeof SpeechSynthesisUtterance==='undefined')return Promise.resolve(false);
 const voice=selectSystemVoice(speechSynthesis.getVoices(),language,preference);
 if(!voice||(personal&&!voice.localService&&!preference.onlineConsent))return Promise.resolve(false);
 return new Promise(resolve=>{
  if(signal.aborted||!current()||speechMuted()||document.hidden){resolve(false);return;}
  const utterance=new SpeechSynthesisUtterance(t(text,language));utterance.lang=LOCALES[language];utterance.voice=voice;
  let done=false;let timer:ReturnType<typeof setInterval>;
  const finish=(played:boolean)=>{if(done)return;done=true;clearInterval(timer);clearTimeout(deadline);signal.removeEventListener('abort',abort);utterance.onend=utterance.onerror=utterance.onstart=null;if(!played){try{speechSynthesis.cancel();}catch{}}resolve(played);};
  const abort=()=>finish(false),deadline=setTimeout(abort,60000);
  signal.addEventListener('abort',abort,{once:true});
  timer=setInterval(()=>{try{const hearing=Number(localStorage.getItem('attune_hearing_audio_focus')||0)>Date.now();if(!current()||speechMuted()||document.hidden||hearing||getLanguage()!==language)abort();}catch{abort();}},100);
  utterance.onstart=()=>{if(current()&&!signal.aborted)onStart();else abort();};
  utterance.onend=()=>finish(current()&&!signal.aborted);utterance.onerror=abort;
  try{speechSynthesis.cancel();speechSynthesis.speak(utterance);}catch{abort();}
 });
}
