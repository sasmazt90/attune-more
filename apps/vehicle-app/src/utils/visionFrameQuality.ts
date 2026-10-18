import { SkinAnalyzer, type FaceAlignment, type ImageQuality } from './skinAnalyzer';
import type { Eye } from './spokenVision';
/** Vision needs usable optotype positioning and visible-eye evidence, not skin
 * texture. Focus uses actual visible eye/eyebrow edges, never room/background or
 * the hand covering the other eye. Existing light/gradient bounds are retained.
 */
export function visionFrameQuality(ctx:CanvasRenderingContext2D,width:number,height:number,a:FaceAlignment,opened:Eye|null):ImageQuality {
 if(!a.box||!a.landmarks||a.faceCount!==1)return SkinAnalyzer.checkQuality(ctx,width,height,false);
 const b=a.box,side=opened==='RIGHT'?{...b,width:b.width*.52}:opened==='LEFT'?{...b,x:b.x+b.width*.48,width:b.width*.52}:b;
 const light=SkinAnalyzer.checkQuality(ctx,width,height,a.faceDetected,side);
 const indices=opened==='RIGHT'?[[33,133,70]]:opened==='LEFT'?[[362,263,300]]:[[33,133,70],[362,263,300]];
 const details=indices.map(ids=>{const p=ids.map(i=>a.landmarks![i]),span=Math.abs(p[0].x-p[1].x)*width,x=Math.min(...p.map(v=>v.x))*width-span*.12,y=Math.min(...p.map(v=>v.y))*height-span*.2;return SkinAnalyzer.checkQuality(ctx,width,height,true,{x,y,width:span*1.24,height:Math.max(...p.map(v=>v.y))*height-y+span*.4});});
 const blurScore=Math.max(...details.map(q=>q.blurScore));
 if(light.status==='TOO_DARK'||light.status==='TOO_BRIGHT'||light.status==='NO_FACE')return {...light,blurScore};
 return {...light,blurScore,isValid:blurScore>=4,status:blurScore>=4?'OPTIMAL':'BLURRY',warningMessageTr:blurScore>=4?undefined:'Açık göz çevresinde yeterli ayrıntı yok. Kamera netliğini ve ışığı kontrol edin.'};
}
