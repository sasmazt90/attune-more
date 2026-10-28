'use client';
import {useTranslations} from '../i18n/LanguageProvider';


import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/** One row at every width; navigation moves the actual scroll container. */
export function CardCarousel({ label, items, itemWidthClassName = 'basis-[90%] sm:basis-72' }: { label: string; items: { id: string; content: ReactNode }[]; itemWidthClassName?: string }) {
 const {text:i18nText,node:i18nNode}=useTranslations();
  const id = useId(), track = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ previous: false, next: false, first: 1 });
  const update = useCallback(() => {
    const element = track.current; if (!element) return;
    const step = (element.firstElementChild?.getBoundingClientRect().width || 1) + 12;
    setPosition({ previous: element.scrollLeft > 2, next: element.scrollLeft < element.scrollWidth - element.clientWidth - 2, first: Math.min(items.length, Math.floor((element.scrollLeft + 2) / step) + 1) });
  }, [items.length]);
  useEffect(() => {
    const element = track.current; if (!element) return;
    const observer = new ResizeObserver(update); observer.observe(element); update();
    return () => observer.disconnect();
    // The track's geometry is authoritative; record refreshes do not reset it.
  }, [update]);
  const move = (direction: number) => {
    const element = track.current; if (!element) return;
    const step = (element.firstElementChild?.getBoundingClientRect().width || element.clientWidth) + 12;
    element.scrollBy({ left: direction * step, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  };
  const arrow = 'inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-white/20 text-togg-turquoise hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise disabled:opacity-30 disabled:cursor-default';
  return <section aria-label={i18nText(label)} aria-roledescription={i18nText("Kaydırılabilir kartlar")} className="min-w-0 space-y-3" data-card-carousel>
    <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold text-slate-300">{i18nNode(label)}</h2><div className="flex gap-2"><button type="button" className={arrow} aria-label={i18nText("Önceki kartlar")} aria-controls={id} disabled={!position.previous} onClick={() => move(-1)}><ChevronLeft aria-hidden="true" className="h-5 w-5"/></button><button type="button" className={arrow} aria-label={i18nText("Sonraki kartlar")} aria-controls={id} disabled={!position.next} onClick={() => move(1)}><ChevronRight aria-hidden="true" className="h-5 w-5"/></button></div></div>
    <div ref={track} id={id} role="list" onScroll={update} className="flex items-stretch gap-3 overflow-x-auto overscroll-x-contain snap-x snap-mandatory scroll-p-1 p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {items.map((item, index) => <div key={item.id} role="listitem" aria-label={i18nText(`${index + 1} / ${items.length}`)} className={`flex min-w-0 shrink-0 snap-start ${itemWidthClassName}`}>{i18nNode(item.content)}</div>)}
    </div>
    <span className="sr-only" role="status" aria-live="polite">{i18nText("İlk görünür kart: ")}{i18nNode(position.first)} / {i18nNode(items.length)}</span>
  </section>;
}
