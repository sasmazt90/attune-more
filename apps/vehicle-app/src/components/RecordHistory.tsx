'use client';
import { PRODUCT_NAME } from '../utils/brand';
import Link from 'next/link';
import {useEffect,useRef,useState} from 'react';
import {AccessibleDialog} from './AccessibleDialog';
import {InformationButton} from './InformationButton';
import {ResultValue} from './ResultValue';
import {SkinRecordDetail} from './skin/SkinRecordDetail';
import {DentalRecordDetail} from './DentalRecordDetail';
import {LetterVisionResult} from './LetterVisionResult';
import {ContinuousVisionResult,OrientationResult} from './ContinuousVisionResult';
import {LetterResult,isLetterProtocol} from '../utils/spokenVision';
import {spokenText} from '../utils/spokenText';
import {translateMood} from '../utils/mentalHistory';
import {HealthCategory,HealthRecord,prepareHealthRecords,deleteHealthRecord,recordDate,RECORD_LABELS} from '../utils/healthRecords';
import {HEALTH_MODULE_IDS,HEALTH_MODULES,careHref} from '../utils/healthModules';
type Row={category:HealthCategory;record:HealthRecord};
const button='min-h-11 px-4 rounded-xl border border-white/20 disabled:opacity-40';
function status(category:HealthCategory,r:HealthRecord){if(category==='skin')return r.analysisMode==='instant-appearance-v2'?'Anlık görünüm':r.isBaseline?'Referans taraması':r.comparisonUnavailable?'Karşılaştırma yok':'Analiz sonucu';return category==='mental'?'Tamamlanan görüşme':'Tamamlanan ön değerlendirme';}
export function RecordHistory({category='all',parked}:{category?:HealthCategory|'all';parked:boolean}){
 const [rows,setRows]=useState<Row[]>([]),[filter,setFilter]=useState<HealthCategory|'all'>('all'),[selected,setSelected]=useState<Row|null>(null),[viewed,setViewed]=useState<Row|null>(null),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
 const inFlight=useRef(false),heading=useRef<HTMLHeadingElement>(null),parkedRef=useRef(parked);parkedRef.current=parked;
 useEffect(()=>{let live=true;let generation=0;const refresh=async()=>{const run=++generation;setLoading(true);const types=category==='all'?HEALTH_MODULE_IDS:[category];const results=await Promise.allSettled(types.map(async c=>({category:c,records:await prepareHealthRecords(c)})));if(!live||run!==generation)return;const next:Row[]=[];const failed:string[]=[];results.forEach((v,i)=>{if(v.status==='fulfilled')v.value.records.forEach(record=>next.push({category:v.value.category,record}));else failed.push(RECORD_LABELS[types[i]]);});next.sort((a,b)=>Date.parse(b.record.timestamp||b.record.date||b.record.completedAt||'')-Date.parse(a.record.timestamp||a.record.date||a.record.completedAt||''));setRows(next);setNotice(failed.length?failed.join(', ')+': kayıtlar okunamadı; veriler korunuyor.':'');setLoading(false);};void refresh();window.addEventListener('attune-records',refresh);window.addEventListener('storage',refresh);return()=>{live=false;window.removeEventListener('attune-records',refresh);window.removeEventListener('storage',refresh);};},[category]);
 useEffect(()=>{if(viewed&&!rows.some(v=>v.category===viewed.category&&v.record.id===viewed.record.id))setViewed(null);},[rows,viewed]);
 const remove=async()=>{if(!selected||!parkedRef.current||inFlight.current)return;inFlight.current=true;setBusy(true);try{setNotice(await deleteHealthRecord(selected.category,selected.record.id));setSelected(null);requestAnimationFrame(()=>heading.current?.focus());}catch(error){setNotice((error as Error).message);}finally{inFlight.current=false;setBusy(false);}};
 const list=rows.filter(v=>filter==='all'||v.category===filter);
 const closeDelete=()=>{if(!inFlight.current){setSelected(null);}};
 return <section data-record-history={category} className="space-y-3">
  <h2 ref={heading} tabIndex={-1} className="font-bold">{category==='all'?'Sağlık kayıtları':RECORD_LABELS[category]+' kayıtları'}</h2>
  {category==='all'&&<div className="flex flex-wrap gap-2" aria-label="Kayıt türü"><button className={button} aria-pressed={filter==='all'} onClick={()=>setFilter('all')}>Tümü</button>{HEALTH_MODULE_IDS.map(c=><button key={c} className={button} aria-pressed={filter===c} onClick={()=>setFilter(c)}>{HEALTH_MODULES[c].name}</button>)}</div>}
  <p className="text-sm text-slate-400">{loading?'Kayıtlar hazırlanıyor…':list.length+' kayıt'}</p>
  {notice&&<p role="status" className="text-sm text-amber-200">{notice}</p>}
  {!loading&&!list.length&&<p className="text-sm text-slate-400">Henüz kayıt yok.</p>}
  {list.map(v=><article key={v.category+v.record.id} data-record-id={v.record.id} data-record-category={v.category} className="rounded-xl border border-white/10 p-4 space-y-3 min-w-0">
   <div className="flex flex-wrap justify-between items-start gap-2"><p className="text-sm font-semibold">{RECORD_LABELS[v.category]}</p><time className="text-sm text-slate-400">{recordDate(v.record)}</time></div>
   <ResultValue value={null} status={status(v.category,v.record)}/>
   <div className="flex flex-wrap gap-2"><button className={button} disabled={!parked||busy} aria-haspopup="dialog" onClick={()=>{setViewed(v);}}>Sonucu Aç</button><button className={button+' border-rose-400/40 text-rose-200'} disabled={!parked||busy} aria-label={RECORD_LABELS[v.category]+' kaydını sil: '+recordDate(v.record)} onClick={()=>{setNotice('');setSelected(v);}}>Sil</button></div>
  </article>)}
  {viewed&&<AccessibleDialog title={RECORD_LABELS[viewed.category]+' sonucu'} onClose={()=>{setViewed(null);}} className="w-full max-w-3xl rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
   <div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-3"><h2 className="text-lg font-bold">{RECORD_LABELS[viewed.category]}</h2>{viewed.category==='vision'&&<InformationButton title="Görme görevi ve hizmet bilgisi"><p>Bu görev klinik görme keskinliği veya göz numarası ölçmez. Kamera pikselleri ve göz başlangıcı yalnız cihaz belleğinde değerlendirilir. Görüntü aynasızdır; sağ ve sol, kendi anatomik gözünüzdür. Mutlak uzaklık ölçülmez.</p></InformationButton>}{viewed.category!=='vision'&&<InformationButton title="Kayıt bilgisi"><ul className="list-disc pl-5 space-y-3"><li>Yalnız bu oturumda kaydedilen sayısal sonuçlar gösterilir.</li><li>{viewed.category==='dental'?'Diş fotoğrafı yalnız ayrı saklama izniyle bu cihazda tutulur.':'Fotoğraf ve ham ses geçmişe eklenmez.'}</li>{viewed.category==='dental'&&<li>Kaynak: {viewed.record.sourceType==='upload'?'Yüklenen tek fotoğraf':'Kamera'}</li>}</ul></InformationButton>}</div><time className="text-sm text-slate-400">{recordDate(viewed.record)}</time></div><button className={button} aria-label="Sonuç penceresini kapat" onClick={()=>{setViewed(null);}}>✕</button></div>
   <RecordDetail key={viewed.record.id} row={viewed}/>

   <Link className={button+' inline-flex items-center'} href={careHref(viewed.category,undefined,viewed.record.id)}>Uzman seçenekleri</Link>
  </AccessibleDialog>}
  {selected&&<AccessibleDialog title="Bu kaydı silmek istiyor musunuz?" onClose={closeDelete} className="w-full max-w-lg rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4"><h2 className="text-lg font-bold">Bu kaydı silmek istiyor musunuz?</h2><p>{RECORD_LABELS[selected.category]} · {recordDate(selected.record)}</p><p className="text-sm">Bu işlem geri alınamaz.</p><div className="flex flex-wrap gap-3"><button className={button} disabled={busy} onClick={closeDelete}>Hayır, vazgeç</button><button className={button+' bg-rose-700'} disabled={busy||!parked} onClick={()=>void remove()}>{busy?'Siliniyor…':'Evet, sil'}</button></div></AccessibleDialog>}
 </section>;
}
function RecordDetail({row:{category,record:r}}:{row:Row}){
 if(category==='vision')return isLetterProtocol(r.protocolVersion)?<LetterVisionResult result={r as LetterResult} showReferral={false}/>:Array.isArray(r.trials)&&['landolt-orientation-guided-v2','landolt-orientation-continuous-v1'].includes(r.protocolVersion)?<ContinuousVisionResult result={r as OrientationResult}/>:<p>Eski protokol · {r.acuityRightSnellen||'—'} / {r.acuityLeftSnellen||'—'}</p>;
 if(category==='mental')return <div className="space-y-4"><p className="text-sm">Başlangıç: {r.startedAt?new Date(r.startedAt).toLocaleString('tr-TR'):'Başlangıç zamanı kaydedilmemiş.'} · Bitiş: {r.completedAt?new Date(r.completedAt).toLocaleString('tr-TR'):'Bitiş zamanı kaydedilmemiş.'}</p><div data-session-transcript className="space-y-3">{r.transcriptConsented&&Array.isArray(r.transcript)?r.transcript.filter((m:any)=>['USER','AI'].includes(m.sender)&&typeof m.text==='string').map((m:any,i:number)=><article key={i} data-session-author={m.sender} className="p-3 rounded-xl border border-white/10"><p className="text-xs text-slate-400">{m.sender==='USER'?'Siz':PRODUCT_NAME}</p><p className="text-sm whitespace-pre-line break-words">{spokenText(m.text)}</p></article>):<p className="text-sm text-slate-400">Bu kayıtta konuşma dökümü bulunmuyor.</p>}</div><h3>Özet</h3><p className="text-sm whitespace-pre-line break-words" data-summary-provider={r.providerType}>{spokenText(translateMood(r.summaryText||'Özet bulunmuyor.'))}</p></div>;
 if(category==='skin')return r.indicators?<SkinRecordDetail key={r.id} record={r}/>:<p>{r.clinicalNoteTr||'Bu kayıtta bölge ölçümü yok.'}</p>;
 if(category==='hearing')return r.thresholds?<div className="grid sm:grid-cols-2 gap-3">{r.thresholds.map((t:any,i:number)=><p key={i} className="text-sm">{t.ear==='left'?'Sol':'Sağ'} · {t.frequency} Hz{t.repeat?' tekrar':''}: {t.value===null?'Eşik bulunamadı':t.value+' dBFS peak'}</p>)}</div>:<div><p>{r.validTrials} geçerli üçlü · {(Number.isFinite(r.digitAccuracy)?Math.round(r.digitAccuracy*100):'—')}% doğru sayı</p><ResultValue value={r.value} status={r.value===null?'Kararlı eşik bulunamadı':undefined} unit="dB SNR"/></div>;
 return <DentalRecordDetail key={r.id} record={r}/>;
}
