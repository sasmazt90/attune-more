import type { FaceAlignment, ImageQuality } from './skinAnalyzer';
import type { LetterConditions } from './spokenVision';
export type PreparationCode='camera'|'framing'|'light'|'bright'|'blur'|'face'|'approach'|'recede'|'pose'|'preparing'|'ready'|'eye'|'uncertain'|'motion';
export const PREPARATION_TEXT:Record<PreparationCode,string>={camera:'Kamera görüntüsü güncel değil. Kamerayı kontrol edin.',framing:'Alın ve çeneniz kadrajda kalacak şekilde yüzünüzü ortalayın.',light:'Yüzünüzü daha iyi aydınlatın.',bright:'Yüzünüzdeki parlamayı azaltın.',blur:'Kamera netliğini ve yüz aydınlatmasını kontrol edin.',face:'Yüzünüzü kameraya gösterin.',approach:'Biraz yaklaşın.',recede:'Biraz geriye gidin.',pose:'Kameraya doğru bakın.',preparing:'Konumunuz doğrulanıyor. Kısa süre sabit durun.',ready:'Konum hazır',eye:'Yönergede istenen göz açık, diğer göz kapalı kalmalı.',uncertain:'Göz örtülmesi doğrulanamadı; açık göz kameraya görünmeli.',motion:'Kısa süre başınızı sabit tutun.'};
export type PreparationEvidence={alignment:FaceAlignment;quality:ImageQuality;width:number;height:number};
export function visionPreparationCode(c:LetterConditions|null,e:PreparationEvidence|null,now:number):PreparationCode {
 if(!c||now-c.observedAt>750||now<c.observedAt||!c.cameraLive)return 'camera';
 if(!e||!c.modelActive||c.faceCount!==1)return 'face';
 if(c.motionStable===false)return 'motion';
 const {alignment:a,quality:q,width,height}=e,b=a.box;
 if(!b||b.x<0||b.y<0||b.x+b.width>width||b.y+b.height>height)return 'framing';
 if(q.status==='TOO_DARK')return 'light';if(q.status==='TOO_BRIGHT')return 'bright';if(q.status==='BLURRY')return 'blur';if(!q.isValid)return 'camera';
 if(Math.abs(a.yaw)>.20||Math.abs(a.pitch)>.22||Math.abs(a.roll)>.15)return 'pose';
 // Once captured, the initial reference is immutable for this task. +/-8%
 // is the existing scoring guard, not an absolute distance estimate.
 if(c.relativeScaleChange!==null){if(c.relativeScaleChange>.08)return 'recede';if(c.relativeScaleChange<-.08)return 'approach';}
 if(a.scaleRatio<.28)return 'approach';if(a.scaleRatio>.68)return 'recede';
 return c.positionValid&&c.relativeScaleChange!==null?'ready':'preparing';
}
