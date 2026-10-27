'use client';
import {useRef,useState,type TouchEvent} from 'react';
import {ArrowLeft,ArrowRight,CircleCheck,Minus,TriangleAlert,ScanLine} from 'lucide-react';
import {useTranslations} from '../../i18n/LanguageProvider';
import {InformationButton} from '../InformationButton';
import {AccessibleDialog} from '../AccessibleDialog';
import {DENTAL_ACCUMULATION_LABEL,DENTAL_POSE_LABELS,DENTAL_QUALITY_REASONS,dentalViewMeasured} from '../../utils/dentalResult';
import {DentalPhotoView,DENTAL_LAYER_COLORS,type DentalLayer} from './DentalPhotoView';
import type {DentalCapture,DentalPose} from '../../utils/dentalCapture';
import styles from './dental.module.css';

type Photo=Pick<DentalCapture,'photo'|'width'|'height'>|undefined;
type Slide={pose:DentalPose;view?:any;photo:Photo};
const ORDER:DentalPose[]=['FRONT','RIGHT','LEFT','BITE'];
const status=(v:any)=>!v?'missing':dentalViewMeasured(v)?'measured':'unmeasured';
function useSwipe(onChange:(delta:number)=>void){
 const start=useRef<{x:number;y:number}|null>(null);
 return {onTouchStart:(e:TouchEvent)=>{const t=e.changedTouches[0];start.current={x:t.clientX,y:t.clientY};},onTouchEnd:(e:TouchEvent)=>{const s=start.current;start.current=null;if(!s)return;const t=e.changedTouches[0],dx=t.clientX-s.x,dy=t.clientY-s.y;if(Math.abs(dx)>65&&Math.abs(dx)>Math.abs(dy)*1.5)onChange(dx<0?1:-1);}};
}
function Title({icon,heading:title,info}:{icon?:React.ReactNode;heading:string;info:React.ReactNode}){
 const {text:t}=useTranslations();
 return <div className={styles.titleRow}><h3>{icon}{t(title)}</h3><InformationButton title={title}>{info}</InformationButton></div>;
}
/** Shared by the live result and by history records (record photos only). */
export function DentalResults({views,photos,missingViews=[],sourceType,footer}:{views:any[];photos:Photo[];missingViews?:string[];sourceType?:string;footer?:React.ReactNode}){
 const {text:t,locale}=useTranslations(),[tab,setTab]=useState(0),[index,setIndex]=useState(0),[layer,setLayer]=useState<DentalLayer|null>(null),[noteOpen,setNoteOpen]=useState(false);
 const slides:Slide[]=sourceType==='upload'?views.map((v,i)=>({pose:v.pose,view:v,photo:photos[i]})):ORDER.filter(p=>views.some(v=>v.pose===p)||missingViews.includes(p)).map(p=>{const i=views.findIndex(v=>v.pose===p);return {pose:p,view:i>=0?views[i]:undefined,photo:i>=0?photos[i]:undefined};});
 const measured=views.filter(dentalViewMeasured),expected=sourceType==='upload'?views.length:4;
 const unmeasured=slides.filter(s=>status(s.view)!=='measured');
 const fmt=(n:number,d=0)=>new Intl.NumberFormat(locale,{maximumFractionDigits:d}).format(n);
 const pose=(p:string)=>t(sourceType==='upload'?'Yüklenen fotoğraf':DENTAL_POSE_LABELS[p]||p);
 const cariesText=(v:any)=>!v?t('Alınmadı'):!dentalViewMeasured(v)?t('Ölçülemedi'):t(`${v.caries.value} görünür aday`);
 const accText=(v:any)=>!v?t('Alınmadı'):!dentalViewMeasured(v)?t('Ölçülemedi'):v.accumulation?.quality!=='valid'||v.accumulation.value===null?t('Diş-dişeti sınırı görünmedi'):`${fmt(v.accumulation.value)}%`;
 const alignmentView=views.find(v=>v.alignment?.quality==='valid')||views.find(v=>v.pose==='BITE')||(sourceType==='upload'?views[0]:undefined);
 const alignmentRows=(v:any)=>v?.alignment?.quality==='valid'&&v.alignment.rows?Object.entries(v.alignment.rows) as [string,any][]:[];
 const alignmentStatus=sourceType!=='upload'&&missingViews.includes('BITE')?t('Kapanış görünümü alınmadı'):!alignmentView?t('Kapanış görünümü alınmadı'):!dentalViewMeasured(alignmentView)?t('Ölçülemedi'):alignmentView.alignment?.quality!=='valid'?t(sourceType==='upload'?'Bu fotoğrafta iki diş sırası birlikte ayrılamadı.':'Diş konturları güvenilir ayrılamadı.'):'';
 const rowText=(row:any)=>row?.quality==='valid'&&Number.isFinite(row.value)?t(`${fmt(row.value)}° yön dağılımı · ${row.contourCount} kontur`):t('Konturlar güvenilir ayrılamadı.');
 const go=(i:number)=>{setIndex(i);setLayer(null);setTab(1);};
 const swipe=useSwipe(d=>{setIndex(i=>Math.max(0,Math.min(slides.length-1,i+d)));setLayer(null);});
 const s=slides[Math.min(index,slides.length-1)],v=s?.view,layers:DentalLayer[]=layer?[layer]:['caries','alignment']; // build-up marks only on request (dense, unvalidated)
 const statusIcon=(st:string)=>st==='measured'?<CircleCheck aria-hidden="true"/>:st==='missing'?<Minus aria-hidden="true"/>:<TriangleAlert aria-hidden="true"/>;
 const statusText=(st:string)=>t(st==='measured'?'Ölçüldü':st==='missing'?'Alınmadı':'Ölçülemedi');
 return <div className={styles.root} data-dental-result data-dental-measured={measured.length} data-dental-expected={expected}>
  <nav className={styles.tabs} aria-label={t('Sonuç sayfaları')}>{['Genel bakış','Görünümler'].map((name,i)=><button key={name} type="button" aria-current={tab===i?'page':undefined} onClick={()=>setTab(i)}>{t(name)}</button>)}</nav>
  {tab===0?<div data-dental-overview>
   <h2>{t(measured.length===expected?'Görünür diş yüzeyleri ölçüldü.':measured.length?'Bazı görünümler ölçülemedi.':'Görünümler ölçülemedi.')}</h2>
   <p className={styles.lead}>{t('İşaretleri fotoğraf üzerinde Görünümler sekmesinde inceleyebilirsiniz.')}</p>
   <div className={styles.cards}>
    <section className={styles.card} data-dental-card="coverage"><Title icon={<ScanLine aria-hidden="true"/>} heading="Ölçülen görünümler" info={<p>{t('Her görünüm yalnız kendi fotoğrafında değerlendirilir. Ölçülemeyen veya alınmayan görünüm sağlıklı kabul edilmez.')}</p>}/>
     <p className={styles.value}>{fmt(measured.length)}<small>/ {fmt(expected)}</small></p>
     <div className={styles.poses}>{slides.map((x,i)=>{const st=status(x.view);return <button key={x.pose+i} type="button" className={`${styles.pose} ${st==='measured'?styles.ok:st==='missing'?styles.miss:styles.bad}`} onClick={()=>go(i)} data-dental-pose-status={x.pose+':'+st}>{statusIcon(st)}<span>{pose(x.pose)}</span><span>{statusText(st)}</span></button>;})}</div>
     {unmeasured.length>0&&<button type="button" className={styles.note} onClick={()=>setNoteOpen(true)} data-dental-measurement-note><TriangleAlert aria-hidden="true"/>{t('Ölçüm notu')}</button>}
    </section>
    <section className={styles.card} data-dental-card="caries"><Title heading="Çürük adayı" info={<><p>{t('Model, fotoğrafta görünen kalıcı diş yüzeylerinde çürük olabilecek alanları işaretler. Aday; tanı, şiddet veya derinlik bilgisi değildir.')}</p><p>{t('Aynı diş birden fazla görünümde yer alabilir; bu nedenle sayılar görünümler arasında toplanmaz.')}</p></>}/>
     <div className={styles.rows}>{slides.map((x,i)=><div key={x.pose+i}><span>{pose(x.pose)}</span><strong className={status(x.view)==='measured'?'':styles.na}>{cariesText(x.view)}</strong></div>)}</div>
    </section>
    <section className={styles.card} data-dental-card="accumulation"><Title heading={DENTAL_ACCUMULATION_LABEL} info={<><p>{t('Diş ile dişeti sınırında renk ve doku görünümünden hesaplanır; görünen sınır alanının yüzdesi olarak verilir.')}</p><p>{t('Leke, yiyecek artığı ve dolgu bu görünümle karışabilir. Diş taşı tanısı değildir.')}</p></>}/>
     <div className={styles.rows}>{slides.map((x,i)=><div key={x.pose+i}><span>{pose(x.pose)}</span><strong className={status(x.view)==='measured'&&x.view?.accumulation?.quality==='valid'?'':styles.na}>{accText(x.view)}</strong></div>)}</div>
    </section>
    <section className={styles.card} data-dental-card="alignment"><Title heading="Ön diş dizilimi" info={<><p>{t('Ön dişler birbirine değerken çekilen kapanış görünümünde, ayrı seçilebilen diş konturlarının yön farkı hesaplanır.')}</p><p>{t('Perspektif sonucu etkiler; çapraşıklık veya kapanış bozukluğu tanısı değildir.')}</p></>}/>
     {alignmentStatus?<p className={styles.warning} data-dental-alignment-unavailable>{alignmentStatus}</p>:<div className={styles.rows}>{alignmentRows(alignmentView).map(([row,x])=><div key={row}><span>{t(row==='upper'?'Üst sıra':'Alt sıra')}</span><strong className={x?.quality==='valid'?'':styles.na}>{rowText(x)}</strong></div>)}</div>}
    </section>
   </div>
  </div>:<div data-dental-views>
   <div {...swipe} aria-roledescription="carousel" aria-label={t('Diş görünümleri')}>
    {s&&<div className={styles.viewGrid} data-dental-slide={s.pose} data-dental-slide-status={status(v)}>
     {s.photo&&v?<div className={styles.photo}><DentalPhotoView photo={s.photo} view={v} layers={dentalViewMeasured(v)?layers:[]}/></div>:<div className={styles.photoEmpty}>{t(!v?'Bu görünüm alınmadı.':'Bu kayıtta fotoğraf saklanmadı.')}</div>}
     <section className={styles.card}>
      <div className={styles.cardHead}><h3>{pose(s.pose)}</h3><span className={styles.label} style={{color:status(v)==='measured'?'var(--cyan)':'var(--warn)'}}>{statusIcon(status(v))}<span style={{marginLeft:6}}>{statusText(status(v))}</span></span></div>
      {!v?<p className={styles.warning}>{t(s.pose==='BITE'?'Kapanış görünümü atlandı; dizilim ölçülmedi.':'Bu görünüm alınmadı.')}</p>
      :!dentalViewMeasured(v)?<><p className={styles.warning}>{t('Bu görünüm için sonuç üretilmedi.')}</p><ul className="list-disc pl-5 space-y-2 text-sm text-slate-300">{(v.quality?.reasons||[]).map((r:string)=><li key={r}>{t(DENTAL_QUALITY_REASONS[r]||'Fotoğraf koşulları uygun değildi.')}</li>)}</ul><p>{t('Daha iyi ışıkta ve sabit durarak yeniden tararsanız bu görünüm için de sonuç alabilirsiniz.')}</p></>
      :<><p>{t('Bir satıra dokunarak yalnız o işaretleri gösterebilirsiniz.')}</p><div className={styles.rows}>
        <button type="button" aria-pressed={layer==='caries'} onClick={()=>setLayer(l=>l==='caries'?null:'caries')} data-dental-layer="caries"><span className={styles.label}><i className={styles.swatch} style={{background:DENTAL_LAYER_COLORS.caries}}/>{t('Çürük adayı')}</span><strong>{cariesText(v)}</strong></button>
        <button type="button" aria-pressed={layer==='accumulation'} onClick={()=>setLayer(l=>l==='accumulation'?null:'accumulation')} data-dental-layer="accumulation"><span className={styles.label}><i className={styles.swatch} style={{background:DENTAL_LAYER_COLORS.accumulation}}/>{t(DENTAL_ACCUMULATION_LABEL)}</span><strong className={v.accumulation?.quality==='valid'?'':styles.na}>{accText(v)}</strong></button>
        {v.alignment?.quality==='valid'?alignmentRows(v).map(([row,x])=><button key={row} type="button" aria-pressed={layer==='alignment'} onClick={()=>setLayer(l=>l==='alignment'?null:'alignment')} data-dental-layer="alignment"><span className={styles.label}><i className={styles.swatch} style={{background:DENTAL_LAYER_COLORS.alignment}}/>{t(row==='upper'?'Üst sıra dizilimi':'Alt sıra dizilimi')}</span><strong className={x?.quality==='valid'?'':styles.na}>{rowText(x)}</strong></button>)
         :<div><span className={styles.label}><i className={styles.swatch} style={{background:DENTAL_LAYER_COLORS.alignment}}/>{t('Dizilim')}</span><strong className={styles.na}>{t(v.pose==='BITE'||sourceType==='upload'?'Konturlar güvenilir ayrılamadı.':'Kapanış görünümünde ölçülür')}</strong></div>}
       </div></>}
     </section>
    </div>}
    {slides.length>1&&<div className={styles.innerFooter}><button type="button" className={styles.arrow} disabled={index===0} aria-label={t('Önceki diş görünümü')} onClick={()=>{setIndex(i=>Math.max(0,i-1));setLayer(null);}}><ArrowLeft aria-hidden="true"/></button><div><span>{pose(s.pose)} · {fmt(index+1)} / {fmt(slides.length)}</span><div className={styles.dots}>{slides.map((x,i)=><button key={x.pose+i} type="button" aria-label={pose(x.pose)} aria-current={index===i?'true':undefined} onClick={()=>{setIndex(i);setLayer(null);}}><b/></button>)}</div></div><button type="button" className={styles.arrow} disabled={index===slides.length-1} aria-label={t('Sonraki diş görünümü')} onClick={()=>{setIndex(i=>Math.min(slides.length-1,i+1));setLayer(null);}}><ArrowRight aria-hidden="true"/></button></div>}
   </div>
  </div>}
  {footer}
  <p className={styles.disclaimer}>{t('Tıbbi teşhis içermez; ön değerlendirme amaçlıdır.')}</p>
  {noteOpen&&<AccessibleDialog title={t('Ölçüm notu')} onClose={()=>setNoteOpen(false)} className="w-full max-w-lg rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
   <div className="flex items-start justify-between gap-3"><h2 className="text-lg font-bold">{t('Ölçüm notu')}</h2><button type="button" aria-label={t('Bilgi penceresini kapat')} onClick={()=>setNoteOpen(false)} className="min-h-11 min-w-11 rounded-xl border border-white/20">✕</button></div>
   <ul className="list-disc pl-5 space-y-3 text-sm text-slate-300">{unmeasured.map(x=><li key={x.pose}><strong>{pose(x.pose)}</strong>{': '}{!x.view?t(x.pose==='BITE'?'Kapanış görünümü atlandı.':'Bu görünüm alınmadı.'):(x.view.quality?.reasons||[]).map((r:string)=>t(DENTAL_QUALITY_REASONS[r]||'Fotoğraf koşulları uygun değildi.')).join(' ')}</li>)}</ul>
   <p className="text-sm text-slate-300">{t('Daha iyi ışıkta ve sabit durarak yeniden tararsanız bu görünümler için de sonuç alabilirsiniz.')}</p>
  </AccessibleDialog>}
 </div>;
}
