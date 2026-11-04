'use client';
import {useSyncExternalStore} from 'react';

/** The user's own record of a booking made outside Attune.more. Stays on this device. */
export const CARE_APPOINTMENTS_KEY='attune.care.appointments.v1';
export const CARE_REGION_KEY='attune.care.region.v1';
const CHANGE_EVENT='attune-care-appointments';

export type AppointmentType='IN_PERSON'|'ONLINE';
export interface CareAppointment {
 id:string;
 specialty:string;
 provider:string;
 /** The time the provider gave, as entered: YYYY-MM-DDTHH:mm, no conversion. */
 localDateTime:string;
 timeZone:string;
 type:AppointmentType;
 address?:string;
 createdAt:string;
 updatedAt:string;
}
export type AppointmentDraft=Pick<CareAppointment,'specialty'|'provider'|'localDateTime'|'type'|'address'>;

/** Directories the provider layer can open. A region is never inferred from the UI language. */
export const CARE_REGIONS=[
 {city:'İstanbul',country:'Türkiye'},{city:'Ankara',country:'Türkiye'},{city:'İzmir',country:'Türkiye'},
 {city:'Berlin',country:'Almanya'},{city:'Hamburg',country:'Almanya'},{city:'München',country:'Almanya'},{city:'Köln',country:'Almanya'},{city:'Frankfurt',country:'Almanya'},
] as const;

export function readCareRegion():string {
 try {const value=localStorage.getItem(CARE_REGION_KEY);return CARE_REGIONS.some(region=>region.city===value)?value!:'';}catch{return '';}
}
export function writeCareRegion(city:string) {
 try {if(city)localStorage.setItem(CARE_REGION_KEY,city);else localStorage.removeItem(CARE_REGION_KEY);}catch { /* Asked again on the next visit. */ }
}

const LOCAL_TIME=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;
function valid(item:unknown):item is CareAppointment {
 const row=item as CareAppointment;
 return !!row&&typeof row.id==='string'&&typeof row.specialty==='string'&&typeof row.provider==='string'&&LOCAL_TIME.test(row.localDateTime||'')&&
  (row.type==='IN_PERSON'||row.type==='ONLINE')&&typeof row.timeZone==='string';
}
function read():CareAppointment[] {
 const raw=localStorage.getItem(CARE_APPOINTMENTS_KEY);
 if(raw===null)return [];
 const value=JSON.parse(raw);
 if(!Array.isArray(value))throw Error('APPOINTMENTS_UNREADABLE');
 return value.filter(valid);
}
export function readAppointments():CareAppointment[] {try{return read();}catch{return [];}}
function write(rows:CareAppointment[]) {
 const raw=JSON.stringify(rows);localStorage.setItem(CARE_APPOINTMENTS_KEY,raw);
 if(localStorage.getItem(CARE_APPOINTMENTS_KEY)!==raw)throw Error('APPOINTMENTS_WRITE_FAILED');
 cached=null;window.dispatchEvent(new Event(CHANGE_EVENT));
}
export function appointmentProblem(draft:AppointmentDraft):string|null {
 if(!draft.specialty.trim())return 'Branş seçin.';
 if(!draft.provider.trim())return 'Doktor veya kurum adını yazın.';
 if(!LOCAL_TIME.test(draft.localDateTime)||!Number.isFinite(new Date(draft.localDateTime).getTime()))return 'Tarih ve saati girin.';
 return null;
}
export function saveAppointment(draft:AppointmentDraft,id?:string):CareAppointment {
 const problem=appointmentProblem(draft);if(problem)throw Error(problem);
 const rows=read(),now=new Date().toISOString(),previous=id?rows.find(row=>row.id===id):undefined;
 const row:CareAppointment={
  id:previous?.id||crypto.randomUUID(),specialty:draft.specialty.trim(),provider:draft.provider.trim(),localDateTime:draft.localDateTime,
  timeZone:previous&&previous.localDateTime===draft.localDateTime?previous.timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone,
  type:draft.type,...(draft.type==='IN_PERSON'&&draft.address?.trim()?{address:draft.address.trim()}:{}),createdAt:previous?.createdAt||now,updatedAt:now,
 };
 write([row,...rows.filter(item=>item.id!==row.id)]);
 return row;
}
export function deleteAppointment(id:string) {write(read().filter(row=>row.id!==id));}

/** Wall-clock time as entered. It is the provider's time, so the browser zone never shifts it. */
export function formatAppointmentTime(row:Pick<CareAppointment,'localDateTime'>,locale:string):string {
 const parts=LOCAL_TIME.exec(row.localDateTime);if(!parts)return row.localDateTime;
 const [,y,m,d,h,min]=parts.map(Number);
 return new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short',timeZone:'UTC'}).format(new Date(Date.UTC(y,m-1,d,h,min)));
}
export function appointmentIsPast(row:Pick<CareAppointment,'localDateTime'>,now=Date.now()):boolean {return new Date(row.localDateTime).getTime()<now;}
/** Soonest upcoming first, then the most recent past visits. */
export function sortAppointments(rows:CareAppointment[],now=Date.now()):CareAppointment[] {
 const time=(row:CareAppointment)=>new Date(row.localDateTime).getTime();
 const upcoming=rows.filter(row=>time(row)>=now).sort((a,b)=>time(a)-time(b));
 const past=rows.filter(row=>time(row)<now).sort((a,b)=>time(b)-time(a));
 return [...upcoming,...past];
}

let cached:CareAppointment[]|null=null;
const EMPTY:CareAppointment[]=[];
function snapshot(){return cached||(cached=readAppointments());}
function subscribe(listener:()=>void) {
 const change=()=>{cached=null;listener();};
 window.addEventListener('storage',change);window.addEventListener(CHANGE_EVENT,change);window.addEventListener('attune-privacy',change);
 return ()=>{window.removeEventListener('storage',change);window.removeEventListener(CHANGE_EVENT,change);window.removeEventListener('attune-privacy',change);};
}
export function useAppointments(){return useSyncExternalStore(subscribe,snapshot,()=>EMPTY);}
