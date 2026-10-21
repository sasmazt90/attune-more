import {getLanguage,Language,VOICE_EVENT} from './core';
import {captureWhileLocked,languageSwitchLocked} from './locks';
// Identity metadata only: neither installation nor service entitlement is inferred.
// https://learn.microsoft.com/azure/ai-services/speech-service/language-support
// https://support.microsoft.com/en-us/accessibility/windows/narrator/appendix-a-supported-languages-and-voices
const azure='https://learn.microsoft.com/azure/ai-services/speech-service/language-support';
const windows='https://support.microsoft.com/en-us/accessibility/windows/narrator/appendix-a-supported-languages-and-voices';
export const MENTAL_VOICE_KEY='attune.mental-system-voice.v1';
export type MentalVoicePreference={voiceId?:string;onlineConsent?:boolean};
const identities=[
 {id:'tr-TR-EmelNeural',locale:'tr-TR',names:['Microsoft Emel Online (Natural) - Turkish (Turkey)'],source:azure},
 {id:'en-GB-AdaMultilingualNeural',locale:'en-GB',names:['Microsoft AdaMultilingual Online (Natural) - English (United Kingdom)'],source:azure},
 {id:'de-DE-KatjaNeural',locale:'de-DE',names:['Microsoft Katja Online (Natural) - German (Germany)'],source:azure},
 {id:'en-US-AriaNeural',locale:'en-US',names:['Microsoft Aria Online (Natural) - English (United States)'],source:azure},
 {id:'en-US-JennyNeural',locale:'en-US',names:['Microsoft Jenny Online (Natural) - English (United States)'],source:azure},
 {id:'en-GB-SoniaNeural',locale:'en-GB',names:['Microsoft Sonia Online (Natural) - English (United Kingdom)'],source:azure},
 {id:'windows-zira',locale:'en-US',names:['Microsoft Zira - English (United States)','Microsoft Zira Desktop - English (United States)'],source:windows},
 {id:'windows-katja',locale:'de-DE',names:['Microsoft Katja - German (Germany)'],source:windows},
 {id:'windows-hedda',locale:'de-DE',names:['Microsoft Hedda - German (Germany)','Microsoft Hedda Desktop - German (Germany)'],source:windows},
];
export function mentalVoiceIdentity(voice:SpeechSynthesisVoice){
 return identities.find(row=>row.locale.toLowerCase()===voice.lang.replace('_','-').toLowerCase()&&(voice.voiceURI===row.id||row.names.includes(voice.name)));
}
/** Web Speech has no gender property: unknown identities are never guessed. */
export function mentalSystemVoices(voices:readonly SpeechSynthesisVoice[],language:Language){
 return voices.filter(v=>v.lang.split(/[-_]/)[0].toLowerCase()===language&&!!mentalVoiceIdentity(v));
}
function storedPreferences():string {try{return localStorage.getItem(MENTAL_VOICE_KEY)||'{}';}catch{return '{}';}}
const lockedPreferences=captureWhileLocked(storedPreferences);
function parsePreference(raw:string,language:Language):MentalVoicePreference{
 try{const value=JSON.parse(raw)[language];return value&&typeof value==='object'?{voiceId:typeof value.voiceId==='string'?value.voiceId:undefined,onlineConsent:value.onlineConsent===true}:{};}catch{return {};}
}
export function mentalVoicePreference(language:Language=getLanguage()):MentalVoicePreference{
 const selected=parsePreference(lockedPreferences(),language),live=parsePreference(storedPreferences(),language);
 // Freeze identity, but never freeze a revoked online-provider permission.
 return {...selected,onlineConsent:selected.onlineConsent===true&&live.onlineConsent===true};
}
export function setMentalVoicePreference(language:Language,value:MentalVoicePreference){
 if(languageSwitchLocked())throw Error('ASSESSMENT_IN_PROGRESS');
 let all:Record<string,MentalVoicePreference>={};try{const previous=JSON.parse(localStorage.getItem(MENTAL_VOICE_KEY)||'{}');if(previous&&typeof previous==='object'&&!Array.isArray(previous))all=previous;}catch{}
 all[language]={voiceId:value.voiceId,onlineConsent:value.onlineConsent===true};const bytes=JSON.stringify(all);localStorage.setItem(MENTAL_VOICE_KEY,bytes);if(localStorage.getItem(MENTAL_VOICE_KEY)!==bytes)throw Error('VOICE_PREFERENCE_WRITE_FAILED');
 window.dispatchEvent(new CustomEvent(VOICE_EVENT,{detail:language}));window.dispatchEvent(new Event('attune-locale-media-cancel'));
}
export function selectMentalSystemVoice(voices:readonly SpeechSynthesisVoice[],language:Language,preference:MentalVoicePreference){
 const candidates=mentalSystemVoices(voices,language).filter(v=>v.localService||preference.onlineConsent===true);
 if(preference.voiceId)return candidates.find(v=>v.voiceURI===preference.voiceId);
 const preferred={tr:'tr-TR-EmelNeural',en:'en-GB-AdaMultilingualNeural',de:'de-DE-KatjaNeural'}[language];
 return candidates.find(v=>mentalVoiceIdentity(v)?.id===preferred)||candidates.find(v=>mentalVoiceIdentity(v)?.id.endsWith('Neural'))||candidates.find(v=>v.localService)||candidates[0];
}
