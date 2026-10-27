import type {DentalCapture} from './dentalCapture';
export const DENTAL_ADULT_POLICY='adult-permanent-D-only-v1';
// Colour/texture appearance at the visible tooth-gum border (dental-border-cv);
// not a validated calculus/tartar detector, so it is not named as one.
export const DENTAL_ACCUMULATION_LABEL='Birikim görünümü';
export const DENTAL_POSE_LABELS:Record<string,string>={FRONT:'Ön',RIGHT:'Anatomik sağ',LEFT:'Anatomik sol',BITE:'Kapanış görünümü'};
/** Backend quality codes -> user guidance (no technical codes on screen). */
export const DENTAL_QUALITY_REASONS:Record<string,string>={INSUFFICIENT_TOOTH_DETAIL:'Dişler küçük göründü; kameraya biraz yaklaşın.',MOUTH_CLOSED:'Ağız yeterince açık değildi.',NATURAL_BITE_REQUIRED:'Ön dişlerin birbirine değdiği kapanış görülemedi.',TEETH_NOT_VISIBLE:'Dişlerin bir kısmı dudak veya dil tarafından örtüldü.',LIGHT_INVALID:'Işık dişler için uygun değildi.',BLURRY:'Fotoğraf yeterince net değildi.',SALIVA_OR_GLARE:'Diş yüzeyinde parlama vardı.',TONGUE_OCCLUSION:'Dil görünür alanı örttü.'};
/** A view the backend measured vs. one it explicitly could not measure. */
export const dentalViewMeasured=(v:any)=>v?.quality?.valid===true&&v?.caries?.quality==='valid';
const fail=()=>{throw Error('Diş sonucu ve kaynak geometrisi doğrulanamadı.');};
const finite=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n);
/** Reject malformed responses; never resize boxes or synthesize healthy values.
 * A view the backend explicitly could not measure stays an "insufficient"
 * view (null values, no marks) instead of discarding the whole scan. */
export function validateDentalView(v:any,source?:Pick<DentalCapture,'photoId'|'pose'|'width'|'height'>,adultOnly=false){
 if(!v||!/^[a-f0-9]{64}$/.test(v.photoId)||!['FRONT','RIGHT','LEFT','BITE'].includes(v.pose)||!Number.isInteger(v.sourceWidth)||!Number.isInteger(v.sourceHeight)||v.sourceWidth<16||v.sourceHeight<16)fail();
 if(source&&(v.photoId!==source.photoId||v.pose!==source.pose||v.sourceWidth!==source.width||v.sourceHeight!==source.height))fail();
 const point=(p:any)=>Array.isArray(p)&&p.length===2&&p.every(finite)&&p[0]>=0&&p[1]>=0&&p[0]<=v.sourceWidth&&p[1]<=v.sourceHeight;
 const box=(b:any)=>b&&['x','y','width','height'].every(k=>finite(b[k]))&&b.x>=0&&b.y>=0&&b.width>0&&b.height>0&&b.x+b.width<=v.sourceWidth+.0001&&b.y+b.height<=v.sourceHeight+.0001;
 if(v.quality?.roi!==undefined&&v.quality.roi!==null&&!box(v.quality.roi))fail();
 const c=v.caries;
 if(v.quality?.valid===false){
  if(!Array.isArray(v.quality.reasons)||!v.quality.reasons.length||v.quality.reasons.some((r:unknown)=>typeof r!=='string'))fail();
  if(!c||c.quality!=='insufficient'||c.value!==null||!Array.isArray(c.candidates)||c.candidates.length)fail();
  if(adultOnly&&c.candidatePolicyVersion!==DENTAL_ADULT_POLICY)fail();
  for(const item of [v.accumulation,v.alignment])if(!item||item.value!==null||item.quality!=='insufficient')fail();
  if((v.accumulation.candidates||[]).length||(v.alignment.contours||[]).length)fail();
  return v;
 }
 if(!v.quality?.valid||!c||c.quality!=='valid'||c.unit!=='candidate-count'||!Array.isArray(c.candidates)||c.value!==c.candidates.length||!Number.isFinite(c.decisionThreshold)||c.decisionThreshold!==.35||!/^[a-f0-9]{64}$/.test(c.modelHash))fail();
 if(adultOnly&&c.candidatePolicyVersion!==DENTAL_ADULT_POLICY)fail();
 const classes=adultOnly||c.candidatePolicyVersion===DENTAL_ADULT_POLICY?['D']:['D','d'];
 if(c.candidates.some((x:any)=>!box(x.bounds)||!classes.includes(x.classCode)||!finite(x.confidence)||x.confidence<.35||x.confidence>1))fail();
 for(const item of [v.accumulation,v.alignment])if(!item||item.value!==null&&typeof item.value==='number'&&!finite(item.value))fail();
 if(!Array.isArray(v.accumulation.candidates)||v.accumulation.candidates.some((x:any)=>!box(x.bounds)||!Array.isArray(x.points)||!x.points.every(point)||!finite(x.areaPixels)||x.areaPixels<=0))fail();
 if(v.accumulation.value!==null&&(!finite(v.accumulation.value)||v.accumulation.value<0||v.accumulation.value>100||!finite(v.accumulation.evaluatedArea)||v.accumulation.evaluatedArea<=100))fail();
 if(!Array.isArray(v.alignment.contours)||v.alignment.contours.some((x:any)=>!Array.isArray(x.points)||!x.points.every(point)||!point(x.centroid)))fail();
 for(const row of Object.values(v.alignment.rows||{}) as any[])if(row.value!==null&&!finite(row.value))fail();
 return v;
}
export function validateDentalResult(value:any,sources:DentalCapture[],adultOnly=false){
 if(!Array.isArray(value?.views)||value.views.length!==sources.length)fail();
 value.views.forEach((v:any,i:number)=>validateDentalView(v,sources[i],adultOnly));
 if(value.missingViews!==undefined&&(!Array.isArray(value.missingViews)||value.missingViews.some((p:string)=>!['FRONT','RIGHT','LEFT','BITE'].includes(p)||value.views.some((v:any)=>v.pose===p))))fail();
 return value;
}
/** New records use exactly the validated product view list, never raw logits. */
export function dentalRecordMeasurements(value:any){
 if(!Array.isArray(value?.views)||value.candidatePolicyVersion!==DENTAL_ADULT_POLICY)fail();
 return value.views.map((view:any)=>({...validateDentalView(view,undefined,true),coordinateSpace:'oriented-source-pixels'}));
}
