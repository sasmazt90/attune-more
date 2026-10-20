'use client';
import {useEffect,useState} from 'react';
import {useTranslations} from '../i18n/LanguageProvider';
import {LANGUAGE_EVENT,VOICE_EVENT} from '../i18n/core';
/** Report a real playback failure; never describe cancelled speech as success. */
export function VoiceAvailabilityNotice(){
 const {text:t}=useTranslations(),[unavailable,setUnavailable]=useState(false);
 useEffect(()=>{
  const failed=()=>setUnavailable(true),clear=()=>setUnavailable(false);
  window.addEventListener('attune-voice-unavailable',failed);
  window.addEventListener(LANGUAGE_EVENT,clear);window.addEventListener(VOICE_EVENT,clear);
  return()=>{window.removeEventListener('attune-voice-unavailable',failed);window.removeEventListener(LANGUAGE_EVENT,clear);window.removeEventListener(VOICE_EVENT,clear);};
 },[]);
 return unavailable?<p role="status" className="px-6 py-2 text-sm text-amber-200">{t('Seçilen ses oynatılamadı. Dil ve ses seçeneklerini kontrol edin; başka bir dilin sesi kullanılmadı.')}</p>:null;
}
