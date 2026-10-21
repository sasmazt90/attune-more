'use client';
import {useSyncExternalStore} from 'react';

export const SERVICE_CONSENT_KEY='attune_health_processing_v1';
export const SERVICE_REQUIREMENTS={
 skin:[['local','Yüz görüntümün ve görünüm göstergelerimin bu cihazda geçici işlenmesine izin veriyorum.']],
 dental:[['local','Diş fotoğraflarımın bu cihazda geçici işlenmesine izin veriyorum.']],
 hearing:[['local','Kulaklık sesleri ve yanıtlarımla yerel işitme testinin yapılmasına izin veriyorum.']],
 vision:[['local','Kamera görüntüsü ve konuşma yanıtlarımın göz görevi için geçici işlenmesine izin veriyorum.'],['speech','Yönerge metinlerinin Microsoft Edge Türkçe ses hizmetinde işlenmesine ve tarayıcı konuşma tanıma hizmetini kullanmaya izin veriyorum.']],
 mental:[['recognition','Sesimin tarayıcı/cihaz konuşma tanıma hizmetinde metne çevrilmesine izin veriyorum; bu hizmet sesi buluta aktarabilir.'],['conversation','Konuşma metnimin yanıt, geçici oturum belleği ve özet için OpenAI tarafından işlenmesine izin veriyorum.'],['speech','Yanıt metninin seçtiğim dilde yerel Chatterbox modeliyle veya açıkça seçtiğim tarayıcı/cihaz sesiyle okunmasına izin veriyorum. Çevrimiçi tarayıcı sesi için ayrıca sağlayıcı izni gerekir.']]
} as const;
export type HealthService=keyof typeof SERVICE_REQUIREMENTS;
type ConsentDocument={version:1;services:Partial<Record<HealthService,{at:string;permissions:string[]}>>};
function readDocument():ConsentDocument {
 const raw=localStorage.getItem(SERVICE_CONSENT_KEY);
 if(raw===null)return {version:1,services:{}};
 const value=JSON.parse(raw);
 if(value?.version!==1||!value.services||typeof value.services!=='object')throw Error('CONSENT_STORAGE_INVALID');
 return value;
}
export function serviceAllowed(service:HealthService):boolean {
 try {const record=readDocument().services[service];return Array.isArray(record?.permissions)&&SERVICE_REQUIREMENTS[service].every(([id])=>record!.permissions.includes(id));}catch{return false;}
}
export function setServiceConsent(service:HealthService,permissions:string[]|null) {
 const doc=readDocument();
 if(permissions===null)delete doc.services[service];
 else {
  if(!SERVICE_REQUIREMENTS[service].every(([id])=>permissions.includes(id)))throw Error('EXPLICIT_PERMISSIONS_REQUIRED');
  doc.services[service]={at:new Date().toISOString(),permissions:SERVICE_REQUIREMENTS[service].map(([id])=>id)};
 }
 const raw=JSON.stringify(doc);localStorage.setItem(SERVICE_CONSENT_KEY,raw);
 if(localStorage.getItem(SERVICE_CONSENT_KEY)!==raw)throw Error('CONSENT_WRITE_FAILED');
 window.dispatchEvent(new Event('attune-service-consent'));window.dispatchEvent(new Event('attune-privacy'));
}
function subscribe(listener:()=>void) {
 window.addEventListener('storage',listener);window.addEventListener('attune-service-consent',listener);
 return ()=>{window.removeEventListener('storage',listener);window.removeEventListener('attune-service-consent',listener);};
}
export function useServiceAllowed(service:HealthService){return useSyncExternalStore(subscribe,()=>serviceAllowed(service),()=>false);}
