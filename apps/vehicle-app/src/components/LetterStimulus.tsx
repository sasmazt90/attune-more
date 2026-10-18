import type { RefObject } from 'react';
import { legacyTransform, type Orientation, type LetterTransform } from '../utils/spokenVision';
/** Vector stimulus has no font dependency. Padding retains acute miter tips
 * after every rotation; size/geometry still comes from the painted DOM. */
export function LetterStimulus({path,orientation='upright',transform,sizePx,svgRef}:{path:string;orientation?:Orientation;transform?:LetterTransform;sizePx:number;svgRef?:RefObject<SVGSVGElement|null>}){
 const t=transform||legacyTransform(orientation);
 return <svg ref={svgRef} data-letter-optotype role="img" aria-label="Yanıtlanacak harf" viewBox="-8 -8 116 116" style={{width:sizePx,height:sizePx,maxWidth:'100%',flexShrink:0,opacity:1,visibility:'visible'}}><g transform={`translate(50 50) rotate(${t.rotation}) scale(${t.mirrored?-1:1} 1) translate(-50 -50)`}><path d={path} stroke="#ffffff" strokeWidth="10" strokeLinecap="square" strokeLinejoin="miter" fill="none"/></g></svg>;
}
