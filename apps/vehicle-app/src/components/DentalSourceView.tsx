'use client';
import {useTranslations} from '../i18n/LanguageProvider';

import type {DentalCapture} from '../utils/dentalCapture';
export function DentalSourceView({photo,view}:{photo:DentalCapture;view:any}){
 const {text:i18nText,node:i18nNode}=useTranslations();return <svg viewBox={`0 0 ${photo.width} ${photo.height}`} role="img" aria-label={i18nText("Gerçek diş fotoğrafı ve görünür adaylar")} className="rounded-2xl w-full"><image href={photo.photo} width={photo.width} height={photo.height}/>{view.caries?.candidates?.map((c:any,i:number)=><rect key={i} x={c.bounds.x} y={c.bounds.y} width={c.bounds.width} height={c.bounds.height} fill="none" stroke="#fda4af" strokeWidth={photo.width/300}/>)}{view.accumulation?.quality==='valid'&&view.accumulation.candidates.map((c:any,i:number)=><path key={i} d={c.points.map((p:number[],j:number)=>`${j?'L':'M'}${p[0]} ${p[1]}`).join(' ')+'Z'} fill="#36e4f1" fillOpacity=".25" stroke="#36e4f1"/>)}{view.alignment?.contours?.map((c:any,i:number)=><path key={i} d={c.points.map((p:number[],j:number)=>`${j?'L':'M'}${p[0]} ${p[1]}`).join(' ')+'Z'} fill="none" stroke="#c4b5fd" strokeWidth={photo.width/600}/>)}</svg>;}
