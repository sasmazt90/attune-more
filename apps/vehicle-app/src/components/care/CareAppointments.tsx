'use client';
import {useState} from 'react';
import {CalendarCheck,MapPin,Pencil,Trash2,Video} from 'lucide-react';
import {AccessibleDialog} from '../AccessibleDialog';
import {useTranslations} from '../../i18n/LanguageProvider';
import {
 AppointmentDraft,AppointmentType,CareAppointment,appointmentIsPast,appointmentProblem,deleteAppointment,
 formatAppointmentTime,saveAppointment,sortAppointments,useAppointments,
} from '../../utils/careAppointments';

const emptyDraft=(specialty='',provider=''):AppointmentDraft=>({specialty,provider,localDateTime:'',type:'IN_PERSON',address:''});
const field='mt-1 block w-full min-h-11 rounded-lg border border-white/20 bg-slate-900 px-3 text-base';

export function AppointmentForm({initial,editing,specialties,onDone}:{initial:AppointmentDraft;editing?:string;specialties:string[];onDone:()=>void}) {
 const {text:i18nText,node:i18nNode}=useTranslations();
 const [draft,setDraft]=useState(initial),[error,setError]=useState('');
 const change=(values:Partial<AppointmentDraft>)=>{setDraft(current=>({...current,...values}));setError('');};
 const submit=()=>{
  const problem=appointmentProblem(draft);
  if(problem){setError(problem);return;}
  try{saveAppointment(draft,editing);onDone();}catch{setError('Randevu kaydedilemedi. Tarayıcı depolama ayarlarını kontrol edin.');}
 };
 return <AccessibleDialog title={i18nText(editing?'Randevuyu düzenle':'Randevuyu kaydet')} onClose={onDone} className="max-w-xl w-full rounded-2xl bg-cockpit-surface border border-white/20 p-6 space-y-4">
  <h2 className="text-xl font-bold">{i18nText(editing?'Randevuyu düzenle':'Randevuyu kaydet')}</h2>
  <p className="text-sm text-slate-300">{i18nText('Bu kayıt yalnız bu cihazda saklanır ve sağlayıcıya gönderilmez.')}</p>
  <label className="block text-sm font-medium">{i18nText('Branş')}
   <select data-appointment-specialty value={draft.specialty} onChange={event=>change({specialty:event.target.value})} className={field}>
    <option value="">{i18nText('Branş seçin')}</option>
    {[...new Set([...specialties,draft.specialty].filter(Boolean))].map(item=><option key={item} value={item}>{i18nText(item)}</option>)}
   </select>
  </label>
  <label className="block text-sm font-medium">{i18nText('Doktor veya kurum')}
   <input data-appointment-provider type="text" maxLength={120} value={draft.provider} onChange={event=>change({provider:event.target.value})} className={field}/>
  </label>
  <label className="block text-sm font-medium">{i18nText('Tarih ve saat')}
   <input data-appointment-time type="datetime-local" value={draft.localDateTime} onChange={event=>change({localDateTime:event.target.value})} className={field}/>
  </label>
  <fieldset className="text-sm">
   <legend className="font-medium">{i18nText('Görüşme türü')}</legend>
   <div className="mt-1 flex flex-wrap gap-4">
    {(['IN_PERSON','ONLINE'] as AppointmentType[]).map(type=><label key={type} className="flex min-h-11 items-center gap-2"><input data-appointment-type={type} type="radio" name="appointment-type" className="h-5 w-5" checked={draft.type===type} onChange={()=>change({type})}/>{i18nText(type==='IN_PERSON'?'Yüz yüze':'Online')}</label>)}
   </div>
  </fieldset>
  {draft.type==='IN_PERSON'&&<label className="block text-sm font-medium">{i18nText('Adres (isteğe bağlı)')}
   <input data-appointment-address type="text" maxLength={240} value={draft.address||''} onChange={event=>change({address:event.target.value})} className={field}/>
  </label>}
  {error&&<p role="alert" className="text-sm text-amber-200">{i18nNode(error)}</p>}
  <div data-dialog-actions className="flex flex-wrap justify-end gap-3">
   <button type="button" onClick={onDone} className="min-h-11 px-4 rounded-xl border border-white/20 text-sm">{i18nText('Vazgeç')}</button>
   <button type="button" data-appointment-save onClick={submit} className="min-h-11 px-5 rounded-xl bg-togg-turquoise text-togg-darkBlue text-sm font-semibold">{i18nText('Kaydet')}</button>
  </div>
 </AccessibleDialog>;
}

function AppointmentRow({row,onEdit,onDelete}:{row:CareAppointment;onEdit:()=>void;onDelete:()=>void}) {
 const {locale,text:i18nText,node:i18nNode}=useTranslations();
 const past=appointmentIsPast(row),zone=Intl.DateTimeFormat().resolvedOptions().timeZone;
 return <article data-appointment-row data-appointment-past={past} className="rounded-xl border border-white/10 bg-slate-950/60 p-4 flex flex-wrap items-start justify-between gap-3">
  <div className="min-w-0 space-y-1">
   <p className="text-base font-semibold break-words">{row.provider}</p>
   <p className="text-sm text-slate-300">{i18nNode(row.specialty)}</p>
   <p className="text-sm text-togg-turquoise">{formatAppointmentTime(row,locale)}{past?<span className="ml-2 text-slate-400">{i18nText('Geçti')}</span>:null}</p>
   {row.timeZone!==zone&&<p className="text-sm text-slate-400">{i18nText('Kaydedildiği saat dilimi: ')}{row.timeZone}</p>}
   <p className="flex items-center gap-1.5 text-sm text-slate-300">
    {row.type==='ONLINE'?<Video className="w-4 h-4 shrink-0" aria-hidden="true"/>:<MapPin className="w-4 h-4 shrink-0" aria-hidden="true"/>}
    <span className="break-words">{i18nText(row.type==='ONLINE'?'Online':'Yüz yüze')}</span>
    {row.type==='IN_PERSON'&&row.address?<span data-appointment-address-value className="break-words">{row.address}</span>:null}
   </p>
  </div>
  <div className="flex gap-2">
   <button type="button" data-appointment-edit aria-label={i18nText('Randevuyu düzenle')} onClick={onEdit} className="min-h-11 min-w-11 inline-flex items-center justify-center rounded-xl border border-white/20"><Pencil className="w-4 h-4" aria-hidden="true"/></button>
   <button type="button" data-appointment-delete aria-label={i18nText('Randevuyu sil')} onClick={onDelete} className="min-h-11 min-w-11 inline-flex items-center justify-center rounded-xl border border-white/20"><Trash2 className="w-4 h-4" aria-hidden="true"/></button>
  </div>
 </article>;
}

export function CareAppointments({specialties,defaultSpecialty,requestedDraft,onRequestHandled}:{specialties:string[];defaultSpecialty:string;requestedDraft:AppointmentDraft|null;onRequestHandled:()=>void}) {
 const {text:i18nText}=useTranslations();
 const rows=sortAppointments(useAppointments());
 const [editing,setEditing]=useState<CareAppointment|null>(null),[adding,setAdding]=useState(false),[deleting,setDeleting]=useState<CareAppointment|null>(null),[error,setError]=useState('');
 const close=()=>{setEditing(null);setAdding(false);onRequestHandled();};
 const form=requestedDraft||(adding?emptyDraft(defaultSpecialty):null);
 return <section data-care-appointments className="space-y-3">
  <div className="flex flex-wrap items-center justify-between gap-3">
   <h2 className="flex items-center gap-2 text-lg font-bold"><CalendarCheck className="w-5 h-5 text-togg-turquoise" aria-hidden="true"/>{i18nText('Randevularım')}</h2>
   <button type="button" data-appointment-add onClick={()=>setAdding(true)} className="min-h-11 px-4 rounded-xl border border-togg-turquoise/40 text-sm font-semibold text-togg-turquoise">{i18nText('Randevu ekle')}</button>
  </div>
  {rows.length===0
   ?<p data-appointments-empty className="text-sm text-slate-300">{i18nText('Kayıtlı randevunuz yok. Sağlayıcıda aldığınız randevuyu buraya ekleyebilirsiniz.')}</p>
   :<div className="grid gap-3 md:grid-cols-2 short:grid-cols-2">{rows.map(row=><AppointmentRow key={row.id} row={row} onEdit={()=>setEditing(row)} onDelete={()=>{setError('');setDeleting(row);}}/>)}</div>}
  {form&&<AppointmentForm initial={form} specialties={specialties} onDone={close}/>}
  {editing&&<AppointmentForm editing={editing.id} initial={{specialty:editing.specialty,provider:editing.provider,localDateTime:editing.localDateTime,type:editing.type,address:editing.address||''}} specialties={specialties} onDone={close}/>}
  {deleting&&<AccessibleDialog title={i18nText('Randevuyu sil')} onClose={()=>setDeleting(null)} className="max-w-md w-full rounded-2xl bg-cockpit-surface border border-white/20 p-6 space-y-4">
   <h2 className="text-xl font-bold">{i18nText('Randevuyu sil')}</h2>
   <p className="text-sm text-slate-300">{i18nText('Bu kayıt yalnız bu cihazdan silinir. Sağlayıcıdaki randevunuz iptal edilmez.')}</p>
   {error&&<p role="alert" className="text-sm text-amber-200">{i18nText(error)}</p>}
   <div data-dialog-actions className="flex flex-wrap justify-end gap-3">
    <button type="button" onClick={()=>setDeleting(null)} className="min-h-11 px-4 rounded-xl border border-white/20 text-sm">{i18nText('Vazgeç')}</button>
    <button type="button" data-appointment-delete-confirm onClick={()=>{try{deleteAppointment(deleting.id);setDeleting(null);}catch{setError('Randevu silinemedi.');}}} className="min-h-11 px-5 rounded-xl bg-rose-700 text-sm font-semibold">{i18nText('Sil')}</button>
   </div>
  </AccessibleDialog>}
 </section>;
}

export {emptyDraft};
