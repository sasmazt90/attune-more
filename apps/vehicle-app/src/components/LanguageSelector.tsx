'use client';
import {usePathname} from 'next/navigation';
import {useEffect,useRef,useState} from 'react';
import {useTranslations} from '../i18n/LanguageProvider';
import {LANGUAGES,LOCALES,setLanguage} from '../i18n/core';
import {systemVoiceChoices,VoiceChoice} from '../i18n/voices';
import {useVehicle} from '../context/VehicleContext';
import {AccessibleDialog} from './AccessibleDialog';
import {mentalSystemSpeech} from '../i18n/systemSpeech';
import {mentalSystemVoices,mentalVoicePreference,setMentalVoicePreference,selectMentalSystemVoice,type MentalVoicePreference} from '../i18n/mentalVoices';
import {approvedClip} from '../i18n/approvedAudio';
import {HEALTH_MODULE_IDS,HEALTH_MODULES} from '../utils/healthModules';
import {useLanguageSwitchLocked} from '../i18n/useLocaleSwitchLock';
export function LanguageSelector(){
 const {language,text:t}=useTranslations(),{isParked}=useVehicle();
 const [open,setOpen]=useState(false),[error,setError]=useState(''),[voices,setVoices]=useState<VoiceChoice[]>([]),[allVoices,setAllVoices]=useState<SpeechSynthesisVoice[]>([]),[preference,setPreference]=useState<MentalVoicePreference>({}),[sample,setSample]=useState(''),[preview,setPreview]=useState('');
 const pathname=usePathname();
 const locked=useLanguageSwitchLocked(),permitted=isParked&&!locked;
 const previewController=useRef<AbortController|null>(null);
 const close=()=>{previewController.current?.abort();previewController.current=null;setSample('');setPreview('');setOpen(false);};
 const changePreference=(value:MentalVoicePreference)=>{previewController.current?.abort();previewController.current=null;try{setMentalVoicePreference(language,value);setPreference(value);setPreview('');}catch{setError('Dil tercihi kaydedilemedi.');}};
 const eligible=mentalSystemVoices(allVoices,language),selectedVoice=selectMentalSystemVoice(allVoices,language,preference);
 useEffect(()=>{
  const update=()=>{const all=typeof speechSynthesis==='undefined'?[]:speechSynthesis.getVoices();setAllVoices(all);setVoices(systemVoiceChoices(all,language));};
  update();if(typeof speechSynthesis==='undefined')return;
  speechSynthesis.addEventListener('voiceschanged',update);return()=>speechSynthesis.removeEventListener('voiceschanged',update);
 },[language]);
 useEffect(()=>{previewController.current?.abort();previewController.current=null;setPreference(mentalVoicePreference(language));setSample('');setPreview('');setError('');},[language]);
 useEffect(()=>{previewController.current?.abort();previewController.current=null;setSample('');setPreview('');},[pathname]);
 useEffect(()=>()=>{previewController.current?.abort();previewController.current=null;},[]);
 useEffect(()=>{if(!permitted){previewController.current?.abort();previewController.current=null;setOpen(false);}},[permitted]);
 return <div className="flex flex-wrap items-center gap-2 min-w-0" data-language-selector>
  <label className="sr-only" htmlFor="attune-language">{t('Uygulama dili')}</label>
  <select id="attune-language" aria-label={t('Uygulama dili')} disabled={!permitted} value={language} className="min-h-11 rounded-xl border border-white/20 bg-slate-950 px-2 text-sm text-white disabled:opacity-50" onChange={e=>{try{const next=e.target.value;if(LANGUAGES.includes(next as typeof language))setLanguage(next as typeof language);}catch{setError('Dil tercihi kaydedilemedi.');}}}>
   {LANGUAGES.map(id=><option key={id} value={id} lang={id}>{id.toUpperCase()}</option>)}
  </select>
  <button type="button" disabled={!permitted} onClick={()=>setOpen(true)} className="min-h-11 px-2 rounded-xl border border-white/20 text-xs disabled:opacity-50" aria-label={t('Ses seçenekleri')}>{t('Ses')}</button>
  {locked&&<span role="status" className="max-w-60 text-xs text-slate-300">{t('Devam eden işlem sırasında dil ve ses seçimi kilitlidir; ilerlemeniz korunur.')}</span>}
  {error&&!open&&<span role="alert" className="max-w-48 text-xs text-amber-200">{t(error)}</span>}
  {open&&<AccessibleDialog title={t('Dil ve ses seçenekleri')} onClose={close} className="w-full max-w-xl rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
   <h2 className="text-lg font-bold">{t('Dil ve ses seçenekleri')}</h2>
   <p className="text-sm">{t('Seçilen dil')} {LOCALES[language]}. {t('Dil tercihi kayıtları, izinleri veya değerlendirme ilerlemesini sıfırlamaz.')}</p>
   <p className="text-sm">{t('Onaylı sesler sağlık modülüne göre seçilir. Başka ses veya dil otomatik olarak kullanılmaz.')}</p>
   <ul className="text-sm space-y-1">{HEALTH_MODULE_IDS.map(module=>{const clip=approvedClip(language,module,module==='vision'?'vision:prepare':module==='mental'?'guidance:mental-entry':module==='skin'?'guidance:skin-front':module==='dental'?'guidance:dental-front':'guidance:hearing-prepare');return <li key={module}>{t(HEALTH_MODULES[module].name)}: {clip?.voice} · {clip?.voiceLocale}</li>;})}</ul>
   <p role="status" className="text-sm text-amber-200">{t('Sabit kayıtlar değişmez. Dinamik Mental yanıtları, seçilen dilde doğrulanmış bir kadın tarayıcı veya cihaz sesi gerektirir.')}</p>
   {voices.length===0&&<p role="status" className="text-sm text-amber-200">{t('Bu dil için sistem sesi bulunamadı. Başka bir dilin sesi kullanılmaz.')}</p>}
   <ul className="text-xs text-slate-300">{voices.map(v=><li key={v.provider+v.id}>{v.name} · {v.locale} · {t(v.gender==='male'?'Erkek':v.gender==='female'?'Kadın':'Cinsiyet bilgisi yok')} · {t(v.local?'Cihazda':'Çevrimiçi')}</li>)}</ul>
   <p className="text-xs text-slate-300">{t('Tarayıcı sesleri cinsiyet bilgisi sağlamaz; isimden cinsiyet tahmin edilmez. Ses envanteri onaylı modül eşlemelerini değiştirmez.')}</p>
   {pathname!=='/'&&<p role="status" className="text-xs text-amber-200">{t('Ses denemesini Kokpit sayfasında yapın; sağlık görevlerinin sesli kontrolleriyle çakışmaz.')}</p>}
   <fieldset className="min-w-0 space-y-3 border-t border-white/15 pt-3" data-mental-system-voice>
    <legend>{t('Dinamik Mental sesi')}</legend>
    <label className="block text-sm">{t('Kadın sistem sesi')}<select className="block w-full min-w-0 max-w-full min-h-11 bg-slate-950 border border-white/20 rounded-xl p-2" value={preference.voiceId||''} disabled={!permitted} onChange={e=>changePreference({voiceId:e.target.value||undefined,onlineConsent:false})}>
     <option value="">{t('Uygun kadın sesini otomatik seç')}</option>
     {preference.voiceId&&!eligible.some(v=>v.voiceURI===preference.voiceId)&&<option value={preference.voiceId} disabled>{t('Kaydedilmiş ses bu cihazda bulunamadı.')}</option>}
     {eligible.map(v=><option key={v.voiceURI} value={v.voiceURI}>{v.name} · {v.lang} · {t(v.localService?'Cihazda':'Çevrimiçi')}</option>)}
    </select></label>
    <p className="text-xs text-slate-300">{t('Yalnız üretici kataloğunda kadın olarak tanımlanan ve tarayıcıda gerçekten bulunan sesler seçilebilir. Bilinmeyen seslerin cinsiyeti tahmin edilmez.')}</p>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={preference.onlineConsent===true} disabled={!permitted} onChange={e=>changePreference({...preference,onlineConsent:e.target.checked})}/>{t('Seçili tarayıcı sesinin çevrimiçi sağlayıcısına dinamik yanıt metni gönderilmesine izin veriyorum.')}</label>
    <p role="status" className="text-xs text-amber-200">{selectedVoice?selectedVoice.name+' · '+selectedVoice.lang:t('Uygun kadın sesi bulunamadı veya çevrimiçi ses izni verilmedi. Başka dil veya erkek ses kullanılmaz.')}</p>
    <label className="block text-sm">{t('Kişisel olmayan ses deneme metni')}<textarea className="block w-full bg-slate-950 border border-white/20 rounded-xl p-2" rows={2} maxLength={500} value={sample} onChange={e=>setSample(e.target.value)}/></label>
    <p className="text-xs text-slate-300">{t('Deneme metni saklanmaz. Bu yalnız ses motoru denemesidir; mikrofon veya yapay zekâ görüşmesi başlatmaz.')}</p>
    <button type="button" className="min-h-11 px-3 border border-white/20 rounded-xl disabled:opacity-40" disabled={!permitted||pathname!=='/'||!sample.trim()||!selectedVoice||['starting','speaking'].includes(preview)} onClick={async()=>{previewController.current?.abort();const controller=new AbortController();previewController.current=controller;setPreview('starting');try{const played=await mentalSystemSpeech(sample,controller.signal,()=>previewController.current===controller,()=>{if(previewController.current===controller)setPreview('speaking');});if(previewController.current===controller)setPreview(played?'Ses denemesi tamamlandı.':'Ses denemesi tamamlanamadı.');}catch{if(previewController.current===controller)setPreview('Ses denemesi tamamlanamadı.');}}}>{t('Dinamik sesi dene')}</button>
    <button type="button" className="min-h-11 px-3 border border-white/20 rounded-xl" onClick={()=>{previewController.current?.abort();previewController.current=null;setPreview('');}}>{t('Durdur')}</button>
    {preview&&<p role="status">{preview==='speaking'?t('Seslendiriliyor'):preview==='starting'?t('Ses hazırlanıyor'):t(preview)}</p>}
   </fieldset>
   {error&&<p role="alert" className="text-sm text-amber-200">{t(error)}</p>}
   <button type="button" className="min-h-11 px-4 border border-white/20 rounded-xl" onClick={close}>{t('Kapat')}</button>
  </AccessibleDialog>}
 </div>;
}
