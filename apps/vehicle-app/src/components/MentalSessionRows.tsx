'use client';
import {getLocale} from '../i18n/core';
import {useTranslations} from '../i18n/LanguageProvider';

import { PRODUCT_NAME } from '../utils/brand';
import { useEffect, useState } from 'react';
import { AccessibleDialog } from './AccessibleDialog';
import { HealthRecord, recordDate } from '../utils/healthRecords';
import { spokenText } from '../utils/spokenText';
import { translateMood } from '../utils/mentalHistory';

export function MentalSessionRows({records,onDelete,parked,busy}:{records:HealthRecord[];onDelete:(record:HealthRecord)=>void;parked:boolean;busy:boolean}){
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [opened,setOpened]=useState<string|null>(null);
  const selected=records.find(r=>r.id===opened);
  useEffect(()=>{if(opened&&!records.some(r=>r.id===opened))setOpened(null);},[opened,records]);
  const validDate=(value:unknown)=>typeof value==='string'&&Number.isFinite(Date.parse(value));
  const label=(record:HealthRecord)=>validDate(record.startedAt)?new Date(record.startedAt).toLocaleString(getLocale()):`Başlangıç kaydı yok · Özet: ${recordDate(record)}`;
  const sorted=[...records].sort((a,b)=>{
    const aa=validDate(a.startedAt),bb=validDate(b.startedAt);
    if(aa!==bb)return aa?-1:1;
    return Date.parse(bb?b.startedAt:b.date||b.timestamp||'')-Date.parse(aa?a.startedAt:a.date||a.timestamp||'');
  });
  const transcript=selected?.transcriptConsented===true&&Array.isArray(selected.transcript)?selected.transcript.filter((m:any)=>m&&typeof m.text==='string'&&['USER','AI'].includes(m.sender)):[];
  return <>
    <div data-session-rows className="max-h-80 overflow-y-auto overscroll-contain space-y-2 pr-1">
      {sorted.map(r=><article key={r.id} data-record-id={r.id} className="flex gap-2 items-center rounded-xl border border-white/10 p-2">
        <button type="button" onClick={()=>setOpened(r.id)} className="min-h-11 flex-1 min-w-0 text-left rounded-lg px-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise" aria-haspopup="dialog"><time className="text-sm block">{i18nNode(label(r))}</time><span className="text-xs text-slate-400">{i18nText(r.transcriptConsented&&r.transcript?.length?'Konuşma ve özet':'Özet kaydı')}</span></button>
        <button type="button" disabled={!parked||busy} onClick={()=>onDelete(r)} aria-label={i18nText(`Ruh Sağlığı özeti kaydını sil: ${recordDate(r)}`)} className="min-h-11 rounded-lg border border-rose-400/40 text-rose-200 px-4 disabled:opacity-40">{i18nText("Sil")}</button>
      </article>)}
    </div>
    {selected&&<AccessibleDialog title={i18nText("Görüşme kaydı")} onClose={()=>{if(!busy)setOpened(null);}} className="w-full max-w-2xl rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
      <div className="flex justify-between items-start gap-3"><h2 className="text-lg font-bold">{i18nText("Görüşme kaydı")}</h2><button className="min-h-11 min-w-11 rounded-lg border border-white/20" aria-label={i18nText("Görüşme kaydını kapat")} disabled={busy} onClick={()=>setOpened(null)}>✕</button></div>
      <div className="text-sm space-y-1"><p>{i18nText("Başlangıç: ")}{i18nNode(validDate(selected.startedAt)?new Date(selected.startedAt).toLocaleString(getLocale()):'Başlangıç zamanı kaydedilmemiş.')}</p><p>{i18nText("Bitiş: ")}{i18nNode(validDate(selected.completedAt)?new Date(selected.completedAt).toLocaleString(getLocale()):'Bitiş zamanı kaydedilmemiş.')}</p>{!validDate(selected.startedAt)&&<p>{i18nText("Özet tarihi: ")}{i18nNode(recordDate(selected))}</p>}</div>
      <div data-session-transcript className="space-y-3 max-h-[50dvh] overflow-y-auto overscroll-contain">
        {transcript.length?transcript.map((m:any,index:number)=><article key={`${m.id||index}-${index}`} data-session-author={m.sender} className="border border-white/10 rounded-xl p-3"><p className="text-xs text-slate-400">{i18nNode(m.sender==='USER'?'Siz':PRODUCT_NAME)}{i18nNode(validDate(m.timestamp)?` · ${new Date(m.timestamp).toLocaleTimeString(getLocale())}`:'')}</p><p className="text-sm whitespace-pre-line break-words">{spokenText(m.text)}</p></article>):<p className="text-sm text-slate-400">{i18nText("Bu kayıtta konuşma dökümü bulunmuyor.")}</p>}
        <section className="border-t border-white/10 pt-3"><h3 className="font-bold text-sm">{i18nText("Özet")}</h3><p data-summary-provider={selected.providerType} className="text-sm whitespace-pre-line break-words">{spokenText(translateMood(selected.summaryText||'Özet bulunmuyor.'))}</p></section>
      </div>
      <button disabled={!parked||busy} onClick={()=>onDelete(selected)} className="min-h-11 rounded-xl border border-rose-400/40 px-4 text-rose-200 disabled:opacity-40">{i18nText("Bu kaydı sil")}</button>
    </AccessibleDialog>}
  </>;
}
