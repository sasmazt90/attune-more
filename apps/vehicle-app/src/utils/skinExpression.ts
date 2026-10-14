/** Local scores from the same MediaPipe call as the accepted landmarks. */
export const EXPRESSION_VERSION='local-mediapipe-expression-support-v1';
export const EXPRESSION_FIELDS=['jawOpen','mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','cheekPuff','mouthPressLeft','mouthPressRight','mouthPucker','mouthFunnel'] as const;
export function expressionScores(categories:{categoryName:string;score:number}[]|undefined):Record<string,number>|undefined {
 if(!categories)return undefined;
 const scores=Object.fromEntries(categories.map(c=>[c.categoryName,c.score]));
 return EXPRESSION_FIELDS.every(k=>Number.isFinite(scores[k])&&scores[k]>=0&&scores[k]<=1)?scores:undefined;
}
export function expressionObservation(scores:Record<string,number>|undefined,photoId:string|undefined){
 if(!scores||!photoId||!EXPRESSION_FIELDS.every(k=>Number.isFinite(scores[k])&&scores[k]>=0&&scores[k]<=1))return undefined;
 return {version:EXPRESSION_VERSION,photoId,scores};
}
