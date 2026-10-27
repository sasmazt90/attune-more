'use client';
import {useTranslations} from '../i18n/LanguageProvider';

import {useEffect,useState} from 'react';
import {loadDentalPhotos,DentalFrames} from '../utils/dentalPhotoHistory';
import {validateDentalView} from '../utils/dentalResult';
import {DentalResults} from './dental/DentalResults';
import type {HealthRecord} from '../utils/healthRecords';
/** History detail: this record's own stored photos only (never the live scan). */
export function DentalRecordDetail({record}:{record:HealthRecord}){
 const {text:i18nText}=useTranslations();
 const views=Array.isArray(record.measurements)?record.measurements:[];
 const [photos,setPhotos]=useState<DentalFrames>();
 useEffect(()=>{let live=true,generation=0;const refresh=async()=>{const run=++generation;setPhotos(undefined);try{const frames=await loadDentalPhotos(record.id);if(live&&run===generation)setPhotos(frames);}catch{/* Preserve numeric data; never reconstruct a missing/corrupt source. */}};void refresh();window.addEventListener('attune-privacy',refresh);window.addEventListener('storage',refresh);return()=>{live=false;window.removeEventListener('attune-privacy',refresh);window.removeEventListener('storage',refresh);};},[record.id]);
 if(!views.length)return <p>{i18nText("Bu kayıtta ölçüm yok.")}</p>;
 // A photo is shown only when its stored pixels/identity match this view.
 const matched=views.map((v:any,i:number)=>{const f=photos?.[i];if(!f)return undefined;try{validateDentalView(v,f);return {photo:f.photo,width:f.width,height:f.height};}catch{return undefined;}});
 const missing=Array.isArray((record as any).missingViews)?(record as any).missingViews:[];
 return <div data-dental-record-carousel data-dental-record={record.id}><DentalResults views={views} photos={matched} missingViews={missing} sourceType={record.sourceType as string|undefined}/></div>;
}
