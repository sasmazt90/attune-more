'use client';
import {useSyncExternalStore} from 'react';
import {meterSnapshot,subscribeMeter} from '../utils/playbackMeter';
const silent=Array(18).fill(0),server=()=>silent;
export function PlaybackWave(){const values=useSyncExternalStore(subscribeMeter,meterSnapshot,server),peak=Math.max(...values);return <div data-playback-wave data-amplitude={peak.toFixed(5)} className="h-9 w-20 sm:w-24 rounded-xl border border-white/20 flex items-center justify-center px-2 shrink-0" role="img" aria-label={peak>.003?'Uygulama sesi çalıyor':'Uygulama sesi sessiz'}><svg viewBox="0 0 72 24" className="w-full h-6" aria-hidden="true">{values.map((value,i)=><line key={i} x1={i*4+2} x2={i*4+2} y1={12-Math.min(10,value*38)} y2={12+Math.min(10,value*38)} stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-togg-turquoise"/>)}</svg></div>;}
