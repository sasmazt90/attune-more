import catalog from '../../../../shared/localization/messages.json';
import {languageSwitchLocked,subscribeLanguageLock} from './locks';

export const LANGUAGES = ['tr', 'en', 'de'] as const;
export type Language = typeof LANGUAGES[number];
export const LOCALES: Record<Language,string> = {tr:'tr-TR',en:'en-US',de:'de-DE'};
export const LANGUAGE_KEY = 'attune.language.v1';
export const VOICE_KEY = 'attune.voice.v1';
export const LANGUAGE_EVENT = 'attune-language-change';
export const VOICE_EVENT = 'attune-voice-change';
export const isLanguage = (value:unknown):value is Language => LANGUAGES.includes(value as Language);
function storedLanguage():Language {
  if(typeof window==='undefined')return 'tr';
  try {const value=localStorage.getItem(LANGUAGE_KEY);return isLanguage(value)?value:'tr';}catch{return 'tr';}
}
let assessmentLanguage:Language|undefined;
/** Freeze every locale consumer, including fetch/audio, for the local lock's lifetime. */
export function getLanguage():Language {return assessmentLanguage||storedLanguage();}
subscribeLanguageLock(()=>{
 if(languageSwitchLocked()){assessmentLanguage=storedLanguage();return;}
 const previous=assessmentLanguage;assessmentLanguage=undefined;
 if(typeof window!=='undefined'&&previous&&previous!==storedLanguage()){
  window.dispatchEvent(new Event('attune-locale-media-cancel'));
  window.dispatchEvent(new CustomEvent(LANGUAGE_EVENT,{detail:storedLanguage()}));
 }
});
export const getLocale = () => LOCALES[getLanguage()];
export function setLanguage(language:Language) {
  if(!isLanguage(language))throw Error('UNSUPPORTED_LANGUAGE');
  if(languageSwitchLocked())throw Error('ASSESSMENT_IN_PROGRESS');
  localStorage.setItem(LANGUAGE_KEY,language);
  if(localStorage.getItem(LANGUAGE_KEY)!==language)throw Error('LANGUAGE_PREFERENCE_WRITE_FAILED');
  window.dispatchEvent(new Event('attune-locale-media-cancel'));
  window.dispatchEvent(new CustomEvent(LANGUAGE_EVENT,{detail:language}));
}
export function languageURL(path:string):string {
  const [base,fragment]=path.split('#',2),separator=base.includes('?')?'&':'?';
  return base+separator+'language='+getLanguage()+(fragment?'#'+fragment:'');
}
type Message={tr:string;en:string;de:string};
const normalize=(text:string)=>text.normalize('NFC').replace(/\s+/g,' ').trim();
const messages=Object.values(catalog) as Message[];
const bySource=new Map(messages.map(message=>[normalize(message.tr),message]));
const escape=(text:string)=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const templateLiteral=(text:string)=>escape(text).replace(/^ | $/g,'\\s*');
const templates=messages.filter(m=>/\{\d+\}/.test(m.tr)).sort((a,b)=>b.tr.replace(/\{\d+\}/g,'').length-a.tr.replace(/\{\d+\}/g,'').length).map(message=>{
  const fields:number[]=[];let pattern='',previous=0;
  for(const match of message.tr.matchAll(/\{(\d+)\}/g)){
    pattern+=templateLiteral(message.tr.slice(previous,match.index))+'(.*?)';fields.push(Number(match[1]));previous=match.index!+match[0].length;
  }
  pattern+=templateLiteral(message.tr.slice(previous));
  return {message,fields,match:new RegExp('^'+pattern+'$','u')};
});
/** Display only. Never use translated strings as policy IDs or rewrite records. */
export function translateText(value:string,language:Language=getLanguage(),depth=0):string {
  if(language==='tr'||!value.trim())return value;
  const normalized=normalize(value),direct=bySource.get(normalized);
  const padded=(text:string)=>(/^\s/.test(value)?' ':'')+text+(/\s$/.test(value)?' ':'');
  if(direct)return padded(direct[language]);
  if(depth<3&&normalized.length<=6000){
    for(const template of templates){
      const match=template.match.exec(normalized);if(!match)continue;
      const parameters=new Map(template.fields.map((field,index)=>[field,translateText(match[index+1],language,depth+1)]));
      return padded(template.message[language].replace(/\{(\d+)\}/g,(_,id)=>parameters.get(Number(id))||''));
    }
  }
  // Unknown/user-authored strings remain unchanged; never send private text to translation APIs.
  return value;
}
export const t=translateText;
export function formatDate(value:Date|string|number,options?:Intl.DateTimeFormatOptions){return new Intl.DateTimeFormat(getLocale(),options).format(new Date(value));}
export function formatNumber(value:number,options?:Intl.NumberFormatOptions){return new Intl.NumberFormat(getLocale(),options).format(value);}
