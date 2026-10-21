'use client';
import {createContext,useContext,useEffect,useSyncExternalStore} from 'react';
import {getLanguage,LANGUAGE_EVENT,LANGUAGE_KEY,VOICE_KEY,VOICE_EVENT,Language,LOCALES,t} from './core';
import {localizedNode} from './render';
import {languageSwitchLocked} from './locks';
import {PRODUCT_TAGLINE,PRODUCT_DESCRIPTION} from '../utils/brand';
const LanguageContext=createContext<Language>('tr');
function subscribe(listener:()=>void){
 const storage=(event:StorageEvent)=>{
  if((event.key===LANGUAGE_KEY||event.key===null)&&!languageSwitchLocked()){
   window.dispatchEvent(new Event('attune-locale-media-cancel'));listener();
  }
  if(event.key===VOICE_KEY||event.key===null){window.dispatchEvent(new Event('attune-locale-media-cancel'));window.dispatchEvent(new Event(VOICE_EVENT));}
 };
 window.addEventListener(LANGUAGE_EVENT,listener);window.addEventListener('storage',storage);
 return ()=>{window.removeEventListener(LANGUAGE_EVENT,listener);window.removeEventListener('storage',storage);};
}
export function useLanguage(){return useContext(LanguageContext);}
export function useTranslations(){
 const language=useLanguage();
 return {language,locale:LOCALES[language],text:(value:string)=>t(value,language),node:(value:React.ReactNode)=>localizedNode(value,language)};
}
export function LanguageProvider({children}:{children:React.ReactNode}){
 const language=useSyncExternalStore(subscribe,getLanguage,()=> 'tr' as Language);
 useEffect(()=>{
  document.documentElement.lang=language;
  document.title='Attune.more — '+t(PRODUCT_TAGLINE,language);
  document.querySelector('meta[name="description"]')?.setAttribute('content',t(PRODUCT_DESCRIPTION,language));
  // Cancel stale utterances; this event never modifies assessment/vehicle/consent state.
  window.dispatchEvent(new Event('attune-guidance-cancel'));
  window.dispatchEvent(new Event('attune-locale-media-cancel'));
 },[language]);
 return <>
  <link rel="manifest" href={language==='tr'?'/manifest.webmanifest':'/localized-manifest?language='+language}/>
  <LanguageContext.Provider value={language}>{children}</LanguageContext.Provider>
 </>;
}
