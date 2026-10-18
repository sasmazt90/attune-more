import type { FaceAlignment } from './skinAnalyzer';
export type DentalPose='FRONT'|'RIGHT'|'LEFT'|'BITE';
export const DENTAL_POSES:DentalPose[]=['FRONT','RIGHT','LEFT','BITE'];
// The legacy nose-offset "yaw" was dimensionless. The rigid transform now
// measures radians: a side view starts at 15 degrees, distinct from the front
// band (0.20 rad), with native tooth visibility still required in every view.
export const DENTAL_SIDE_MIN_RADIANS=Math.PI/12;
export const DENTAL_GUIDANCE:Record<DentalPose,string>={FRONT:'Başınız karşıda. Ağzınızı rahatça açın; ön dişleriniz görünsün.',RIGHT:'Başınızı kendi sağınıza hafifçe çevirin; ağzınızı rahatça açık tutun.',LEFT:'Başınızı kendi solunuza hafifçe çevirin; ağzınızı rahatça açık tutun.',BITE:'Başınız karşıda. Dişlerinizi doğal, rahat kapanışta tutun; ön dişleriniz görünsün. Zorlamayın.'};
export type DentalCapture={sourceType?:'camera'|'upload';photo:string;photoId:string;width:number;height:number;pose:DentalPose;landmarks:{x:number;y:number;z?:number}[];conditions:Record<string,number>};
/** Dental uses measured rigid head rotation, not expression-dependent nose/chin ratios. */
export function dentalPose(a:FaceAlignment){
 const m=a.faceTransform;
 if(!m||m.length!==16||!m.every(Number.isFinite))return null;
 const scale=Math.hypot(m[0],m[1],m[2]);if(scale<=0)return null;
 return {yaw:Math.atan2(m[8],m[10]),pitch:Math.atan2(-m[9],Math.hypot(m[8],m[10])),roll:Math.atan2(m[1],m[5])};
}
export function assessDentalCapture(ctx:CanvasRenderingContext2D,a:FaceAlignment,pose:DentalPose){
 const points=a.landmarks,reasons:string[]=[];if(!points||points.length<468||!a.faceDetected||!a.isMediaPipeActive)return {valid:false,reasons:['Yüz algılanamadı.'],opening:0,visibleFraction:0};
 const width=ctx.canvas.width,height=ctx.canvas.height,p=points.map(v=>({x:v.x*width,y:v.y*height}));
 const mouthWidth=Math.hypot(p[78].x-p[308].x,p[78].y-p[308].y),opening=Math.hypot(p[13].x-p[14].x,p[13].y-p[14].y)/Math.max(mouthWidth,1);
 const indices=[78,81,82,13,312,311,308,402,317,14,87,178];
 const path=new Path2D();indices.forEach((index,i)=>i?path.lineTo(p[index].x,p[index].y):path.moveTo(p[index].x,p[index].y));path.closePath();
 const xs=indices.map(i=>p[i].x),ys=indices.map(i=>p[i].y),x0=Math.max(0,Math.floor(Math.min(...xs))),y0=Math.max(0,Math.floor(Math.min(...ys))),x1=Math.min(width,Math.ceil(Math.max(...xs))),y1=Math.min(height,Math.ceil(Math.max(...ys)));
 if(x1<=x0||y1<=y0)return {valid:false,reasons:['Ağız görünmüyor.'],opening,visibleFraction:0};
 // Pale enamel can carry a pink lighting cast; require the existing tissue
 // saturation floor as well as the red hue before excluding it as tissue.
 const pixels=ctx.getImageData(x0,y0,x1-x0,y1-y0).data;let tooth=0,total=0,light=0,glare=0,gradient=0,comparisons=0;
 const columns=new Uint16Array(x1-x0);
 const gray=new Float32Array((x1-x0)*(y1-y0)),valid=new Uint8Array(gray.length),redInterior=new Uint8Array(gray.length);
 for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++)if(ctx.isPointInPath(path,x+.5,y+.5)){const i=(y-y0)*(x1-x0)+x-x0,k=i*4,r=pixels[k],g=pixels[k+1],b=pixels[k+2],v=Math.max(r,g,b),sat=v?(v-Math.min(r,g,b))/v:0,lum=.299*r+.587*g+.114*b,pink=sat>60/255&&r>g*1.10&&g-b<v*.08;gray[i]=lum;valid[i]=1;redInterior[i]=+(sat>60/255&&pink&&lum>40);light+=lum;total++;if(v>100&&sat<.58&&lum>90&&r<g*1.25&&g>b*.85&&!pink){if(v>=250&&sat<.08)glare++;else{tooth++;columns[x-x0]++;}}}
 const w=x1-x0;for(let i=w+1;i<gray.length-w-1;i++)if(valid[i]&&valid[i-1]&&valid[i+1]&&valid[i-w]&&valid[i+w]){const lap=gray[i-1]+gray[i+1]+gray[i-w]+gray[i+w]-4*gray[i];gradient+=lap*lap;comparisons++;}
 let tongue=0;for(let y=3;y<y1-y0-3;y++)for(let x=3;x<w-3;x++){let interior=true;for(let dy=-3;dy<=3&&interior;dy++)for(let dx=-3;dx<=3;dx++)if(!redInterior[(y+dy)*w+x+dx]){interior=false;break;}if(interior)tongue++;}
 // A normal open mouth adds dark cavity/tongue area without hiding the upper
 // teeth. Coverage therefore measures supported enamel columns across the
 // actual lip aperture, independently of its vertical opening.
 const supportedColumns=Array.from(columns).filter(n=>n>=Math.max(2,mouthWidth*.015)).length;
 const visibleFraction=supportedColumns/Math.max(mouthWidth,1),sharp=gradient/Math.max(comparisons,1),rotation=dentalPose(a);
 if(mouthWidth<65)reasons.push('Ön dişleriniz daha belirgin görünmeli.');
 if(pose!=='BITE'&&opening<.12)reasons.push('Ağzınızı rahatça açın.');
 if(pose==='BITE'&&opening>.32)reasons.push('Doğal kapanışta ön dişlerinizi gösterin.');
 if(tooth<Math.max(150,mouthWidth*mouthWidth*.008)||visibleFraction<.30)reasons.push(light/Math.max(total,1)<90?'Ön dişlerinize ışık gelsin; ağzınızı rahatça açık tutun.':'Ön dişleriniz dudak ve dil tarafından örtülmeden görünsün.');
 if(light/Math.max(total,1)<45||light/Math.max(total,1)>230)reasons.push('Dişlerin ışığını düzenleyin.');
 if(sharp<12)reasons.push('Kamera netliğini kontrol edin.');
 if(glare/Math.max(tooth+glare,1)>.12)reasons.push('Tükürük yansıması veya fazla parlama var.');
 if(tongue/Math.max(total,1)>.7)reasons.push('Dil görünür alanı örtüyor; dişleriniz rahatça görünmeli.');
 const poseValid=rotation&&Math.abs(rotation.pitch)<=.22&&Math.abs(rotation.roll)<=.15&&(pose==='RIGHT'?rotation.yaw>=-.65&&rotation.yaw<=-DENTAL_SIDE_MIN_RADIANS:pose==='LEFT'?rotation.yaw>=DENTAL_SIDE_MIN_RADIANS&&rotation.yaw<=.65:Math.abs(rotation.yaw)<=.20);
 if(!poseValid)reasons.push(DENTAL_GUIDANCE[pose]);
 return {valid:reasons.length===0,reasons,opening,visibleFraction,enamelAreaFraction:tooth/Math.max(total,1),toothPixels:tooth,mouthPixels:total,supportedColumns,mouthWidth,light:light/Math.max(total,1),sharp,glareFraction:glare/Math.max(tooth+glare,1),tongueFraction:tongue/Math.max(total,1),rotation,sourceWidth:width,sourceHeight:height};
}
export async function captureDental(canvas:HTMLCanvasElement,a:FaceAlignment,pose:DentalPose):Promise<DentalCapture>{
 const pixels=canvas.getContext('2d')!.getImageData(0,0,canvas.width,canvas.height).data,digest=await crypto.subtle.digest('SHA-256',pixels);
 const rotation=dentalPose(a);if(!rotation)throw Error('Baş pozu doğrulanamadı.');
 return {photo:canvas.toDataURL('image/png'),photoId:Array.from(new Uint8Array(digest)).map(v=>v.toString(16).padStart(2,'0')).join(''),width:canvas.width,height:canvas.height,pose,landmarks:a.landmarks!,conditions:{...rotation,scaleRatio:a.scaleRatio}};
}
