/** Local, source-guided alpha refinement. No RGB synthesis/decontamination.
 * Fast guided filter coefficients are fitted on a bounded grid, evaluated on
 * ORIGINAL full-resolution RGB. Only the semantic silhouette's unknown band
 * may change; the opaque face interior remains exactly opaque.
 */
function boxMean(src:Float32Array,w:number,h:number,r:number) {
 const tmp=new Float32Array(src.length),out=new Float32Array(src.length);
 for(let y=0;y<h;y++){let sum=0;for(let x=0;x<=Math.min(r,w-1);x++)sum+=src[y*w+x];for(let x=0;x<w;x++){tmp[y*w+x]=sum/(Math.min(w-1,x+r)-Math.max(0,x-r)+1);if(x-r>=0)sum-=src[y*w+x-r];if(x+r+1<w)sum+=src[y*w+x+r+1];}}
 for(let x=0;x<w;x++){let sum=0;for(let y=0;y<=Math.min(r,h-1);y++)sum+=tmp[y*w+x];for(let y=0;y<h;y++){out[y*w+x]=sum/(Math.min(h-1,y+r)-Math.max(0,y-r)+1);if(y-r>=0)sum-=tmp[(y-r)*w+x];if(y+r+1<h)sum+=tmp[(y+r+1)*w+x];}}
 return out;
}
function sample(a:Float32Array,w:number,h:number,x:number,y:number){const x0=Math.max(0,Math.min(w-1,Math.floor(x))),y0=Math.max(0,Math.min(h-1,Math.floor(y))),x1=Math.min(w-1,x0+1),y1=Math.min(h-1,y0+1),fx=Math.max(0,x-x0),fy=Math.max(0,y-y0);return (a[y0*w+x0]*(1-fx)+a[y0*w+x1]*fx)*(1-fy)+(a[y1*w+x0]*(1-fx)+a[y1*w+x1]*fx)*fy;}
export function refineSkinMatte(rgba:Uint8ClampedArray,alpha:Uint8Array,width:number,height:number,maskWidth:number,method:'guided'|'color'='guided') {
 if(rgba.length!==width*height*4||alpha.length!==width*height)throw Error('INVALID_MATTE_INPUT');
 const start=performance.now(),scale=Math.min(1,512/Math.max(width,height)),w=Math.ceil(width*scale),h=Math.ceil(height*scale),n=w*h;
 const guide=Array.from({length:3},()=>new Float32Array(n)),p=new Float32Array(n);
 const corr=Array.from({length:6},()=>new Float32Array(n)),ip=Array.from({length:3},()=>new Float32Array(n));
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){const k=y*w+x,i=Math.min(height-1,Math.floor((y+.5)/scale))*width+Math.min(width-1,Math.floor((x+.5)/scale)),j=i*4;for(let c=0;c<3;c++){guide[c][k]=rgba[j+c]/255;ip[c][k]=guide[c][k]*alpha[i]/255;}p[k]=alpha[i]/255;const [r,g,b]=guide.map(c=>c[k]);[r*r,r*g,r*b,g*g,g*b,b*b].forEach((v,c)=>corr[c][k]=v);}
 const radius=Math.max(2,Math.round(width/maskWidth*scale*2));
 const means=guide.map(c=>boxMean(c,w,h,radius)),meanP=boxMean(p,w,h,radius),cov=corr.map(c=>boxMean(c,w,h,radius)),covP=ip.map(c=>boxMean(c,w,h,radius));
 const aa=Array.from({length:3},()=>new Float32Array(n)),bb=new Float32Array(n);
 for(let i=0;i<n;i++){const [r,g,b]=means.map(c=>c[i]),[rr,rg,rb,gg,gb,bbv]=cov.map(c=>c[i]);const A=rr-r*r+.001,B=rg-r*g,C=rb-r*b,D=gg-g*g+.001,E=gb-g*b,F=bbv-b*b+.001;
 const c00=D*F-E*E,c01=C*E-B*F,c02=B*E-C*D,c11=A*F-C*C,c12=B*C-A*E,c22=A*D-B*B,det=Math.max(1e-12,A*c00+B*c01+C*c02),v=covP.map((c,k)=>c[i]-means[k][i]*meanP[i]);
 aa[0][i]=(c00*v[0]+c01*v[1]+c02*v[2])/det;aa[1][i]=(c01*v[0]+c11*v[1]+c12*v[2])/det;aa[2][i]=(c02*v[0]+c12*v[1]+c22*v[2])/det;bb[i]=meanP[i]-aa[0][i]*r-aa[1][i]*g-aa[2][i]*b;}
 const meanA=aa.map(c=>boxMean(c,w,h,radius)),meanB=boxMean(bb,w,h,radius),out=new Uint8Array(alpha.length);
 const r=Math.max(2,Math.round(width/maskWidth*2));let changed=0,unknown=0;
 for(let y=0;y<height;y++){const row=y*width,above=Math.max(0,y-r)*width,below=Math.min(height-1,y+r)*width;for(let x=0;x<width;x++){
  const i=y*width+x,prior=alpha[i];
  // Bound all changes to two mask cells from actual semantic support.
  const left=alpha[row+Math.max(0,x-r)],right=alpha[row+Math.min(width-1,x+r)],top=alpha[above+x],bottom=alpha[below+x];
  if((prior===255&&left===255&&right===255&&top===255&&bottom===255)||(prior===0&&left===0&&right===0&&top===0&&bottom===0)){out[i]=prior;continue;}
  unknown++;const j=i*4;
  let value=sample(meanB,w,h,(x+.5)*scale-.5,(y+.5)*scale-.5);for(let c=0;c<3;c++)value+=sample(meanA[c],w,h,(x+.5)*scale-.5,(y+.5)*scale-.5)*rgba[j+c]/255;
  if(method==='color'){
   let fg:number[]|undefined,bg:number[]|undefined,fd=Infinity,bd=Infinity;
   for(const d of [1,2,3])for(const [dx,dy] of [[-1,0],[1,0],[0,-1],[0,1],[-1,-1],[1,-1],[-1,1],[1,1]]){const nx=Math.max(0,Math.min(width-1,x+dx*r*d)),ny=Math.max(0,Math.min(height-1,y+dy*r*d)),k=ny*width+nx,t=k*4,c=[rgba[t],rgba[t+1],rgba[t+2]],dist=(nx-x)**2+(ny-y)**2;if(alpha[k]===255&&dist<fd){fg=c;fd=dist;}if(alpha[k]===0&&dist<bd){bg=c;bd=dist;}}
   if(fg&&bg){const diff=fg.map((v,k)=>v-bg![k]),norm=diff.reduce((s,v)=>s+v*v,0);if(norm>900)value=diff.reduce((s,v,k)=>s+(rgba[j+k]-bg![k])*v,0)/norm;}
  }
  out[i]=Math.round(Math.max(0,Math.min(1,(value-.08)/.84))*255);if(out[i]!==prior)changed++;
 }}
 return {alpha:out,method,elapsedMs:performance.now()-start,changedPixels:changed,unknownPixels:unknown,workingBytes:n*4*40+out.byteLength};
}
