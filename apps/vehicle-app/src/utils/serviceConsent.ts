'use client';
import {useSyncExternalStore} from 'react';
import {cloudSpeechEnabled,CLOUD_SPEECH_PERMISSION,CLOUD_SPEECH_COPY} from './speechProvider';

export const SERVICE_CONSENT_KEY='attune_health_processing_v1';
const BASE_SERVICE_REQUIREMENTS={
 skin:[['local','Attune.more\'nun yüz görüntümü ve görünüm göstergelerimi geçici olarak işlemesine izin veriyorum.']],
 dental:[['local','Attune.more\'nun diş fotoğraflarımı geçici olarak işlemesine izin veriyorum.']],
 hearing:[['local','Attune.more\'nun kulaklık sesleri ve yanıtlarımla işitme testi yapmasına izin veriyorum.']],
 vision:[['local','Attune.more\'nun kamera görüntümü ve konuşma yanıtlarımı göz görevi için geçici olarak işlemesine izin veriyorum.'],['speech','Attune.more\'nun sesli yönerge vermesine ve konuşma yanıtlarımı tanımasına izin veriyorum. Tanıma için sesim buluta aktarılabilir.']],
 mental:[['recognition','Attune.more\'nun sesimi metne çevirmesine izin veriyorum. Bunun için sesim buluta aktarılabilir.'],['conversation','Attune.more\'nun konuşma metnimi yanıtlar, geçici oturum belleği ve özet için işlemesine izin veriyorum.'],['speech-output-v2','Attune.more\'nun yanıtlarını seçtiğim dilde kendi sesiyle veya seçtiğim tarayıcı ya da cihaz sesiyle okumasına izin veriyorum. Çevrimiçi tarayıcı sesi için ayrıca izin istenir.']]
} as const;
export type HealthService=keyof typeof BASE_SERVICE_REQUIREMENTS;
const cloudRequirements=cloudSpeechEnabled()?[[CLOUD_SPEECH_PERMISSION,CLOUD_SPEECH_COPY] as const]:[];
export const SERVICE_REQUIREMENTS:Record<HealthService,readonly (readonly [string,string])[]>={
 ...BASE_SERVICE_REQUIREMENTS,
 vision:[...BASE_SERVICE_REQUIREMENTS.vision,...cloudRequirements],
 mental:[...BASE_SERVICE_REQUIREMENTS.mental,...cloudRequirements],
};
export const MENTAL_HISTORY_PERMISSION='prior-summaries-v1';
export const MENTAL_HISTORY_COPY='İsteğe bağlı: İlgili önceki görüşme özetlerimin yeni Attune.more özetinde kullanılmasına izin veriyorum. Bu izin olmadan da görüşmeye başlayabilirim.';
type ConsentDocument={version:1;services:Partial<Record<HealthService,{at:string;permissions:string[];optionalPermissions?:string[]}>>};
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
export function mentalHistoryAllowed():boolean {
 try{const optional=readDocument().services.mental?.optionalPermissions;return serviceAllowed('mental')&&Array.isArray(optional)&&optional.includes(MENTAL_HISTORY_PERMISSION);}catch{return false;}
}
export function setMentalHistoryConsent(allowed:boolean){
 const doc=readDocument(),record=doc.services.mental;
 if(!record||!serviceAllowed('mental'))throw Error('SERVICE_PERMISSION_REQUIRED');
 record.optionalPermissions=allowed?[MENTAL_HISTORY_PERMISSION]:[];
 writeDocument(doc);
}
function writeDocument(doc:ConsentDocument){
 const raw=JSON.stringify(doc);localStorage.setItem(SERVICE_CONSENT_KEY,raw);
 if(localStorage.getItem(SERVICE_CONSENT_KEY)!==raw)throw Error('CONSENT_WRITE_FAILED');
 window.dispatchEvent(new Event('attune-service-consent'));window.dispatchEvent(new Event('attune-privacy'));
}
export function setServiceConsent(service:HealthService,permissions:string[]|null,priorSummaries=false) {
 const doc=readDocument();
 if(permissions===null)delete doc.services[service];
 else {
  if(!SERVICE_REQUIREMENTS[service].every(([id])=>permissions.includes(id)))throw Error('EXPLICIT_PERMISSIONS_REQUIRED');
  doc.services[service]={at:new Date().toISOString(),permissions:SERVICE_REQUIREMENTS[service].map(([id])=>id),...(service==='mental'?{optionalPermissions:priorSummaries?[MENTAL_HISTORY_PERMISSION]:[]}: {})};
 }
 writeDocument(doc);
}
function subscribe(listener:()=>void) {
 window.addEventListener('storage',listener);window.addEventListener('attune-service-consent',listener);
 return ()=>{window.removeEventListener('storage',listener);window.removeEventListener('attune-service-consent',listener);};
}
export function useServiceAllowed(service:HealthService){return useSyncExternalStore(subscribe,()=>serviceAllowed(service),()=>false);}
export function useMentalHistoryAllowed(){return useSyncExternalStore(subscribe,mentalHistoryAllowed,()=>false);}
