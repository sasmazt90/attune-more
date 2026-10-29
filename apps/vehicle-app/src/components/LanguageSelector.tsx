'use client';
import {useState} from 'react';
import {useTranslations} from '../i18n/LanguageProvider';
import {LANGUAGES,setLanguage} from '../i18n/core';
import {useVehicle} from '../context/VehicleContext';
import {useLanguageSwitchLocked} from '../i18n/useLocaleSwitchLock';
/** Voice routing stays internal; the header changes only application language. */
export function LanguageSelector(){
 const {language,text:t}=useTranslations(),{isParked}=useVehicle();
 const locked=useLanguageSwitchLocked(),[error,setError]=useState('');
 return <div className="flex flex-wrap items-center gap-2 min-w-0" data-language-selector>
  <label className="sr-only" htmlFor="attune-language">{t('Uygulama dili')}</label>
  <select id="attune-language" aria-label={t('Uygulama dili')} disabled={!isParked||locked} value={language} className="min-h-11 rounded-xl border border-white/20 bg-slate-950 px-2 text-sm text-white disabled:opacity-50" onChange={e=>{try{const next=e.target.value;if(LANGUAGES.includes(next as typeof language))setLanguage(next as typeof language);setError('');}catch{setError('Dil tercihi kaydedilemedi.');}}}>
   {LANGUAGES.map(id=><option key={id} value={id} lang={id}>{id.toUpperCase()}</option>)}
  </select>
  {locked&&<span role="status" className="max-w-60 text-xs text-slate-300">{t('Devam eden işlem sırasında dil seçimi kilitlidir; ilerlemeniz korunur.')}</span>}
  {error&&<span role="alert" className="max-w-48 text-xs text-amber-200">{t(error)}</span>}
 </div>;
}
