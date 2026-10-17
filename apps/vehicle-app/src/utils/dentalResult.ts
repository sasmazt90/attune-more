import type {DentalCapture} from './dentalCapture';
const fail=()=>{throw Error('Diş sonucu ve kaynak geometrisi doğrulanamadı.');};
const finite=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n);
/** Reject malformed responses; never resize boxes or synthesize healthy values. */
export function validateDentalView(v:any,source?:Pick<DentalCapture,'photoId'|'pose'|'width'|'height'>){
 if(!v||!/^[a-f0-9]{64}$/.test(v.photoId)||!['FRONT','RIGHT','LEFT','BITE'].includes(v.pose)||!Number.isInteger(v.sourceWidth)||!Number.isInteger(v.sourceHeight)||v.sourceWidth<16||v.sourceHeight<16)fail();
 if(source&&(v.photoId!==source.photoId||v.pose!==source.pose||v.sourceWidth!==source.width||v.sourceHeight!==source.height))fail();
 const point=(p:any)=>Array.isArray(p)&&p.length===2&&p.every(finite)&&p[0]>=0&&p[1]>=0&&p[0]<=v.sourceWidth&&p[1]<=v.sourceHeight;
 const box=(b:any)=>b&&['x','y','width','height'].every(k=>finite(b[k]))&&b.x>=0&&b.y>=0&&b.width>0&&b.height>0&&b.x+b.width<=v.sourceWidth+.0001&&b.y+b.height<=v.sourceHeight+.0001;
 const c=v.caries;
 if(!v.quality?.valid||!c||c.quality!=='valid'||c.unit!=='candidate-count'||!Array.isArray(c.candidates)||c.value!==c.candidates.length||!Number.isFinite(c.decisionThreshold)||c.decisionThreshold!==.35||!/^[a-f0-9]{64}$/.test(c.modelHash))fail();
 if(c.candidates.some((x:any)=>!box(x.bounds)||!['D','d'].includes(x.classCode)||!finite(x.confidence)||x.confidence<.35||x.confidence>1))fail();
 for(const item of [v.accumulation,v.alignment])if(!item||item.value!==null&&typeof item.value==='number'&&!finite(item.value))fail();
 if(!Array.isArray(v.accumulation.candidates)||v.accumulation.candidates.some((x:any)=>!box(x.bounds)||!Array.isArray(x.points)||!x.points.every(point)||!finite(x.areaPixels)||x.areaPixels<=0))fail();
 if(v.accumulation.value!==null&&(!finite(v.accumulation.value)||v.accumulation.value<0||v.accumulation.value>100||!finite(v.accumulation.evaluatedArea)||v.accumulation.evaluatedArea<=100))fail();
 if(!Array.isArray(v.alignment.contours)||v.alignment.contours.some((x:any)=>!Array.isArray(x.points)||!x.points.every(point)||!point(x.centroid)))fail();
 for(const row of Object.values(v.alignment.rows||{}) as any[])if(row.value!==null&&!finite(row.value))fail();
 return v;
}
export function validateDentalResult(value:any,sources:DentalCapture[]){
 if(!Array.isArray(value?.views)||value.views.length!==sources.length)fail();
 value.views.forEach((v:any,i:number)=>validateDentalView(v,sources[i]));return value;
}
