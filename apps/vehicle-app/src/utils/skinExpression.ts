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
 return {version:EXPRESSION_VERSION,photoId,scores:{...scores}};
}

/** Same existing backend geometry/blendshape thresholds. Missing support is
 * unknown, never neutral. Only capture eligibility is affected, not quality
 * scores or any unrelated skin criterion. */
export function lowerFaceExpressionReason(a:{landmarks?:{x:number;y:number}[];expressionScores?:Record<string,number>},width:number,height:number):string|undefined {
 const s=a.expressionScores,p=a.landmarks;
 if(!s||!EXPRESSION_FIELDS.every(k=>Number.isFinite(s[k])&&s[k]>=0&&s[k]<=1))return 'EXPRESSION_SUPPORT_UNAVAILABLE';
 if(!p||p.length<468||![width,height].every(v=>Number.isFinite(v)&&v>0))return 'EXPRESSION_SOURCE_UNAVAILABLE';
 if(![13,14,61,291,33,263,234,454].every(i=>Number.isFinite(p[i]?.x)&&Number.isFinite(p[i]?.y)))return 'EXPRESSION_SOURCE_UNAVAILABLE';
 const xy=(i:number)=>[p[i].x*width,p[i].y*height];
 const distance=(a:number[],b:number[])=>Math.hypot(a[0]-b[0],a[1]-b[1]);
 const mouth=Math.max(distance(xy(61),xy(291)),1),opening=distance(xy(13),xy(14))/mouth;
 const eye=[xy(263)[0]-xy(33)[0],xy(263)[1]-xy(33)[1]],length=Math.hypot(...eye);
 if(!Number.isFinite(length)||length<1)return 'EXPRESSION_SOURCE_UNAVAILABLE';
 const face=Math.max(Math.abs((xy(454)[0]-xy(234)[0])*eye[0]/length+(xy(454)[1]-xy(234)[1])*eye[1]/length),1);
 if(opening>.10||s.jawOpen>.15)return 'EXPRESSION_OPEN_MOUTH';
 for(const [keys,label] of [[['mouthSmileLeft','mouthSmileRight'],'SMILE'],[['mouthFrownLeft','mouthFrownRight'],'FROWN'],[['cheekPuff'],'CHEEK_PUFF'],[['mouthPressLeft','mouthPressRight'],'MOUTH_PRESS']] as const)if(Math.max(...keys.map(k=>s[k]))>.5)return 'EXPRESSION_'+label;
 if(s.mouthPucker>.5&&(mouth/face<.35||s.mouthFunnel>.25))return 'EXPRESSION_PUCKER';
 return undefined;
}
