import {apiFetch as fetch} from './localBackend';
import {ACNE_V5_PREVIEW,LOCAL_API_BASE} from './previewLocalApi';
import {validateAcneV5Response,type AcneV5Runtime} from './acneV5Contract';
import {expressionObservation} from './skinExpression';
import type { SkinSnapshot } from './skinSnapshot';
import type { SkinIndicators, SkinMeasurement } from './skinIndicators';
import { samplingSupportVersion,supportedAppearanceMethod } from './skinIndicators';
import type { SkinLocalMap } from './skinLocalMaps';
import {isSkinHostedProcessingAllowed} from './attuneMode';
export type MeasurementKind='appearance_proxy'|'trained_prediction'|'longitudinal_measurement';
export type MeasurementReceipt={status?:'measured'|'unavailable';reason?:string|null;coverage?:number|null;calibrationVersion?:string|null;localConfidence?:number|null};
export type AppearanceMeasurement=MeasurementReceipt & {id:string;type:MeasurementKind;value:number|null;unit:string;methodVersion:string;modelVersion:string|null;modelHash:string|null;scoreDirection?:'higher-is-more-visible';normalizationVersion?:string;quality:'valid'|'invalid'|'insufficient';uncertainty:string[];region:string;evaluatedArea:Record<string,number>;captureConditions:Record<string,number|string>;limitationCode:string|null;referenceId:string|null;localMap:{key:string;photoId:string;region:string;criterion:string;coordinateSpace:'source-pixels'}|null;components:Record<string,any>};
export type AppearanceResponse={acneRuntime?:AcneV5Runtime;acneCandidates?:SkinSnapshot['acneCandidates'];general?:{skinType:import('./skinOverview').SkinOverview['skinType'];measurements:AppearanceMeasurement[];normalizationVersion:string;modelInputTransform?:Record<string,number|string|boolean>|null;modelInference?:Record<string,Record<string,number|string>>};photoId:string;sourceWidth:number;sourceHeight:number;measurements:Record<string,AppearanceMeasurement[]>;maps:Record<string,SkinLocalMap>;contours:Record<string,{points:{x:number;y:number}[];lines?:{x:number;y:number}[][];features:number[]}>};
export const APPEARANCE_UNITS:Record<string,string>={'appearance-score-0-100':'%','percent-visible-area':'% görünür alan','candidate-count':'aday','relative-color-index-0-100':'/ 100 · renk farkı','directional-line-index-0-100':'/ 100 · çizgi indeksi','normalized-contour-ratio':'kontur oranı','contour-fold-index-0-100':'/ 100 · görünüm indeksi'};
export async function analyzeAppearance(snapshot:SkinSnapshot,qualityValid:boolean,conditions:Record<string,number>,temporal:unknown[],current:()=>boolean):Promise<AppearanceResponse>{
 const hostedConsent=isSkinHostedProcessingAllowed();
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),45000);
 const stale=setInterval(()=>{if(!current()||isSkinHostedProcessingAllowed()!==hostedConsent)controller.abort();},100);
 try {
  const response=await fetch(`${LOCAL_API_BASE}/api/local-health/skin`,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({experimentalAcneV5:ACNE_V5_PREVIEW,requestId:crypto.randomUUID(),capturePreflight:{engine:'browser-mediapipe',faceCount:snapshot.captureFaceCount,quality:{isValid:qualityValid,avgLuminance:conditions.avgLuminance,blurScore:conditions.blurScore}},processingConsent:true,hostedProcessingConsent:hostedConsent,photo:snapshot.dataUrl,photoId:snapshot.photoId,pose:snapshot.angle,meshes:snapshot.meshes,exclusions:snapshot.exclusions,landmarks:snapshot.landmarks,expressionObservation:expressionObservation(snapshot.expressionScores,snapshot.photoId),qualityValid,conditions,temporal})});
  if(!response.ok){
   const detail=await response.json().catch(()=>({}));
   throw Error(detail.detail==='SKIN_EYEWEAR_PRESENT'?'Cilt analizi için gözlüğünüzü çıkarın.':detail.detail==='SKIN_EYEWEAR_CHECK_UNCERTAIN'?'Göz çevresi yeterince doğrulanamadı; yeniden çekin.':'Yerel görünüm analizi tamamlanamadı.');
  }
  const result:AppearanceResponse=await response.json();
  if(!current()||isSkinHostedProcessingAllowed()!==hostedConsent||result.photoId!==snapshot.photoId||result.sourceWidth!==snapshot.width||result.sourceHeight!==snapshot.height)throw Error('STALE_SOURCE');
  if(ACNE_V5_PREVIEW)validateAcneV5Response(result);
  return result;
 } finally {clearTimeout(timer);clearInterval(stale);}
}
/** Only measurement numbers enter records. Photo, maps and source contours are volatile. */
export function attachAppearance(indicators:SkinIndicators,result:AppearanceResponse){
 for(const [region,values] of Object.entries(result.measurements))for(const value of values){
  const target=indicators[region]?.find(row=>row.id===value.id);if(!target)continue;
  if(value.region!==region||!supportedAppearanceMethod(value.id,value.methodVersion)||value.value!==null&&!Number.isFinite(value.value))throw Error('INVALID_MEASUREMENT');
  target.score=value.value;target.unit=APPEARANCE_UNITS[value.unit]||value.unit;target.method=value.methodVersion;
  target.reason=value.limitationCode==='REFERENCE_CREATED'?'Kişisel kontur referansı oluşturuldu; sonraki uyumlu taramada değişim karşılaştırılır.':value.value===null?`Bu karede yeterli güvenilir ölçüm yok (${value.limitationCode}).`:'Görünür yüzeyin kozmetik görünüm vekili; hastalık, nem veya klinik şiddet ölçümü değildir.';
  target.appearance=value;
  target.measurement={scope:'regional',region,methodVersion:value.methodVersion,modelHash:value.modelHash,unit:value.unit,rawValue:value.value,confidence:null,quality:value.quality,validation:'appearance-proxy',unavailableReason:value.value===null?value.limitationCode:null} as SkinMeasurement;
 }
}
export function compareAppearance(row:import('./skinIndicators').SkinIndicator,prior:import('./skinIndicators').SkinIndicator|undefined,compatible:boolean,referenceId:string){
 const value=row.appearance,base=prior?.appearance;if(!value)return;
 delete row.referenceDelta;
 if(value.value===null)return; // Preserve the actual quality failure.
 if(!compatible||!base||base.methodVersion!==value.methodVersion||base.unit!==value.unit||base.normalizationVersion!==value.normalizationVersion||base.calibrationVersion!==value.calibrationVersion||samplingSupportVersion(base)!==samplingSupportVersion(value)||base.value===null){
  if(value.type==='longitudinal_measurement'){
   value.referenceId=null;
   value.limitationCode=compatible?'REFERENCE_NOT_AVAILABLE':'CAPTURE_CONDITIONS_INCOMPATIBLE';
   row.reason=compatible?'Önceki taramada bu bölge için geçerli kontur referansı yok.':'Poz, ifade veya ışık referansla uyumlu değil; değişim hesaplanmadı.';
  }return;
 }
 value.referenceId=base.referenceId||referenceId;
 if(value.type==='longitudinal_measurement'){
  const a=value.components.features as number[],b=base.components.features as number[];
  if(!a?.length||a.length!==b?.length)return;
  row.referenceDelta=a.reduce((sum,x,i)=>sum+x-b[i],0)/a.length;
  value.limitationCode=null;value.components.normalizedContourDelta=row.referenceDelta;
  row.reason='Aynı kişinin uyumlu taramasına göre ölçekten arındırılmış kontur farkı; sarkma şiddeti değildir.';
 }else row.referenceDelta=value.value-base.value;
}

/** Fill only a previously missing first valid contour; never replace a valid reference. */
export function initializeMissingContourReferences(prior:any,indicators:SkinIndicators,compatibleRegions:string[],referenceId:string){
 if(!prior)return null;
 const updated=JSON.parse(JSON.stringify(prior));let changed=false;
 for(const region of compatibleRegions)for(const row of indicators[region]||[]){
  const value=row.appearance;if(!value||value.type!=='longitudinal_measurement'||value.quality!=='valid'||value.value===null)continue;
  const rows=updated.indicators[region]||[],index=rows.findIndex((v:any)=>v.id===row.id),old=rows[index]?.appearance;
  if(old?.value!==null&&old?.value!==undefined)continue;
  const reference=JSON.parse(JSON.stringify(row));reference.appearance.referenceId=referenceId;
  reference.appearance.limitationCode='REFERENCE_CREATED';delete reference.referenceDelta;
  delete reference.appearance.components.normalizedContourDelta;
  if(index>=0)rows[index]=reference;else rows.push(reference);
  updated.indicators[region]=rows;changed=true;
  value.referenceId=referenceId;value.limitationCode='REFERENCE_CREATED';delete row.referenceDelta;
  row.reason='Bu bölgenin ilk geçerli kişisel kontur referansı oluşturuldu; sonraki uyumlu taramada değişim karşılaştırılır.';
 }
 return changed?updated:null;
}
