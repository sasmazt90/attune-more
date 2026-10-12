import type { SkinSnapshot } from './skinSnapshot';
import type { ImageQuality } from './skinAnalyzer';
import { researchTarget, isAdmittedResearchMeasurement } from './skinResearchAdapter';
export const SKIN_SIGN_CONTRACT='regional-appearance-v4';
export type SkinMeasurement={scope:'regional'|'whole-face';region?:string;target?:string;methodVersion:string;modelHash:string|null;datasetHash?:string|null;evidenceHash?:string|null;unit:'appearance-score-0-100'|'color-index-0-100'|'visible-highlight-area-percent'|'class-probability'|'ordinal-grade'|'lesion-count'|'percent-visible-area'|'candidate-count'|'relative-color-index-0-100'|'directional-line-index-0-100'|'normalized-contour-ratio'|'contour-fold-index-0-100';rawValue:number|null;confidence:number|null;quality:'valid'|'invalid'|'insufficient';validation:'analytic-pixel-index'|'development-only'|'independently-validated'|'unavailable'|'appearance-proxy';unavailableReason:string|null};
export type SkinIndicator={appearance?:import('./appearanceMeasurements').AppearanceMeasurement;id:string;label:string;score:number|null;referenceDelta?:number;reason:string;method:string;unit:string;sampleCount:number;measurement?:SkinMeasurement};
export type SkinIndicators=Record<string,SkinIndicator[]>;
export const SIGN_LABELS:Record<string,string>={tone:'Ton eşitsizliği',oil:'Yağlı görünüm',redness:'Kızarıklık eğilimi',acne:'Sivilce görünümü',sag:'Sarkma',dry:'Cilt kuruluğu',dark:'Göz altı morluğu',bags:'Göz altı torbaları',lines:'Kaz ayakları'};
export function skinCriterionLabel(id:string,scope:'regional'|'whole-face'='regional') {
 return scope==='whole-face'&&id==='sag'?'Sarkma görünümü':scope==='whole-face'&&id==='dry'?'Cilt kuruluğu görünümü':SIGN_LABELS[id]||id;
}
export function indicatorIds(region:string){return region==='periorbital'?['dark','bags','lines','dry']:region==='nose'?['tone','oil','redness','acne','dry']:['tone','oil','redness','acne','sag','dry'];}
/** Overview carries the real regional components inside sourceComponents. */
export function samplingSupportVersion(value?:import('./appearanceMeasurements').AppearanceMeasurement):string|null {
 return value?.components?.samplingSupportVersion || value?.components?.sourceComponents?.samplingSupportVersion || null;
}
export function validSkinIndicators(value:unknown):value is SkinIndicators {
 if(!value||typeof value!=='object')return false;
 return ['forehead','rightCheek','leftCheek','nose','chin','periorbital'].every(region=>{
  const rows=(value as SkinIndicators)[region],ids=indicatorIds(region);
  return Array.isArray(rows)&&rows.length===ids.length&&ids.every(id=>{
   const matching=rows.filter(row=>row?.id===id);if(matching.length!==1)return false;
   const row=matching[0];return typeof row.reason==='string'&&!!row.reason&&typeof row.method==='string'&&!!row.method&&
    (row.score===null||(typeof row.score==='number'&&Number.isFinite(row.score)&&(['tone','redness'].includes(id)?row.score>=0&&row.score<=100:!!row.appearance)))&&
    (row.referenceDelta===undefined||Number.isFinite(row.referenceDelta))&&validMeasurement(row,region);
  });
 });
}
export function validMeasurement(row:SkinIndicator,region:string) {
 const appearance=row.appearance;
 if(appearance){
  const m=row.measurement;
  return appearance.region===region&&['appearance_proxy','longitudinal_measurement'].includes(appearance.type)&&['appearance-cv-1','appearance-cv-2','appearance-cv-3','appearance-cv-4','appearance-cv-5','appearance-cv-6'].includes(appearance.methodVersion)&&
   !!m&&m.validation==='appearance-proxy'&&m.region===region&&m.rawValue===appearance.value&&row.score===appearance.value&&
   ['appearance-score-0-100','percent-visible-area','candidate-count','relative-color-index-0-100','directional-line-index-0-100','normalized-contour-ratio','contour-fold-index-0-100'].includes(appearance.unit)&&
   ['valid','invalid','insufficient'].includes(appearance.quality)&&
   (appearance.value===null?!!appearance.limitationCode:Number.isFinite(appearance.value)&&appearance.quality==='valid')&&
   !!appearance.captureConditions&&!!appearance.evaluatedArea&&Array.isArray(appearance.uncertainty);
 }
 const m=row.measurement;if(!m)return true; // Existing V3 records remain readable.
 if(m.scope!=='regional'||m.region!==region||typeof m.methodVersion!=='string'||!m.methodVersion||!(m.modelHash===null||/^[a-f0-9]{64}$/.test(m.modelHash)))return false;
 if(!['color-index-0-100','visible-highlight-area-percent','class-probability','ordinal-grade','lesion-count'].includes(m.unit)||!['valid','invalid','insufficient'].includes(m.quality)||!['analytic-pixel-index','development-only','independently-validated','unavailable'].includes(m.validation))return false;
 if([m.datasetHash,m.evidenceHash].some(v=>v!==undefined&&v!==null&&!/^[a-f0-9]{64}$/.test(v)))return false;
 if(m.target!==undefined&&m.target!==researchTarget(row.id)&&!(row.id==='acne'&&m.target==='acne-count'))return false;
 if(m.confidence!==null&&(!Number.isFinite(m.confidence)||m.confidence<0||m.confidence>1))return false;
 if(m.rawValue===null)return typeof m.unavailableReason==='string'&&!!m.unavailableReason&&row.score===null;
 if(!Number.isFinite(m.rawValue)||m.rawValue<0||m.quality!=='valid'||m.unavailableReason!==null)return false;
 if(['tone','redness'].includes(row.id))return m.unit==='color-index-0-100'&&m.rawValue<=100&&m.validation==='analytic-pixel-index'&&m.modelHash===null;
 // Experimental values cannot travel into ordinary persisted user results.
 if(row.score!==null||!isAdmittedResearchMeasurement(m))return false;
 if(row.id==='oil')return m.unit==='visible-highlight-area-percent'&&m.rawValue<=100;
 if(row.id==='acne')return m.target==='acne-presence'&&m.unit==='class-probability'&&m.rawValue<=1||m.target==='acne-count'&&m.unit==='lesion-count'&&Number.isInteger(m.rawValue);
 return ['dry','sag'].includes(row.id)&&m.unit==='ordinal-grade'&&Number.isInteger(m.rawValue)&&m.rawValue<=3;
}
export function canCompareIndicator(a:SkinIndicator,b:SkinIndicator) {
 if(a.id!==b.id||a.method!==b.method||a.unit!==b.unit)return false;
 if(a.appearance?.normalizationVersion!==b.appearance?.normalizationVersion||a.appearance?.calibrationVersion!==b.appearance?.calibrationVersion)return false;
 if(samplingSupportVersion(a.appearance)!==samplingSupportVersion(b.appearance))return false;
 const x=a.measurement,y=b.measurement;
 if(x&&y)return x.scope===y.scope&&x.region===y.region&&x.methodVersion===y.methodVersion&&x.modelHash===y.modelHash&&x.datasetHash===y.datasetHash&&x.evidenceHash===y.evidenceHash&&x.target===y.target&&x.unit===y.unit&&x.validation===y.validation;
 // Only the exact pre-existing color formula is compatible with legacy V3.
 return ['tone','redness'].includes(a.id)&&(!x||x.methodVersion==='regional-rgb-v3')&&(!y||y.methodVersion==='regional-rgb-v3');
}
const unavailable:Record<string,string>={oil:'Yüzey parlaklığı yöntemi bağımsız doğrulanmadığı için bu taramada puan gösterilmez.',acne:'Ben, sakal ve artefaktlardan ayıran lisanslı ve doğrulanmış model yok.',sag:'Bu kamera ve tek poz için doğrulanmış derinlik/şiddet ölçümü yok.',dry:'Fotoğraf nem veya cilt bariyerini güvenilir ölçmüyor.',dark:'Gölge ile pigment farkını ayıran doğrulanmış yöntem yok.',bags:'Gölge ile hacim farkını ayıracak doğrulanmış 3B ölçüm yok.',lines:'İfade/poz ve ince çizgi ayrıntısı için doğrulanmış model yok.'};
function inside(x:number,y:number,p:{x:number;y:number}[],tri:number[]){const [a,b,c]=tri.map(i=>p[i]);const d=(v:typeof a,w:typeof a)=>(x-w.x)*(v.y-w.y)-(v.x-w.x)*(y-w.y);const u=d(a,b),v=d(b,c),w=d(c,a);return (u>=0&&v>=0&&w>=0)||(u<=0&&v<=0&&w<=0);}
/** Direct image color indices, NOT calibrated disease/sign severity or probability.
 * ROI is the union of triangles actually present in the selected anatomical mesh.
 * Each region uses its accepted source pose. No LLM or skin disease model.
 */
export function measureSkinIndicators(ctx:CanvasRenderingContext2D,snapshot:SkinSnapshot,quality:ImageQuality):SkinIndicators {
 const result:SkinIndicators={};
 for(const [region,mesh] of Object.entries(snapshot.meshes)){
  const edges=new Set(mesh.edges.flatMap(([a,b])=>[`${a}:${b}`,`${b}:${a}`])),triangles:number[][]=[];
  for(let a=0;a<mesh.points.length;a++)for(let b=a+1;b<mesh.points.length;b++)if(edges.has(`${a}:${b}`))for(let c=b+1;c<mesh.points.length;c++)if(edges.has(`${a}:${c}`)&&edges.has(`${b}:${c}`))triangles.push([a,b,c]);
  const data=ctx.getImageData(0,0,snapshot.width,snapshot.height).data,chromas:number[]=[],reds:number[]=[];
  const minX=Math.max(0,Math.floor(Math.min(...mesh.points.map(p=>p.x)))),maxX=Math.min(snapshot.width,Math.ceil(Math.max(...mesh.points.map(p=>p.x))));
  const minY=Math.max(0,Math.floor(Math.min(...mesh.points.map(p=>p.y)))),maxY=Math.min(snapshot.height,Math.ceil(Math.max(...mesh.points.map(p=>p.y))));
  // At most about 16K source samples per region; sampling never changes RGB.
  const step=Math.max(1,Math.ceil(Math.sqrt(Math.max(0,(maxX-minX)*(maxY-minY))/16000)));
  for(let y=minY;y<maxY;y+=step)for(let x=minX;x<maxX;x+=step)if(triangles.some(t=>inside(x,y,mesh.points,t))){const i=(y*snapshot.width+x)*4,r=data[i],g=data[i+1],b=data[i+2],lum=.299*r+.587*g+.114*b;if(lum<40||lum>220)continue;const total=r+g+b;if(!total)continue;chromas.push((r-g)/total);reds.push(Math.max(0,Math.min(100,(2*r-g-b)/255*100)));}
  const count=reds.length,mean=reds.reduce((a,b)=>a+b,0)/Math.max(1,count),center=chromas.reduce((a,b)=>a+b,0)/Math.max(1,count);
  const spread=Math.sqrt(chromas.reduce((a,b)=>a+(b-center)**2,0)/Math.max(1,count));
  result[region]=indicatorIds(region).map(id=>{const measured=id==='redness'||id==='tone',usable=quality.isValid&&count>=100;
   return {id,label:SIGN_LABELS[id],score:measured&&usable?Math.round((id==='redness'?mean:Math.min(100,100*spread))*10)/10:null,
    reason:measured?(usable?'Yalnız fotoğraftaki renk indeksi; ışık, ten tonu, gölge ve sakal etkiler. Kalibre edilmiş belirti şiddeti değildir.':'Geçerli ışık/netlik veya yeterli görünür örnek yok.'):unavailable[id],
    method:measured?(id==='redness'?'mean(clamp(100*(2R-G-B)/255,0,100))':'100*std((R-G)/(R+G+B))'):'unavailable',unit:measured?'Renk indeksi / 100':'',sampleCount:count,
    measurement:{scope:'regional',region,...(researchTarget(id)?{target:researchTarget(id)}:{}),methodVersion:measured?'regional-rgb-v3':'unavailable-v1',modelHash:null,unit:id==='oil'?'visible-highlight-area-percent':id==='acne'?'class-probability':['dry','sag'].includes(id)?'ordinal-grade':'color-index-0-100',rawValue:measured&&usable?(id==='redness'?mean:Math.min(100,100*spread)):null,confidence:null,quality:usable?'valid':quality.isValid?'insufficient':'invalid',validation:measured&&usable?'analytic-pixel-index':'unavailable',unavailableReason:measured&&usable?null:measured?'insufficient-valid-source-samples':'no-independent-validation'}};});
 }
 return result;
}
