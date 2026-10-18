
'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';

/** A bounded, keyboard accessible dialog. Restore the caller and background on close. */
export function AccessibleDialog({ title, onClose, children, className }: {
  title: string; onClose: () => void; children: ReactNode; className: string;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose); close.current = onClose;
  useLayoutEffect(() => {
    const element = panel.current;
    if (!element) return;
    element.style.setProperty('--dialog-background', getComputedStyle(element).backgroundColor);
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const background: { element: HTMLElement; inert: boolean }[] = [];
    let branch: HTMLElement = element;
    while (branch.parentElement) {
      for (const sibling of Array.from(branch.parentElement.children)) {
        if (sibling !== branch && sibling instanceof HTMLElement) {
          background.push({ element: sibling, inert: sibling.inert }); sibling.inert = true;
        }
      }
      branch = branch.parentElement;
      if (branch === document.body) break;
    }
    const controls = () => Array.from(element.querySelectorAll<HTMLElement>(
      'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]'
    )).filter(node => node.getClientRects().length > 0 && !node.closest('[inert]'));
    const focusFirst = () => (controls()[0] || element).focus({ preventScroll: true });
    focusFirst();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close.current(); }
      if (event.key !== 'Tab') return;
      const items = controls(), first = items[0], last = items[items.length - 1];
      if (!first) { event.preventDefault(); element.focus(); }
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === element)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    const keepFocus = (event: FocusEvent) => { if (!element.contains(event.target as Node)) focusFirst(); };
    document.addEventListener('keydown', keyboard, true);
    document.addEventListener('focusin', keepFocus);
    return () => {
      document.removeEventListener('keydown', keyboard, true);
      document.removeEventListener('focusin', keepFocus);
      for (const item of background) item.element.inert = item.inert;
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [mounted]);
  return mounted ? createPortal(<div onClick={onClose} style={{ margin: 0 }} className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
    <div ref={panel} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}
      onClick={event => event.stopPropagation()} className={`max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain ${className}`}>
      {children}
    </div>
  </div>, document.body) : null;
}
