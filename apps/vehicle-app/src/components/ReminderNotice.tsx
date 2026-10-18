"use client";
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { readSkinReminder } from '../utils/skinReminder';
import { useVehicle } from '../context/VehicleContext';
export function ReminderNotice() {
  const { isParked } = useVehicle();
  const [due, setDue] = useState(false);
  useEffect(()=>{
    const refresh=()=>{try{const item=readSkinReminder();setDue(!!item && Date.parse(item.dueAt)<=Date.now());}catch{setDue(false);}};
    refresh(); const timer=setInterval(refresh,60000);
    window.addEventListener('attune-reminder',refresh);window.addEventListener('storage',refresh);window.addEventListener('focus',refresh);
    return()=>{clearInterval(timer);window.removeEventListener('attune-reminder',refresh);window.removeEventListener('storage',refresh);window.removeEventListener('focus',refresh);};
  },[]);
  return due && isParked ? <p role="status" className="text-sm text-sky-200 mb-4">Planlanan takip zamanı geldi. <Link href="/skin">Takibi aç</Link></p> : null;
}
