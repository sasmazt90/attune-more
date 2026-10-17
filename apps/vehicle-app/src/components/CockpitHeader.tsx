'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {PlaybackWave} from './PlaybackWave';
import { muteGuidance } from '../utils/audioGuidance';
import { HEALTH_MODULES, HEALTH_MODULE_IDS } from '../utils/healthModules';
import { InformationButton } from './InformationButton';
import { HealthModuleIcon } from './HealthModuleIcon';
import { usePathname } from 'next/navigation';
import { useVehicle } from '../context/VehicleContext';
import {
  HeartPulse,
  CalendarCheck,
  User,
  Volume2, VolumeX,
  Car,
  Activity,
} from 'lucide-react';

export const CockpitHeader: React.FC = () => {
  const pathname = usePathname();
  const navigation = useRef<HTMLElement>(null);
  const [open,setOpen]=useState(false),[guidanceMuted,setGuidanceMuted]=useState(false);
  const trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null);
  const close=(focus=false)=>{setOpen(false);if(focus)trigger.current?.focus();};
  useEffect(()=>{setOpen(false);window.dispatchEvent(new Event('attune-guidance-cancel'));},[pathname]);
  useEffect(()=>{if(!open)return;const outside=(e:PointerEvent)=>{if(!panel.current?.contains(e.target as Node)&&!trigger.current?.contains(e.target as Node))setOpen(false);};const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();close(true);}};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key);};},[open]);
  const move=(e:React.KeyboardEvent)=>{const links=Array.from(panel.current?.querySelectorAll<HTMLAnchorElement>('a')||[]);let i=links.indexOf(document.activeElement as HTMLAnchorElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();i=e.key==='Home'?0:e.key==='End'?links.length-1:(i+(e.key==='ArrowDown'?1:-1)+links.length)%links.length;links[i]?.focus();}};
  const { state, toggleDrivingMode, isParked, syncStatus, syncError } = useVehicle();
  const healthActive=HEALTH_MODULE_IDS.some(id=>pathname===HEALTH_MODULES[id].route);
  const navItems=[{href:'/',label:'Kokpit',icon:Activity},{href:'/care',label:'Uzman & Randevu',icon:CalendarCheck},{href:'/profile',label:'Sağlık Geçmişim',icon:User}];
  const itemClass=(active:boolean)=>`flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all min-h-touch ${active?'bg-togg-turquoise/15 text-togg-turquoise border border-togg-turquoise/30 font-bold':'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`;
  const dropdownClass=(active:boolean)=>`flex items-center justify-start text-left gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all min-h-touch w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-togg-turquoise ${active?'bg-togg-turquoise/15 text-togg-turquoise border border-togg-turquoise/30 font-bold':'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`;
  return (
    <header data-cockpit-header className="border-b border-white/10 bg-[#050b14]/95 backdrop-blur-md md:sticky top-0 z-50">
      {/* Üst Telemetri ve Güvenlik Durum Çubuğu */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-2 border-b border-white/5 text-xs">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
            <img
              src="/brand/togg/togg-logo.svg"
              alt="Togg"
              className="h-5 w-auto object-contain"
            />
            <span className="h-3.5 w-px bg-slate-700/60" />
            <span className="font-extrabold text-white tracking-wide text-sm flex items-center">
              Attune<span className="text-togg-turquoise">.more</span>
            </span>
          </Link>


        </div>

        {/* Sensörler, Batarya ve Araç Durumu Butonu */}
        <div className="flex items-center gap-3"><PlaybackWave/><button type="button" className="min-h-11 min-w-11 rounded-full border border-white/20 inline-flex items-center justify-center" aria-label={guidanceMuted?'Seslendirmeyi aç':'Seslendirmeyi kapat'} aria-pressed={guidanceMuted} onClick={()=>{const next=!guidanceMuted;setGuidanceMuted(next);muteGuidance(next);}}>{guidanceMuted?<VolumeX className="h-4 w-4"/>:<Volume2 className="h-4 w-4"/>}</button>


          {/* Sürüş / Park Durumu */}
          <span data-vehicle-status className={`flex items-center gap-2 rounded-full px-3 py-2 border text-xs ${isParked?'text-emerald-300 border-emerald-800':'text-amber-200 border-amber-700'}`}><Car className="w-3.5 h-3.5"/>{syncStatus!=='synced'?(syncStatus==='failed'?'ARAÇ DURUMU BELİRSİZ':'ARAÇ DURUMU DOĞRULANIYOR'):isParked?'PARK':'SÜRÜŞ'}</span>
          <InformationButton title="Demo araç durumu"><p>Windows MVP’si gerçek araç API/CAN bağlantısına sahip değildir. Aşağıdaki demo kontrolü gerçek frontend/backend durumunu değiştirir. PARK doğrulanmadan işlemler açılmaz. Kamera ve mikrofonun native izinleri araç sensörlerinden bağımsızdır.</p>          <button
            onClick={toggleDrivingMode}
            disabled={syncStatus === 'loading' || syncStatus === 'updating'}
            className={`flex items-center gap-2 px-3 py-1 rounded-full shrink-0 font-bold text-xs transition-all border shadow-sm ${
              isParked
                ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/70 hover:bg-emerald-900/60'
                : 'bg-amber-950/60 text-amber-300 border-amber-700/80 hover:bg-amber-900/70 animate-pulse'
            }`}
            title="Sürüş ve Park modları arasında geçiş"
          >
            <Car className="w-3.5 h-3.5" />
            <span className="whitespace-nowrap">
              {syncStatus !== 'synced' ? <strong>{syncStatus === 'failed' ? 'ARAÇ DURUMU BELİRSİZ' : 'ARAÇ DURUMU DOĞRULANIYOR'}</strong> : isParked ? (
                <>
                  <strong>PARK</strong> • 0 km/s
                </>
              ) : (
                <>
                  <strong>SÜRÜŞ</strong> • {state.currentSpeed} km/s
                </>
              )}
            </span>
            <span className="text-[9px] bg-white/10 px-1.5 py-0.2 rounded text-slate-300 font-normal">
              Değiştir
            </span>
          </button></InformationButton>
        </div>
      </div>

      <nav ref={navigation} aria-label="Ana sekmeler" className="relative px-3 sm:px-6 py-1.5">
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-1.5">
          <Link href="/" aria-current={pathname==='/'?'page':undefined} className={itemClass(pathname==='/')}><Activity className="w-3.5 h-3.5 shrink-0"/>Kokpit</Link>
          <div className="relative min-w-0">
            <button ref={trigger} type="button" aria-expanded={open} aria-controls="health-centre-links" className={itemClass(healthActive)+' w-full'} onClick={()=>setOpen(v=>!v)} onKeyDown={e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setOpen(true);requestAnimationFrame(()=>{const links=panel.current?.querySelectorAll<HTMLAnchorElement>('a');links?.[e.key==='ArrowDown'?0:links.length-1]?.focus();});}}}><HeartPulse className="w-3.5 h-3.5 shrink-0"/>Sağlık Merkezi</button>
            {open&&<div ref={panel} id="health-centre-links" onKeyDown={move} className="absolute top-full right-0 sm:left-0 sm:right-auto mt-2 w-56 max-w-[calc(100vw-2rem)] rounded-xl border border-white/20 bg-[#0b1424] shadow-2xl p-2 z-[60]" aria-label="Sağlık modülleri">
              {HEALTH_MODULE_IDS.map(id=><Link key={id} href={HEALTH_MODULES[id].route} aria-current={pathname===HEALTH_MODULES[id].route?'page':undefined} onClick={()=>close()} className={dropdownClass(pathname===HEALTH_MODULES[id].route)}><span className="w-[18px] shrink-0 inline-flex"><HealthModuleIcon module={id}/></span><span className="min-w-0 break-words">{HEALTH_MODULES[id].name}</span></Link>)}
            </div>}
          </div>
          {navItems.slice(1).map(item=>{const Icon=item.icon;return <Link key={item.href} href={item.href} aria-current={pathname===item.href?'page':undefined} className={itemClass(pathname===item.href)}><Icon className="w-3.5 h-3.5 shrink-0"/>{item.label}</Link>;})}
        </div>
      </nav>
      {syncError && <p role="alert" className="px-6 py-2 text-xs text-amber-200">{syncError}</p>}
    </header>
  );
};
