'use client';
import {useEffect,useState} from 'react';
import {ChevronLeft,ChevronRight} from 'lucide-react';
import {loadDentalPhotos,DentalFrames} from '../utils/dentalPhotoHistory';
import {validateDentalView} from '../utils/dentalResult';
import {DentalSourceView} from './DentalSourceView';
import type {HealthRecord} from '../utils/healthRecords';
export function DentalRecordDetail({record}:{record:HealthRecord}){
 const [index,setIndex]=useState(0),views=Array.isArray(record.measurements)?record.measurements:[];
 const [photos,setPhotos]=useState<DentalFrames>();
 useEffect(()=>{let live=true,generation=0;const refresh=async()=>{const run=++generation;setPhotos(undefined);try{const frames=await loadDentalPhotos(record.id);if(live&&run===generation)setPhotos(frames);}catch{/* Preserve numeric data; never reconstruct a missing/corrupt source. */}};void refresh();window.addEventListener('attune-privacy',refresh);window.addEventListener('storage',refresh);return()=>{live=false;window.removeEventListener('attune-privacy',refresh);window.removeEventListener('storage',refresh);};},[record.id]);
 const v=views[index];if(!v)return <p>Bu kayıtta ölçüm yok.</p>;
 return <div className="space-y-4" data-dental-record-carousel>
  {photos?.[index]&&(()=>{try{validateDentalView(v,photos[index]);return <DentalSourceView photo={photos[index]} view={v}/>;}catch{return null;}})()}
  <h3 className="font-bold">{v.pose==='BITE'?'Kapanış görünümü':v.pose==='RIGHT'?'Sağ':v.pose==='LEFT'?'Sol':'Ön'}</h3>
  <div className="grid sm:grid-cols-2 gap-3">
   <div className="rounded-xl border border-white/10 p-4"><h4 className="font-bold">Çürük adayı</h4><p>{v.caries?.value==null?'—':v.caries.value+' görünür aday'}</p></div>
   <div className="rounded-xl border border-white/10 p-4"><h4 className="font-bold">Birikim görünümü</h4><p>{v.accumulation?.value==null?'—':Math.round(v.accumulation.value)+'% görünür sınır alanı'}</p></div>
   {v.alignment?.rows&&Object.entries(v.alignment.rows).map(([side,x]:[string,any])=><div key={side} className="rounded-xl border border-white/10 p-4"><h4 className="font-bold">{side==='upper'?'Üst':'Alt'} dizilim</h4><p>{x.value==null?'—':Math.round(x.value)+'° yön dağılımı'}</p></div>)}
  </div>
  {views.length>1&&<div className="flex justify-center items-center gap-5"><button aria-label="Önceki diş görünümü" className="min-w-11 min-h-11 rounded-full border border-togg-turquoise/50 text-togg-turquoise flex items-center justify-center" onClick={()=>setIndex(i=>(i+views.length-1)%views.length)}><ChevronLeft/></button><span>{index+1} / {views.length}</span><button aria-label="Sonraki diş görünümü" className="min-w-11 min-h-11 rounded-full border border-togg-turquoise/50 text-togg-turquoise flex items-center justify-center" onClick={()=>setIndex(i=>(i+1)%views.length)}><ChevronRight/></button></div>}
 </div>;
}
