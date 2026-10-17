import type {AppearanceResponse} from './appearanceMeasurements';
export const ACNE_V5_METHOD='appearance-acne-step0-verifier-v5-1';
export const ACNE_V5_MODEL_HASH='b8200e999c6c744247d264de70df5280900e08f0ba5130479425a6dac92d13f5';
export type AcneV5Runtime={methodVersion:string;status:'measured'|'unavailable';reason:string|null;experimental:true;accepted:false;modelHash:string|null;step0SHA256:string;onnxSHA256:string|null;verifierSHA256:string;threshold:number;candidateCount:number};
/** Verify the actual engine before attaching its rows; the unit is source-box area, never probability. */
export function validateAcneV5Response(result:AppearanceResponse){
 const runtime=result.acneRuntime;
 if(!runtime||runtime.methodVersion!==ACNE_V5_METHOD||runtime.experimental!==true||runtime.accepted!==false||runtime.step0SHA256!=='18e94a9579a3c0dd548c3357899ba20f316a0d01bf2fdbfbc6eed4288a26d655'||runtime.verifierSHA256!=='0d7bf03ca4d9898ef1b2e78c6d54d61be6aff580329b20b78a9232f79cfd43bb'||runtime.threshold!==0.15628215094908582)throw Error('INVALID_ACNE_MODEL_IDENTITY');
 const rows=[...Object.values(result.measurements).flat(),...(result.general?.measurements||[])].filter(row=>row.id==='acne');
 for(const row of rows){
  if(row.methodVersion!==ACNE_V5_METHOD||row.modelHash!==runtime.modelHash||row.unit!=='appearance-score-0-100'||row.normalizationVersion!=='unique-detection-box-anatomical-area-v2')throw Error('INVALID_ACNE_MEASUREMENT');
  if(row.value!==null&&(runtime.status!=='measured'||runtime.modelHash!==ACNE_V5_MODEL_HASH||runtime.onnxSHA256!=='9c87475d9302aed16f09abedc109211c2ac1b49f22f465f86aab408a5244d0be'||row.quality!=='valid'||row.components.candidateCount!==row.components.bounds.length))throw Error('INVALID_ACNE_MEASUREMENT');
 }
}
