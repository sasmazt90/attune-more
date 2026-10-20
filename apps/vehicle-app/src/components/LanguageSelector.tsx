'use client';
import {apiFetch as fetch} from '../utils/localBackend';
import {useEffect,useState} from 'react';
import {useTranslations} from '../i18n/LanguageProvider';
import {LANGUAGES,LOCALES,setLanguage} from '../i18n/core';
import {systemVoiceChoices,VoiceChoice} from '../i18n/voices';
import {useVehicle} from '../context/VehicleContext';
import {AccessibleDialog} from './AccessibleDialog';
import {localBackend} from '../utils/localBackend';
import {approvedClip} from '../i18n/approvedAudio';
import {HEALTH_MODULE_IDS,HEALTH_MODULES} from '../utils/healthModules';
import {useLanguageSwitchLocked} from '../i18n/useLocaleSwitchLock';
export function LanguageSelector(){
 const {language,text:t}=useTranslations(),{isParked}=useVehicle();
 const [open,setOpen]=useState(false),[error,setError]=useState(''),[voices,setVoices]=useState<VoiceChoice[]>([]),[edge,setEdge]=useState<VoiceChoice[]>([]),[loading,setLoading]=useState(false);
 const locked=useLanguageSwitchLocked(),permitted=isParked&&!locked;
 useEffect(()=>{
  const update=()=>setVoices(typeof speechSynthesis==='undefined'?[]:systemVoiceChoices(speechSynthesis.getVoices(),language));
  update();if(typeof speechSynthesis==='undefined')return;
  speechSynthesis.addEventListener('voiceschanged',update);return()=>speechSynthesis.removeEventListener('voiceschanged',update);
 },[language]);
 useEffect(()=>{setEdge([]);setError('');},[language]);
 useEffect(()=>{if(!permitted)setOpen(false);},[permitted]);
 return <div className="flex flex-wrap items-center gap-2 min-w-0" data-language-selector>
  <label className="sr-only" htmlFor="attune-language">{t('Uygulama dili')}</label>
  <select id="attune-language" aria-label={t('Uygulama dili')} disabled={!permitted} value={language} className="min-h-11 rounded-xl border border-white/20 bg-slate-950 px-2 text-sm text-white disabled:opacity-50" onChange={e=>{try{const next=e.target.value;if(LANGUAGES.includes(next as typeof language))setLanguage(next as typeof language);}catch{setError('Dil tercihi kaydedilemedi.');}}}>
   {LANGUAGES.map(id=><option key={id} value={id} lang={id}>{id.toUpperCase()}</option>)}
  </select>
  <button type="button" disabled={!permitted} onClick={()=>setOpen(true)} className="min-h-11 px-2 rounded-xl border border-white/20 text-xs disabled:opacity-50" aria-label={t('Ses seçenekleri')}>{t('Ses')}</button>
  {locked&&<span role="status" className="max-w-60 text-xs text-slate-300">{t('Devam eden işlem sırasında dil ve ses seçimi kilitlidir; ilerlemeniz korunur.')}</span>}
  {error&&!open&&<span role="alert" className="max-w-48 text-xs text-amber-200">{t(error)}</span>}
  {open&&<AccessibleDialog title={t('Dil ve ses seçenekleri')} onClose={()=>setOpen(false)} className="w-full max-w-xl rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
   <h2 className="text-lg font-bold">{t('Dil ve ses seçenekleri')}</h2>
   <p className="text-sm">{t('Seçilen dil')} {LOCALES[language]}. {t('Dil tercihi kayıtları, izinleri veya değerlendirme ilerlemesini sıfırlamaz.')}</p>
   <p className="text-sm">{t('Onaylı sesler sağlık modülüne göre seçilir. Başka ses veya dil otomatik olarak kullanılmaz.')}</p>
   <ul className="text-sm space-y-1">{HEALTH_MODULE_IDS.map(module=>{const clip=approvedClip(language,module,module==='vision'?'vision:prepare':module==='mental'?'guidance:mental-entry':module==='skin'?'guidance:skin-front':module==='dental'?'guidance:dental-front':'guidance:hearing-prepare');return <li key={module}>{t(HEALTH_MODULES[module].name)}: {clip?.voice} · {clip?.voiceLocale}</li>;})}</ul>
   <p role="status" className="text-sm text-amber-200">{t('Sabit kayıtlar canlı konuşma sentezi değildir. Dinamik yanıtlar aynı kadın sesini gerektirir; canlı sağlayıcı kullanılamazsa sesli yanıt durdurulur.')}</p>
   {voices.length===0&&<p role="status" className="text-sm text-amber-200">{t('Bu dil için sistem sesi bulunamadı. Başka bir dilin sesi kullanılmaz.')}</p>}
   <ul className="text-xs text-slate-300">{[...voices,...edge].map(v=><li key={v.provider+v.id}>{v.name} · {v.locale} · {t(v.gender==='male'?'Erkek':v.gender==='female'?'Kadın':'Cinsiyet bilgisi yok')} · {t(v.local?'Cihazda':'Çevrimiçi')}</li>)}</ul>
   <p className="text-xs text-slate-300">{t('Tarayıcı sesleri cinsiyet bilgisi sağlamaz; isimden cinsiyet tahmin edilmez. Ses envanteri onaylı modül eşlemelerini değiştirmez.')}</p>
   <button type="button" disabled={loading||!permitted} className="min-h-11 px-4 border border-white/20 rounded-xl" onClick={async()=>{setLoading(true);setError('');try{const r=await fetch(localBackend('/api/speech/voices'));if(!r.ok)throw Error();const data=await r.json();if(!Array.isArray(data.voices))throw Error();setEdge(data.voices);if(!data.voices.length)setError('Microsoft ses kataloğuna ulaşılamadı veya eşleşen ses yok.');}catch{setError('Microsoft ses kataloğuna ulaşılamadı veya eşleşen ses yok.');}finally{setLoading(false);}}}>{t(loading?'Sesler sorgulanıyor…':'Ücretsiz Microsoft seslerini sorgula')}</button>
   <p className="text-xs text-slate-400">{t('Çevrimiçi seslendirme ayrıca ilgili hizmet izninizi gerektirir. Ücretli hizmet kullanılmaz. İşitme testinin onaylı sayı kayıtları ses tercihiyle değiştirilmez.')}</p>
   {error&&<p role="alert" className="text-sm text-amber-200">{t(error)}</p>}
   <button type="button" className="min-h-11 px-4 border border-white/20 rounded-xl" onClick={()=>setOpen(false)}>{t('Kapat')}</button>
  </AccessibleDialog>}
 </div>;
}
