import {getLanguage,Language,LOCALES,VOICE_EVENT,VOICE_KEY} from './core';
import {recordedProfile} from './fixedAudio';
import {languageSwitchLocked} from './locks';
export type VoiceGender='male'|'female'|'unknown';
export type VoiceChoice={id:string;name:string;locale:string;gender:VoiceGender;provider:'system'|'edge'|'local';local:boolean};
export type VoicePreference={provider:'approved'|'system'|'edge'|'local';voiceId?:string;gender?:VoiceGender;onlineConsent?:boolean};
/** Web Speech has no standardized voice gender. Never infer it from a name. */
export function systemVoiceChoices(voices:readonly SpeechSynthesisVoice[],language:Language):VoiceChoice[]{
 return voices.filter(v=>v.lang.replace('_','-').toLowerCase()===LOCALES[language].toLowerCase()).map(v=>({id:v.voiceURI,name:v.name,locale:v.lang,gender:'unknown',provider:'system',local:v.localService}));
}
export function voicePreference(language:Language=getLanguage()):VoicePreference {
 try {const data=JSON.parse(localStorage.getItem(VOICE_KEY)||'{}'),value=data[language];if(value&&['approved','system','edge','local'].includes(value.provider)&&(!value.voiceId||typeof value.voiceId==='string'))return value;}catch{}
 return {provider:'approved'};
}
export function setVoicePreference(language:Language,value:VoicePreference){
 if(languageSwitchLocked())throw Error('ASSESSMENT_IN_PROGRESS');
 let all:Partial<Record<Language,VoicePreference>>={};try{all=JSON.parse(localStorage.getItem(VOICE_KEY)||'{}');}catch{}
 if(!all||typeof all!=='object'||Array.isArray(all))all={};
 all[language]=value;const serialized=JSON.stringify(all);localStorage.setItem(VOICE_KEY,serialized);
 if(localStorage.getItem(VOICE_KEY)!==serialized)throw Error('VOICE_PREFERENCE_WRITE_FAILED');
 window.dispatchEvent(new CustomEvent(VOICE_EVENT,{detail:language}));
 window.dispatchEvent(new Event('attune-locale-media-cancel'));window.dispatchEvent(new Event('attune-guidance-cancel'));
}
export function selectSystemVoice(voices:readonly SpeechSynthesisVoice[],language:Language,preference:VoicePreference):SpeechSynthesisVoice|undefined {
 const available=voices.filter(v=>v.lang.replace('_','-').toLowerCase()===LOCALES[language].toLowerCase());
 if(preference.gender&&preference.gender!=='unknown')return undefined;
 return preference.voiceId?available.find(v=>v.voiceURI===preference.voiceId):available.find(v=>v.localService)||available[0];
}
