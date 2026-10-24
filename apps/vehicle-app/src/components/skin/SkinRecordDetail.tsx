'use client';
import {useTranslations} from '../../i18n/LanguageProvider';

import {useEffect,useState,useSyncExternalStore} from 'react';
import {REGION_ORDER} from '../../data/skinDemoFixture';
import type {HealthRecord} from '../../utils/healthRecords';
import {SkinRegionNavigator} from './SkinRegionNavigator';
import {SkinIndicatorValue} from './SkinIndicatorValue';
import {SkinFacePanel} from './SkinFacePanel';
import {snapshotAngleForRegion} from '../../utils/skinSnapshot';
import {readSkinSnapshots,skinSnapshotVersion,subscribeSkinSnapshots} from '../../utils/skinVolatileHistory';
import {loadSkinPhotos} from '../../utils/skinPhotoHistory';
import type {SkinSnapshot} from '../../utils/skinSnapshot';
import type {SkinAngle} from '../../utils/skinMultiAngle';
import {buildSkinViewModel, type SkinViewId, SKIN_TYPE_LABELS} from '../../utils/skinOverview';
import {isCriterionApplicableToRegion} from '../../utils/skinIndicators';

/** Numeric history is separate from explicitly permitted local source photos. */
export function SkinRecordDetail({record}:{record:HealthRecord}){
 const {text:i18nText,node:i18nNode}=useTranslations();
 const regions:SkinViewId[]=[...(record.general?['overview' as const]:[]),...REGION_ORDER.filter(id=>Array.isArray(record.indicators?.[id]))];
 const [index,setIndex]=useState(0);
 const [selectedCriterion,setSelectedCriterion]=useState<string|null>(null);
 const version=useSyncExternalStore(subscribeSkinSnapshots,skinSnapshotVersion,()=>0);
 const [stored,setStored]=useState<{id:string;frames:Partial<Record<SkinAngle,SkinSnapshot>>}|null>(null);
 const [photoError,setPhotoError]=useState(false);
 useEffect(()=>{let current=true,revision=0;setStored(null);setPhotoError(false);const refresh=()=>{const ticket=++revision;setStored(null);setPhotoError(false);void loadSkinPhotos(record.id).then(frames=>{if(current&&ticket===revision)setStored(frames?{id:record.id,frames}:null);}).catch(()=>{if(current&&ticket===revision)setPhotoError(true);});};refresh();window.addEventListener('attune-privacy',refresh);window.addEventListener('attune-records',refresh);window.addEventListener('storage',refresh);return()=>{current=false;window.removeEventListener('attune-privacy',refresh);window.removeEventListener('attune-records',refresh);window.removeEventListener('storage',refresh);};},[record.id,version]);
 useEffect(()=>{setIndex(0);setSelectedCriterion(null);},[record.id]);
 const id=regions[index]||regions[0];
 if(!id)return <p>{i18nText("Bu kayıtta bölge ölçümü yok.")}</p>;
 const region={...buildSkinViewModel(id,record),index:index+1,viewTotal:regions.length};
 const snapshot=(stored?.id===record.id?stored.frames:readSkinSnapshots(record.id))?.[snapshotAngleForRegion(id,record.comparisonScope==='three-angle-v2')];
 const selected=selectedCriterion&&isCriterionApplicableToRegion(selectedCriterion,id)?selectedCriterion:null;
 const previous=()=>{setIndex(v=>(v+regions.length-1)%regions.length);};
 const next=()=>{setIndex(v=>(v+1)%regions.length);};
 const visibleIndicators=(region.indicators||[]).filter(v=>isCriterionApplicableToRegion(v.id,id));
 const skinTypeDisplay=region.skinType?.quality==='valid'&&region.skinType.value
  ? SKIN_TYPE_LABELS[region.skinType.value]||region.skinType.value
  : region.skinType?.limitationCode==='INCOMPLETE_CHEEKS_UNVERIFIED'
    ? i18nText('Belirsiz (Yanak verisi eksik)')
    : region.skinType?.limitationCode==='INCOMPLETE_TZONE_UNVERIFIED'
      ? i18nText('Belirsiz (T-bölgesi verisi eksik)')
      : '—';
 return <div className="space-y-4" data-skin-record-carousel>
  <h3 className="font-bold text-lg">{i18nNode(region.nameTr)}</h3>
  {!snapshot&&<p className="text-sm text-slate-400">{i18nNode(photoError?'Kayıtlı fotoğraf açılamadı. Sayısal sonuçlar korunuyor.':'Bu kaydın fotoğrafı saklanmamış.')}</p>}
  <div className={snapshot?'grid lg:grid-cols-2 items-start gap-5':'space-y-4'}>
   {snapshot&&<SkinFacePanel currentRegion={region} snapshot={snapshot} selectedCriterion={selected} onPrev={previous} onNext={next}/>}
   <div className="space-y-3">{id==='overview'&&<div className="rounded-xl border border-white/10 p-4 flex flex-wrap justify-between gap-2" data-skin-type><span>{i18nText("Cilt tipi")}</span><strong>{i18nNode(skinTypeDisplay)}</strong></div>}<div className="grid sm:grid-cols-2 gap-3">{visibleIndicators.map(v=><button type="button" key={v.id} data-skin-record-indicator={v.id} aria-pressed={selected===v.id} onClick={()=>setSelectedCriterion(selected===v.id?null:v.id)} className={`rounded-xl border p-4 space-y-2 text-left ${selected===v.id?'border-togg-turquoise':'border-white/10'}`}><h4 className="text-sm font-semibold">{i18nNode(v.label)}</h4><SkinIndicatorValue indicator={v}/></button>)}</div></div>
  </div>
  {!snapshot&&<SkinRegionNavigator currentRegion={region} total={regions.length} onPrev={previous} onNext={next}/>}
 </div>;
}
