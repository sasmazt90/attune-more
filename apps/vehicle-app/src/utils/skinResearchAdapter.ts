import type { SkinIndicator, SkinMeasurement } from './skinIndicators';

export type ResearchTarget = 'visible-highlight-area' | 'acne-presence' | 'acne-count' | 'visible-flaking-grade' | 'visible-sagging-grade';
export type ResearchArtifact = {
 target:ResearchTarget; methodVersion:string; modelHash:string; datasetHash:string;
 evidenceHash:string; region:string; rawValue:number; confidence:number|null;
 unit:SkinMeasurement['unit']; gradeMaximum?:number; photoId:string; pose:'FRONT'|'LEFT'|'RIGHT';
 sourceWidth:number; sourceHeight:number; quality:'valid'|'invalid';
 rights:{code:boolean;weights:boolean;data:boolean}; independentCases:number;
 validation:'development-only'|'independently-validated';
};
const specification = {
 'visible-highlight-area':{id:'oil',unit:'visible-highlight-area-percent',maximum:100},
 'acne-presence':{id:'acne',unit:'class-probability',maximum:1},
 'acne-count':{id:'acne',unit:'lesion-count',maximum:Infinity},
 'visible-flaking-grade':{id:'dry',unit:'ordinal-grade',maximum:3},
 'visible-sagging-grade':{id:'sag',unit:'ordinal-grade',maximum:3},
} as const;
// No researched model has passed skin-domain rights + independent acceptance.
// Admission is tied to an immutable model/data/evaluation triple, never a
// caller's "validated" flag. Populate only after review of a completed test.
const admittedEvidence = new Set<string>();
const sha=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
export function isAdmittedResearchMeasurement(m:SkinMeasurement):boolean {
 return sha(m.modelHash)&&sha(m.datasetHash)&&sha(m.evidenceHash)&&m.validation==='independently-validated'&&admittedEvidence.has(`${m.modelHash}:${m.datasetHash}:${m.evidenceHash}`);
}

/** A regional grade/probability/count never becomes a score or a pixel map. */
export function adaptResearchResult(artifact:ResearchArtifact,context:{photoId:string;pose:string;region:string;width:number;height:number},base:SkinIndicator):SkinIndicator {
 const spec=specification[artifact.target];
 let reason:string|null=null;
 if(!spec||base.id!==spec.id||artifact.unit!==spec.unit)reason='target-unit-mismatch';
 else if(!sha(artifact.modelHash)||!sha(artifact.datasetHash)||!sha(artifact.evidenceHash))reason='missing-immutable-provenance';
 else if(artifact.photoId!==context.photoId||artifact.pose!==context.pose||artifact.region!==context.region||artifact.sourceWidth!==context.width||artifact.sourceHeight!==context.height)reason='source-coordinate-mismatch';
 else if(artifact.quality!=='valid')reason='invalid-source-quality';
 else if(!Number.isFinite(artifact.rawValue)||artifact.rawValue<0||artifact.rawValue>spec.maximum||(artifact.unit==='lesion-count'&&!Number.isInteger(artifact.rawValue))||(artifact.unit==='ordinal-grade'&&(!Number.isInteger(artifact.rawValue)||artifact.gradeMaximum!==3)))reason='invalid-target-value';
 else if(artifact.confidence!==null&&(!Number.isFinite(artifact.confidence)||artifact.confidence<0||artifact.confidence>1))reason='invalid-model-confidence';
 else if(!artifact.rights?.code||!artifact.rights.weights||!artifact.rights.data)reason='unresolved-usage-rights';
 else if(artifact.validation!=='independently-validated'||!Number.isInteger(artifact.independentCases)||artifact.independentCases<=0||!admittedEvidence.has(`${artifact.modelHash}:${artifact.datasetHash}:${artifact.evidenceHash}`))reason='no-reviewed-independent-skin-acceptance';
 if(reason)return {...base,score:null,measurement:{scope:'regional',region:context.region,methodVersion:artifact.methodVersion||'unavailable-v1',modelHash:sha(artifact.modelHash)?artifact.modelHash:null,datasetHash:sha(artifact.datasetHash)?artifact.datasetHash:null,evidenceHash:sha(artifact.evidenceHash)?artifact.evidenceHash:null,target:artifact.target,unit:spec?.unit??'ordinal-grade',rawValue:null,confidence:null,quality:artifact.quality==='invalid'?'invalid':'insufficient',validation:'unavailable',unavailableReason:reason}};
 return {...base,score:null,method:artifact.methodVersion,measurement:{scope:'regional',region:context.region,target:artifact.target,methodVersion:artifact.methodVersion,modelHash:artifact.modelHash,datasetHash:artifact.datasetHash,evidenceHash:artifact.evidenceHash,unit:artifact.unit,rawValue:artifact.rawValue,confidence:artifact.confidence,quality:'valid',validation:'independently-validated',unavailableReason:null}};
}

export function researchTarget(id:string):ResearchTarget|undefined {
 return ({oil:'visible-highlight-area',acne:'acne-presence',dry:'visible-flaking-grade',sag:'visible-sagging-grade'} as Record<string,ResearchTarget>)[id];
}
