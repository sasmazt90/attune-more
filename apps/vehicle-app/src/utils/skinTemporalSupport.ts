/** Real source-frame support for lower-lid contour/edge tracking; volatile. */
export function skinTemporalSupport(ctx:CanvasRenderingContext2D,points:{x:number;y:number;z?:number}[]){
 const width=ctx.canvas.width,height=ctx.canvas.height,faceWidth=Math.abs(points[454].x-points[234].x)*width;
 const step=Math.max(1,Math.round(faceWidth/320));let edgeSum=0,contrastSum=0,n=0;
 for(const [outer,inner,lid] of [[33,133,145],[263,362,373]]){
  const x0=Math.max(0,Math.floor(Math.min(points[outer].x,points[inner].x)*width)),x1=Math.min(width,Math.ceil(Math.max(points[outer].x,points[inner].x)*width));
  const y0=Math.max(0,Math.floor(points[lid].y*height+faceWidth*.02)),y1=Math.min(height,Math.ceil(y0+faceWidth*.11));
  if(x1-x0<8||y1-y0<8)continue;
  const data=ctx.getImageData(x0,y0,x1-x0,y1-y0).data,w=x1-x0,h=y1-y0;
  const gray=(x:number,y:number)=>{const i=(y*w+x)*4;return (.299*data[i]+.587*data[i+1]+.114*data[i+2])/255;};
  let edge=0,mean=0,mean2=0,samples=0;
  for(let y=step;y<h-step;y+=step)for(let x=step;x<w-step;x+=step){const v=gray(x,y);if(v<.08||v>.975)continue;edge+=Math.abs(gray(x,y+step)-gray(x,y-step));mean+=v;mean2+=v*v;samples++;}
  if(samples){edgeSum+=edge/samples;contrastSum+=Math.sqrt(Math.max(0,mean2/samples-(mean/samples)**2));n++;}
 }
 return {points,eyelidEdge:n?edgeSum/n:null,underEyeContrast:n?contrastSum/n:null};
}
