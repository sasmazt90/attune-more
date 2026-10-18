'use client';

import { useState, type ReactNode } from 'react';
import { AccessibleDialog } from './AccessibleDialog';

export function InformationButton({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <>
    <button type="button" aria-label={`${title} hakkında bilgi`} aria-haspopup="dialog" onClick={() => setOpen(true)} className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full border border-white/20 text-togg-turquoise focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise"><span aria-hidden="true">ⓘ</span></button>
    {open && <AccessibleDialog title={title} onClose={() => setOpen(false)} className="w-full max-w-lg rounded-2xl border border-white/20 bg-cockpit-surface p-5 space-y-4">
      <div className="flex items-start justify-between gap-3"><h2 className="text-lg font-bold">{title}</h2><button type="button" aria-label="Bilgi penceresini kapat" onClick={() => setOpen(false)} className="min-h-11 min-w-11 rounded-xl border border-white/20">✕</button></div>
      <div className="space-y-3 text-sm leading-relaxed text-slate-300">{children}</div>
    </AccessibleDialog>}
  </>;
}
