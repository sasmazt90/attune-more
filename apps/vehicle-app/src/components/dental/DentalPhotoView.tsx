'use client';
import {useTranslations} from '../../i18n/LanguageProvider';
import type {DentalCapture} from '../../utils/dentalCapture';
export type DentalLayer='caries'|'accumulation'|'alignment';
export const DENTAL_LAYER_COLORS:Record<DentalLayer,string>={caries:'#fda4af',accumulation:'#36e4f1',alignment:'#c4b5fd'};
const path=(points:number[][])=>points.map((p,j)=>`${j?'L':'M'}${p[0]} ${p[1]}`).join(' ')+'Z';
/** Mouth-region crop of the *same* source photo; marks stay in source pixels.
 * The crop comes from the backend's measured inner-mouth ROI of this view, so
 * every mark is drawn on the photo it was computed from. */
export function dentalCrop(view:any,width:number,height:number){
 const roi=view?.quality?.roi;
 if(!roi||![roi.x,roi.y,roi.width,roi.height].every(Number.isFinite)||roi.width<=0||roi.height<=0)return {x:0,y:0,width,height};
 const cx=roi.x+roi.width/2,cy=roi.y+roi.height/2;
 let w=Math.max(roi.width*1.7,roi.height*1.7*1.6),h=w/1.6;
 if(w>width){w=width;h=Math.min(height,w/1.6);}if(h>height){h=height;w=Math.min(width,h*1.6);}
 const x=Math.min(Math.max(0,cx-w/2),width-w),y=Math.min(Math.max(0,cy-h/2),height-h);
 return {x,y,width:w,height:h};
}
export function DentalPhotoView({photo,view,layers}:{photo:Pick<DentalCapture,'photo'|'width'|'height'>;view:any;layers:DentalLayer[]}){
 const {text:t}=useTranslations(),crop=dentalCrop(view,photo.width,photo.height),stroke=crop.width/260;
 return <svg viewBox={`${crop.x} ${crop.y} ${crop.width} ${crop.height}`} role="img" aria-label={t('Gerçek diş fotoğrafı ve görünür adaylar')} data-dental-photo={view?.photoId} data-dental-crop={[crop.x,crop.y,crop.width,crop.height].map(Math.round).join(',')} preserveAspectRatio="xMidYMid slice">
  <image href={photo.photo} width={photo.width} height={photo.height}/>
  {layers.includes('accumulation')&&view?.accumulation?.quality==='valid'&&view.accumulation.candidates.map((c:any,i:number)=><path key={'a'+i} d={path(c.points)} fill={DENTAL_LAYER_COLORS.accumulation} fillOpacity=".28" stroke={DENTAL_LAYER_COLORS.accumulation} strokeWidth={stroke*.6} data-dental-mark="accumulation"/>)}
  {layers.includes('alignment')&&view?.alignment?.contours?.map((c:any,i:number)=><path key={'c'+i} d={path(c.points)} fill="none" stroke={DENTAL_LAYER_COLORS.alignment} strokeWidth={stroke*.7} data-dental-mark="alignment"/>)}
  {layers.includes('caries')&&view?.caries?.candidates?.map((c:any,i:number)=><g key={'k'+i} data-dental-mark="caries"><rect x={c.bounds.x} y={c.bounds.y} width={c.bounds.width} height={c.bounds.height} rx={stroke*2} fill="none" stroke={DENTAL_LAYER_COLORS.caries} strokeWidth={stroke*1.4}/><circle cx={c.bounds.x+c.bounds.width} cy={c.bounds.y} r={stroke*6} fill={DENTAL_LAYER_COLORS.caries}/><text x={c.bounds.x+c.bounds.width} y={c.bounds.y+stroke*2.6} textAnchor="middle" fontSize={stroke*7.5} fill="#031318" fontWeight="600">{i+1}</text></g>)}
 </svg>;
}
