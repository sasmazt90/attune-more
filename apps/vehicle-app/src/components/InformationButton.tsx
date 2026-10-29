'use client';
import {useTranslations} from '../i18n/LanguageProvider';


import { Children, isValidElement, useState, type ReactNode } from 'react';
import {getLocale} from '../i18n/core';
import { AccessibleDialog } from './AccessibleDialog';

export function InformationButton({ title, children }: { title: string; children: ReactNode }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" aria-label={i18nText(`${title} hakkında bilgi`)} aria-haspopup="dialog" onClick={() => setOpen(true)} className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full border border-white/20 text-togg-turquoise focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise"><span aria-hidden="true">ⓘ</span></button>
    {open && <AccessibleDialog title={i18nText(title)} onClose={() => setOpen(false)} className="w-full max-w-lg rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
      <div className="flex items-start justify-between gap-3"><h2 className="text-lg font-bold">{i18nNode(title)}</h2><button type="button" aria-label={i18nText("Bilgi penceresini kapat")} onClick={() => setOpen(false)} className="min-h-11 min-w-11 rounded-xl border border-white/20">✕</button></div>
      <div className="space-y-3 text-sm leading-relaxed text-slate-300 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-3">{informationContent(i18nNode(children))}</div>
    </AccessibleDialog>}
  </>;
}

/** Presentation only. Existing lists, controls, links and labels remain intact. */
export function informationContent(content:ReactNode):ReactNode {
 const flat=(node:ReactNode):string|null=>{
  if(typeof node==='string'||typeof node==='number')return String(node);
  if(Array.isArray(node)){const parts=node.map(flat);return parts.every(p=>p!==null)?parts.join(''):null;}
  return null;
 };
 const nodes=Children.toArray(content);
 const multipleParagraphs=nodes.filter(child=>isValidElement<{children?:ReactNode}>(child)&&child.type==='p'&&flat(child.props.children)!==null).length>1;
 return nodes.map((child,index)=>{
  if(!isValidElement<{children?:ReactNode}>(child)||child.type!=='p')return child;
  const text=flat(child.props.children);if(!text)return child;
  const segments=Array.from(new Intl.Segmenter(getLocale(),{granularity:'sentence'}).segment(text),part=>part.segment.trim()).filter(Boolean);
  if(segments.length<2&&!multipleParagraphs)return child;
  return <ul key={child.key||index} className="list-disc pl-5 space-y-3">{segments.map((part,i)=><li key={i}>{part}</li>)}</ul>;
 });
}
