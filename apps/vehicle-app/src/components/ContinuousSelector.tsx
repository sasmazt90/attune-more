'use client';
import { useRef } from 'react';
import { normalizeAngle } from '../utils/continuousVision';
/** Single arrow; pointer capture keeps continuous touch drag on the ring. */
export function ContinuousSelector({ angle, disabled, onChange }: { angle:number; disabled:boolean; onChange:(angle:number)=>void }) {
  const pointer=useRef<number|null>(null);
  const move=(event:React.PointerEvent<HTMLDivElement>)=>{
    if(disabled || pointer.current!==event.pointerId) return;
    const rect=event.currentTarget.getBoundingClientRect(),x=event.clientX-rect.left-rect.width/2,y=event.clientY-rect.top-rect.height/2;
    if(Math.hypot(x,y)<rect.width*.18)return;
    onChange(normalizeAngle(Math.atan2(y,x)*180/Math.PI));
  };
  return <div role="slider" tabIndex={disabled?-1:0} aria-label="Boşluk yönünü ayarlayın" aria-disabled={disabled} aria-valuemin={0} aria-valuemax={360} aria-valuenow={angle} aria-valuetext="Okun seçili yönü" data-continuous-selector
    className={`relative w-56 h-56 max-w-full rounded-full border-2 border-togg-turquoise/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-togg-turquoise ${disabled?'opacity-40':'cursor-grab active:cursor-grabbing'}`} style={{touchAction:'none'}}
    onPointerDown={event=>{if(disabled)return;pointer.current=event.pointerId;event.currentTarget.setPointerCapture(event.pointerId);move(event);}}
    onPointerMove={move} onPointerUp={event=>{if(pointer.current===event.pointerId){move(event);pointer.current=null;event.currentTarget.releasePointerCapture(event.pointerId);}}}
    onPointerCancel={()=>{pointer.current=null;}} onLostPointerCapture={()=>{pointer.current=null;}}
    onKeyDown={event=>{if(disabled)return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();onChange(normalizeAngle(angle+(['ArrowLeft','ArrowUp'].includes(event.key)?-1:1)));}}}>
    <svg viewBox="0 0 224 224" className="w-full h-full pointer-events-none" aria-hidden="true"><g transform={`rotate(${angle} 112 112)`}><path d="M 80 112 H 181 M 162 95 L 181 112 L 162 129" fill="none" stroke="#67e8f9" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" /></g></svg>
  </div>;
}
