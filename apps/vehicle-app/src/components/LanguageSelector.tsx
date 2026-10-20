'use client';
import {apiFetch as fetch} from '../utils/localBackend';
import {useEffect,useState} from 'react';
import {useTranslations} from '../i18n/LanguageProvider';
import {LANGUAGES,LOCALES,setLanguage,VOICE_EVENT} from '../i18n/core';
import {systemVoiceChoices,setVoicePreference,voicePreference,VoiceChoice} from '../i18n/voices';
import {useVehicle} from '../context/VehicleContext';
import {AccessibleDialog} from './AccessibleDialog';
import {localBackend} from '../utils/localBackend';
import {recordedProfile} from '../i18n/fixedAudio';
import {useLanguageSwitchLocked} from '../i18n/useLocaleSwitchLock';
export function LanguageSelector(){
 const {language,text:t}=useTranslations(),{isParked}=useVehicle();
 const [open,setOpen]=useState(false),[error,setError]=useState(''),[voices,setVoices]=useState<VoiceChoice[]>([]),[edge,setEdge]=useState<VoiceChoice[]>([]),[loading,setLoading]=useState(false),[,setRevision]=useState(0);
 const locked=useLanguageSwitchLocked(),permitted=isParked&&!locked;
 const choice=voicePreference(language);
 const fixed=[recordedProfile(language,'male'),recordedProfile(language,'female')].filter((v):v is NonNullable<typeof v>=>!!v);
 const [dynamicLocal,setDynamicLocal]=useState<string[]|null>(null);
 useEffect(()=>{
  const update=()=>setVoices(typeof speechSynthesis==='undefined'?[]:systemVoiceChoices(speechSynthesis.getVoices(),language));
  update();if(typeof speechSynthesis==='undefined')return;
  speechSynthesis.addEventListener('voiceschanged',update);return()=>speechSynthesis.removeEventListener('voiceschanged',update);
 },[language]);
 useEffect(()=>{const refresh=()=>setRevision(v=>v+1);window.addEventListener(VOICE_EVENT,refresh);return()=>window.removeEventListener(VOICE_EVENT,refresh);},[]);
 useEffect(()=>{setEdge([]);setError('');setDynamicLocal(null);},[language]);
 useEffect(()=>{if(!open||language==='tr')return;let mounted=true;const controller=new AbortController();const deadline=setTimeout(()=>controller.abort(),15000);void fetch(localBackend('/api/speech/local-voices'),{signal:controller.signal}).then(r=>r.ok?r.json():Promise.reject()).then(data=>{if(mounted)setDynamicLocal(Array.isArray(data.voices)?data.voices.map((v:VoiceChoice)=>v.id):[]);}).catch(()=>{if(mounted)setDynamicLocal([]);}).finally(()=>clearTimeout(deadline));return()=>{mounted=false;controller.abort();clearTimeout(deadline);};},[open,language]);
 useEffect(()=>{if(!permitted)setOpen(false);},[permitted]);
 const choose=(value:string)=>{try{if(value==='approved')setVoicePreference(language,{provider:'approved'});else{const found=[...voices,...fixed,...edge].find(v=>v.id===value);if(found)setVoicePreference(language,{provider:found.provider,voiceId:found.id,gender:found.gender});}}catch{setError('Ses tercihi kaydedilemedi.');}};
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
   <label className="block text-sm">{t('Ses seçimi')}<select className="block w-full min-h-11 mt-2 bg-slate-950 border border-white/20 rounded-xl px-3" value={choice.provider==='approved'?'approved':choice.voiceId||''} onChange={e=>choose(e.target.value)}>
    {language==='tr'&&<option value="approved">{t('Onaylı Türkçe kayıtlar ve mevcut Microsoft profilleri')}</option>}
    <option value="" disabled>{t(choice.provider==='system'&&!choice.voiceId?'Otomatik eşleşen sistem sesi':'Kullanılabilir bir ses seçin')}</option>
    {choice.voiceId&&![...voices,...fixed,...edge].some(v=>v.id===choice.voiceId)&&<option value={choice.voiceId} disabled>{t('Kayıtlı ses şu anda doğrulanamadı; başka bir ses seçebilirsiniz.')} ({choice.voiceId})</option>}
    {[...voices,...fixed,...edge].map(v=><option key={v.provider+v.id} value={v.id}>{v.name} · {v.locale} · {t(v.gender==='male'?'Erkek':v.gender==='female'?'Kadın':'Cinsiyet bilgisi yok')} · {t(v.provider==='local'?'Yeni yerel sentez kayıtları':v.local?'Cihazda':'Çevrimiçi')}</option>)}
   </select></label>
   {choice.provider==='system'&&voices.some(v=>v.id===choice.voiceId&&!v.local)&&<label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={choice.onlineConsent===true} onChange={e=>{try{setVoicePreference(language,{...choice,onlineConsent:e.target.checked});}catch{setError('Ses tercihi kaydedilemedi.');}}}/><span>{t('Yanıt metnimin seçtiğim çevrimiçi sistem sesinde işlenmesine izin veriyorum.')}</span></label>}
   {voices.length===0&&<p role="status" className="text-sm text-amber-200">{t('Bu dil için sistem sesi bulunamadı. Başka bir dilin sesi kullanılmaz.')}</p>}
   {choice.provider==='local'&&<p role="status" className="text-sm">{t(dynamicLocal===null?'Yeni kayıtlar yönergeler için hazır; serbest metin seslendirmesi doğrulanıyor.':dynamicLocal.includes(choice.voiceId||'')?'Yerel serbest metin seslendirmesi doğrulandı.':'Yönerge kayıtları kullanılabilir; bu sunucuda yerel serbest metin seslendirmesi kullanılamıyor.')}</p>}
   <p className="text-xs text-slate-300">{t('Tarayıcı sesleri cinsiyet bilgisi sağlamaz; isimden cinsiyet tahmin edilmez. Onaylı Türkçe kayıtlar değiştirilmez. Yeni sentez, onaylı kayıt değildir.')}</p>
   <button type="button" disabled={loading||!permitted} className="min-h-11 px-4 border border-white/20 rounded-xl" onClick={async()=>{setLoading(true);setError('');try{const r=await fetch(localBackend('/api/speech/voices'));if(!r.ok)throw Error();const data=await r.json();if(!Array.isArray(data.voices))throw Error();setEdge(data.voices);if(!data.voices.length)setError('Microsoft ses kataloğuna ulaşılamadı veya eşleşen ses yok.');}catch{setError('Microsoft ses kataloğuna ulaşılamadı veya eşleşen ses yok.');}finally{setLoading(false);}}}>{t(loading?'Sesler sorgulanıyor…':'Ücretsiz Microsoft seslerini sorgula')}</button>
   <p className="text-xs text-slate-400">{t('Çevrimiçi seslendirme ayrıca ilgili hizmet izninizi gerektirir. Ücretli hizmet kullanılmaz. İşitme testinin onaylı sayı kayıtları ses tercihiyle değiştirilmez.')}</p>
   {error&&<p role="alert" className="text-sm text-amber-200">{t(error)}</p>}
   <button type="button" className="min-h-11 px-4 border border-white/20 rounded-xl" onClick={()=>setOpen(false)}>{t('Kapat')}</button>
  </AccessibleDialog>}
 </div>;
}
