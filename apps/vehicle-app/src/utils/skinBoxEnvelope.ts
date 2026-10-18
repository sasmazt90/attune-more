// Measurement envelope only; the visible anatomical mesh is unchanged.
export function skinBoxEnvelope(points: {x:number;y:number}[]) {
  const sorted=[...points].sort((a,b)=>a.x-b.x||a.y-b.y);
  const cross=(a:typeof sorted[number],b:typeof sorted[number],c:typeof sorted[number])=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
  const half=(items:typeof sorted)=>{const h:typeof sorted=[];for(const p of items){while(h.length>1&&cross(h[h.length-2],h[h.length-1],p)<=0)h.pop();h.push(p);}return h;};
  const lower=half(sorted),upper=half([...sorted].reverse());
  return [...lower.slice(0,-1),...upper.slice(0,-1)].map((p,i)=>`${i?'L':'M'}${p.x} ${p.y}`).join('')+'Z';
}
