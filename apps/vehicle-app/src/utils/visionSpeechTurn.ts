import {parseLetterAnswer,type Letter,type ParsedAnswer} from './spokenVision';
export const VISION_ANSWER_SETTLE_MS=750;
/** Alternatives constrain confidence; they never vote for the expected answer. */
export function visionRecognitionChoice(alternatives:{transcript:string;confidence:number}[],language:'tr'|'en'|'de',context:{letter:Letter}){
 const top=alternatives[0];if(!top)return null;
 const signature=(p:ParsedAnswer)=>JSON.stringify([p.command,p.letter,p.rotation,p.mirrored===true,p.clarify,p.ambiguous]);
 const parsed=parseLetterAnswer(top.transcript,language,context),key=signature(parsed);
 const conflict=alternatives.slice(1).some(a=>Number.isFinite(a.confidence)&&a.confidence>0&&a.confidence>=Math.max(.5,top.confidence-.15)&&signature(parseLetterAnswer(a.transcript,language,context))!==key);
 return {...top,confidence:conflict?.3:Number.isFinite(top.confidence)?top.confidence:0,parsed};
}

export type VisionComponentConfidence=Partial<Record<'letter'|'rotation'|'mirror',number>>;
/** Native confidence is per result, not per word. Preserve distinct result
 * confidence when a final event contains separate letter/orientation segments. */
export function visionRecognitionConfidence(finals:{parsed:ParsedAnswer;confidence:number}[]):VisionComponentConfidence{
 const fields:VisionComponentConfidence={};
 for(const {parsed,confidence}of finals){
  if(parsed.letter||parsed.ambiguous==='letter')fields.letter=confidence;
  if(parsed.rotation!==undefined||parsed.orientation||parsed.ambiguous==='rotation')fields.rotation=confidence;
  if(parsed.mirrored!==undefined||parsed.clarify==='reverse')fields.mirror=confidence;
 }
 return fields;
}
